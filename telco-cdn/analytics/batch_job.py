# analytics/batch_job.py
import sqlite3
import json
import os
from datetime import datetime, timedelta
import pandas as pd

LOG_DB = os.environ.get('LOG_DB', '/logs/requests.db')
REPORT_PATH = os.environ.get('REPORT_PATH', '/logs/analytics_report.json')

def run_batch_job():
    print("[ANALYTICS] Starting batch job...")

    try:
        conn = sqlite3.connect(LOG_DB)

        # Load all logs into a DataFrame
        df = pd.read_sql_query("SELECT * FROM requests", conn)
        conn.close()

        if df.empty:
            print("[ANALYTICS] No data found in logs.")
            return {"error": "No data available"}

        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # ── 1. Top 10 most requested videos (last hour) ──
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent = df[df['timestamp'] >= one_hour_ago]
        top_videos = (
            recent.groupby('video_id')
            .size()
            .sort_values(ascending=False)
            .head(10)
            .to_dict()
        )

        # ── 2. Cache hit rate per edge ──
        hit_rate = (
            df.groupby('edge_id')['cache_hit']
            .mean()
            .mul(100)
            .round(2)
            .to_dict()
        )

        # ── 3. Average latency per edge ──
        avg_latency = (
            df.groupby('edge_id')['latency_ms']
            .mean()
            .round(2)
            .to_dict()
        )

        # ── 4. Busiest time windows (requests per 5-minute bucket) ──
        df['time_bucket'] = df['timestamp'].dt.floor('5min').astype(str)
        busiest_windows = (
            df.groupby('time_bucket')
            .size()
            .sort_values(ascending=False)
            .head(5)
            .to_dict()
        )

        # ── 5. Overall stats ──
        overall = {
            "total_requests": len(df),
            "overall_hit_rate_pct": round(df['cache_hit'].mean() * 100, 2),
            "avg_latency_ms": round(df['latency_ms'].mean(), 2),
            "unique_videos": df['video_id'].nunique(),
            "edges_active": df['edge_id'].nunique()
        }

        report = {
            "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "overall": overall,
            "top_videos_last_hour": top_videos,
            "cache_hit_rate_per_edge": hit_rate,
            "avg_latency_per_edge_ms": avg_latency,
            "busiest_time_windows": busiest_windows
        }

        # Save report to file
        with open(REPORT_PATH, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"[ANALYTICS] Report saved to {REPORT_PATH}")
        return report

    except Exception as e:
        print(f"[ANALYTICS] Error: {e}")
        return {"error": str(e)}


if __name__ == '__main__':
    report = run_batch_job()
    print(json.dumps(report, indent=2))