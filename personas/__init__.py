"""Persona registry — maps persona IDs to their configurations."""

from personas._base import PersonaConfig

# Lazy imports to avoid circular dependencies
_registry: dict[str, PersonaConfig] | None = None


def _load_registry() -> dict[str, PersonaConfig]:
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


def get_registry() -> dict[str, PersonaConfig]:
    global _registry
    if _registry is None:
        _registry = _load_registry()
    return _registry


VALID_PERSONA_IDS = ["eminescu", "bratianu", "caragiale", "eliade", "cioran"]


def get_persona(persona_id: str) -> PersonaConfig:
    """Get persona config by ID, raise ValueError if not found."""
    registry = get_registry()
    if persona_id not in registry:
        raise ValueError(
            f"Personalitate necunoscuta: '{persona_id}'. "
            f"Personalitati disponibile: {', '.join(VALID_PERSONA_IDS)}"
        )
    return registry[persona_id]
