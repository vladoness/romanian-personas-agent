FROM public.ecr.aws/docker/library/python:3.13-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY config.py .
COPY ingest/ ./ingest/
COPY agent/ ./agent/
COPY personas/ ./personas/

# Install Python deps
RUN pip install --no-cache-dir .

# Bake in the vector stores and data (pre-built locally)
COPY chroma_db/ ./chroma_db/
COPY data/ ./data/

EXPOSE 8080

# Run MCP server in streamable-http mode
CMD ["python", "-m", "agent.mcp_server", "--transport", "streamable-http"]
