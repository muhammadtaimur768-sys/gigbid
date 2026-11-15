# GigSim marketplace simulator (provided, unmodified). Build context: repository root.
FROM python:3.11.13-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_LINK_MODE=copy \
    PYTHONPATH=/app

RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
RUN uv pip install --system -r pyproject.toml

COPY gigsim ./gigsim
RUN mkdir -p data/processed

RUN useradd --create-home --uid 10001 gigbid && chown -R gigbid /app
USER gigbid

EXPOSE 8100
HEALTHCHECK --interval=10s --timeout=4s --start-period=20s --retries=6 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8100/health', timeout=3).status == 200 else 1)"

# Seed is idempotent ((re)creates gs_ tables from gigsim/seed_data/*.json) unless GIGSIM_SKIP_SEED=1.
CMD ["sh", "-c", "if [ \"${GIGSIM_SKIP_SEED:-0}\" != \"1\" ]; then python -m gigsim.seed; fi && exec uvicorn gigsim.app:app --host 0.0.0.0 --port 8100"]
