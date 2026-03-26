# Telco-Edge CDN Architecture Flowchart

## System Architecture Overview

```mermaid
flowchart TB
    subgraph CLIENT["CLIENT LAYER"]
        CD["Client Dashboard<br/>Port 8080<br/>Chart.js Dashboard<br/>Auto-refresh 15s"]
    end

    subgraph LB["LOAD BALANCER LAYER"]
        NGINX["NGINX<br/>Port 80<br/>Round-robin load balancer<br/>Routes: /video/*, /cache-index, /health"]
    end

    subgraph EDGE["EDGE LAYER"]
        E1["Edge1 :5001<br/>Helsinki<br/>Latency: 10ms<br/>Max 3 videos cache"]
        E2["Edge2 :5002<br/>Stockholm<br/>Latency: 15ms<br/>Max 3 videos cache"]
        E3["Edge3 :5003<br/>Oslo<br/>Latency: 12ms<br/>Max 3 videos cache"]
    end

    subgraph SHARED["SHARED STATE LAYER"]
        REDIS[("Redis :6379<br/>popular_videos<br/>cache:edge:video keys")]
    end

    subgraph CORE["CORE / ORIGIN LAYER"]
        CORESVR["Core Server :5000<br/>Video Origin<br/>Precache Orchestrator<br/>Background Thread 2min"]
        VIDEOS[("Video Storage<br/>videoA.mp4<br/>videoB.mp4<br/>videoC.mp4<br/>videoD.mp4")]
    end

    subgraph ANALYTICS["ANALYTICS / ML LAYER"]
        ANAL["Analytics Service :5010<br/>Batch Aggregation<br/>ML Spike Prediction<br/>LinearRegression"]
        DB[("requests.db<br/>SQLite Database")]
        REPORT["analytics_report.json"]
    end

    CD -->|HTTP| NGINX
    CD -.->|Poll:5001| E1
    CD -.->|Poll:5002| E2
    CD -.->|Poll:5003| E3
    CD -.->|Poll:5000| CORESVR
    CD -.->|Poll:5010| ANAL

    NGINX -->|Round-robin| E1
    NGINX -->|Round-robin| E2
    NGINX -->|Round-robin| E3

    E1 <-->|Read/Write| REDIS
    E2 <-->|Read/Write| REDIS
    E3 <-->|Read/Write| REDIS

    E1 -.->|Cache MISS| CORESVR
    E2 -.->|Cache MISS| CORESVR
    E3 -.->|Cache MISS| CORESVR

    CORESVR -.->|GET /predict/spikes| ANAL
    CORESVR -->|Serve videos| VIDEOS

    ANAL -->|Read/Write| DB
    ANAL -->|Write| REPORT

    E1 -.->|Replication sync| E2
    E2 -.->|Replication sync| E3
    E3 -.->|Replication sync| E1

    classDef clientStyle fill:#e1f5ff,stroke:#0066cc,stroke-width:2px
    classDef lbStyle fill:#fff4e1,stroke:#ff9900,stroke-width:2px
    classDef edgeStyle fill:#e8f5e9,stroke:#4caf50,stroke-width:2px
    classDef sharedStyle fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px
    classDef coreStyle fill:#fff3e0,stroke:#ff5722,stroke-width:2px
    classDef analyticsStyle fill:#fce4ec,stroke:#e91e63,stroke-width:2px

    class CD clientStyle
    class NGINX lbStyle
    class E1,E2,E3 edgeStyle
    class REDIS sharedStyle
    class CORESVR,VIDEOS coreStyle
    class ANAL,DB,REPORT analyticsStyle
```

## Data Flow Sequences

### 1. Video Request (Cache MISS)

```mermaid
sequenceDiagram
    participant C as Client
    participant N as NGINX
    participant E as Edge Node
    participant R as Redis
    participant Core as Core Server
    participant DB as SQLite

    C->>N: Request video
    N->>E: Round-robin route
    E->>E: Check local cache
    E->>Core: Cache MISS - fetch video
    Core-->>E: Return video
    E->>R: Set cache:edgeId:video = 1
    E->>R: zincrby popular_videos
    E->>DB: Log request (hit=0)
    E-->>C: Serve video (X-Cache: MISS)
```

### 2. Video Request (Cache HIT)

```mermaid
sequenceDiagram
    participant C as Client
    participant N as NGINX
    participant E as Edge Node
    participant R as Redis
    participant DB as SQLite

    C->>N: Request video
    N->>E: Round-robin route
    E->>E: Check local cache
    E->>R: zincrby popular_videos
    E->>DB: Log request (hit=1)
    E-->>C: Serve video (X-Cache: HIT)
```

### 3. Edge Replication Sync (every 30s)

```mermaid
sequenceDiagram
    participant E1 as Edge1
    participant R as Redis
    participant E2 as Edge2
    participant E3 as Edge3

    E1->>R: zrevrange popular_videos top 5
    R-->>E1: Return popular videos
    E1->>R: Check cache:otherEdge:video
    alt Video found on other edge
        E1->>E2: Fetch video from /video/:id
        E2-->>E1: Return video
        E1->>R: Set cache:edge1:video = 1
    end
```

### 4. ML-Driven Pre-caching (every 2 min)

```mermaid
sequenceDiagram
    participant Core as Core Server
    participant Anal as Analytics
    participant DB as SQLite
    participant E1 as Edge1
    participant E2 as Edge2
    participant E3 as Edge3

    Core->>Anal: GET /predict/spikes
    Anal->>DB: Read all requests
    Anal->>Anal: Fit LinearRegression
    Anal-->>Core: Return spike list
    Core->>E1: POST /precache video_id
    Core->>E2: POST /precache video_id
    Core->>E3: POST /precache video_id
    E1->>Core: Fetch video from /video/:id
    E2->>Core: Fetch video from /video/:id
    E3->>Core: Fetch video from /video/:id
```

### 5. LRU-Popularity Eviction

```mermaid
flowchart LR
    A[Cache MISS or Pre-cache] --> B{Cached count >= 3?}
    B -->|No| C[Store video normally]
    B -->|Yes| D[Query Redis zscore for each cached video]
    D --> E[Find lowest-score video]
    E --> F[Delete local file]
    F --> G[Delete Redis cache key]
    G --> H[Store new video]
    C --> I[Update Redis cache key]
    H --> I
```

## Docker Networks

```mermaid
graph LR
    subgraph Networks
        CN[core_network]
        EN[edge_network]
        CLN[client_network]
    end

    subgraph Services
        CORE[Core Server]
        E1[Edge1]
        E2[Edge2]
        E3[Edge3]
        REDIS[Redis]
        ANAL[Analytics]
        NGINX[NGINX]
        CLIENT[Client Dashboard]
    end

    CORE --- CN
    E1 --- CN
    E1 --- EN
    E2 --- CN
    E2 --- EN
    E3 --- CN
    E3 --- EN
    REDIS --- CN
    ANAL --- CN
    ANAL --- CLN
    NGINX --- EN
    NGINX --- CLN
    CLIENT --- CLN
```

## Port Mapping

| Service   | Host Port | Container Port |
| --------- | --------- | -------------- |
| core      | 5000      | 5000           |
| edge1     | 5001      | 5001           |
| edge2     | 5002      | 5002           |
| edge3     | 5003      | 5003           |
| redis     | 6379      | 6379           |
| analytics | 5010      | 5010           |
| nginx     | 80        | 80             |
| client    | 8080      | 80             |

## Key Features

- **Edge Caching**: Local file system cache with max 3 videos per edge
- **Load Balancing**: Round-robin across 3 edge nodes
- **Replication**: Edge-to-edge sync every 30 seconds via Redis
- **ML Pre-caching**: Predictive caching based on LinearRegression spike detection
- **LRU Eviction**: Least Recently Used eviction based on popularity scores
- **Analytics**: Real-time dashboard with 15s auto-refresh
