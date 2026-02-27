# edge/app.py
import os
import time
import sqlite3
import requests
import redis
from flask import Flask, send_file, jsonify, request, g

app = Flask(__name__)

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
CORE_URL = os.environ.get('CORE_URL', 'http://localhost:5000')
EDGE_ID = os.environ.get('EDGE_ID', 'edge1')
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
MAX_CACHE_SIZE = int(os.environ.get('MAX_CACHE_SIZE', 3))  # max videos per edge
LOG_DB = os.environ.get('LOG_DB', '/logs/requests.db')

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOG_DB), exist_ok=True)

# Redis connection
r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)

# ─────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────

def init_db():
    """Create the requests table if it doesn't exist."""
    conn = sqlite3.connect(LOG_DB)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            edge_id   TEXT,
            video_id  TEXT,
            cache_hit INTEGER,
            latency_ms REAL,
            user_ip   TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print(f"[{EDGE_ID}] Database initialized at {LOG_DB}")

init_db()

# ─────────────────────────────────────────
# LOGGING MIDDLEWARE
# ─────────────────────────────────────────

@app.before_request
def start_timer():
    """Record request start time before every request."""
    g.start_time = time.time()

@app.after_request
def log_request(response):
    """After every request, log it to SQLite."""
    # Only log video requests, not health checks or cache-status
    if '/video/' not in request.path:
        return response

    latency = round((time.time() - g.start_time) * 1000, 2)
    video_id = request.path.split('/video/')[-1]
    cache_hit = 1 if response.headers.get('X-Cache') == 'HIT' else 0
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

    try:
        conn = sqlite3.connect(LOG_DB)
        conn.execute('''
            INSERT INTO requests (timestamp, edge_id, video_id, cache_hit, latency_ms, user_ip)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (timestamp, EDGE_ID, video_id, cache_hit, latency, request.remote_addr))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[{EDGE_ID}] Logging error: {e}")

    return response

# ─────────────────────────────────────────
# LRU EVICTION
# ─────────────────────────────────────────

def evict_if_needed():
    """
    If cache is full, evict the least popular video.
    Uses Redis popularity scores to decide what to remove.
    """
    cached_videos = os.listdir(CACHE_DIR)

    if len(cached_videos) < MAX_CACHE_SIZE:
        return  # Cache not full, nothing to do

    print(f"[{EDGE_ID}] Cache full ({len(cached_videos)}/{MAX_CACHE_SIZE}) — running eviction...", flush=True)

    # Find the cached video with the lowest popularity score
    least_popular = None
    lowest_score = float('inf')

    for video in cached_videos:
        # Get popularity score from Redis sorted set
        score = r.zscore('popular_videos', video)
        score = float(score) if score is not None else 0.0

        if score < lowest_score:
            lowest_score = score
            least_popular = video

    if least_popular:
        # Remove from local cache
        os.remove(os.path.join(CACHE_DIR, least_popular))
        # Remove from Redis cache index
        r.delete(f"cache:{EDGE_ID}:{least_popular}")
        print(f"[{EDGE_ID}] EVICTED {least_popular} (score: {lowest_score})", flush=True)

# ─────────────────────────────────────────
# MAIN VIDEO ENDPOINT
# ─────────────────────────────────────────

@app.route('/video/<video_id>', methods=['GET'])
def serve_video(video_id):
    cache_path = os.path.join(CACHE_DIR, video_id)

    # Increment popularity score in Redis every request
    r.zincrby('popular_videos', 1, video_id)

    if os.path.exists(cache_path):
        # CACHE HIT
        r.set(f"cache:{EDGE_ID}:{video_id}", 1)
        print(f"[{EDGE_ID}] CACHE HIT  | {video_id}")
        response = send_file(cache_path, mimetype='video/mp4')
        response.headers['X-Cache'] = 'HIT'
        return response

    else:
        # CACHE MISS — evict if needed, then fetch from core
        print(f"[{EDGE_ID}] CACHE MISS | {video_id} | fetching from core...")
        evict_if_needed()

        core_response = requests.get(f"{CORE_URL}/video/{video_id}", stream=True)

        if core_response.status_code != 200:
            return jsonify({"error": "Video not found on core"}), 404

        with open(cache_path, 'wb') as f:
            for chunk in core_response.iter_content(chunk_size=8192):
                f.write(chunk)

        r.set(f"cache:{EDGE_ID}:{video_id}", 1)
        print(f"[{EDGE_ID}] CACHED     | {video_id}")
        response = send_file(cache_path, mimetype='video/mp4')
        response.headers['X-Cache'] = 'MISS'
        return response

# ─────────────────────────────────────────
# STATUS ENDPOINTS
# ─────────────────────────────────────────

@app.route('/cache-status', methods=['GET'])
def cache_status():
    """Show cached videos with their popularity scores."""
    cached = os.listdir(CACHE_DIR)
    scores = {}
    for video in cached:
        score = r.zscore('popular_videos', video)
        scores[video] = float(score) if score else 0.0

    return jsonify({
        "edge_id": EDGE_ID,
        "cached_videos": scores,
        "count": len(cached),
        "max_cache_size": MAX_CACHE_SIZE
    })

@app.route('/cache-index', methods=['GET'])
def cache_index():
    """Show what all edges have cached via Redis."""
    keys = r.keys("cache:*")
    index = {}
    for key in keys:
        parts = key.split(":")
        if len(parts) == 3:
            _, edge, video = parts
            if edge not in index:
                index[edge] = []
            index[edge].append(video)
    return jsonify({"cache_index": index, "total_keys": len(keys)})

@app.route('/popularity', methods=['GET'])
def popularity():
    """Show top 10 most popular videos across the whole system."""
    top_videos = r.zrevrange('popular_videos', 0, 9, withscores=True)
    return jsonify({
        "top_videos": [{"video": v, "requests": int(s)} for v, s in top_videos]
    })

@app.route('/logs', methods=['GET'])
def get_logs():
    """Show last 20 request logs from SQLite."""
    try:
        conn = sqlite3.connect(LOG_DB)
        cursor = conn.execute('''
            SELECT timestamp, edge_id, video_id, cache_hit, latency_ms, user_ip
            FROM requests
            ORDER BY id DESC
            LIMIT 20
        ''')
        rows = cursor.fetchall()
        conn.close()
        logs = [
            {
                "timestamp": r[0],
                "edge_id": r[1],
                "video_id": r[2],
                "cache_hit": bool(r[3]),
                "latency_ms": r[4],
                "user_ip": r[5]
            }
            for r in rows
        ]
        return jsonify({"logs": logs, "count": len(logs)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "edge_id": EDGE_ID})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)