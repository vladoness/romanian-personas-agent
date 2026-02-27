"""Persona CRUD endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from pathlib import Path
import uuid
import json
import logging

from api.dependencies import verify_admin, get_db_session
from models.database import Persona

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Schemas
class PersonaCreate(BaseModel):
    """Request schema for creating a new persona."""
    persona_id: str = Field(..., description="Unique slug identifier (e.g., 'eminescu')")
    display_name: str = Field(..., description="Display name (e.g., 'Mihai Eminescu')")
    birth_year: int = Field(..., description="Birth year")
    death_year: Optional[int] = Field(None, description="Death year (optional for living personas)")
    description: str = Field(..., description="Short biographical description")
    speaking_style: str = Field(..., description="Persona's speaking style characteristics")
    key_themes: str = Field(..., description="Key intellectual themes")
    voice_prompt: str = Field(..., description="System prompt for Claude synthesis")
    representative_quotes: List[str] = Field(default_factory=list, description="Representative quotes")
    color: str = Field(default="#666666", description="Hex color for UI display")

    # Optional retrieval overrides
    works_top_k: Optional[int] = Field(None, description="Override default works retrieval count")
    quotes_top_k: Optional[int] = Field(None, description="Override default quotes retrieval count")
    profile_top_k: Optional[int] = Field(None, description="Override default profile retrieval count")
    works_chunk_size: Optional[int] = Field(None, description="Override default works chunk size")
    works_chunk_overlap: Optional[int] = Field(None, description="Override default works chunk overlap")


class PersonaResponse(BaseModel):
    """Response schema for persona data."""
    id: str
    persona_id: str
    display_name: str
    birth_year: int
    death_year: Optional[int]
    description: str
    color: str
    status: str
    created_at: str
    updated_at: Optional[str]

    class Config:
        from_attributes = True


class PersonaDetail(PersonaResponse):
    """Detailed persona response including voice configuration."""
    speaking_style: str
    key_themes: str
    voice_prompt: str
    representative_quotes: List[str]
    works_top_k: Optional[int]
    quotes_top_k: Optional[int]
    profile_top_k: Optional[int]
    works_chunk_size: Optional[int]
    works_chunk_overlap: Optional[int]

    @classmethod
    def from_db(cls, persona: Persona):
        """Create PersonaDetail from database model."""
        return cls(
            id=persona.id,
            persona_id=persona.persona_id,
            display_name=persona.display_name,
            birth_year=persona.birth_year,
            death_year=persona.death_year,
            description=persona.description,
            speaking_style=persona.speaking_style,
            key_themes=persona.key_themes,
            voice_prompt=persona.voice_prompt,
            representative_quotes=persona.get_quotes_list(),
            color=persona.color,
            status=persona.status,
            created_at=persona.created_at,
            updated_at=persona.updated_at,
            works_top_k=persona.works_top_k,
            quotes_top_k=persona.quotes_top_k,
            profile_top_k=persona.profile_top_k,
            works_chunk_size=persona.works_chunk_size,
            works_chunk_overlap=persona.works_chunk_overlap,
        )


# Endpoints
@router.get("", response_model=dict)
def list_personas(
    status: Optional[str] = None,
    db: Session = Depends(get_db_session)
):
    """
    List all personas (no authentication required for reading).

    Query params:
    - status: Filter by status (draft, ingesting, active, failed). Default: active only
    """
    query = db.query(Persona)

    if status:
        query = query.filter(Persona.status == status)
    else:
        # Default: only show active personas
        query = query.filter(Persona.status == "active")

    personas = query.all()

    return {
        "personas": [PersonaResponse.from_attributes(p) for p in personas],
        "count": len(personas)
    }


@router.get("/{persona_id}", response_model=PersonaDetail)
def get_persona(
    persona_id: str,
    db: Session = Depends(get_db_session)
):
    """
    Get detailed information for a specific persona.

    No authentication required for reading.
    """
    persona = db.query(Persona).filter(Persona.persona_id == persona_id).first()

    if not persona:
        raise HTTPException(
            status_code=404,
            detail=f"Persona '{persona_id}' not found"
        )

    return PersonaDetail.from_db(persona)


@router.post("", response_model=dict)
def create_persona(
    data: PersonaCreate,
    admin: str = Depends(verify_admin),
    db: Session = Depends(get_db_session)
):
    """
    Create a new persona (admin authentication required).

    Returns the created persona's ID.
    """
    # Check uniqueness
    existing = db.query(Persona).filter(Persona.persona_id == data.persona_id).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Persona ID '{data.persona_id}' already exists"
        )

    # Validate persona_id format (alphanumeric + underscores/hyphens)
    if not data.persona_id.replace('-', '').replace('_', '').isalnum():
        raise HTTPException(
            status_code=400,
            detail="Persona ID must contain only letters, numbers, hyphens, and underscores"
        )

    # Create persona record
    now = datetime.utcnow().isoformat()
    persona = Persona(
        id=str(uuid.uuid4()),
        persona_id=data.persona_id,
        display_name=data.display_name,
        birth_year=data.birth_year,
        death_year=data.death_year,
        description=data.description,
        speaking_style=data.speaking_style,
        key_themes=data.key_themes,
        voice_prompt=data.voice_prompt,
        representative_quotes=json.dumps(data.representative_quotes),
        color=data.color,
        works_top_k=data.works_top_k,
        quotes_top_k=data.quotes_top_k,
        profile_top_k=data.profile_top_k,
        works_chunk_size=data.works_chunk_size,
        works_chunk_overlap=data.works_chunk_overlap,
        status="draft",
        created_at=now,
        updated_at=now
    )

    db.add(persona)
    db.commit()

    # Create data directories
    from config import settings
    persona_dir = Path(settings.data_dir) / persona.persona_id
    try:
        (persona_dir / "works").mkdir(parents=True, exist_ok=True)
        (persona_dir / "quotes").mkdir(parents=True, exist_ok=True)
        (persona_dir / "profile").mkdir(parents=True, exist_ok=True)
        logger.info(f"Created data directories for persona: {persona.persona_id}")
    except Exception as e:
        logger.error(f"Failed to create directories for {persona.persona_id}: {e}")
        # Don't fail the request - directories can be created later

    logger.info(f"Created persona: {persona.persona_id} (ID: {persona.id})")

    return {
        "status": "created",
        "id": persona.id,
        "persona_id": persona.persona_id,
        "message": f"Persona '{data.display_name}' created successfully. Upload files next."
    }


@router.delete("/{persona_id}", response_model=dict)
def delete_persona(
    persona_id: str,
    admin: str = Depends(verify_admin),
    db: Session = Depends(get_db_session)
):
    """
    Delete a persona and all associated ChromaDB collections (admin only).

    This will:
    1. Delete ChromaDB collections (works, quotes, profile)
    2. Cascade delete ingestion jobs and data sources
    3. Remove persona record from database

    Note: Uploaded files in data/ are NOT deleted.
    """
    persona = db.query(Persona).filter(Persona.persona_id == persona_id).first()

    if not persona:
        raise HTTPException(
            status_code=404,
            detail=f"Persona '{persona_id}' not found"
        )

    # Delete ChromaDB collections
    from ingest.run_ingestion import _get_chroma_client

    deleted_collections = []
    failed_collections = []

    try:
        client = _get_chroma_client()

        for col_type in ["works", "quotes", "profile"]:
            col_name = f"{persona_id}_{col_type}"
            try:
                client.delete_collection(col_name)
                deleted_collections.append(col_name)
                logger.info(f"Deleted ChromaDB collection: {col_name}")
            except Exception as e:
                # Collection might not exist - not a fatal error
                failed_collections.append(col_name)
                logger.warning(f"Failed to delete collection {col_name}: {e}")

    except Exception as e:
        logger.error(f"Failed to connect to ChromaDB: {e}")
        # Continue with database deletion even if ChromaDB fails

    # Delete persona from database (cascade deletes jobs and sources)
    db.delete(persona)
    db.commit()

    logger.info(f"Deleted persona: {persona_id} (ID: {persona.id})")

    return {
        "status": "deleted",
        "persona_id": persona_id,
        "deleted_collections": deleted_collections,
        "failed_collections": failed_collections,
        "message": f"Persona '{persona.display_name}' deleted successfully"
    }
