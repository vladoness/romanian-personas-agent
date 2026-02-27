# Models Package - Database Schema

SQLAlchemy models for the Persona Marketplace MVP.

## Database Schema

### Personas Table
Stores persona configuration and metadata.

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR (PK) | UUID primary key |
| persona_id | VARCHAR (UNIQUE) | Slug identifier (e.g., "eminescu") |
| display_name | VARCHAR | Display name |
| birth_year | INTEGER | Birth year |
| death_year | INTEGER (NULL) | Death year |
| description | TEXT | Persona description |
| speaking_style | TEXT | Speaking style guidelines |
| key_themes | TEXT | Key themes |
| voice_prompt | TEXT | System prompt for Claude |
| representative_quotes | TEXT (JSON) | JSON array of quotes |
| color | VARCHAR | UI color (hex code) |
| works_top_k | INTEGER (NULL) | Override for works retrieval |
| quotes_top_k | INTEGER (NULL) | Override for quotes retrieval |
| profile_top_k | INTEGER (NULL) | Override for profile retrieval |
| works_chunk_size | INTEGER (NULL) | Override for works chunking |
| works_chunk_overlap | INTEGER (NULL) | Override for works overlap |
| status | VARCHAR | Status: draft, ingesting, active, failed |
| created_at | TEXT (ISO) | Creation timestamp |
| updated_at | TEXT (ISO) | Last update timestamp |

### Ingestion Jobs Table
Tracks ChromaDB ingestion progress.

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR (PK) | UUID primary key |
| persona_id | VARCHAR (FK) | References personas.id |
| collection_type | VARCHAR | Type: works, quotes, profile |
| status | VARCHAR | Status: pending, processing, completed, failed |
| progress | INTEGER | Progress percentage (0-100) |
| total_vectors | INTEGER (NULL) | Total vectors ingested |
| error_message | TEXT (NULL) | Error message if failed |
| started_at | TEXT (ISO) | Start timestamp |
| completed_at | TEXT (ISO) | Completion timestamp |

### Data Sources Table
Tracks uploaded files.

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR (PK) | UUID primary key |
| persona_id | VARCHAR (FK) | References personas.id |
| collection_type | VARCHAR | Type: works, quotes, profile |
| file_name | VARCHAR | Original filename |
| file_path | VARCHAR | Full file path |
| file_size_bytes | INTEGER (NULL) | File size in bytes |
| created_at | TEXT (ISO) | Upload timestamp |

## Usage Examples

### Initialize Database

```python
from models import init_db

# Create all tables
tables = init_db()
print(f"Created tables: {tables}")
```

### Create a Persona

```python
from models import get_session, Persona
import uuid
import json
from datetime import datetime

with get_session() as session:
    persona = Persona(
        id=str(uuid.uuid4()),
        persona_id="tesla",
        display_name="Nikola Tesla",
        birth_year=1856,
        death_year=1943,
        description="Inventor and electrical engineer",
        speaking_style="Scientific and visionary",
        key_themes="Electricity, innovation, future technology",
        voice_prompt="You are Nikola Tesla. Speak with scientific precision.",
        representative_quotes=json.dumps([
            "The present is theirs; the future is mine.",
            "If you want to find the secrets of the universe, think in terms of energy."
        ]),
        color="#4A90E2",
        status="draft",
        created_at=datetime.utcnow().isoformat()
    )
    session.add(persona)
    session.commit()
    print(f"Created persona: {persona.persona_id}")
```

### Query Personas

```python
from models import get_session, Persona

with get_session() as session:
    # Get all active personas
    personas = session.query(Persona).filter_by(status="active").all()
    for p in personas:
        print(f"{p.persona_id}: {p.display_name}")

    # Get specific persona
    persona = session.query(Persona).filter_by(persona_id="eminescu").first()
    if persona:
        quotes = persona.get_quotes_list()
        print(f"Found {len(quotes)} quotes")
```

### Create Ingestion Jobs

```python
from models import get_session, IngestionJob
import uuid

with get_session() as session:
    persona = session.query(Persona).filter_by(persona_id="tesla").first()

    for collection_type in ["profile", "works", "quotes"]:
        job = IngestionJob(
            id=str(uuid.uuid4()),
            persona_id=persona.id,
            collection_type=collection_type,
            status="pending",
            progress=0
        )
        session.add(job)

    session.commit()
    print(f"Created ingestion jobs for {persona.persona_id}")
```

### Track Data Sources

```python
from models import get_session, DataSource
import uuid
from datetime import datetime

with get_session() as session:
    persona = session.query(Persona).filter_by(persona_id="tesla").first()

    source = DataSource(
        id=str(uuid.uuid4()),
        persona_id=persona.id,
        collection_type="works",
        file_name="inventions.txt",
        file_path="/data/tesla/works/inventions.txt",
        file_size_bytes=125000,
        created_at=datetime.utcnow().isoformat()
    )
    session.add(source)
    session.commit()
```

### Update Persona Status

```python
from models import get_session, Persona
from datetime import datetime

with get_session() as session:
    persona = session.query(Persona).filter_by(persona_id="tesla").first()

    # Mark as ingesting
    persona.status = "ingesting"
    persona.updated_at = datetime.utcnow().isoformat()
    session.commit()

    # Later: mark as active
    persona.status = "active"
    persona.updated_at = datetime.utcnow().isoformat()
    session.commit()
```

### Query Relationships

```python
from models import get_session, Persona

with get_session() as session:
    persona = session.query(Persona).filter_by(persona_id="tesla").first()

    # Access related jobs
    print(f"Ingestion jobs: {len(persona.ingestion_jobs)}")
    for job in persona.ingestion_jobs:
        print(f"  - {job.collection_type}: {job.status}")

    # Access related data sources
    print(f"Data sources: {len(persona.data_sources)}")
    for source in persona.data_sources:
        print(f"  - {source.file_name}: {source.file_size_bytes} bytes")
```

### Delete Persona (Cascade)

```python
from models import get_session, Persona

with get_session() as session:
    persona = session.query(Persona).filter_by(persona_id="tesla").first()

    # This will also delete all related ingestion_jobs and data_sources
    session.delete(persona)
    session.commit()
    print("Persona and all related records deleted")
```

## Database Location

The SQLite database is created at:
```
/path/to/romanian-personas-agent/personas.db
```

## Session Management

The `get_session()` context manager handles:
- Session creation
- Automatic commit on success
- Automatic rollback on error
- Proper session cleanup

Always use it with a context manager:

```python
with get_session() as session:
    # Your database operations here
    pass
```

## Testing

Run the test suite to verify the database implementation:

```bash
python test_database.py
```

This will:
- Initialize the database
- Create test records
- Verify all relationships
- Test cascade deletion
- Clean up test data

## Next Steps

After Phase 1, proceed to:
- **Phase 2**: FastAPI Backend (CRUD endpoints)
- **Phase 3**: Celery Background Jobs (ingestion workers)
- **Phase 4**: Dynamic Persona Registry (runtime loading)
