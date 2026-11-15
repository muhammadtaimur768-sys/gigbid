# One image for all three GigBid MCP servers; the command selects the server:
#   docker run gigbid-mcp portfolio      (port 8201)
#   docker run gigbid-mcp marketplace    (port 8202)
#   docker run gigbid-mcp workspace      (port 8203)
# Build context: repository root.
FROM python:3.11.13-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONPATH=/app \
    MCP_HOST=0.0.0.0

RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
RUN uv pip install --system -r pyproject.toml

COPY agent ./agent
COPY rag ./rag
COPY mcp_servers ./mcp_servers
COPY data/personas ./data/personas
COPY data/policy_pack ./data/policy_pack
COPY infra/docker/mcp-entrypoint.sh /usr/local/bin/mcp-entrypoint
RUN chmod +x /usr/local/bin/mcp-entrypoint \
 && mkdir -p data/processed

RUN useradd --create-home --uid 10001 gigbid && chown -R gigbid /app
USER gigbid

EXPOSE 8201 8202 8203
HEALTHCHECK --interval=10s --timeout=4s --start-period=60s --retries=10 \
  CMD python -c "import os,sys,urllib.request; p=os.environ.get('MCP_HEALTH_PORT','8201'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{p}/health', timeout=3).status == 200 else 1)"
ENTRYPOINT ["mcp-entrypoint"]
CMD ["portfolio"]
