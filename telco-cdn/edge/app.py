# edge/app.py
import os
import time
import requests
from flask import Flask, send_file, jsonify

app = Flask(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', 'cache')
CORE_URL = os.environ.get('CORE_URL', 'http://localhost:5000')
EDGE_ID = os.environ.get('EDGE_ID', 'edge1')

# Make sure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)

@app.route('/video/<video_id>', methods=['GET'])
def serve_video(video_id):
    """
    Main endpoint. Check cache first.
    Hit  → serve from local cache (fast)
    Miss → fetch from core, save to cache, then serve (slow first time only)
    """
    cache_path = os.path.join(CACHE_DIR, video_id)
    start_time = time.time()

    if os.path.exists(cache_path):
        # ✅ CACHE HIT
        latency = round((time.time() - start_time) * 1000, 2)
        print(f"[{EDGE_ID}] CACHE HIT  | {video_id} | {latency}ms")
        return send_file(cache_path, mimetype='video/mp4')
    
    else:
        # ❌ CACHE MISS — fetch from core
        print(f"[{EDGE_ID}] CACHE MISS | {video_id} | fetching from core...")
        
        core_response = requests.get(f"{CORE_URL}/video/{video_id}", stream=True)
        
        if core_response.status_code != 200:
            return jsonify({"error": "Video not found on core"}), 404
        
        # Save to local cache
        with open(cache_path, 'wb') as f:
            for chunk in core_response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        latency = round((time.time() - start_time) * 1000, 2)
        print(f"[{EDGE_ID}] CACHED     | {video_id} | {latency}ms")
        
        return send_file(cache_path, mimetype='video/mp4')

@app.route('/cache-status', methods=['GET'])
def cache_status():
    """Show what's currently cached on this edge node."""
    cached = os.listdir(CACHE_DIR)
    return jsonify({
        "edge_id": EDGE_ID,
        "cached_videos": cached,
        "count": len(cached)
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)