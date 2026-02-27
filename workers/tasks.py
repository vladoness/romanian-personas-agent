"""Background tasks for persona ingestion into ChromaDB."""

import logging
from datetime import datetime
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from workers.celery_app import celery_app
from models.database import get_session, IngestionJob, Persona
from ingest.run_ingestion import ingest_works, ingest_quotes, ingest_profile

logger = logging.getLogger(__name__)


class CallbackTask(Task):
    """
    Base task class with automatic status updates on success/failure.

    All ingestion tasks inherit from this to ensure job status is properly
    updated in the database regardless of outcome.
    """

    def on_success(self, retval, task_id, args, kwargs):
        """Called when task completes successfully."""
        job_id = kwargs.get("job_id")
        if not job_id:
            logger.warning(f"Task {task_id} succeeded but no job_id provided")
            return

        try:
            with get_session() as session:
                job = session.query(IngestionJob).filter_by(id=job_id).first()
                if job:
                    job.status = "completed"
                    job.progress = 100
                    job.completed_at = datetime.utcnow().isoformat()
                    session.commit()
                    logger.info(f"Job {job_id} marked as completed (vectors: {job.total_vectors})")
        except Exception as e:
            logger.error(f"Failed to update job {job_id} on success: {e}")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails."""
        job_id = kwargs.get("job_id")
        if not job_id:
            logger.warning(f"Task {task_id} failed but no job_id provided")
            return

        try:
            with get_session() as session:
                job = session.query(IngestionJob).filter_by(id=job_id).first()
                if job:
                    job.status = "failed"
                    job.error_message = str(exc)
                    job.completed_at = datetime.utcnow().isoformat()
                    session.commit()
                    logger.error(f"Job {job_id} marked as failed: {exc}")
        except Exception as e:
            logger.error(f"Failed to update job {job_id} on failure: {e}")


@celery_app.task(base=CallbackTask, bind=True, name="workers.tasks.ingest_persona_works")
def ingest_persona_works(self, persona_id: str, job_id: str):
    """
    Background task to ingest persona works collection into ChromaDB.

    Args:
        persona_id: Persona identifier (e.g., 'eminescu')
        job_id: IngestionJob ID for status tracking

    Returns:
        dict: Task result with vector count
    """
    logger.info(f"Starting works ingestion for persona={persona_id}, job={job_id}")

    try:
        # Update job status to processing
        with get_session() as session:
            job = session.query(IngestionJob).filter_by(id=job_id).first()
            if not job:
                raise ValueError(f"IngestionJob {job_id} not found")

            job.status = "processing"
            job.started_at = datetime.utcnow().isoformat()
            session.commit()

        # Run ingestion (this may take several minutes)
        logger.info(f"Calling ingest_works for {persona_id}")
        vector_count = ingest_works(persona_id)

        # Update vector count in job
        with get_session() as session:
            job = session.query(IngestionJob).filter_by(id=job_id).first()
            if job:
                job.total_vectors = vector_count if vector_count else 0
                job.progress = 90  # Almost done, CallbackTask will set to 100
                session.commit()

        logger.info(f"Works ingestion completed for {persona_id}: {vector_count} vectors")
        return {"persona_id": persona_id, "collection_type": "works", "vectors": vector_count}

    except SoftTimeLimitExceeded:
        logger.error(f"Works ingestion timed out for {persona_id}")
        raise
    except Exception as e:
        logger.error(f"Works ingestion failed for {persona_id}: {e}", exc_info=True)
        raise


@celery_app.task(base=CallbackTask, bind=True, name="workers.tasks.ingest_persona_quotes")
def ingest_persona_quotes(self, persona_id: str, job_id: str):
    """
    Background task to ingest persona quotes collection into ChromaDB.

    Args:
        persona_id: Persona identifier (e.g., 'eminescu')
        job_id: IngestionJob ID for status tracking

    Returns:
        dict: Task result with vector count
    """
    logger.info(f"Starting quotes ingestion for persona={persona_id}, job={job_id}")

    try:
        # Update job status to processing
        with get_session() as session:
            job = session.query(IngestionJob).filter_by(id=job_id).first()
            if not job:
                raise ValueError(f"IngestionJob {job_id} not found")

            job.status = "processing"
            job.started_at = datetime.utcnow().isoformat()
            session.commit()

        # Run ingestion
        logger.info(f"Calling ingest_quotes for {persona_id}")
        vector_count = ingest_quotes(persona_id)

        # Update vector count in job
        with get_session() as session:
            job = session.query(IngestionJob).filter_by(id=job_id).first()
            if job:
                job.total_vectors = vector_count if vector_count else 0
                job.progress = 90
                session.commit()

        logger.info(f"Quotes ingestion completed for {persona_id}: {vector_count} vectors")
        return {"persona_id": persona_id, "collection_type": "quotes", "vectors": vector_count}

    except SoftTimeLimitExceeded:
        logger.error(f"Quotes ingestion timed out for {persona_id}")
        raise
    except Exception as e:
        logger.error(f"Quotes ingestion failed for {persona_id}: {e}", exc_info=True)
        raise


@celery_app.task(base=CallbackTask, bind=True, name="workers.tasks.ingest_persona_profile")
def ingest_persona_profile(self, persona_id: str, job_id: str):
    """
    Background task to ingest persona profile collection into ChromaDB.

    Args:
        persona_id: Persona identifier (e.g., 'eminescu')
        job_id: IngestionJob ID for status tracking

    Returns:
        dict: Task result with vector count
    """
    logger.info(f"Starting profile ingestion for persona={persona_id}, job={job_id}")

    try:
        # Update job status to processing
        with get_session() as session:
            job = session.query(IngestionJob).filter_by(id=job_id).first()
            if not job:
                raise ValueError(f"IngestionJob {job_id} not found")

            job.status = "processing"
            job.started_at = datetime.utcnow().isoformat()
            session.commit()

        # Run ingestion (profile is usually fastest)
        logger.info(f"Calling ingest_profile for {persona_id}")
        vector_count = ingest_profile(persona_id)

        # Update vector count in job
        with get_session() as session:
            job = session.query(IngestionJob).filter_by(id=job_id).first()
            if job:
                job.total_vectors = vector_count if vector_count else 0
                job.progress = 90
                session.commit()

        logger.info(f"Profile ingestion completed for {persona_id}: {vector_count} vectors")
        return {"persona_id": persona_id, "collection_type": "profile", "vectors": vector_count}

    except SoftTimeLimitExceeded:
        logger.error(f"Profile ingestion timed out for {persona_id}")
        raise
    except Exception as e:
        logger.error(f"Profile ingestion failed for {persona_id}: {e}", exc_info=True)
        raise


@celery_app.task(name="workers.tasks.ingest_full_persona")
def ingest_full_persona(persona_id: str, job_ids: dict):
    """
    Orchestrator task to trigger all three ingestion tasks for a persona.

    This task coordinates the ingestion of works, quotes, and profile collections.
    Profile runs first (fastest), then works and quotes run in parallel.

    Args:
        persona_id: Persona identifier (e.g., 'eminescu')
        job_ids: Dict with keys 'works', 'quotes', 'profile' mapping to job IDs

    Returns:
        dict: Summary of triggered tasks
    """
    logger.info(f"Starting full ingestion orchestration for {persona_id}")
    logger.info(f"Job IDs: {job_ids}")

    try:
        # Update persona status to 'ingesting'
        with get_session() as session:
            persona = session.query(Persona).filter_by(persona_id=persona_id).first()
            if persona:
                persona.status = "ingesting"
                persona.updated_at = datetime.utcnow().isoformat()
                session.commit()
                logger.info(f"Persona {persona_id} status set to 'ingesting'")

        # Trigger profile first (fastest, provides biographical context)
        profile_task = ingest_persona_profile.apply_async(
            kwargs={"persona_id": persona_id, "job_id": job_ids["profile"]},
            task_id=f"profile_{job_ids['profile']}"
        )
        logger.info(f"Triggered profile ingestion: {profile_task.id}")

        # Trigger works and quotes in parallel (these take longer)
        works_task = ingest_persona_works.apply_async(
            kwargs={"persona_id": persona_id, "job_id": job_ids["works"]},
            task_id=f"works_{job_ids['works']}"
        )
        logger.info(f"Triggered works ingestion: {works_task.id}")

        quotes_task = ingest_persona_quotes.apply_async(
            kwargs={"persona_id": persona_id, "job_id": job_ids["quotes"]},
            task_id=f"quotes_{job_ids['quotes']}"
        )
        logger.info(f"Triggered quotes ingestion: {quotes_task.id}")

        return {
            "persona_id": persona_id,
            "tasks": {
                "profile": profile_task.id,
                "works": works_task.id,
                "quotes": quotes_task.id,
            },
            "message": "All ingestion tasks triggered successfully"
        }

    except Exception as e:
        logger.error(f"Failed to orchestrate ingestion for {persona_id}: {e}", exc_info=True)

        # Mark persona as failed
        try:
            with get_session() as session:
                persona = session.query(Persona).filter_by(persona_id=persona_id).first()
                if persona:
                    persona.status = "failed"
                    persona.updated_at = datetime.utcnow().isoformat()
                    session.commit()
        except Exception as db_error:
            logger.error(f"Failed to update persona status: {db_error}")

        raise
