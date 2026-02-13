"""Test persona loading and configuration validation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from personas import get_persona, get_registry, VALID_PERSONA_IDS
from personas._base import PersonaConfig


def test_all_personas_load():
    """All 5 personas should load without errors."""
    registry = get_registry()
    assert len(registry) == 5, f"Expected 5 personas, got {len(registry)}"
    for pid in VALID_PERSONA_IDS:
        assert pid in registry, f"Missing persona: {pid}"
    print("PASS: All 5 personas load correctly")


def test_persona_configs_valid():
    """Each persona config should have all required fields populated."""
    for pid in VALID_PERSONA_IDS:
        persona = get_persona(pid)
        assert isinstance(persona, PersonaConfig)
        assert persona.persona_id == pid
        assert len(persona.display_name) > 0, f"{pid}: missing display_name"
        assert persona.birth_year > 0, f"{pid}: invalid birth_year"
        assert persona.death_year > persona.birth_year, f"{pid}: invalid death_year"
        assert len(persona.description) > 20, f"{pid}: description too short"
        assert len(persona.speaking_style) > 50, f"{pid}: speaking_style too short"
        assert len(persona.key_themes) > 100, f"{pid}: key_themes too short"
        assert len(persona.voice_prompt) > 200, f"{pid}: voice_prompt too short"
        assert len(persona.representative_quotes) >= 5, f"{pid}: need at least 5 quotes, got {len(persona.representative_quotes)}"
        print(f"  PASS: {pid} ({persona.display_name}) — config valid")

    print("PASS: All persona configs validated")


def test_collection_names():
    """Collection names should follow the {persona_id}_{type} pattern."""
    for pid in VALID_PERSONA_IDS:
        persona = get_persona(pid)
        assert persona.works_collection == f"{pid}_works", f"Unexpected works collection: {persona.works_collection}"
        assert persona.quotes_collection == f"{pid}_quotes", f"Unexpected quotes collection: {persona.quotes_collection}"
        assert persona.profile_collection == f"{pid}_profile", f"Unexpected profile collection: {persona.profile_collection}"

    print("PASS: All collection names correct")


def test_profile_md_paths():
    """Profile markdown files should exist for all personas."""
    for pid in VALID_PERSONA_IDS:
        persona = get_persona(pid)
        profile_path = persona.profile_md_path
        assert profile_path.exists(), f"Missing profile.md for {pid} at {profile_path}"
        content = profile_path.read_text(encoding="utf-8")
        assert len(content) > 1000, f"Profile too short for {pid}: {len(content)} chars"
        print(f"  PASS: {pid} profile.md exists ({len(content)} chars)")

    print("PASS: All profile.md files present")


def test_invalid_persona_raises():
    """Requesting an invalid persona should raise ValueError."""
    try:
        get_persona("nonexistent")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "necunoscuta" in str(e).lower() or "nonexistent" in str(e)
        print(f"PASS: Invalid persona raises ValueError: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("PERSONA TESTS")
    print("=" * 60)

    test_all_personas_load()
    test_persona_configs_valid()
    test_collection_names()
    test_profile_md_paths()
    test_invalid_persona_raises()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
