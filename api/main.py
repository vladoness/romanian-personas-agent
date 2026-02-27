"""FastAPI main application for Persona Marketplace."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from models.database import init_db
import logging

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Persona Marketplace API",
    description="REST API for creating and managing Romanian historical personas",
    version="1.0.0"
)

# Configure CORS for debate UI (port 3000) and admin UI (port 3001)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Debate UI
        "http://localhost:3001",  # Admin UI
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized successfully")


@app.get("/health")
def health_check():
    """
    Health check endpoint (unauthenticated).

    Returns server status.
    """
    return {
        "status": "healthy",
        "service": "persona-marketplace-api"
    }


# Include routers
from api.routes import personas, uploads, ingestion

app.include_router(
    personas.router,
    prefix="/api/personas",
    tags=["personas"]
)

app.include_router(
    uploads.router,
    prefix="/api/personas",
    tags=["uploads"]
)

app.include_router(
    ingestion.router,
    prefix="/api/personas",
    tags=["ingestion"]
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
