# Build context is the repo root (see deploy/docker-compose.yml) — apps/api's MCP
# client spawns `python -m mcp_memory.server` as a subprocess, so the sibling
# packages/mcp-memory package must be installed in this image too.
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY packages/mcp-memory /packages/mcp-memory
COPY apps/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/api/. .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
