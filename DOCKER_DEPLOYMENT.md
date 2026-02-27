# Docker Deployment Guide

Complete guide to building and running the Romanian Personas Agent as a multi-service application using Docker Compose.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Environment Setup](#environment-setup)
- [Building Services](#building-services)
- [Running Services](#running-services)
- [Accessing Services](#accessing-services)
- [Development Workflow](#development-workflow)
- [Monitoring & Logs](#monitoring--logs)
- [Troubleshooting](#troubleshooting)
- [Production Considerations](#production-considerations)

## Prerequisites

You must have the following installed:

- **Docker Desktop** (Mac/Windows) or **Docker Engine + Docker Compose** (Linux)
  - Docker: v20.10+
  - Docker Compose: v2.0+
  - Verify: `docker --version && docker-compose --version`

- **Pre-built ChromaDB** (required before first run)
  ```bash
  # If you haven't built the vector stores locally yet, run:
  python -m ingest.scraper
  python -m ingest.extract_quotes
  python -m ingest.run_ingestion
  ```
  This creates `chroma_db/` (123MB) and `data/` directories used by the Docker containers.

- **API Keys** in `.env` file (see [Environment Setup](#environment-setup))

## Quick Start

```bash
# 1. Clone the repository
cd /path/to/romanian-personas-agent

# 2. Create .env file with required API keys
cp .env.example .env
# Edit .env and add your keys:
#   ANTHROPIC_API_KEY=sk-ant-...
#   OPENAI_API_KEY=sk-...
#   ADMIN_PASSWORD=your_secure_password

# 3. Build all services
docker-compose build

# 4. Start all services in background
docker-compose up -d

# 5. Verify services are healthy
docker-compose ps
curl http://localhost:8000/health
curl http://localhost:8080/health
curl http://localhost:3000
curl http://localhost:3001

# 6. View logs (optional)
docker-compose logs -f

# 7. Stop services
docker-compose down
```

## Environment Setup

### Create `.env` File

Create a `.env` file in the project root with the following required variables:

```bash
# LLM API Keys (REQUIRED)
ANTHROPIC_API_KEY=sk-ant-v01-xxxxxxxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxx

# Marketplace Configuration
ADMIN_PASSWORD=your_secure_admin_password_here

# Optional: MCP API Key for remote access
MCP_API_KEY=your_mcp_api_key_here

# Optional: Override defaults (usually not needed)
# REDIS_URL=redis://redis:6379/0
# DATABASE_URL=sqlite:///./personas.db
# CHROMA_PERSIST_DIR=./chroma_db
# DATA_DIR=./data
# SYNTHESIS_MODEL=claude-opus-4-6
# EMBEDDING_MODEL=text-embedding-3-small
```

### Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | - | Claude API key for synthesis |
| `OPENAI_API_KEY` | Yes | - | OpenAI API key for embeddings |
| `ADMIN_PASSWORD` | Yes | - | Admin UI login password |
| `MCP_API_KEY` | No | - | Optional auth token for MCP server |
| `REDIS_URL` | No | `redis://redis:6379/0` | Redis connection string |
| `DATABASE_URL` | No | `sqlite:///./personas.db` | SQLite database path |
| `CHROMA_PERSIST_DIR` | No | `./chroma_db` | ChromaDB persistence directory |
| `DATA_DIR` | No | `./data` | Directory for uploaded persona data |
| `SYNTHESIS_MODEL` | No | `claude-opus-4-6` | Claude model for responses |
| `EMBEDDING_MODEL` | No | `text-embedding-3-small` | OpenAI embedding model |

## Building Services

### Build All Services

```bash
# Build all services (takes 2-5 minutes)
docker-compose build

# Or build specific service
docker-compose build api
docker-compose build mcp_server
docker-compose build celery_worker
docker-compose build debate_ui
docker-compose build admin_ui
```

### Build Options

```bash
# Build with no cache (force rebuild)
docker-compose build --no-cache

# Build specific service only
docker-compose build api

# Build in parallel (faster)
docker-compose build --parallel
```

### Dockerfile Overview

| Service | Dockerfile | Purpose |
|---------|-----------|---------|
| api | `Dockerfile.api` | FastAPI backend (REST API) |
| mcp_server | `Dockerfile` | MCP server for debate UI |
| celery_worker | `Dockerfile.worker` | Background job processor |
| debate_ui | `persona-debate-ui/Dockerfile` | React debate UI |
| admin_ui | `admin-ui/Dockerfile` | React admin UI (Phase 5) |

## Running Services

### Start All Services

```bash
# Start in background (detached mode)
docker-compose up -d

# Start in foreground (see logs as they happen)
docker-compose up

# Start specific services only
docker-compose up -d redis api mcp_server
```

### Service Startup Order

Docker Compose respects the `depends_on` constraints:

1. **redis** - starts first (dependency for others)
2. **mcp_server** - starts independently (reads pre-built ChromaDB)
3. **api** - starts after redis is healthy
4. **celery_worker** - starts after redis is healthy
5. **debate_ui** - starts after mcp_server is healthy
6. **admin_ui** - starts after api is healthy

### Check Service Status

```bash
# List all services and their status
docker-compose ps

# Check health of specific service
docker-compose ps api
docker-compose ps redis

# Verify all services are healthy
docker-compose ps --format "table {{.Service}}\t{{.Status}}"
```

## Accessing Services

### Web Interfaces

| Service | URL | Purpose | Auth |
|---------|-----|---------|------|
| **API** | http://localhost:8000 | REST API & docs | Basic Auth |
| **API Docs** | http://localhost:8000/docs | Swagger UI | Basic Auth |
| **MCP Server** | http://localhost:8080 | MCP backend | Optional Bearer Token |
| **MCP Health** | http://localhost:8080/health | MCP health check | No auth |
| **Debate UI** | http://localhost:3000 | Debate interface | No auth |
| **Admin UI** | http://localhost:3001 | Admin panel | Password protected |

### API Authentication

FastAPI routes use HTTP Basic Auth:

```bash
# Using curl
curl -u admin:your_admin_password http://localhost:8000/api/personas

# Using httpx/requests
import requests
response = requests.get(
    'http://localhost:8000/api/personas',
    auth=('admin', 'your_admin_password')
)
```

### Testing Connectivity

```bash
# Test API health
curl http://localhost:8000/health

# Test MCP server health
curl http://localhost:8080/health

# Test debate UI
curl http://localhost:3000

# Test API docs
curl http://localhost:8000/docs

# List personas (requires auth)
curl -u admin:password http://localhost:8000/api/personas/list
```

## Development Workflow

### Enable Hot Reload

For faster local development, enable code hot-reload:

```bash
# Copy development overrides
cp docker-compose.override.yml.example docker-compose.override.yml

# Start services with development settings
docker-compose up -d
```

This enables:
- Live code reloading (changes reflected immediately)
- Debug logging (more verbose output)
- Auto-restart on crashes

### Modifying Code

With `docker-compose.override.yml` enabled:

```bash
# Changes to Python files are reflected automatically
# Changes to Node files require npm rebuild

# Edit Python code
vim api/routes/personas.py

# Edit FastAPI routes - changes auto-reload
curl -u admin:password http://localhost:8000/api/personas

# Edit Celery tasks
vim workers/tasks.py
# Check worker logs: docker-compose logs -f celery_worker

# Edit React components
vim persona-debate-ui/src/components/...
# Changes auto-refresh in browser
```

### Rebuilding Services

```bash
# Rebuild after adding new Python dependencies
docker-compose build api

# Restart the service to use new build
docker-compose up -d api

# Or rebuild and restart in one command
docker-compose up -d --build api
```

## Monitoring & Logs

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service (real-time)
docker-compose logs -f api
docker-compose logs -f mcp_server
docker-compose logs -f celery_worker
docker-compose logs -f debate_ui

# Last 100 lines of API logs
docker-compose logs --tail=100 api

# Logs from past hour
docker-compose logs --since 1h api

# Follow logs with timestamps
docker-compose logs -f --timestamps api
```

### Service Health Checks

```bash
# Check status of all services
docker-compose ps

# Check specific service health
docker inspect personas-api | grep -A 10 Health

# Manual health check
docker exec personas-api curl http://localhost:8000/health
docker exec personas-mcp-server curl http://localhost:8080/health
docker exec personas-redis redis-cli ping
```

### Monitor Resource Usage

```bash
# Real-time resource usage
docker stats

# Specific container
docker stats personas-api personas-redis personas-celery-worker
```

### View Container Events

```bash
# Watch container lifecycle events
docker-compose events

# Restart a crashed service
docker-compose restart api

# View recent events
docker events --filter type=container --since 10m
```

## Troubleshooting

### Common Issues

#### Services failing to start

```bash
# Check full error messages
docker-compose logs -f

# Rebuild from scratch
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

#### Redis connection errors

```bash
# Verify Redis is running
docker-compose ps redis

# Test Redis connection
docker exec personas-redis redis-cli ping
# Should return: PONG

# If Redis won't start, check port conflict
lsof -i :6379
```

#### API can't connect to Redis

```bash
# Verify REDIS_URL is correct (for docker-compose: redis://redis:6379/0)
docker exec personas-api printenv REDIS_URL

# Test connection from API container
docker exec personas-api redis-cli -u redis://redis:6379/0 ping

# Check Redis logs
docker-compose logs -f redis
```

#### Celery worker not picking up tasks

```bash
# Check worker is running
docker-compose ps celery_worker

# Check worker logs
docker-compose logs -f celery_worker

# Verify Redis broker
docker-compose logs -f redis

# Test task submission (requires API)
curl -X POST -u admin:password \
  http://localhost:8000/api/personas/1/ingest \
  -H "Content-Type: application/json"
```

#### ChromaDB not found or empty

```bash
# Verify volumes mounted
docker inspect personas-api | grep -A 20 Mounts | grep chroma

# Check local chroma_db directory exists
ls -la chroma_db/

# If missing, build it locally first:
python -m ingest.scraper
python -m ingest.extract_quotes
python -m ingest.run_ingestion

# Then restart containers
docker-compose down -v
docker-compose up -d
```

#### Port conflicts

```bash
# Check what's using ports
lsof -i :8000  # API
lsof -i :8080  # MCP
lsof -i :3000  # Debate UI
lsof -i :3001  # Admin UI
lsof -i :6379  # Redis

# Use different ports in docker-compose.yml
# Or kill the process using the port
kill -9 <PID>
```

#### Database locked (SQLite)

```bash
# SQLite "database is locked" usually means:
# 1. Multiple processes accessing it simultaneously
# 2. Journal file not cleaned up

# Remove stale lock files
rm personas.db-journal 2>/dev/null

# Restart affected services
docker-compose restart api celery_worker

# Check database integrity
docker exec personas-api sqlite3 personas.db ".tables"
```

#### Out of memory

```bash
# Check container memory limits
docker stats personas-api personas-celery-worker

# Increase memory in docker-compose.yml under deploy.resources.limits.memory
# Or via Docker Desktop settings:
# Preferences > Resources > Memory > Increase to 8GB+

# Restart containers
docker-compose restart
```

### Debugging Commands

```bash
# Enter container shell
docker exec -it personas-api bash

# Run Python commands in container
docker exec personas-api python -c "import config; print(config.settings.redis_url)"

# Check environment variables in container
docker exec personas-api env | grep -E "REDIS|DATABASE|ANTHROPIC"

# Check network connectivity from container
docker exec personas-api curl http://redis:6379/health
docker exec personas-celery-worker ping redis

# Test ChromaDB from API container
docker exec personas-api python -c "
from ingest.run_ingestion import load_retriever
retriever = load_retriever('eminescu', 'profile')
print(f'Loaded {retriever._db._client._get_collection(\"eminescu_profile\").count()} vectors')
"
```

## Production Considerations

### Pre-Deployment Checklist

- [ ] Build ChromaDB locally: `python -m ingest.scraper && python -m ingest.extract_quotes && python -m ingest.run_ingestion`
- [ ] Test all services locally: `docker-compose up -d && docker-compose ps`
- [ ] Set strong `ADMIN_PASSWORD` in `.env`
- [ ] Set `MCP_API_KEY` for remote access
- [ ] Configure `REDIS_URL` to external Redis (not localhost)
- [ ] Use external PostgreSQL or managed SQLite (not single-container SQLite)
- [ ] Enable Docker logging driver (JSON file, CloudWatch, etc.)
- [ ] Set resource limits in `docker-compose.yml` (memory, CPU)
- [ ] Configure backup strategy for `personas.db`

### Production Docker Compose

For production deployments, update:

```yaml
api:
  restart: always
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 4G
      reservations:
        cpus: '1'
        memory: 2G
  logging:
    driver: "awslogs"
    options:
      awslogs-group: "/ecs/personas"
      awslogs-region: "us-east-1"
      awslogs-stream-prefix: "ecs"

redis:
  restart: always
  image: redis:7-alpine
  # Or use managed Redis (AWS ElastiCache)

celery_worker:
  deploy:
    resources:
      limits:
        cpus: '1'
        memory: 2G
    replicas: 3  # Scale workers

# Add backup container for SQLite
backup:
  image: alpine
  volumes:
    - personas_db:/data
  command: sh -c "tar czf /backup/personas-$(date +%Y%m%d).tar.gz /data/personas.db"
  # Run periodically via cron job
```

### Environment Secrets Management

For production, use secret management instead of `.env`:

```bash
# AWS Secrets Manager
aws secretsmanager get-secret-value --secret-id personas/prod

# Docker Secrets (swarm mode)
docker secret create anthropic_key -
docker secret create openai_key -
docker secret create admin_password -

# Update docker-compose.yml to use secrets
secrets:
  anthropic_key:
    external: true
  openai_key:
    external: true
```

### Scaling

For high traffic, scale workers and use external services:

```bash
# Scale Celery workers
docker-compose up -d --scale celery_worker=5

# Use managed Redis
REDIS_URL=redis://managed-redis.aws.amazon.com:6379/0

# Use managed database
DATABASE_URL=postgresql://user:pass@db.example.com/personas

# Load balance API
# Deploy multiple API instances behind nginx
```

### Monitoring & Alerting

Add monitoring stack (optional):

```yaml
prometheus:
  image: prom/prometheus
  ports:
    - "9090:9090"
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml

grafana:
  image: grafana/grafana
  ports:
    - "3010:3000"
  depends_on:
    - prometheus
```

## Cleanup

### Stop Services

```bash
# Stop all services (keep volumes)
docker-compose stop

# Stop and remove containers (keep volumes)
docker-compose down

# Remove everything including volumes
docker-compose down -v
```

### Clean Up Images & Containers

```bash
# Remove unused images
docker image prune -a

# Remove all stopped containers
docker container prune

# Remove all unused volumes
docker volume prune

# Full cleanup (destructive)
docker system prune -a --volumes
```

## Support

For issues or questions:

1. Check [Troubleshooting](#troubleshooting) section above
2. Review logs: `docker-compose logs -f`
3. Check service health: `docker-compose ps`
4. Verify `.env` configuration
5. Ensure ChromaDB is built locally before first run

---

**Last Updated:** February 2026
**Project:** Romanian Personas Agent Marketplace MVP
**Docker Compose Version:** 3.9+
