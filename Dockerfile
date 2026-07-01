# ── Searchpin Docker Image ────────────────────────────────
# Multi-stage: build in context, ship a lean runtime.
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY searchpin/ ./searchpin/
COPY search_server.py ./

# Install dependencies
# Note: embedding model is NOT pre-downloaded — it will be
# fetched from HuggingFace on first container start.
RUN pip install --no-cache-dir .

# ── Runtime stage ─────────────────────────────────────────
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

ENV SEARCHPIN_TIMING_LOG=""

# MCP stdio server — MCP clients run this with `docker run -i`.
CMD ["searchpin-server"]
