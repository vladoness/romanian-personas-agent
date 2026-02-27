"""SQLAlchemy models for persona marketplace."""
from sqlalchemy import Column, String, Integer, Text, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Session
from contextlib import contextmanager
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()

# Database path
DATABASE_PATH = Path(__file__).parent.parent / "personas.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"


class Persona(Base):
    """Persona model - stores persona configuration and metadata."""

    __tablename__ = "personas"

    id = Column(String, primary_key=True)
    persona_id = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String, nullable=False)
    birth_year = Column(Integer, nullable=False)
    death_year = Column(Integer)
    description = Column(Text, nullable=False)
    speaking_style = Column(Text, nullable=False)
    key_themes = Column(Text, nullable=False)
    voice_prompt = Column(Text, nullable=False)
    representative_quotes = Column(Text)  # JSON array
    color = Column(String, default="#666666")

    # Retrieval overrides (nullable = use defaults)
    works_top_k = Column(Integer)
    quotes_top_k = Column(Integer)
    profile_top_k = Column(Integer)
    works_chunk_size = Column(Integer)
    works_chunk_overlap = Column(Integer)

    status = Column(String, default="draft")  # draft, ingesting, active, failed
    created_at = Column(Text)  # ISO format datetime
    updated_at = Column(Text)  # ISO format datetime

    # Relationships
    ingestion_jobs = relationship("IngestionJob", back_populates="persona", cascade="all, delete-orphan")
    data_sources = relationship("DataSource", back_populates="persona", cascade="all, delete-orphan")

    def get_quotes_list(self):
        """Parse representative_quotes JSON into Python list."""
        if not self.representative_quotes:
            return []
        try:
            return json.loads(self.representative_quotes)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to parse quotes for {self.persona_id}: {e}")
            return []

    def __repr__(self):
        return f"<Persona(id={self.id}, persona_id={self.persona_id}, status={self.status})>"


class IngestionJob(Base):
    """Ingestion job tracking - monitors ChromaDB ingestion progress."""

    __tablename__ = "ingestion_jobs"

    id = Column(String, primary_key=True)
    persona_id = Column(String, ForeignKey("personas.id"), nullable=False, index=True)
    collection_type = Column(String, nullable=False)  # works, quotes, profile
    status = Column(String, default="pending")  # pending, processing, completed, failed
    progress = Column(Integer, default=0)  # 0-100
    total_vectors = Column(Integer)
    error_message = Column(Text)
    started_at = Column(Text)  # ISO format datetime
    completed_at = Column(Text)  # ISO format datetime

    # Relationships
    persona = relationship("Persona", back_populates="ingestion_jobs")

    def __repr__(self):
        return f"<IngestionJob(id={self.id}, persona_id={self.persona_id}, type={self.collection_type}, status={self.status})>"


class DataSource(Base):
    """Data source tracking - uploaded files for persona ingestion."""

    __tablename__ = "data_sources"

    id = Column(String, primary_key=True)
    persona_id = Column(String, ForeignKey("personas.id"), nullable=False, index=True)
    collection_type = Column(String, nullable=False)  # works, quotes, profile
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size_bytes = Column(Integer)
    created_at = Column(Text)  # ISO format datetime

    # Relationships
    persona = relationship("Persona", back_populates="data_sources")

    def __repr__(self):
        return f"<DataSource(id={self.id}, file_name={self.file_name}, type={self.collection_type})>"


# Database session management
_engine = None
_SessionLocal = None


def _get_engine():
    """Get or create SQLAlchemy engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False},  # SQLite-specific
            echo=False  # Set to True for SQL debugging
        )
        logger.info(f"Created database engine: {DATABASE_URL}")
    return _engine


def _get_session_factory():
    """Get or create session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        engine = _get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        logger.info("Created session factory")
    return _SessionLocal


@contextmanager
def get_session() -> Session:
    """
    Context manager for database sessions.

    Usage:
        with get_session() as session:
            persona = session.query(Persona).filter_by(persona_id='eminescu').first()
    """
    SessionLocal = _get_session_factory()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        session.close()


def init_db():
    """
    Initialize database - create all tables.

    This should be called once at application startup or during initial setup.
    Safe to call multiple times (won't recreate existing tables).
    """
    engine = _get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info(f"Database initialized at {DATABASE_PATH}")

    # Verify tables were created
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    logger.info(f"Database tables: {tables}")

    return tables


def get_db_info():
    """Get database information for debugging."""
    from sqlalchemy import inspect

    engine = _get_engine()
    inspector = inspect(engine)

    info = {
        "database_path": str(DATABASE_PATH),
        "database_exists": DATABASE_PATH.exists(),
        "tables": []
    }

    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        info["tables"].append({
            "name": table_name,
            "columns": [{"name": c["name"], "type": str(c["type"])} for c in columns]
        })

    return info
