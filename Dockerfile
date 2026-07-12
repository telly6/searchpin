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

# Use HuggingFace official endpoint for Docker builds (Glama/GitHub Actions run overseas).
# searchpin defaults to hf-mirror.com at runtime for China users — no impact on them.
ENV HF_ENDPOINT=https://huggingface.co

# Install dependencies and pre-download the embedding model.
# Model is baked into the image — zero delay on first container start.
RUN pip install --no-cache-dir . && \
    searchpin-setup

# ── Runtime stage ─────────────────────────────────────────
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /root/.cache/huggingface /root/.cache/huggingface

ENV SEARCHPIN_TIMING_LOG=""

# MCP stdio server — MCP clients run this with `docker run -i`.
CMD ["searchpin-server"]
