"""Romanian Personas Agent — MCP Server via Streamable HTTP transport.

Supports both local (stdio) and remote (streamable-http) modes:
  - Local:  python -m agent.mcp_server --transport stdio
  - Remote: python -m agent.mcp_server --transport streamable-http

When running remotely, set MCP_API_KEY env var to require Bearer token auth.
"""

import argparse
import asyncio
import logging
import secrets
import sys
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy-loaded retrievers: Dict[(persona_id, collection_type), retriever]
# ---------------------------------------------------------------------------
_retrievers: dict[tuple[str, str], Any] = {}


def _get_retriever(persona_id: str, collection_type: str):
    """Get or create a retriever for a specific persona collection."""
    key = (persona_id, collection_type)
    if key not in _retrievers:
        from personas import get_persona
        from ingest.run_ingestion import get_index

        persona = get_persona(persona_id)
        collection_name = getattr(persona, f"{collection_type}_collection")

        # Use persona-specific top_k or fall back to settings default
        top_k = getattr(persona, f"{collection_type}_top_k", None)
        if top_k is None:
            top_k = getattr(settings, f"default_{collection_type}_top_k")

        index = get_index(persona_id, collection_type)
        _retrievers[key] = index.as_retriever(similarity_top_k=top_k)
        logger.info(f"Loaded retriever: {collection_name} (top_k={top_k})")

    return _retrievers[key]


# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "romanian-personas-agent",
    host=settings.host,
    port=settings.port,
    stateless_http=True,
)


@mcp.tool()
async def ask_persona(
    query: Annotated[str, "Intrebare de adresat personalitatii istorice romanesti"],
    persona: Annotated[str, "Personalitate: eminescu, bratianu, caragiale, eliade, cioran"],
) -> str:
    """Converseaza cu personalitati istorice romanesti.

    Pune o intrebare si primeste un raspuns in vocea personalitatii alese,
    bazat pe opera, gandirea si biografia lor reala.

    Personalitati disponibile:
    - eminescu: Mihai Eminescu (1850-1889) — poetul national al Romaniei
    - bratianu: Ion C. Bratianu (1821-1891) — om de stat, prim-ministru
    - caragiale: Ion Luca Caragiale (1852-1912) — dramaturg si satirist
    - eliade: Mircea Eliade (1907-1986) — istoric al religiilor, filozof
    - cioran: Emil Cioran (1911-1995) — filozof si eseist

    Raspunsurile sunt exclusiv in limba romana."""

    from personas import get_persona

    persona_config = get_persona(persona)

    sections = []
    all_sources: set[str] = set()

    # 3 parallel searches
    profile_task = asyncio.create_task(_search_collection(query, persona, "profile"))
    works_task = asyncio.create_task(_search_collection(query, persona, "works"))
    quotes_task = asyncio.create_task(_search_collection(query, persona, "quotes"))

    profile_chunks, profile_sources = await profile_task
    works_chunks, works_sources = await works_task
    quotes_chunks, quotes_sources = await quotes_task

    # Assemble context with hierarchy — profile first as interpretive lens
    if profile_chunks:
        sections.append(
            "## Profil si Context Biografic\n"
            "Foloseste acest context pentru a incadra si interpreta informatiile.\n\n"
            + "\n\n---\n\n".join(profile_chunks)
        )
        all_sources.update(profile_sources)

    if works_chunks:
        sections.append(
            f"## Opera (texte din lucrarile lui {persona_config.display_name})\n\n"
            + "\n\n---\n\n".join(works_chunks)
        )
        all_sources.update(works_sources)

    if quotes_chunks:
        sections.append(
            "## Citate Reprezentative\n\n"
            + "\n\n---\n\n".join(quotes_chunks)
        )
        all_sources.update(quotes_sources)

    if not sections:
        return (
            f"Nu am gasit informatii relevante despre aceasta intrebare "
            f"in baza de cunostinte a lui {persona_config.display_name}."
        )

    context = "\n\n".join(sections)
    source_list = "\n".join(f"  - {s}" for s in sorted(all_sources))

    synthesized = await _synthesize_with_claude(
        query, context, source_list, persona_config.voice_prompt, persona_config.display_name
    )
    return synthesized


async def _search_collection(
    query: str, persona_id: str, collection_type: str
) -> tuple[list[str], set[str]]:
    """Search a specific ChromaDB collection for a persona."""
    try:
        retriever = _get_retriever(persona_id, collection_type)
        nodes = retriever.retrieve(query)
        chunks = []
        sources: set[str] = set()

        # Truncation limits per collection type
        max_chars = {"profile": 1200, "works": 600, "quotes": 0}  # 0 = no truncation
        limit = max_chars.get(collection_type, 600)

        for node in nodes:
            meta = node.metadata
            source = meta.get("source_file", meta.get("file_name", "unknown"))
            sources.add(source)
            content = node.get_content()
            if limit > 0:
                content = content[:limit]
            chunks.append(content)

        return chunks, sources
    except Exception as e:
        logger.error(f"Search error ({persona_id}/{collection_type}): {e}")
        return [], set()


async def _synthesize_with_claude(
    query: str,
    context: str,
    source_list: str,
    voice_prompt: str,
    display_name: str,
) -> str:
    """Call Claude Opus to synthesize a persona-voice response from retrieved context."""
    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

        user_message = (
            f"# Context Recuperat\n\n{context}\n\n"
            f"# Intrebarea Utilizatorului\n{query}\n\n"
            f"# Surse\n{source_list}\n\n"
            f"# Instructiuni de Raspuns\n"
            f"Folosind contextul recuperat de mai sus, raspunde la intrebarea "
            f"utilizatorului in vocea lui {display_name}.\n\n"
            f"**Ierarhia informatiei:**\n"
            f"1. Profilul biografic/intelectual = LENTILA prin care interpretezi totul.\n"
            f"2. Citatele = calibrarea vocii (ton, expresii, aforisme).\n"
            f"3. Opera = dovezi textuale primare (scrierile reale).\n\n"
            f"Fii detaliat si cuprinzator. Citeaza din opera cand e relevant. "
            f"Raspunde EXCLUSIV in limba romana."
        )

        response = await client.messages.create(
            model=settings.synthesis_model,
            max_tokens=4096,
            system=voice_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        return response.content[0].text

    except Exception as e:
        logger.error(f"Claude synthesis error: {e}")
        return (
            f"{context}\n\n"
            f"# Surse\n{source_list}\n\n"
            f"(Nota: Sinteza LLM a esuat — se returneaza contextul brut. Eroare: {e})"
        )


# ---------------------------------------------------------------------------
# API key middleware (wraps the Starlette app for streamable-http)
# ---------------------------------------------------------------------------


def _wrap_with_api_key_auth(app):
    """ASGI middleware that checks X-API-Key or Authorization: Bearer header."""
    api_key = settings.mcp_api_key

    if not api_key:
        logger.warning("MCP_API_KEY not set — server is running WITHOUT authentication!")
        return app

    logger.info("API key authentication enabled")

    async def middleware(scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path == "/health":
                await app(scope, receive, send)
                return

            headers = dict(scope.get("headers", []))
            key = headers.get(b"x-api-key", b"").decode()
            if not key:
                auth = headers.get(b"authorization", b"").decode()
                if auth.startswith("Bearer "):
                    key = auth[7:]

            if not secrets.compare_digest(key, api_key):
                await send({
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [[b"content-type", b"application/json"]],
                })
                await send({
                    "type": "http.response.body",
                    "body": b'{"error":"Invalid or missing API key"}',
                })
                return

        await app(scope, receive, send)

    return middleware


# ---------------------------------------------------------------------------
# Health check route
# ---------------------------------------------------------------------------


@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    from starlette.responses import JSONResponse

    return JSONResponse({"status": "ok", "server": "romanian-personas-agent"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Romanian Personas Agent MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="Transport mode (default: stdio for local, streamable-http for remote)",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        logger.info("Starting MCP server in stdio mode")
        mcp.run(transport="stdio")
    else:
        logger.info(f"Starting MCP server on {settings.host}:{settings.port} (streamable-http)")
        starlette_app = mcp.streamable_http_app()
        wrapped_app = _wrap_with_api_key_auth(starlette_app)

        import uvicorn

        uvicorn.run(
            wrapped_app,
            host=settings.host,
            port=settings.port,
            log_level="info",
        )


if __name__ == "__main__":
    main()
