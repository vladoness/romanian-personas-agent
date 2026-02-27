# Workers Package

Background job workers for persona marketplace ingestion using Celery and Redis.

## Overview

This package provides asynchronous ChromaDB ingestion workers that process persona data in the background. Tasks automatically update database status and handle errors gracefully.

## Package Structure

```
workers/
├── __init__.py      # Package exports
├── celery_app.py    # Celery configuration
├── tasks.py         # Task implementations
└── README.md        # This file
```

## Tasks

### Individual Collection Tasks

#### `ingest_persona_works(persona_id: str, job_id: str)`
Ingests literary works collection into ChromaDB.
- **Input:** Persona ID and IngestionJob ID
- **Source:** `data/{persona_id}/works/*.{txt,md}`
- **Output:** Vector count stored in job
- **Time:** Variable (depends on corpus size)

#### `ingest_persona_quotes(persona_id: str, job_id: str)`
Ingests quotes collection into ChromaDB.
- **Input:** Persona ID and IngestionJob ID
- **Source:** `data/{persona_id}/quotes/all_quotes.jsonl`
- **Output:** Vector count stored in job
- **Time:** ~2-5 minutes

#### `ingest_persona_profile(persona_id: str, job_id: str)`
Ingests profile collection into ChromaDB.
- **Input:** Persona ID and IngestionJob ID
- **Source:** `personas/{persona_id}/profile.md` + `data/{persona_id}/profile/`
- **Output:** Vector count stored in job
- **Time:** ~30-60 seconds (fastest)

### Orchestrator Task

#### `ingest_full_persona(persona_id: str, job_ids: dict)`
Coordinates all three ingestion tasks.
- **Input:** Persona ID and dict of job IDs: `{"works": "...", "quotes": "...", "profile": "..."}`
- **Flow:**
  1. Updates persona status to 'ingesting'
  2. Triggers profile task (fast)
  3. Triggers works + quotes tasks (parallel)
- **Output:** Dict with triggered task IDs

## CallbackTask Base Class

All ingestion tasks inherit from `CallbackTask` for automatic status management:

```python
class CallbackTask(Task):
    def on_success(self, retval, task_id, args, kwargs):
        # Automatically updates job status to 'completed'
        # Sets progress to 100%
        # Records completion timestamp

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        # Automatically updates job status to 'failed'
        # Stores error message
        # Records completion timestamp
```

## Configuration

### Celery Settings
- **Broker:** Redis (from `settings.redis_url`)
- **Backend:** Redis
- **Time limit:** 7200s (2 hours)
- **Soft limit:** 6900s (1h 55m)
- **Serializer:** JSON
- **Prefetch:** 1 task at a time
- **Max tasks per child:** 10

### Environment Variables
Required in `.env`:
```bash
REDIS_URL=redis://localhost:6379/0
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

## Usage

### Starting the Worker

```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start worker
celery -A workers.celery_app worker --loglevel=info
```

### Triggering Tasks (from Python)

```python
from workers.tasks import ingest_full_persona

# Trigger full ingestion
result = ingest_full_persona.apply_async(
    kwargs={
        "persona_id": "eminescu",
        "job_ids": {
            "works": "job-uuid-1",
            "quotes": "job-uuid-2",
            "profile": "job-uuid-3"
        }
    }
)

print(f"Task ID: {result.id}")
```

### Checking Task Status

```python
from celery.result import AsyncResult
from workers import celery_app

result = AsyncResult(task_id, app=celery_app)
print(f"Status: {result.status}")  # PENDING, STARTED, SUCCESS, FAILURE
print(f"Result: {result.result}")
```

### Checking Job Status (Database)

```python
from models.database import get_session, IngestionJob

with get_session() as session:
    job = session.query(IngestionJob).filter_by(id=job_id).first()
    print(f"Status: {job.status}")        # pending, processing, completed, failed
    print(f"Progress: {job.progress}%")   # 0-100
    print(f"Vectors: {job.total_vectors}")
    print(f"Error: {job.error_message}")
```

## Task Flow

```
FastAPI Endpoint
  ↓
ingest_full_persona.apply_async()
  ↓
┌─────────────────────────────────┐
│ Update Persona: status=ingesting │
└─────────────────────────────────┘
  ↓
  ├─→ ingest_persona_profile (fastest)
  │     ├─ Update job: status=processing
  │     ├─ Call ingest_profile()
  │     ├─ Store vector count
  │     └─ CallbackTask: status=completed
  │
  ├─→ ingest_persona_works (parallel)
  │     ├─ Update job: status=processing
  │     ├─ Call ingest_works()
  │     ├─ Store vector count
  │     └─ CallbackTask: status=completed
  │
  └─→ ingest_persona_quotes (parallel)
        ├─ Update job: status=processing
        ├─ Call ingest_quotes()
        ├─ Store vector count
        └─ CallbackTask: status=completed
```

## Error Handling

### Soft Time Limit Exceeded
```python
from celery.exceptions import SoftTimeLimitExceeded

try:
    # Long-running operation
    result = ingest_works(persona_id)
except SoftTimeLimitExceeded:
    # Warning: approaching hard limit
    logger.warning("Soft time limit exceeded")
    raise
```

### Task Failure
- CallbackTask automatically updates job status to 'failed'
- Error message stored in `IngestionJob.error_message`
- Task can be retried manually or automatically (if configured)

### Database Errors
- Session rollback on exception
- Proper logging with traceback
- Worker continues processing other tasks

## Monitoring

### Celery Events
```bash
celery -A workers.celery_app events
```

### Flower (Web UI)
```bash
pip install flower
celery -A workers.celery_app flower
# Open http://localhost:5555
```

### Logs
```python
import logging
logging.basicConfig(level=logging.INFO)
```

## Testing

### Setup Tests
```bash
python test_workers.py
```
Verifies:
- Imports
- Configuration
- Database integration
- Task signatures
- Ingestion functions

### Integration Tests
```bash
python test_worker_integration.py
```
Tests:
- CallbackTask success/failure
- Job status updates
- Persona status updates

## Production Deployment

### Docker
```dockerfile
# Install dependencies
RUN pip install -r requirements-workers.txt

# Start worker
CMD celery -A workers.celery_app worker \
    --loglevel=info \
    --concurrency=2 \
    --max-tasks-per-child=10
```

### Supervisor
```ini
[program:celery_worker]
command=/path/to/venv/bin/celery -A workers.celery_app worker --loglevel=info
directory=/path/to/project
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=600
```

### Scaling
```bash
# Multiple workers
celery -A workers.celery_app worker --concurrency=4

# Multiple worker instances
celery multi start w1 w2 w3 -A workers.celery_app -l info
```

## Dependencies

Defined in `requirements-workers.txt`:
```
celery[redis]>=5.3.0
redis>=5.0.0
python-multipart>=0.0.6
pydantic>=2.0.0
pydantic-settings>=2.0.0
python-dotenv>=1.0.0
```

## Integration Points

### With Database Models
- `Persona` - status updates (draft → ingesting → active)
- `IngestionJob` - full lifecycle tracking
- Uses `get_session()` context manager

### With Ingestion Pipeline
- Calls `ingest.run_ingestion.ingest_works()`
- Calls `ingest.run_ingestion.ingest_quotes()`
- Calls `ingest.run_ingestion.ingest_profile()`
- All functions return `int` (vector count)

### With FastAPI
- Triggered by POST `/api/personas/{id}/ingest`
- Status checked via GET `/api/jobs/{id}`
- Results displayed in admin UI

## Troubleshooting

### Worker won't start
```bash
# Check Redis
redis-cli ping  # Should return PONG

# Check imports
python -c "from workers import celery_app"
```

### Tasks not executing
```bash
# Check Redis queues
redis-cli
> KEYS celery*
> LLEN celery

# Check worker logs
celery -A workers.celery_app worker --loglevel=debug
```

### Database locked (SQLite)
- SQLite has limited concurrency
- Consider PostgreSQL for production
- Or use connection pooling

## Further Reading

- [Celery Documentation](https://docs.celeryproject.org/)
- [Redis Documentation](https://redis.io/docs/)
- Parent project: `PHASE3_IMPLEMENTATION.md`
- Quick start: `WORKERS_QUICK_START.md`
