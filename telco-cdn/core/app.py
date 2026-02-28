# core/app.py

# Import Flask framework and utilities for web serving
import os
from flask import Flask, send_file, jsonify

# Initialize Flask application instance
app = Flask(__name__)

# Get video directory from environment variable or use default path, then resolve to absolute path
VIDEO_DIR = os.environ.get('VIDEO_DIR', r'C:\telco-edge-cdn\telco-cdn\videos')
VIDEO_DIR = os.path.abspath(VIDEO_DIR)
print(f"[CORE] Video directory: {VIDEO_DIR}")

# API endpoint to list all available videos in the video directory
@app.route('/videos', methods=['GET'])
def list_videos():
    """List all available videos."""
    try:
        # Scan video directory for .mp4 files and return as JSON list
        videos = [f for f in os.listdir(VIDEO_DIR) if f.endswith('.mp4')]
        return jsonify({"videos": videos})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API endpoint to stream a specific video by filename/video_id
@app.route('/video/<video_id>', methods=['GET'])
def stream_video(video_id):
    """Stream a video file to whoever requests it (edge nodes or direct clients)."""
    # Construct full path to the requested video file
    video_path = os.path.join(VIDEO_DIR, video_id)
    
    # Return 404 if video file doesn't exist on disk
    if not os.path.exists(video_path):
        return jsonify({"error": "Video not found"}), 404
    
    # Log the request and serve the video file with correct MIME type
    print(f"[CORE] Serving {video_id} to edge node")
    return send_file(video_path, mimetype='video/mp4')

# Run Flask development server on all network interfaces when script is executed directly
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)