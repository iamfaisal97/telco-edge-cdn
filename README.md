# Telco-Edge CDN

A distributed CDN simulation built with Python, Docker, Redis, and NGINX.

## Architecture
```
[Users] → [NGINX :80] → [Edge1][Edge2][Edge3]
                              ↕ Redis (shared index)
                         [Core Server :5000]
```

## Stack
- Python Flask — all services
- Redis — shared cache index + popularity tracking
- Docker + Docker Compose — multi-node simulation
- NGINX — load balancer
- SQLite + Pandas — logging and analytics (Day 3-4)
- Scikit-learn — demand prediction (Day 4)

## How to Run
1. Add sample videos to `/videos/` folder (any .mp4 files)
2. Run `docker compose up --build`
3. Open `client/index.html` in browser
4. Hit `localhost:80/video/<filename>` to test

## Progress
- [x] Day 1 — Core server + Edge with cache hit/miss
- [x] Day 2 — Multiple edge nodes + NGINX + Redis shared index
- [ ] Day 3 — Logging middleware + LRU eviction
- [ ] Day 4 — Replication + batch analytics + ML prediction
- [ ] Day 5 — Pre-caching + microservices + demo dashboard

## Sample Test
```bash
# Hit same video 9 times, watch round-robin in Docker logs
for ($i=1; $i -le 9; $i++) { curl -s http://localhost:80/video/videoA.mp4 -o $null }
```