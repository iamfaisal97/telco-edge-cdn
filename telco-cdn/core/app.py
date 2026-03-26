# core/app.py
import os
import time
import threading
import requests
from flask_cors import CORS
from flask import Flask, send_file, jsonify, request

app = Flask(__name__)

CORS(app)

VIDEO_DIR = os.environ.get('VIDEO_DIR', r'C:\telco-edge-cdn\telco-cdn\videos')
VIDEO_DIR = os.path.abspath(VIDEO_DIR)
ANALYTICS_URL = os.environ.get('ANALYTICS_URL', 'http://analytics:5010')

EDGE_URLS = {
    'edge1': 'http://edge1:5001',
    'edge2': 'http://edge2:5002',
    'edge3': 'http://edge3:5003',
}

print(f"[CORE] Video directory: {VIDEO_DIR}")

# ─────────────────────────────────────────
# VIDEO ENDPOINTS
# ─────────────────────────────────────────

@app.route('/videos', methods=['GET'])
def list_videos():
    try:
        videos = [f for f in os.listdir(VIDEO_DIR) if f.endswith('.mp4')]
        return jsonify({"videos": videos})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/video/<video_id>', methods=['GET'])
def stream_video(video_id):
    video_path = os.path.join(VIDEO_DIR, video_id)
    if not os.path.exists(video_path):
        return jsonify({"error": "Video not found"}), 404
    print(f"[CORE] Serving {video_id} to edge node")
    return send_file(video_path, mimetype='video/mp4')

# ─────────────────────────────────────────
# PRE-CACHE ORCHESTRATION
# ─────────────────────────────────────────

precache_log = []

def precache_orchestrator():
    """
    Background job — runs every 2 minutes.
    1. Calls analytics service for spike predictions
    2. For each predicted spike video → POST /precache to ALL edges
    This is the Edge-Cloud Continuum in action.
    """
    global precache_log
    time.sleep(30)  # wait for everything to start up first

    while True:
        try:
            print("[CORE] Running pre-cache orchestration...", flush=True)

            resp = requests.get(f"{ANALYTICS_URL}/predict/spikes", timeout=10)
            if resp.status_code != 200:
                print("[CORE] Could not get predictions", flush=True)
                time.sleep(120)
                continue

            predictions = resp.json()
            spikes = predictions.get('spikes', [])

            if not spikes:
                print("[CORE] No spikes predicted — nothing to pre-cache", flush=True)
                time.sleep(120)
                continue

            print(f"[CORE] Spikes detected: {[s['video_id'] for s in spikes]}", flush=True)

            for spike in spikes:
                video_id = spike['video_id']

                for edge_id, edge_url in EDGE_URLS.items():
                    try:
                        r = requests.post(
                            f"{edge_url}/precache",
                            json={"video_id": video_id},
                            timeout=60
                        )
                        result = r.json()
                        status = result.get('status', 'unknown')
                        print(f"[CORE] Pre-cache {video_id} → {edge_id}: {status}", flush=True)

                        precache_log.append({
                            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
                            "video_id": video_id,
                            "edge_id": edge_id,
                            "status": status
                        })
                        precache_log = precache_log[-50:]

                    except Exception as e:
                        print(f"[CORE] Pre-cache error {edge_id}: {e}", flush=True)

        except Exception as e:
            print(f"[CORE] Orchestration error: {e}", flush=True)

        time.sleep(120)


@app.route('/precache-log', methods=['GET'])
def get_precache_log():
    return jsonify({
        "precache_events": precache_log,
        "count": len(precache_log)
    })

@app.route('/precache/trigger', methods=['POST'])
def manual_precache_trigger():
    """Manually trigger pre-cache for a specific video — useful for demo."""
    data = request.get_json()
    if not data or 'video_id' not in data:
        return jsonify({"error": "video_id required"}), 400

    video_id = data['video_id']
    results = {}

    for edge_id, edge_url in EDGE_URLS.items():
        try:
            r = requests.post(
                f"{edge_url}/precache",
                json={"video_id": video_id},
                timeout=60
            )
            results[edge_id] = r.json()
        except Exception as e:
            results[edge_id] = {"error": str(e)}

    return jsonify({"video_id": video_id, "results": results})


# Start pre-cache orchestrator background thread
orchestrator_thread = threading.Thread(target=precache_orchestrator, daemon=True)
orchestrator_thread.start()
print("[CORE] Pre-cache orchestrator started", flush=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)