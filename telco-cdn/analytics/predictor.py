# analytics/predictor.py
import sqlite3
import json
import os
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.linear_model import LinearRegression

LOG_DB = os.environ.get('LOG_DB', '/logs/requests.db')

def predict_spikes():
    """
    Reads request counts per video per 5-minute window.
    Uses linear regression to predict the next window's request count.
    Flags videos where predicted count > 2x current average (spike incoming).
    """
    print("[PREDICTOR] Running demand prediction...")

    try:
        conn = sqlite3.connect(LOG_DB)
        df = pd.read_sql_query("SELECT * FROM requests", conn)
        conn.close()

        if df.empty or len(df) < 5:
            return {"error": "Not enough data to predict", "spikes": []}

        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['time_bucket'] = df['timestamp'].dt.floor('5min')

        predictions = []

        for video_id in df['video_id'].unique():
            video_df = df[df['video_id'] == video_id]

            # Count requests per 5-minute window
            counts = (
                video_df.groupby('time_bucket')
                .size()
                .reset_index(name='count')
                .sort_values('time_bucket')
            )

            if len(counts) < 2:
                continue  # Need at least 2 windows to predict

            # X = window index (0, 1, 2, ...), Y = request count
            X = np.arange(len(counts)).reshape(-1, 1)
            y = counts['count'].values

            # Fit linear regression
            model = LinearRegression()
            model.fit(X, y)

            # Predict next window
            next_window = np.array([[len(counts)]])
            predicted_count = float(model.predict(next_window)[0])
            current_avg = float(y.mean())

            # Flag as spike if predicted > 2x current average
            is_spike = predicted_count > (2 * current_avg) and predicted_count > 2

            predictions.append({
                "video_id": video_id,
                "current_avg_requests": round(current_avg, 2),
                "predicted_next_window": round(predicted_count, 2),
                "spike_incoming": is_spike,
                "windows_analyzed": len(counts)
            })

        # Sort — spikes first, then by predicted count
        predictions.sort(key=lambda x: (-x['spike_incoming'], -x['predicted_next_window']))

        spikes = [p for p in predictions if p['spike_incoming']]
        print(f"[PREDICTOR] Found {len(spikes)} spike(s): {[s['video_id'] for s in spikes]}")

        return {
            "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "spikes": spikes,
            "all_predictions": predictions
        }

    except Exception as e:
        print(f"[PREDICTOR] Error: {e}")
        return {"error": str(e), "spikes": []}


if __name__ == '__main__':
    result = predict_spikes()
    print(json.dumps(result, indent=2))