#!/bin/sh
# Read latency from environment variable, default to 10ms
LATENCY=${SIMULATED_LATENCY:-10ms}
echo "Setting up network latency: ${LATENCY}"
tc qdisc add dev eth0 root netem delay ${LATENCY} 2>/dev/null || true
exec python app.py