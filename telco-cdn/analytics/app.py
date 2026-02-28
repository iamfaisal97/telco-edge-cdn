# analytics/app.py
import os
from flask import Flask, jsonify
from batch_job import run_batch_job
from predictor import predict_spikes

app = Flask(__name__)

@app.route('/analytics/report', methods=['GET'])
def analytics_report():
    """Run batch job and return report."""
    report = run_batch_job()
    return jsonify(report)

@app.route('/predict/spikes', methods=['GET'])
def spike_predictions():
    """Run ML predictor and return spike predictions."""
    result = predict_spikes()
    return jsonify(result)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "analytics"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5010, debug=True)