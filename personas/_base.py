"""Base persona configuration dataclass."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PersonaConfig:
    """Configuration for a single historical persona."""

    persona_id: str
    display_name: str
    birth_year: int
    death_year: int
    description: str
    speaking_style: str
    key_themes: str
    voice_prompt: str
    representative_quotes: list[str] = field(default_factory=list)

    # Per-persona retrieval overrides (None = use defaults from Settings)
    works_top_k: int | None = None
    quotes_top_k: int | None = None
    profile_top_k: int | None = None
    works_chunk_size: int | None = None
    works_chunk_overlap: int | None = None

    @property
    def works_collection(self) -> str:
        return f"{self.persona_id}_works"

    @property
    def quotes_collection(self) -> str:
        return f"{self.persona_id}_quotes"

    @property
    def profile_collection(self) -> str:
        return f"{self.persona_id}_profile"

    @property
    def data_dir(self) -> Path:
        return Path(f"./data/{self.persona_id}")

    @property
    def profile_md_path(self) -> Path:
        return Path(f"./personas/{self.persona_id}/profile.md")
