   # Telco-Edge CDN — Architecture Diagram

   ```
   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │                              CLIENT LAYER                                       │
   │                                                                                 │
   │   ┌──────────────────────────────────────────────────────────────┐              │
   │   │  Client Dashboard  (port 8080 → Nginx static host)          │              │
   │   │  index.html  — Chart.js dashboard, live auto-refresh 15s    │              │
   │   │                                                              │              │
   │   │  Polls:  edge1:5001  edge2:5002  edge3:5003  (cache-status) │              │
   │   │          core:5000   (videos list, precache-log)            │              │
   │   │          analytics:5010  (predict/spikes, analytics/report) │              │
   │   └──────────────────────────┬───────────────────────────────────┘              │
   │                              │  HTTP (client_network)                           │
   └─────────────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │                          LOAD BALANCER LAYER                                    │
   │                                                                                 │
   │   ┌──────────────────────────────────────────────────────────────┐              │
   │   │  NGINX  (port 80)                                            │              │
   │   │  Round-robin across edge1, edge2, edge3                      │              │
   │   │  Routes:  /video/*  →  upstream edges                       │              │
   │   │           /cache-index  →  upstream edges                   │              │
   │   │           /health  →  upstream edges                        │              │
   │   │  Header:  X-Served-By  (shows which edge responded)         │              │
   │   └─────────┬──────────────┬─────────────────┬──────────────────┘              │
   │             │              │                 │   (edge_network + client_network) │
   └─────────────────────────────────────────────────────────────────────────────────┘
               │              │                 │
      ┌────────┘    ┌─────────┘      ┌──────────┘
      ▼             ▼                ▼
   ┌──────────────────────────────────────────────────────────────────────────────────┐
   │                               EDGE LAYER                                         │
   │                                                                                  │
   │  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐             │
   │  │   edge1 :5001    │   │   edge2 :5002    │   │   edge3 :5003    │             │
   │  │  Helsinki        │   │  Stockholm       │   │  Oslo            │             │
   │  │  latency: 10ms   │   │  latency: 15ms   │   │  latency: 12ms   │             │
   │  │                  │   │                  │   │                  │             │
   │  │  Local FS cache  │   │  Local FS cache  │   │  Local FS cache  │             │
   │  │  (max 3 videos)  │   │  (max 3 videos)  │   │  (max 3 videos)  │             │
   │  │                  │   │                  │   │                  │             │
   │  │  Endpoints:      │   │  Endpoints:      │   │  Endpoints:      │             │
   │  │  GET /video/:id  │   │  GET /video/:id  │   │  GET /video/:id  │             │
   │  │  POST /precache  │   │  POST /precache  │   │  POST /precache  │             │
   │  │  GET /cache-status│  │  GET /cache-status│  │  GET /cache-status│            │
   │  │  GET /cache-index│   │  GET /cache-index│   │  GET /cache-index│             │
   │  │  GET /popularity │   │  GET /popularity │   │  GET /popularity │             │
   │  │  GET /logs       │   │  GET /logs       │   │  GET /logs       │             │
   │  │  GET /health     │   │  GET /health     │   │  GET /health     │             │
   │  │  GET /sync-status│   │  GET /sync-status│   │  GET /sync-status│             │
   │  └────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘             │
   │           │    ▲ replication     │    ▲ replication     │    ▲                  │
   │           │    └─────────────────┼────┴─────────────────┘    │                  │
   │           │    edge-to-edge sync │  every 30s via Redis index │                  │
   └──────────────────────────────────────────────────────────────────────────────────┘
            │                       │
            │ CACHE MISS            │  ALL edges read/write Redis
            │ fetch from core       │
            ▼                       ▼
   ┌──────────────────────────────────────────────────────────────────────────────────┐
   │                           SHARED STATE LAYER                                     │
   │                                                                                  │
   │  ┌──────────────────────────────────────────────────────────────────────────┐    │
   │  │  Redis  :6379  (core_network + edge_network)                             │    │
   │  │                                                                          │    │
   │  │  Sorted Set:   popular_videos          — global request counts per video │    │
   │  │  String keys:  cache:<edge_id>:<video> — which edge has which video      │    │
   │  │                                                                          │    │
   │  │  Used for:  LRU-popularity eviction · replication sync · global ranking  │    │
   │  └──────────────────────────────────────────────────────────────────────────┘    │
   └──────────────────────────────────────────────────────────────────────────────────┘
            │
            ▼
   ┌──────────────────────────────────────────────────────────────────────────────────┐
   │                              CORE / ORIGIN LAYER                                 │
   │                                                                                  │
   │  ┌──────────────────────────────────────────────────────────────────────────┐    │
   │  │  Core Server  :5000  (core_network)                                      │    │
   │  │                                                                          │    │
   │  │  Endpoints:                                                              │    │
   │  │    GET  /videos            — list all .mp4 files                         │    │
   │  │    GET  /video/:id         — stream video file (origin source)           │    │
   │  │    POST /precache/trigger  — manually push video to all edges            │    │
   │  │    GET  /precache-log      — last 50 pre-cache orchestration events      │    │
   │  │                                                                          │    │
   │  │  Background thread (every 2 min):                                        │    │
   │  │    1. GET analytics:5010/predict/spikes  →  spike list                   │    │
   │  │    2. POST edge1,2,3:/precache {video_id}  →  push before demand hits    │    │
   │  │    (Edge-Cloud Continuum orchestration)                                  │    │
   │  │                                                                          │    │
   │  │  Volume: ./videos  (videoA.mp4, videoB.mp4, videoC.mp4, videoD.mp4)     │    │
   │  └──────────────────────────────────────────────────────────────────────────┘    │
   └──────────────────────────────────────────────────────────────────────────────────┘
            │
            ▼
   ┌──────────────────────────────────────────────────────────────────────────────────┐
   │                          ANALYTICS / ML LAYER                                    │
   │                                                                                  │
   │  ┌──────────────────────────────────────────────────────────────────────────┐    │
   │  │  Analytics Service  :5010  (core_network + client_network)               │    │
   │  │                                                                          │    │
   │  │  Endpoints:                                                              │    │
   │  │    GET /analytics/report   — batch aggregation (pandas)                  │    │
   │  │    GET /predict/spikes     — ML spike prediction (sklearn LinearReg)     │    │
   │  │    GET /health                                                           │    │
   │  │                                                                          │    │
   │  │  batch_job.py:                                                           │    │
   │  │    Reads requests.db  →  top videos / hit rates / latency / time windows │    │
   │  │    Writes analytics_report.json                                          │    │
   │  │                                                                          │    │
   │  │  predictor.py:                                                           │    │
   │  │    Reads requests.db  →  5-min time buckets per video                    │    │
   │  │    Fits LinearRegression per video  →  predicts next window count        │    │
   │  │    Flags spike if predicted > 2× avg AND predicted > 2                   │    │
   │  └──────────────────────────────────────────────────────────────────────────┘    │
   │                                     ▲                                            │
   │  Shared volume: ./logs/requests.db ─┘ (also written by all edge nodes)          │
   │                  ./logs/analytics_report.json                                    │
   └──────────────────────────────────────────────────────────────────────────────────┘

   ═══════════════════════════════════════════════════════════════════════════════════
                           DATA FLOWS — KEY SEQUENCES
   ═══════════════════════════════════════════════════════════════════════════════════

   ① User requests a video (cache MISS):
      Client → NGINX :80 → Edge (round-robin) → CACHE MISS
      Edge → Core :5000/video/:id  (fetch + store locally)
      Edge → Redis  (set cache:<edgeId>:<video> = 1, zincrby popular_videos)
      Edge → SQLite requests.db  (log: timestamp, edge, video, hit=0, latency, ip)
      Edge → Client  (serve video, X-Cache: MISS)

   ② User requests a video (cache HIT):
      Client → NGINX → Edge → Local FS cache HIT
      Edge → Redis  (zincrby popular_videos)
      Edge → SQLite (log: hit=1)
      Edge → Client  (serve video, X-Cache: HIT)

   ③ Edge Replication Sync  (every 30s per edge):
      Edge → Redis  (zrevrange popular_videos top 5)
      For each popular video not locally cached:
      Check Redis cache:<otherEdge>:<video>
      If found → fetch from other edge's /video/:id  (edge-to-edge)
      Store locally + set Redis cache key

   ④ ML-Driven Pre-caching  (every 2 min, Core orchestrator):
      Core → Analytics :5010/predict/spikes
      Analytics → SQLite  (read all requests, fit LinearRegression)
      Analytics → Core  (spike list)
      Core → edge1,2,3 POST /precache {video_id}
      Each Edge → Core /video/:id  (fetch + store before users ask)

   ⑤ LRU-Popularity Eviction  (on every cache MISS or pre-cache):
      If cached count ≥ MAX_CACHE_SIZE (3):
      Query Redis zscore for each cached video
      Delete local file of lowest-score video
      Delete Redis cache:<edgeId>:<video> key

   ═══════════════════════════════════════════════════════════════════════════════════
                                 DOCKER NETWORKS
   ═══════════════════════════════════════════════════════════════════════════════════

   core_network   — core, edge1, edge2, edge3, redis, analytics
   edge_network   — edge1, edge2, edge3, redis, nginx
   client_network — nginx, analytics, client

   (analytics is on core_network + client_network → reachable by core AND dashboard)
   (nginx is on edge_network + client_network → bridges user traffic to edges)

   ═══════════════════════════════════════════════════════════════════════════════════
                                 PORT MAP
   ═══════════════════════════════════════════════════════════════════════════════════

   Service       Host Port  Container Port
   ─────────     ─────────  ──────────────
   core          5000       5000
   edge1         5001       5001
   edge2         5002       5002
   edge3         5003       5003
   redis         6379       6379
   analytics     5010       5010
   nginx         80         80
   client        8080       80
   ```
