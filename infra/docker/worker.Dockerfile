# GigBid worker (Arq on Redis): scheduled scouting and long agent runs.
# Build context: repository root.
FROM python:3.11.13-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONPATH=/app \
    WORKER_SETTINGS=worker.settings.WorkerSettings

RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
RUN uv pip install --system -r pyproject.toml

COPY agent ./agent
COPY rag ./rag
COPY mcp_servers ./mcp_servers
COPY apps/api ./apps/api
COPY worker ./worker
COPY gigsim ./gigsim
COPY evals ./evals
COPY data/personas ./data/personas
COPY data/policy_pack ./data/policy_pack
RUN mkdir -p data/processed

RUN useradd --create-home --uid 10001 gigbid && chown -R gigbid /app
USER gigbid

# Arq exposes no HTTP port; liveness = the worker can reach Redis.
HEALTHCHECK --interval=20s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import os,redis; redis.Redis.from_url(os.environ.get('REDIS_URL','redis://redis:6379/0')).ping()"

# The settings class is configurable so the worker module can evolve without a rebuild.
CMD ["sh", "-c", "exec arq \"$WORKER_SETTINGS\""]
