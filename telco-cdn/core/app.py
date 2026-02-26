# core/app.py
import os
from flask import Flask, send_file, jsonify

app = Flask(__name__)

VIDEO_DIR = os.environ.get('VIDEO_DIR', r'C:\telco-edge-cdn\telco-cdn\videos')
VIDEO_DIR = os.path.abspath(VIDEO_DIR)
print(f"[CORE] Video directory: {VIDEO_DIR}")

@app.route('/videos', methods=['GET'])
def list_videos():
    """List all available videos."""
    try:
        videos = [f for f in os.listdir(VIDEO_DIR) if f.endswith('.mp4')]
        return jsonify({"videos": videos})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/video/<video_id>', methods=['GET'])
def stream_video(video_id):
    """Stream a video file to whoever requests it (edge nodes or direct clients)."""
    video_path = os.path.join(VIDEO_DIR, video_id)
    
    if not os.path.exists(video_path):
        return jsonify({"error": "Video not found"}), 404
    
    print(f"[CORE] Serving {video_id} to edge node")
    return send_file(video_path, mimetype='video/mp4')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)