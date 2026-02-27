"""Ingestion control endpoints - trigger and monitor ChromaDB ingestion."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
import logging

from api.dependencies import verify_admin, get_db_session
from models.database import Persona, IngestionJob

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/{persona_id}/ingest")
def trigger_ingestion(
    persona_id: str,
    admin: str = Depends(verify_admin),
    db: Session = Depends(get_db_session)
):
    """
    Trigger background ingestion for a persona (admin only).

    Creates ingestion job records and triggers Celery tasks.

    The ingestion process:
    1. Profile collection (fastest, makes persona usable sooner)
    2. Works collection (primary writings)
    3. Quotes collection (representative quotes)

    Returns job IDs for status monitoring.
    """
    # Verify persona exists
    persona = db.query(Persona).filter(Persona.persona_id == persona_id).first()
    if not persona:
        raise HTTPException(
            status_code=404,
            detail=f"Persona '{persona_id}' not found"
        )

    # Check if ingestion already in progress
    active_jobs = db.query(IngestionJob).filter(
        IngestionJob.persona_id == persona.id,
        IngestionJob.status.in_(["pending", "processing"])
    ).all()

    if active_jobs:
        raise HTTPException(
            status_code=409,
            detail=f"Ingestion already in progress. {len(active_jobs)} active jobs found."
        )

    # Create job records for each collection type
    jobs = []
    for col_type in ["profile", "works", "quotes"]:
        job = IngestionJob(
            id=str(uuid.uuid4()),
            persona_id=persona.id,
            collection_type=col_type,
            status="pending",
            progress=0,
            started_at=None,
            completed_at=None
        )
        db.add(job)
        jobs.append(job)

    db.commit()

    # Update persona status
    persona.status = "ingesting"
    persona.updated_at = datetime.utcnow().isoformat()
    db.commit()

    # Trigger Celery tasks (Phase 3 will implement workers)
    try:
        from workers.tasks import ingest_full_persona
        job_ids = [j.id for j in jobs]
        ingest_full_persona.delay(persona_id, job_ids)
        logger.info(f"Triggered ingestion for {persona_id} with jobs: {job_ids}")
    except ImportError:
        logger.warning("Celery workers not available. Jobs created but not triggered.")
        # For Phase 2, we just create the jobs. Phase 3 will implement workers.

    return {
        "status": "triggered",
        "persona_id": persona_id,
        "jobs": [
            {
                "id": j.id,
                "collection_type": j.collection_type,
                "status": j.status
            }
            for j in jobs
        ],
        "message": f"Ingestion triggered for '{persona.display_name}'. Monitor progress with GET /{persona_id}/ingestion/status"
    }


@router.get("/{persona_id}/ingestion/status")
def get_ingestion_status(
    persona_id: str,
    db: Session = Depends(get_db_session)
):
    """
    Get ingestion job status for a persona.

    Returns overall status and individual job progress.
    No authentication required (read-only).
    """
    # Verify persona exists
    persona = db.query(Persona).filter(Persona.persona_id == persona_id).first()
    if not persona:
        raise HTTPException(
            status_code=404,
            detail=f"Persona '{persona_id}' not found"
        )

    # Get all ingestion jobs (sorted by most recent first)
    jobs = db.query(IngestionJob).filter(
        IngestionJob.persona_id == persona.id
    ).order_by(IngestionJob.started_at.desc()).all()

    # Calculate overall progress
    if not jobs:
        overall_progress = 0
    else:
        # Only consider latest run (3 jobs per run)
        latest_jobs = jobs[:3] if len(jobs) >= 3 else jobs
        total_progress = sum(j.progress or 0 for j in latest_jobs)
        overall_progress = total_progress // len(latest_jobs) if latest_jobs else 0

    # Check if all jobs completed
    all_completed = all(j.status == "completed" for j in jobs[:3]) if len(jobs) >= 3 else False
    any_failed = any(j.status == "failed" for j in jobs[:3]) if len(jobs) >= 3 else False

    return {
        "persona_id": persona_id,
        "display_name": persona.display_name,
        "overall_status": persona.status,
        "overall_progress": overall_progress,
        "all_completed": all_completed,
        "any_failed": any_failed,
        "jobs": [
            {
                "id": j.id,
                "collection_type": j.collection_type,
                "status": j.status,
                "progress": j.progress,
                "total_vectors": j.total_vectors,
                "error_message": j.error_message,
                "started_at": j.started_at,
                "completed_at": j.completed_at
            }
            for j in jobs
        ],
        "total_jobs": len(jobs)
    }


@router.post("/{persona_id}/ingestion/retry")
def retry_failed_ingestion(
    persona_id: str,
    admin: str = Depends(verify_admin),
    db: Session = Depends(get_db_session)
):
    """
    Retry failed ingestion jobs (admin only).

    Resets failed jobs to pending and triggers ingestion again.
    """
    # Verify persona exists
    persona = db.query(Persona).filter(Persona.persona_id == persona_id).first()
    if not persona:
        raise HTTPException(
            status_code=404,
            detail=f"Persona '{persona_id}' not found"
        )

    # Find failed jobs
    failed_jobs = db.query(IngestionJob).filter(
        IngestionJob.persona_id == persona.id,
        IngestionJob.status == "failed"
    ).all()

    if not failed_jobs:
        raise HTTPException(
            status_code=400,
            detail="No failed jobs found to retry"
        )

    # Reset jobs to pending
    for job in failed_jobs:
        job.status = "pending"
        job.progress = 0
        job.error_message = None
        job.started_at = None
        job.completed_at = None

    db.commit()

    # Update persona status
    persona.status = "ingesting"
    persona.updated_at = datetime.utcnow().isoformat()
    db.commit()

    # Trigger Celery tasks
    try:
        from workers.tasks import ingest_full_persona
        job_ids = [j.id for j in failed_jobs]
        ingest_full_persona.delay(persona_id, job_ids)
        logger.info(f"Retrying ingestion for {persona_id} with jobs: {job_ids}")
    except ImportError:
        logger.warning("Celery workers not available. Jobs reset but not triggered.")

    return {
        "status": "retrying",
        "persona_id": persona_id,
        "retried_jobs": [
            {
                "id": j.id,
                "collection_type": j.collection_type
            }
            for j in failed_jobs
        ],
        "message": f"Retrying {len(failed_jobs)} failed jobs"
    }


@router.delete("/{persona_id}/ingestion/jobs")
def clear_ingestion_history(
    persona_id: str,
    admin: str = Depends(verify_admin),
    db: Session = Depends(get_db_session)
):
    """
    Clear ingestion job history for a persona (admin only).

    Only deletes completed or failed jobs, not active ones.
    """
    # Verify persona exists
    persona = db.query(Persona).filter(Persona.persona_id == persona_id).first()
    if not persona:
        raise HTTPException(
            status_code=404,
            detail=f"Persona '{persona_id}' not found"
        )

    # Delete completed/failed jobs
    deleted_count = db.query(IngestionJob).filter(
        IngestionJob.persona_id == persona.id,
        IngestionJob.status.in_(["completed", "failed"])
    ).delete(synchronize_session=False)

    db.commit()

    logger.info(f"Cleared {deleted_count} ingestion jobs for {persona_id}")

    return {
        "status": "cleared",
        "persona_id": persona_id,
        "deleted_jobs": deleted_count
    }
