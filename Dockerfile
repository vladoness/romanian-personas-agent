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

# Create directories for EFS volumes (will be mounted at runtime)
# Note: For marketplace deployment, chroma_db and data are NOT baked in
# They will be mounted from EFS at runtime in ECS
RUN mkdir -p ./chroma_db ./data

EXPOSE 8080

# Health check
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run MCP server in streamable-http mode
CMD ["python", "-m", "agent.mcp_server", "--transport", "streamable-http"]
