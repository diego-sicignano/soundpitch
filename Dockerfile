# One container serves the API and the page. Build from the repository root:
#   docker build -t soundpitch .
#   docker run -p 8000:8000 soundpitch
#
# The judges' image runs SOUNDPITCH_LLM=replay: recorded Foundry replies, checked by the verifier on every
# session, through the Microsoft Agent Framework workflow (SOUNDPITCH_ORCHESTRATOR=workflow, D31). It needs no
# key, no Azure login, no network and no writable path (D12). The live Foundry describer and its cost ledger
# are not part of this image: they need requirements-agents.txt, an Azure identity and a persistent file,
# none of which the judges' path uses (docs/DEPLOY.md). The same image serves the match to an AI agent over MCP:
#   docker run -i --rm <image> python -m app.mcp_server   (SPEC §16, D32)
FROM python:3.13-slim

# Links the package on ghcr.io to the repository, so it inherits the repository's visibility settings page.
LABEL org.opencontainers.image.source="https://github.com/diego-sicignano/soundpitch" \
      org.opencontainers.image.description="SoundPitch judges' image: replay mode, no key and no network needed" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    SOUNDPITCH_LLM=replay \
    SOUNDPITCH_ORCHESTRATOR=workflow

WORKDIR /srv/backend
COPY backend/requirements.txt backend/requirements-workflow.txt backend/requirements-mcp.txt ./
RUN pip install -r requirements-workflow.txt -r requirements-mcp.txt

COPY backend/app ./app
COPY frontend /srv/frontend

RUN useradd --system --no-create-home --uid 10001 soundpitch
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
