"""Persona registry — supports both static (legacy) and database personas."""

import logging
from personas._base import PersonaConfig

logger = logging.getLogger(__name__)

# Static legacy personas
_static_registry: dict[str, PersonaConfig] | None = None

# Database personas cache
_db_registry: dict[str, PersonaConfig] = {}
_db_registry_loaded: bool = False


def _load_static_registry() -> dict[str, PersonaConfig]:
    """Load 5 hardcoded personas."""
    from personas.eminescu import persona_config as eminescu
    from personas.bratianu import persona_config as bratianu
    from personas.caragiale import persona_config as caragiale
    from personas.eliade import persona_config as eliade
    from personas.cioran import persona_config as cioran

    return {
        "eminescu": eminescu,
        "bratianu": bratianu,
        "caragiale": caragiale,
        "eliade": eliade,
        "cioran": cioran,
    }


def _load_db_registry() -> dict[str, PersonaConfig]:
    """Load active personas from database."""
    try:
        from models.database import DATABASE_PATH
        import json
        import sqlite3

        # Check if database exists and has tables
        if not DATABASE_PATH.exists():
            return {}

        # Check if personas table exists before attempting to query
        conn = sqlite3.connect(str(DATABASE_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='personas'")
        table_exists = cursor.fetchone() is not None
        conn.close()

        if not table_exists:
            logger.debug("Database exists but personas table not yet created")
            return {}

        from models.database import get_session, Persona as DBPersona

        with get_session() as session:
            db_personas = session.query(DBPersona).filter_by(status='active').all()

            registry = {}
            for db_persona in db_personas:
                config = PersonaConfig(
                    persona_id=db_persona.persona_id,
                    display_name=db_persona.display_name,
                    birth_year=db_persona.birth_year,
                    death_year=db_persona.death_year,
                    description=db_persona.description,
                    speaking_style=db_persona.speaking_style,
                    key_themes=db_persona.key_themes,
                    voice_prompt=db_persona.voice_prompt,
                    representative_quotes=json.loads(db_persona.representative_quotes or '[]'),
                    works_top_k=db_persona.works_top_k,
                    quotes_top_k=db_persona.quotes_top_k,
                    profile_top_k=db_persona.profile_top_k,
                    works_chunk_size=db_persona.works_chunk_size,
                    works_chunk_overlap=db_persona.works_chunk_overlap,
                )
                registry[db_persona.persona_id] = config

            if len(registry) > 0:
                logger.info(f"Loaded {len(registry)} database personas")
            return registry
    except ImportError as e:
        logger.debug(f"Database models not available: {e}")
        return {}
    except Exception as e:
        logger.debug(f"Failed to load database personas: {type(e).__name__}: {e}")
        return {}


def get_registry(force_reload: bool = False) -> dict[str, PersonaConfig]:
    """Get merged registry (static + database)."""
    global _static_registry, _db_registry, _db_registry_loaded

    if _static_registry is None:
        _static_registry = _load_static_registry()
        logger.info(f"Loaded {len(_static_registry)} static personas")

    if not _db_registry_loaded or force_reload:
        _db_registry = _load_db_registry()
        _db_registry_loaded = True

    # Merge: database overrides static if same ID
    return {**_static_registry, **_db_registry}


def reload_registry():
    """Force reload database personas (call after creation/ingestion)."""
    logger.info("Reloading persona registry from database")
    get_registry(force_reload=True)


# Keep VALID_PERSONA_IDS for backward compatibility (will be deprecated)
VALID_PERSONA_IDS = ["eminescu", "bratianu", "caragiale", "eliade", "cioran"]


def get_persona(persona_id: str) -> PersonaConfig:
    """Get persona by ID, raise ValueError if not found."""
    registry = get_registry()
    if persona_id not in registry:
        available = ", ".join(sorted(registry.keys()))
        raise ValueError(
            f"Personalitate necunoscuta: '{persona_id}'. "
            f"Personalitati disponibile: {available}"
        )
    return registry[persona_id]
