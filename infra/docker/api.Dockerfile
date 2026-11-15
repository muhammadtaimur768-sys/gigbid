# GigBid API (FastAPI + LangGraph). Build context: repository root.
#   docker build -f infra/docker/api.Dockerfile -t gigbid-api .
FROM python:3.11.13-slim-bookworm AS base

COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONPATH=/app

RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first (cached layer): only pyproject.toml is needed to resolve them.
COPY pyproject.toml ./
RUN uv pip install --system -r pyproject.toml

# Application code.
COPY agent ./agent
COPY rag ./rag
COPY mcp_servers ./mcp_servers
COPY apps/api ./apps/api
COPY worker ./worker
COPY gigsim ./gigsim
COPY evals ./evals
COPY data/personas ./data/personas
COPY data/policy_pack ./data/policy_pack
COPY scripts ./scripts
RUN mkdir -p data/processed

RUN useradd --create-home --uid 10001 gigbid && chown -R gigbid /app
USER gigbid

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
