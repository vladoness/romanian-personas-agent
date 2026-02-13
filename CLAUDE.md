# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## What This Project Is

Romanian Personas Agent — a RAG knowledge assistant that lets you converse with Romanian historical personalities. Each persona responds in their authentic voice, drawing from their real writings, biography, and famous quotes. All responses are in Romanian. Deployed as an MCP server on AWS ECS Fargate.

Available personas:
- **Eminescu** — Mihai Eminescu (1850-1889), poetul national
- **Bratianu** — Ion C. Bratianu (1821-1891), om de stat
- **Caragiale** — Ion Luca Caragiale (1852-1912), dramaturg si satirist
- **Eliade** — Mircea Eliade (1907-1986), istoric al religiilor
- **Cioran** — Emil Cioran (1911-1995), filozof si eseist

## Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e .                          # install project + deps
pip install -e '.[dev]'                   # include pytest

# Scraping (fetches data from Wikisource, Wikipedia, quote sites)
python -m ingest.scraper                            # scrape all personas
python -m ingest.scraper --persona eminescu         # single persona
python -m ingest.scraper --works                    # works only
python -m ingest.scraper --profile                  # Wikipedia profiles only

# Quote extraction (from scraped works + online sources)
python -m ingest.extract_quotes                     # all personas
python -m ingest.extract_quotes --persona eminescu  # single persona

# Ingestion (builds ChromaDB collections from scraped data)
python -m ingest.run_ingestion                              # all personas, all collections
python -m ingest.run_ingestion --persona eminescu            # single persona
python -m ingest.run_ingestion --persona eminescu --works    # works collection only
python -m ingest.run_ingestion --persona eminescu --quotes   # quotes collection only
python -m ingest.run_ingestion --persona eminescu --profile  # profile collection only

# Run MCP server
python -m agent.mcp_server --transport streamable-http  # production (Docker default)
python -m agent.mcp_server --transport stdio             # local/Claude Code stdio

# Tests
python test_personas.py       # verify persona loading
python test_mcp_server.py     # end-to-end MCP server test

# Docker
docker build -t romanian-personas-agent .
docker run -p 8080:8080 --env-file .env romanian-personas-agent
```

## Architecture

### MCP Server (`agent/mcp_server.py`)

Single `ask_persona(query, persona)` tool exposed via FastMCP. Validates persona ID, runs 3 parallel async searches across ChromaDB collections, assembles context with information hierarchy, and synthesizes response via Claude Opus using persona-specific voice prompt.

### Retrieval Flow

Three parallel searches per query via `asyncio.create_task`:

1. **Profile** (top_k=5) → `{persona_id}_profile` — biographical/intellectual context
2. **Works** (top_k=8) → `{persona_id}_works` — primary writings
3. **Quotes** (top_k=10) → `{persona_id}_quotes` — famous/representative quotes

**Information hierarchy in synthesis:**
- Profile = the LENS (biographical context, placed first)
- Quotes = voice calibration (tone, aphorisms, phrasing)
- Works = primary textual evidence (actual writings)

### Persona System

`PersonaConfig` dataclass in `personas/_base.py` with registry in `personas/__init__.py`. Each persona has:
- `personas/{id}/persona.py` — SPEAKING_STYLE, KEY_THEMES, VOICE_PROMPT, REPRESENTATIVE_QUOTES
- `personas/{id}/profile.md` — scholarly summary (~10-25K words)

### ChromaDB Collections (15 total = 5 personas x 3 types)

| Type | Naming | Chunk Size | top_k | Content |
|------|--------|-----------|-------|---------|
| Works | `{id}_works` | 1024/128 | 8 | Poems, plays, essays, speeches |
| Quotes | `{id}_quotes` | 512/64 | 10 | Famous quotes and passages |
| Profile | `{id}_profile` | 2048/256 | 5 | Wikipedia + scholarly summaries |

Lazy-loaded retrievers cached in `dict[(persona_id, collection_type)]`.

### Ingestion Pipeline

Three-stage pipeline: scraping → quote extraction → ChromaDB ingestion.

Data sources per persona:
- **Eminescu**: ro.wikisource.org (300+ poems), Wikipedia
- **Caragiale**: ro.wikisource.org (plays + 100+ sketches), Wikipedia
- **Cioran**: ro.wikisource.org + archive.org, Wikipedia (RO/EN)
- **Eliade**: ro.wikisource.org + archive.org, Wikipedia (RO/EN)
- **Bratianu**: archive.org + manual curation, Wikipedia

## Key Files

- `config.py` — Pydantic Settings, loads from `.env`
- `agent/mcp_server.py` — FastMCP server with `ask_persona` tool
- `personas/_base.py` — PersonaConfig dataclass
- `personas/__init__.py` — persona registry, `get_persona()` validator
- `personas/{id}/persona.py` — per-persona voice prompt and configuration
- `personas/{id}/profile.md` — scholarly biography summary
- `ingest/run_ingestion.py` — multi-persona ChromaDB ingestion
- `ingest/scraper.py` — Wikisource + Wikipedia scraper
- `ingest/extract_quotes.py` — quote extraction pipeline

## Environment Variables

Required in `.env`:
- `ANTHROPIC_API_KEY` — for Claude synthesis
- `OPENAI_API_KEY` — for text-embedding-3-small embeddings
- `MCP_API_KEY` — for remote MCP auth (optional; unauthenticated if missing)

## Deployment

Docker image bakes in `chroma_db/` and `data/` directories (pre-built locally). Deployed via AWS CodeBuild (`buildspec.yml`) to ECR, then ECS Fargate (1 vCPU, 4GB RAM). ALB health check hits `GET /health`.
