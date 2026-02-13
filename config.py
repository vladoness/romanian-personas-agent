"""Configuration for the Romanian Personas Agent."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM (synthesis)
    anthropic_api_key: str = ""
    synthesis_model: str = "claude-opus-4-6"

    # Embeddings
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"

    # Vector store
    chroma_persist_dir: str = "./chroma_db"

    # Data paths
    data_dir: str = "./data"

    # Collection naming suffixes
    works_collection_suffix: str = "works"
    quotes_collection_suffix: str = "quotes"
    profile_collection_suffix: str = "profile"

    # Chunking defaults (per-persona overrides in persona.py)
    default_works_chunk_size: int = 1024
    default_works_chunk_overlap: int = 128
    default_quotes_chunk_size: int = 512
    default_quotes_chunk_overlap: int = 64
    default_profile_chunk_size: int = 2048
    default_profile_chunk_overlap: int = 256

    # Retrieval defaults
    default_works_top_k: int = 8
    default_quotes_top_k: int = 10
    default_profile_top_k: int = 5

    # Server
    host: str = "0.0.0.0"
    port: int = 8080
    mcp_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
