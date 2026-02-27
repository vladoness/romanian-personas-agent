#!/usr/bin/env python3
"""Migrate the 5 hardcoded legacy personas into the database."""

import sys
import json
from pathlib import Path
from datetime import datetime
from uuid import uuid4

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from models.database import get_session, Persona, init_db
from personas import _load_static_registry

# Color mapping for legacy personas
PERSONA_COLORS = {
    'eminescu': '#8b4513',    # Brown
    'caragiale': '#2e7d32',   # Green
    'bratianu': '#1565c0',    # Blue
    'eliade': '#6a1b9a',      # Purple
    'cioran': '#c62828',      # Red
}


def migrate_legacy_personas():
    """Migrate hardcoded personas to database."""
    print("=" * 60)
    print("LEGACY PERSONA MIGRATION")
    print("=" * 60)

    # Initialize database
    print("\n1. Initializing database...")
    init_db()
    print("   ✓ Database initialized")

    # Load static personas
    print("\n2. Loading static personas...")
    static_registry = _load_static_registry()
    print(f"   ✓ Found {len(static_registry)} personas")

    # Migrate each persona
    with get_session() as session:
        migrated = 0
        skipped = 0

        for persona_id, config in static_registry.items():
            print(f"\n3. Migrating '{persona_id}'...")

            # Check if already exists
            existing = session.query(Persona).filter_by(persona_id=persona_id).first()
            if existing:
                print(f"   ⚠ Already exists in database (skipping)")
                skipped += 1
                continue

            # Create database record
            db_persona = Persona(
                id=str(uuid4()),
                persona_id=config.persona_id,
                display_name=config.display_name,
                birth_year=config.birth_year,
                death_year=config.death_year,
                description=config.description,
                speaking_style=config.speaking_style,
                key_themes=config.key_themes,
                voice_prompt=config.voice_prompt,
                representative_quotes=json.dumps(config.representative_quotes),
                color=PERSONA_COLORS.get(persona_id, '#666666'),

                # Retrieval overrides
                works_top_k=config.works_top_k,
                quotes_top_k=config.quotes_top_k,
                profile_top_k=config.profile_top_k,
                works_chunk_size=config.works_chunk_size,
                works_chunk_overlap=config.works_chunk_overlap,

                # Status: active (already have ChromaDB collections)
                status='active',
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat()
            )

            session.add(db_persona)
            print(f"   ✓ Migrated: {config.display_name} ({config.birth_year}-{config.death_year})")
            migrated += 1

        # Commit all changes
        session.commit()

        print("\n" + "=" * 60)
        print("MIGRATION COMPLETE")
        print("=" * 60)
        print(f"✓ Migrated: {migrated} personas")
        print(f"⚠ Skipped:  {skipped} personas (already in database)")
        print(f"\nTotal personas in database: {session.query(Persona).count()}")
        print("\nVerify with:")
        print('  sqlite3 personas.db "SELECT persona_id, display_name, status FROM personas;"')
        print("\n" + "=" * 60)


if __name__ == "__main__":
    try:
        migrate_legacy_personas()
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
