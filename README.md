# Metrics Dashboard

Real-time VPS monitoring dashboard with Python metrics agent and web frontend.

**Live Demo:** https://agent.hyperflash.uk

---

## Overview

This project provides a complete VPS monitoring solution with:
- **Python metrics agent** - High-performance system metrics collector
- **Web dashboard** - Real-time frontend with 2-second refresh
- **Token-based API** - Secure metrics endpoint
- **Zero dependencies** - Runs in a single Docker container

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              INTERNET                                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         CLOUDFLARE TUNNEL                                │
│  ┌─────────────────────────┐    ┌─────────────────────────┐            │
│  │ agent.hyperflash.uk     │    │ api.hyperflash.uk       │            │
│  │ → localhost:80 (Caddy)  │    │ → localhost:80 (Caddy)  │            │
│  └─────────────────────────┘    └─────────────────────────┘            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         CADDY (Docker)                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ agent.hyperflash.uk → Serves static frontend files             │   │
│  ├─────────────────────────────────────────────────────────────────┤   │
│  │ api.hyperflash.uk/metrics?token=SECRET                           │   │
│  │   - Token authentication                                        │   │
│  │   - Proxies → metrics-agent container (Docker)                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    METRICS AGENT (Docker container)                      │
│  - Python agent exposing JSON at /metrics                               │
│  - Reads from /proc for accurate system metrics                         │
│  - Docker socket access for container status                            │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
metrics-dashboard/
├── frontend/              # Dashboard HTML files
│   ├── index.html        # Main dashboard
│   ├── alt.html          # Alternative layout
│   └── simple.html       # Minimal version
├── agent/                # Python metrics agent
│   ├── Dockerfile        # Container build
│   ├── agent.py          # Metrics collector (v1.0.0)
│   └── README.md         # Agent documentation
└── deployment/           # Reference configs
    ├── docker-compose.yml
    └── Caddyfile.snippet
```

---

## Quick Start

### 1. Deploy the Agent

Add the metrics-agent service to your docker-compose.yml:

```yaml
services:
  metrics-agent:
    build:
      context: ./agent
      dockerfile: Dockerfile
    container_name: metrics-agent
    restart: unless-stopped
    volumes:
      - /proc:/proc:ro
      - /sys:/sys:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    group_add:
      - "996"  # Docker socket group
```

### 2. Configure Caddy

Add the reverse proxy with token authentication:

```caddy
@metrics {
    path /metrics*
    host api.hyperflash.uk
    query token=YOUR_SECRET_TOKEN
}

handle @metrics {
    header Access-Control-Allow-Origin "https://agent.hyperflash.uk"
    reverse_proxy metrics-agent:8000
}
```

### 3. Deploy the Frontend

Copy `frontend/*.html` files to your web root (e.g., `~/caddy/wwwroot/`).

---

## API Endpoints

### GET /metrics

Returns system metrics as JSON.

**Authentication:** URL parameter `token=YOUR_SECRET_TOKEN`

**Response:**
```json
{
  "hostname": "vps-name",
  "uptime": 1234567,
  "cpu": {
    "percent": 15.2,
    "cores": [12.5, 8.3, 18.1, ...]
  },
  "memory": {
    "total": 8589934592,
    "used": 4294967296,
    "percent": 50.0
  },
  "disk": [...],
  "docker": {...},
  "processes": [...],
  "logs": [...]
}
```

**Query Parameters:**
- `?compact=1` - Minified JSON response

---

## Features

### Agent (`agent/`)
- Per-core CPU usage tracking
- Memory and disk statistics
- Docker container status
- Top 5 processes by CPU/memory
- System logs (last 10 entries)
- Delta-based network rate calculations
- LRU-cached static system info

### Frontend (`frontend/`)
- Real-time updates (2-second interval)
- Responsive design
- Activity ticker
- Contact form integration
- Multiple layout options

---

## Requirements

- Docker and Docker Compose
- Caddy web server (or equivalent)
- Linux host with /proc filesystem

---

## Development

### Build the Agent

```bash
cd agent
docker build -t metrics-agent .
```

### Run Locally

```bash
docker run -p 8000:8000 \
  -v /proc:/proc:ro \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  metrics-agent
```

### Test the API

```bash
curl http://localhost:8000/metrics
```

---

## Related Projects

- **[vps-config](https://github.com/bilawalriaz/vps-config)** - Complete VPS setup and configuration
- **[agent-contact-worker](https://github.com/bilawalriaz/agent-contact-worker)** - Contact form Cloudflare Worker

---

## License

Private - All rights reserved.
