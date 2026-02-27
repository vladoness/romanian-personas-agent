"""File upload endpoints for persona data sources."""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pathlib import Path
from datetime import datetime
import uuid
import shutil
import logging

from api.dependencies import verify_admin, get_db_session
from models.database import Persona, DataSource
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# File extension validation
WORKS_EXTENSIONS = {'.txt', '.md'}
QUOTES_EXTENSIONS = {'.jsonl'}
PROFILE_EXTENSIONS = {'.txt', '.md', '.pdf'}


def validate_file_extension(filename: str, allowed_extensions: set) -> bool:
    """Check if file has an allowed extension."""
    ext = Path(filename).suffix.lower()
    return ext in allowed_extensions


async def save_uploaded_file(
    file: UploadFile,
    destination: Path
) -> dict:
    """
    Save uploaded file to destination path.

    Returns file metadata.
    """
    try:
        with destination.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        file_size = destination.stat().st_size

        return {
            "name": file.filename,
            "path": str(destination),
            "size_bytes": file_size,
            "success": True
        }
    except Exception as e:
        logger.error(f"Failed to save file {file.filename}: {e}")
        return {
            "name": file.filename,
            "error": str(e),
            "success": False
        }


@router.post("/{persona_id}/upload/works")
async def upload_works(
    persona_id: str,
    files: List[UploadFile] = File(...),
    admin: str = Depends(verify_admin),
    db: Session = Depends(get_db_session)
):
    """
    Upload literary works for a persona (.txt, .md files).

    Files are saved to data/{persona_id}/works/
    """
    # Verify persona exists
    persona = db.query(Persona).filter(Persona.persona_id == persona_id).first()
    if not persona:
        raise HTTPException(
            status_code=404,
            detail=f"Persona '{persona_id}' not found"
        )

    works_dir = Path(settings.data_dir) / persona_id / "works"
    works_dir.mkdir(parents=True, exist_ok=True)

    uploaded = []
    skipped = []

    for file in files:
        # Validate extension
        if not validate_file_extension(file.filename, WORKS_EXTENSIONS):
            skipped.append({
                "name": file.filename,
                "reason": f"Invalid extension. Allowed: {', '.join(WORKS_EXTENSIONS)}"
            })
            continue

        # Save file
        file_path = works_dir / file.filename
        result = await save_uploaded_file(file, file_path)

        if result["success"]:
            # Track in database
            source = DataSource(
                id=str(uuid.uuid4()),
                persona_id=persona.id,
                collection_type="works",
                file_name=file.filename,
                file_path=str(file_path),
                file_size_bytes=result["size_bytes"],
                created_at=datetime.utcnow().isoformat()
            )
            db.add(source)
            uploaded.append({
                "name": file.filename,
                "size_bytes": result["size_bytes"]
            })
            logger.info(f"Uploaded works file for {persona_id}: {file.filename}")
        else:
            skipped.append({
                "name": file.filename,
                "reason": result["error"]
            })

    db.commit()

    return {
        "persona_id": persona_id,
        "collection_type": "works",
        "uploaded": uploaded,
        "skipped": skipped,
        "uploaded_count": len(uploaded),
        "skipped_count": len(skipped)
    }


@router.post("/{persona_id}/upload/quotes")
async def upload_quotes(
    persona_id: str,
    files: List[UploadFile] = File(...),
    admin: str = Depends(verify_admin),
    db: Session = Depends(get_db_session)
):
    """
    Upload quotes for a persona (.jsonl files).

    JSONL format:
    {"quote": "Text of quote", "source": "Optional source"}
    {"quote": "Another quote", "source": "Source info"}

    Files are saved to data/{persona_id}/quotes/
    """
    # Verify persona exists
    persona = db.query(Persona).filter(Persona.persona_id == persona_id).first()
    if not persona:
        raise HTTPException(
            status_code=404,
            detail=f"Persona '{persona_id}' not found"
        )

    quotes_dir = Path(settings.data_dir) / persona_id / "quotes"
    quotes_dir.mkdir(parents=True, exist_ok=True)

    uploaded = []
    skipped = []

    for file in files:
        # Validate extension
        if not validate_file_extension(file.filename, QUOTES_EXTENSIONS):
            skipped.append({
                "name": file.filename,
                "reason": f"Invalid extension. Allowed: {', '.join(QUOTES_EXTENSIONS)}"
            })
            continue

        # Save file
        file_path = quotes_dir / file.filename
        result = await save_uploaded_file(file, file_path)

        if result["success"]:
            # Track in database
            source = DataSource(
                id=str(uuid.uuid4()),
                persona_id=persona.id,
                collection_type="quotes",
                file_name=file.filename,
                file_path=str(file_path),
                file_size_bytes=result["size_bytes"],
                created_at=datetime.utcnow().isoformat()
            )
            db.add(source)
            uploaded.append({
                "name": file.filename,
                "size_bytes": result["size_bytes"]
            })
            logger.info(f"Uploaded quotes file for {persona_id}: {file.filename}")
        else:
            skipped.append({
                "name": file.filename,
                "reason": result["error"]
            })

    db.commit()

    return {
        "persona_id": persona_id,
        "collection_type": "quotes",
        "uploaded": uploaded,
        "skipped": skipped,
        "uploaded_count": len(uploaded),
        "skipped_count": len(skipped)
    }


@router.post("/{persona_id}/upload/profile")
async def upload_profile(
    persona_id: str,
    files: List[UploadFile] = File(...),
    admin: str = Depends(verify_admin),
    db: Session = Depends(get_db_session)
):
    """
    Upload profile documents for a persona (.txt, .md, .pdf files).

    Profile documents should be biographical/scholarly summaries.

    Files are saved to data/{persona_id}/profile/
    """
    # Verify persona exists
    persona = db.query(Persona).filter(Persona.persona_id == persona_id).first()
    if not persona:
        raise HTTPException(
            status_code=404,
            detail=f"Persona '{persona_id}' not found"
        )

    profile_dir = Path(settings.data_dir) / persona_id / "profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    uploaded = []
    skipped = []

    for file in files:
        # Validate extension
        if not validate_file_extension(file.filename, PROFILE_EXTENSIONS):
            skipped.append({
                "name": file.filename,
                "reason": f"Invalid extension. Allowed: {', '.join(PROFILE_EXTENSIONS)}"
            })
            continue

        # Save file
        file_path = profile_dir / file.filename
        result = await save_uploaded_file(file, file_path)

        if result["success"]:
            # Track in database
            source = DataSource(
                id=str(uuid.uuid4()),
                persona_id=persona.id,
                collection_type="profile",
                file_name=file.filename,
                file_path=str(file_path),
                file_size_bytes=result["size_bytes"],
                created_at=datetime.utcnow().isoformat()
            )
            db.add(source)
            uploaded.append({
                "name": file.filename,
                "size_bytes": result["size_bytes"]
            })
            logger.info(f"Uploaded profile file for {persona_id}: {file.filename}")
        else:
            skipped.append({
                "name": file.filename,
                "reason": result["error"]
            })

    db.commit()

    return {
        "persona_id": persona_id,
        "collection_type": "profile",
        "uploaded": uploaded,
        "skipped": skipped,
        "uploaded_count": len(uploaded),
        "skipped_count": len(skipped)
    }


@router.get("/{persona_id}/files")
def list_uploaded_files(
    persona_id: str,
    collection_type: str = None,
    db: Session = Depends(get_db_session)
):
    """
    List uploaded files for a persona.

    Query params:
    - collection_type: Filter by type (works, quotes, profile)
    """
    # Verify persona exists
    persona = db.query(Persona).filter(Persona.persona_id == persona_id).first()
    if not persona:
        raise HTTPException(
            status_code=404,
            detail=f"Persona '{persona_id}' not found"
        )

    query = db.query(DataSource).filter(DataSource.persona_id == persona.id)

    if collection_type:
        if collection_type not in ["works", "quotes", "profile"]:
            raise HTTPException(
                status_code=400,
                detail="collection_type must be 'works', 'quotes', or 'profile'"
            )
        query = query.filter(DataSource.collection_type == collection_type)

    sources = query.all()

    return {
        "persona_id": persona_id,
        "files": [
            {
                "id": s.id,
                "collection_type": s.collection_type,
                "file_name": s.file_name,
                "file_size_bytes": s.file_size_bytes,
                "created_at": s.created_at
            }
            for s in sources
        ],
        "count": len(sources)
    }
