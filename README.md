# Telco-Edge CDN for Latency-Sensitive Video Streaming

> A complete Multi-access Edge Computing (MEC) CDN built with Docker, Flask, Redis, and scikit-learn — achieving **92% cache hit rate** and **500× latency reduction** for cached video content.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Requirements](#requirements)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [How It Works](#how-it-works)
- [Results](#results)
- [Troubleshooting](#troubleshooting)

---

## Overview

This project implements a full telco-edge Content Delivery Network simulating a real MEC deployment with three geographically distributed edge nodes (Helsinki, Stockholm, Oslo) connected to a core datacenter (Frankfurt). The system meets all 12 project requirements including distributed ML-driven demand prediction and an Edge-Cloud Continuum pre-caching pipeline.

### Key Metrics

| Metric                 | Value                       |
| ---------------------- | --------------------------- |
| Cache Hit Rate         | **92.1%**                   |
| Cache HIT Latency      | **~5ms**                    |
| Cache MISS Latency     | **~2,500ms** (origin fetch) |
| Latency Reduction      | **~500×**                   |
| Total Requests Logged  | **343**                     |
| Requirements Completed | **12 / 12**                 |

---

## Architecture

The system runs **8 Docker containers** across **3 isolated network zones**:

```
┌─────────────────────────────────────────────────────────────┐
│  ① CLIENT NETWORK                                           │
│   [User Browser] ──► [Dashboard :8080] ──► [NGINX :80]     │
└───────────────────────────┬─────────────────────────────────┘
                            │ Round-Robin Load Balancing
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
┌────────────────────────────────────────────────────────────┐
│  ② EDGE NETWORK — MEC Layer                                │
│  [edge1:5001]        [edge2:5002]        [edge3:5003]      │
│  Helsinki · 10ms     Stockholm · 15ms    Oslo · 12ms       │
│  Local Cache         Local Cache         Local Cache        │
│  LRU Eviction        LRU Eviction        LRU Eviction      │
│  Replication ◄──────────────────────────► Replication      │
└──────────┬────────────────┬──────────────────┬─────────────┘
           │ Cache Miss     │                  │
           ▼                ▼                  ▼
┌────────────────────────────────────────────────────────────┐
│  ③ CORE NETWORK — Frankfurt DC · 50ms backhaul             │
│  [Core :5000]     [Redis :6379]     [Analytics :5010]      │
│  Origin Server    Shared Metadata   Batch + ML Pipeline    │
│  Pre-cache Orch.  Cache Index       Pandas + scikit-learn  │
└────────────────────────────────────────────────────────────┘
```

### Network Isolation

| Network          | Members                           | Purpose                    |
| ---------------- | --------------------------------- | -------------------------- |
| `client_network` | nginx, client                     | Public-facing user traffic |
| `edge_network`   | edge1, edge2, edge3, nginx        | MEC layer — cache serving  |
| `core_network`   | core, redis, analytics, edge1/2/3 | Datacenter backbone        |

> Clients **cannot** reach the core origin server directly — all traffic must pass through NGINX and the edge layer.

---

## Features

### Requirements 1–6: Foundation Layer

| #   | Feature                                | Implementation                                                                                              |
| --- | -------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| 1   | **Video Streaming**                    | Flask serves MP4 via HTTP. Edge nodes intercept, cache, and serve with `X-Cache: HIT/MISS` headers          |
| 2   | **Edge-Core Communication**            | Cache MISS → edge fetches from core (~2,500ms). Cache HIT → served from `/app/cache` in ~5ms                |
| 3   | **Consistent Cache Index**             | Redis key `cache:edgeN:videoX = 1` shared across all edges — any node sees every other node's state in O(1) |
| 4   | **Load Balancing**                     | NGINX round-robin across edge1/2/3 with health probes every 10s                                             |
| 5   | **Replication & Eventual Consistency** | Background thread every 30s: edges pull top-5 popular videos from peers via Redis `ZREVRANGE`               |
| 6   | **LRU Cache Eviction**                 | `MAX_CACHE_SIZE=3` per edge. On full: `ZSCORE` each cached video, evict lowest popularity score             |

### Requirements 7–12: Advanced Layer

| #   | Feature                            | Implementation                                                                                             |
| --- | ---------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| 7   | **Microservice Architecture**      | 8 separate Docker containers, each with its own Dockerfile, port, and network membership                   |
| 8   | **Logging & Analytics Middleware** | Flask `before_request`/`after_request` hooks log every request to shared SQLite. Pandas aggregates reports |
| 9   | **Network Topology Simulation**    | 3 Docker bridge networks + Linux `tc-netem` for geographic latency injection per node                      |
| 10  | **Big Data Batch Processing**      | `batch_job.py` reads entire SQLite log via shared Docker volume and runs `groupby` aggregations            |
| 11  | **Distributed ML Prediction**      | `predictor.py` fits `LinearRegression` on 5-min windows aggregated from all 3 edges                        |
| 12  | **Edge-Cloud Continuum**           | Core polls `/predict/spikes` every 2 min. On spike → POSTs `/precache` to all edges automatically          |

---

## Requirements

- **Docker Desktop** (Windows) or **Docker Engine** (Linux/macOS)
- **Docker Compose** v2+
- **PowerShell** (Windows) or Bash (Linux/macOS) for running demo commands
- Ports available: `80`, `5000`, `5001`, `5002`, `5003`, `5010`, `6379`, `8080`

---

## Project Structure

```
telco-cdn/
├── docker-compose.yml          # Orchestrates all 8 services
│
├── core/                       # Origin server + pre-cache orchestrator
│   ├── app.py                  # Flask app — video library, pre-cache trigger, background thread
│   ├── Dockerfile
│   └── setup_network.sh        # tc-netem latency injection (50ms)
│
├── edge/                       # Edge node (shared by edge1, edge2, edge3)
│   ├── app.py                  # Flask app — cache, LRU, replication, pre-cache receiver
│   ├── Dockerfile
│   └── setup_network.sh        # tc-netem latency injection (10/12/15ms)
│
├── analytics/                  # Batch + ML service
│   ├── app.py                  # Flask app — exposes /analytics/report and /predict/spikes
│   ├── batch_job.py            # Pandas groupby on SQLite logs
│   ├── predictor.py            # scikit-learn LinearRegression spike detector
│   └── Dockerfile
│
├── client/                     # Live dashboard
│   ├── index.html              # Single-page dashboard — 6 panels, auto-refresh 15s
│   └── Dockerfile              # nginx:alpine static file server
│
└── videos/                     # Shared video library (mounted into core)
    ├── videoA.mp4
    ├── videoB.mp4
    ├── videoC.mp4
    └── videoD.mp4
```

---

## Quick Start

### 1. Clone and navigate

```powershell
git clone <your-repo-url>
cd telco-edge-cdn\telco-cdn
```

### 2. Start all 8 containers

```powershell
docker compose up
```

Wait 20–30 seconds for all services to initialize.

### 3. Verify everything is running

```powershell
docker ps
```

You should see all 8 containers with `Status: Up`:

```
telco-cdn-core-1
telco-cdn-edge1-1
telco-cdn-edge2-1
telco-cdn-edge3-1
telco-cdn-redis-1
telco-cdn-analytics-1
telco-cdn-nginx-1
telco-cdn-client-1
```

### 4. Open the live dashboard

Go to **[http://localhost:8080](http://localhost:8080)**

All 6 panels auto-refresh every 15 seconds:

- **Edge Cache Status** — live slot utilisation per node
- **Video Popularity** — Redis sorted set scores
- **ML Spike Predictions** — scikit-learn predictions per video
- **System Analytics** — hit rate, latency, request count
- **Pre-cache Events** — Edge-Cloud Continuum activity log
- **Video Player** — streams through the full CDN stack

### 5. Showcase all 12 features in 3 commands

```powershell
# 1. Generate traffic (populates cache, logs, popularity scores)
for ($i=1; $i -le 50; $i++) { Invoke-WebRequest http://localhost:80/video/videoD.mp4 -OutFile NUL }

# 2. Trigger the Edge-Cloud Continuum pre-cache pipeline
curl.exe -X POST http://localhost:5000/precache/trigger -H "Content-Type: application/json" --data "{`"video_id`": `"videoD.mp4`"}"

# 3. Show live proof of all features
curl http://localhost:5001/health; curl http://localhost:5002/health; curl http://localhost:5003/health; curl http://localhost:5000/precache-log; curl http://localhost:5010/predict/spikes; curl http://localhost:5010/analytics/report
```

---

## Configuration

All configuration is done via environment variables in `docker-compose.yml`:

| Variable            | Service   | Default            | Description                                 |
| ------------------- | --------- | ------------------ | ------------------------------------------- |
| `SIMULATED_LATENCY` | edge1     | `10ms`             | Helsinki last-mile latency                  |
| `SIMULATED_LATENCY` | edge2     | `15ms`             | Stockholm last-mile latency                 |
| `SIMULATED_LATENCY` | edge3     | `12ms`             | Oslo last-mile latency                      |
| `SIMULATED_LATENCY` | core      | `50ms`             | Frankfurt backhaul latency                  |
| `MAX_CACHE_SIZE`    | edge1/2/3 | `3`                | Max videos cached per edge node             |
| `EDGE_ID`           | edge1/2/3 | `edge1` etc.       | Node identifier used in logs and Redis keys |
| `REDIS_HOST`        | all       | `redis`            | Redis service hostname                      |
| `CORE_URL`          | edge1/2/3 | `http://core:5000` | Origin server URL for cache miss fetches    |

---

## API Reference

### Core Server `:5000`

| Method | Endpoint            | Description                                                         |
| ------ | ------------------- | ------------------------------------------------------------------- |
| `GET`  | `/videos`           | List all available videos                                           |
| `GET`  | `/video/<id>`       | Stream video file                                                   |
| `GET`  | `/precache-log`     | View last 50 pre-cache events                                       |
| `POST` | `/precache/trigger` | Manually trigger pre-cache for a video `{"video_id": "videoD.mp4"}` |
| `GET`  | `/health`           | Service health check                                                |

### Edge Nodes `:5001 / :5002 / :5003`

| Method | Endpoint        | Description                                              |
| ------ | --------------- | -------------------------------------------------------- |
| `GET`  | `/video/<id>`   | Serve video — HIT from cache or MISS fetch from core     |
| `GET`  | `/cache-status` | Show all currently cached videos on this node            |
| `GET`  | `/health`       | Returns node ID, location, simulated latency             |
| `POST` | `/precache`     | Pre-warm cache with a video `{"video_id": "videoD.mp4"}` |

### Analytics Service `:5010`

| Method | Endpoint            | Description                                                    |
| ------ | ------------------- | -------------------------------------------------------------- |
| `GET`  | `/analytics/report` | Batch Pandas report: hit rate, latency, top videos per edge    |
| `GET`  | `/predict/spikes`   | ML predictions: current avg vs predicted next window per video |
| `GET`  | `/health`           | Service health check                                           |

---

## How It Works

### Cache Hit / Miss Flow

```
User Request
    │
    ▼
NGINX (round-robin)
    │
    ▼
Edge Node
    ├─ Cache HIT ──► Serve from /app/cache ──► ~5ms response
    │                Update Redis ZINCRBY
    │
    └─ Cache MISS ──► Fetch from Core (~2,500ms)
                      Save to /app/cache
                      Set Redis cache:edgeN:videoX = 1
                      ZINCRBY popularity score
                      ──► Serve to user
```

### LRU Eviction

When an edge cache is full (`MAX_CACHE_SIZE=3`) and a new video is requested:

1. Get all currently cached videos
2. `ZSCORE` each against the `popular_videos` Redis sorted set
3. Evict the video with the **lowest score** (least popular)
4. Cache the new video in the freed slot

### Replication (Eventual Consistency)

Every 30 seconds on each edge:

1. `ZREVRANGE popular_videos 0 4` → get top-5 most popular videos
2. Check local cache — which ones are missing?
3. Fetch missing hot videos directly from peer edges
4. All nodes converge on the same hot content without a central coordinator

### ML-Driven Edge-Cloud Continuum

```
[All 3 edges] ──► SQLite logs ──► [Analytics :5010]
                                       │
                                  Pandas groupby
                                  5-min time windows
                                       │
                                  LinearRegression
                                  fit per video
                                       │
                              predicted > 2× avg?
                                       │
                              YES ──► spike_incoming: true
                                       │
                              [Core :5000 background thread]
                              polls every 2 minutes
                                       │
                              POST /precache to edge1/2/3
                                       │
                          Edges pre-warm cache before
                          next user wave arrives
```

### Network Latency Simulation

Each container runs `setup_network.sh` as its entrypoint, which uses Linux `tc-netem` to inject realistic geographic latency:

```bash
tc qdisc add dev eth0 root netem delay ${SIMULATED_LATENCY}
```

Verify with:

```powershell
docker exec telco-cdn-edge1-1 tc qdisc show dev eth0
# → qdisc netem 8004: root refcnt 13 limit 1000 delay 10ms
```

---

## Results

### Cache Hit Rate Progression

| Day | Overall   | edge1 Helsinki | edge2 Stockholm | edge3 Oslo |
| --- | --------- | -------------- | --------------- | ---------- |
| 1   | 38.2%     | 40.1%          | 35.8%           | 38.7%      |
| 2   | 61.5%     | 63.2%          | 59.7%           | 61.6%      |
| 3   | 74.8%     | 76.0%          | 73.1%           | 75.3%      |
| 4   | 86.1%     | 87.5%          | 84.9%           | 86.0%      |
| 5   | **92.1%** | **92.5%**      | **87.2%**       | **92.1%**  |

### ML Spike Detection

| Video  | Current Avg      | Predicted        | Status    |
| ------ | ---------------- | ---------------- | --------- |
| videoD | 8.71 req/window  | 29.57 req/window | **SPIKE** |
| videoA | 13.17 req/window | 13.14 req/window | Stable    |
| videoB | 2.40 req/window  | 1.53 req/window  | Stable    |
| videoC | 2.14 req/window  | 1.29 req/window  | Stable    |

videoD triggered an automatic pre-cache push to all 3 edge nodes.

---

## Troubleshooting

### Containers not starting / port conflict

```powershell
docker compose down
docker compose build --no-cache
docker compose up
```

### Latency not showing on edge containers

The `setup_network.sh` files must have **Unix (LF) line endings**. Fix on Windows:

```powershell
(Get-Content telco-cdn\edge\setup_network.sh -Raw).Replace("`r`n", "`n") | Set-Content telco-cdn\edge\setup_network.sh -NoNewline
(Get-Content telco-cdn\core\setup_network.sh -Raw).Replace("`r`n", "`n") | Set-Content telco-cdn\core\setup_network.sh -NoNewline
```

Then rebuild: `docker compose build --no-cache && docker compose up`

### Dashboard panels showing "Error loading"

CORS must be enabled on all Flask services. Check each service has:

```python
from flask_cors import CORS
CORS(app)
```

Then rebuild the affected service: `docker compose build --no-cache <service-name>`

### Pre-cache events not appearing

The background thread runs every **2 minutes**. Either wait, or manually trigger:

```powershell
# First generate a traffic spike on a video
for ($i=1; $i -le 50; $i++) { Invoke-WebRequest http://localhost:80/video/videoD.mp4 -OutFile NUL }

# Then manually trigger
curl.exe -X POST http://localhost:5000/precache/trigger -H "Content-Type: application/json" --data "{`"video_id`": `"videoD.mp4`"}"
```

### Check logs for any service

```powershell
docker logs telco-cdn-edge1-1 --follow
docker logs telco-cdn-core-1 --follow 2>&1 | findstr PRE-CACHE
docker logs telco-cdn-edge2-1 2>&1 | findstr Replicat
```

---

## Technology Stack

| Component               | Technology                    | Justification                                                                      |
| ----------------------- | ----------------------------- | ---------------------------------------------------------------------------------- |
| Edge / Core / Analytics | Flask (Python 3.11)           | Lightweight, native HTTP streaming, threading for background jobs                  |
| Shared Metadata         | Redis 7 Alpine                | Microsecond R/W, sorted sets for O(log N) popularity ranking                       |
| Orchestration           | Docker Compose                | 8-service isolation, network segmentation, shared volume mounts                    |
| Load Balancer           | NGINX Alpine                  | Round-robin, health probes, sits at network boundary                               |
| Analytics Pipeline      | SQLite + Pandas               | Zero-config, shared via Docker volume, `groupby` aggregations                      |
| ML Predictor            | scikit-learn LinearRegression | Interpretable, cheap to run per API call, sufficient for monotonic trend detection |
| Latency Simulation      | tc-netem (iproute2)           | Kernel-level, per-container, configurable via environment variable                 |
| Dashboard               | HTML/JS (nginx:alpine)        | Zero dependencies, CORS fetch to all backend APIs, 15s auto-refresh                |

---
