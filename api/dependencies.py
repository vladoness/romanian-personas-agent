"""FastAPI dependencies - authentication and database session management."""
from fastapi import Security, HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session
from config import settings
from models.database import get_session
import secrets
import logging

logger = logging.getLogger(__name__)

security = HTTPBasic()


def verify_admin(credentials: HTTPBasicCredentials = Security(security)) -> str:
    """
    Verify admin credentials using HTTP Basic Auth.

    Username: "admin"
    Password: from settings.admin_password

    Uses constant-time comparison to prevent timing attacks.
    """
    if not settings.admin_password:
        raise HTTPException(
            status_code=500,
            detail="Admin password not configured. Set ADMIN_PASSWORD in .env"
        )

    correct_username = secrets.compare_digest(credentials.username, "admin")
    correct_password = secrets.compare_digest(
        credentials.password,
        settings.admin_password
    )

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    logger.info(f"Admin authenticated: {credentials.username}")
    return credentials.username


def get_db_session():
    """
    FastAPI dependency for database session management.

    Yields a SQLAlchemy session and ensures proper cleanup.

    Usage:
        @router.get("/personas")
        def list_personas(db: Session = Depends(get_db_session)):
            personas = db.query(Persona).all()
            return personas
    """
    with get_session() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            raise
