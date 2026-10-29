FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim-bookworm
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
COPY backend/ backend/
RUN uv sync --frozen --no-dev --no-editable
COPY pipelines/deployment/ pipelines/deployment/
COPY database/snapshots/ database/snapshots/
RUN uv run --no-sync python -m pipelines.deployment.snapshot restore
COPY --from=frontend /build/frontend/dist/ frontend/dist/
ENV REMOTE_PDF_ENABLED=true PYTHONUNBUFFERED=1 SECURITY_RAG_ROOT=/app
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 10000
CMD ["sh", "-c", "exec uv run --no-sync uvicorn security_rag.deployed_app:create_app --factory --host 0.0.0.0 --port ${PORT:-10000} --workers 1"]
