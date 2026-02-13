"""Ingestion pipeline: load per-persona documents, chunk, embed, store in ChromaDB.

Supports 3 collection types per persona (15 total):
  - {persona_id}_works   — primary writings (poems, plays, essays, speeches)
  - {persona_id}_quotes  — famous/representative quotes
  - {persona_id}_profile — Wikipedia + scholarly summaries

Usage:
  python -m ingest.run_ingestion                     # ingest all personas, all collections
  python -m ingest.run_ingestion --persona eminescu   # single persona, all collections
  python -m ingest.run_ingestion --persona eminescu --works   # single collection type
  python -m ingest.run_ingestion --persona eminescu --quotes
  python -m ingest.run_ingestion --persona eminescu --profile
"""

import json
import sys
from pathlib import Path

import chromadb
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

# Add parent to path so config is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_chroma_client():
    """Return a persistent ChromaDB client."""
    persist_dir = Path(settings.chroma_persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(persist_dir))


def _get_embedding():
    """Return the shared embedding model."""
    return OpenAIEmbedding(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
    )


def _get_chunk_params(persona_config, collection_type: str) -> tuple[int, int]:
    """Resolve chunk_size and chunk_overlap for a collection type.

    Uses persona-specific overrides if set, otherwise falls back to
    global defaults from settings.
    """
    size_attr = f"{collection_type}_chunk_size"
    overlap_attr = f"{collection_type}_chunk_overlap"

    chunk_size = getattr(persona_config, size_attr, None)
    if chunk_size is None:
        chunk_size = getattr(settings, f"default_{collection_type}_chunk_size")

    chunk_overlap = getattr(persona_config, overlap_attr, None)
    if chunk_overlap is None:
        chunk_overlap = getattr(settings, f"default_{collection_type}_chunk_overlap")

    return chunk_size, chunk_overlap


def _get_vector_store(collection_name: str) -> ChromaVectorStore:
    """Get or create a ChromaDB vector store for a named collection."""
    client = _get_chroma_client()
    chroma_collection = client.get_or_create_collection(collection_name)
    print(f"  ChromaDB '{collection_name}': {chroma_collection.count()} existing vectors")
    return ChromaVectorStore(chroma_collection=chroma_collection)


def _build_pipeline(vector_store: ChromaVectorStore, chunk_size: int, chunk_overlap: int) -> IngestionPipeline:
    """Create an ingestion pipeline with specified chunking parameters."""
    return IngestionPipeline(
        transformations=[
            SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap),
            _get_embedding(),
        ],
        vector_store=vector_store,
    )


def _verify_collection(collection_name: str) -> int:
    """Verify and return the vector count for a collection."""
    client = _get_chroma_client()
    collection = client.get_collection(collection_name)
    count = collection.count()
    print(f"  Total vectors in '{collection_name}': {count}")
    return count


# ---------------------------------------------------------------------------
# Works ingestion
# ---------------------------------------------------------------------------

def ingest_works(persona_id: str):
    """Ingest literary works for a persona from data/{persona_id}/works/."""
    from personas import get_persona

    persona = get_persona(persona_id)
    works_dir = Path(settings.data_dir) / persona_id / "works"

    if not works_dir.exists() or not any(works_dir.iterdir()):
        print(f"  No works data found at {works_dir}")
        return

    print(f"\n--- Ingesting works for {persona.display_name} ---")

    docs = SimpleDirectoryReader(
        input_dir=str(works_dir),
        recursive=True,
        required_exts=[".txt", ".md"],
        filename_as_id=True,
    ).load_data(num_workers=4)

    # Enrich metadata
    for doc in docs:
        fp = doc.metadata.get("file_path", "")
        fname = Path(fp).name if fp else "unknown"
        doc.metadata["source_type"] = "literary_work"
        doc.metadata["source_file"] = fname
        doc.metadata["persona_id"] = persona_id
        doc.metadata["persona_name"] = persona.display_name

    print(f"  Loaded {len(docs)} work documents")

    chunk_size, chunk_overlap = _get_chunk_params(persona, "works")
    collection_name = persona.works_collection
    vector_store = _get_vector_store(collection_name)
    pipeline = _build_pipeline(vector_store, chunk_size, chunk_overlap)

    print(f"  Chunking: size={chunk_size}, overlap={chunk_overlap}")
    nodes = pipeline.run(documents=docs, num_workers=4, show_progress=True)
    print(f"  Ingested {len(nodes)} nodes")
    _verify_collection(collection_name)


# ---------------------------------------------------------------------------
# Quotes ingestion
# ---------------------------------------------------------------------------

def ingest_quotes(persona_id: str):
    """Ingest quotes for a persona from data/{persona_id}/quotes/all_quotes.jsonl."""
    from personas import get_persona

    persona = get_persona(persona_id)
    quotes_file = Path(settings.data_dir) / persona_id / "quotes" / "all_quotes.jsonl"

    if not quotes_file.exists():
        print(f"  No quotes file found at {quotes_file}")
        return

    print(f"\n--- Ingesting quotes for {persona.display_name} ---")

    quotes = []
    with open(quotes_file, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                quotes.append(json.loads(line))

    print(f"  Loaded {len(quotes)} quotes")

    docs = []
    for q in quotes:
        doc = Document(
            text=q["text"],
            metadata={
                "source_type": q.get("source_type", "quote"),
                "source_file": q.get("source_file", "unknown"),
                "persona_id": persona_id,
                "persona_name": persona.display_name,
            },
        )
        docs.append(doc)

    chunk_size, chunk_overlap = _get_chunk_params(persona, "quotes")
    collection_name = persona.quotes_collection
    vector_store = _get_vector_store(collection_name)
    pipeline = _build_pipeline(vector_store, chunk_size, chunk_overlap)

    print(f"  Chunking: size={chunk_size}, overlap={chunk_overlap}")
    nodes = pipeline.run(documents=docs, num_workers=4, show_progress=True)
    print(f"  Ingested {len(nodes)} nodes")
    _verify_collection(collection_name)


# ---------------------------------------------------------------------------
# Profile ingestion
# ---------------------------------------------------------------------------

def ingest_profile(persona_id: str):
    """Ingest profile documents for a persona.

    Sources (in priority order):
    1. data/{persona_id}/profile/ — additional profile docs
    2. personas/{persona_id}/profile.md — built-in scholarly summary
    """
    from personas import get_persona

    persona = get_persona(persona_id)
    profile_data_dir = Path(settings.data_dir) / persona_id / "profile"
    profile_md = persona.profile_md_path

    print(f"\n--- Ingesting profile for {persona.display_name} ---")

    docs = []

    # Load profile.md (always present)
    if profile_md.exists():
        profile_docs = SimpleDirectoryReader(
            input_files=[str(profile_md)],
            filename_as_id=True,
        ).load_data()
        for doc in profile_docs:
            doc.metadata["source_type"] = "profile_summary"
            doc.metadata["source_file"] = profile_md.name
            doc.metadata["persona_id"] = persona_id
            doc.metadata["persona_name"] = persona.display_name
        docs.extend(profile_docs)
        print(f"  Loaded profile.md ({len(profile_docs)} pages)")

    # Load additional profile documents from data dir
    if profile_data_dir.exists() and any(profile_data_dir.iterdir()):
        extra_docs = SimpleDirectoryReader(
            input_dir=str(profile_data_dir),
            recursive=True,
            required_exts=[".txt", ".md"],
            filename_as_id=True,
        ).load_data(num_workers=4)

        for doc in extra_docs:
            fp = doc.metadata.get("file_path", "")
            fname = Path(fp).name if fp else "unknown"
            doc.metadata["source_type"] = "profile_document"
            doc.metadata["source_file"] = fname
            doc.metadata["persona_id"] = persona_id
            doc.metadata["persona_name"] = persona.display_name
        docs.extend(extra_docs)
        print(f"  Loaded {len(extra_docs)} additional profile documents")

    if not docs:
        print(f"  No profile data found for {persona_id}")
        return

    chunk_size, chunk_overlap = _get_chunk_params(persona, "profile")
    collection_name = persona.profile_collection
    vector_store = _get_vector_store(collection_name)
    pipeline = _build_pipeline(vector_store, chunk_size, chunk_overlap)

    print(f"  Chunking: size={chunk_size}, overlap={chunk_overlap}")
    nodes = pipeline.run(documents=docs, num_workers=4, show_progress=True)
    print(f"  Ingested {len(nodes)} nodes")
    _verify_collection(collection_name)


# ---------------------------------------------------------------------------
# Public API: get_index (used by MCP server for lazy retriever creation)
# ---------------------------------------------------------------------------

def get_index(persona_id: str, collection_type: str) -> VectorStoreIndex:
    """Load an existing vector store index for a specific persona collection.

    Used by the MCP server to create retrievers at runtime.
    """
    from personas import get_persona

    persona = get_persona(persona_id)
    collection_name = getattr(persona, f"{collection_type}_collection")
    vector_store = _get_vector_store(collection_name)

    return VectorStoreIndex.from_vector_store(
        vector_store,
        embed_model=_get_embedding(),
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def ingest_persona(persona_id: str, works: bool = True, quotes: bool = True, profile: bool = True):
    """Ingest all collection types for a single persona."""
    from personas import get_persona

    persona = get_persona(persona_id)
    print(f"\n{'=' * 60}")
    print(f"INGESTING: {persona.display_name} ({persona_id})")
    print(f"{'=' * 60}")

    if works:
        ingest_works(persona_id)
    if quotes:
        ingest_quotes(persona_id)
    if profile:
        ingest_profile(persona_id)


def ingest_all():
    """Ingest all personas, all collection types."""
    from personas import VALID_PERSONA_IDS

    print("=" * 60)
    print("FULL INGESTION — ALL PERSONAS")
    print("=" * 60)

    for persona_id in VALID_PERSONA_IDS:
        ingest_persona(persona_id)

    # Final summary
    print("\n" + "=" * 60)
    print("INGESTION COMPLETE — SUMMARY")
    print("=" * 60)

    client = _get_chroma_client()
    total = 0
    for collection in client.list_collections():
        count = collection.count()
        total += count
        print(f"  {collection.name}: {count} vectors")
    print(f"\n  TOTAL: {total} vectors across {len(client.list_collections())} collections")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Romanian Personas Ingestion Pipeline")
    parser.add_argument("--persona", type=str, help="Specific persona ID to ingest")
    parser.add_argument("--works", action="store_true", help="Ingest works only")
    parser.add_argument("--quotes", action="store_true", help="Ingest quotes only")
    parser.add_argument("--profile", action="store_true", help="Ingest profile only")
    args = parser.parse_args()

    if args.persona:
        # If no specific collection type flags, do all
        do_works = args.works or (not args.works and not args.quotes and not args.profile)
        do_quotes = args.quotes or (not args.works and not args.quotes and not args.profile)
        do_profile = args.profile or (not args.works and not args.quotes and not args.profile)
        ingest_persona(args.persona, works=do_works, quotes=do_quotes, profile=do_profile)
    else:
        ingest_all()
