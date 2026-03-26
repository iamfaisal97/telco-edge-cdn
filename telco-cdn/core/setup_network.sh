#!/bin/sh
# Simulate core datacenter latency (50ms — farther from users)
tc qdisc add dev eth0 root netem delay 50ms 2>/dev/null || true
exec python app.py