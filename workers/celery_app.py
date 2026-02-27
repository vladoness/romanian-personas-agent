"""Celery application configuration for persona marketplace workers."""

from celery import Celery
from config import settings

# Create Celery app
celery_app = Celery(
    "persona_marketplace",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=7200,  # 2 hours hard limit
    task_soft_time_limit=6900,  # 1h 55m soft limit (warning)
    worker_prefetch_multiplier=1,  # Process one task at a time
    worker_max_tasks_per_child=10,  # Restart worker after 10 tasks (prevent memory leaks)
)

# Auto-discover tasks from workers.tasks module
celery_app.autodiscover_tasks(["workers"])

if __name__ == "__main__":
    celery_app.start()
