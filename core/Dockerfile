# syntax=docker/dockerfile:1.7
#
# Build context: repo root (so we can COPY both `core/` and `database/`).
# CI invokes this with: docker build -f core/Dockerfile .
############################################
# 1️⃣  shared deps  (never re-installed if unchanged)
############################################
FROM python:3.11-slim AS deps
WORKDIR /install

# build tools + cache APT index between builds
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends build-essential gcc && \
    rm -rf /var/lib/apt/lists/*

COPY core/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install --prefer-binary --prefix=/install -r requirements.txt

# 2️⃣  runtime image  (what you actually deploy)
############################################
FROM python:3.11-slim AS runtime
WORKDIR /app

# runtime helpers (no curl/wget — hardened against RCE exploitation)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates espeak-ng ghostscript icc-profiles-free && \
    rm -rf /var/lib/apt/lists/*

# bring in the wheels
COPY --from=deps /install /usr/local

# Copy api source + database/ (schema, migrations, seed runner).
# `database/` ships in the image so the one-shot `db-init` service can
# run `python -m database.scripts.runner --target-pg-url ...` against
# the live stock postgres at first deploy.
COPY core/app/ ./app/
COPY database/ ./database/
# Bake seed assets (text excerpts, themes) so first-deploy db-init can
# resolve them from /app/uploads. uploads/call (700MB of test data)
# and uploads/audio|video (runtime artifacts) are pruned via .dockerignore.
COPY uploads/ ./uploads/

# non-root for prod
ARG APP_UID=1001
ARG APP_GID=1001   # pick any unused id ≥ 1000

# create group & user with those ids
RUN addgroup --system --gid $APP_GID appuser && \
    adduser  --system --uid $APP_UID --gid $APP_GID \
             --home /home/appuser appuser

RUN chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app
EXPOSE 8000

CMD ["gunicorn", "app.main:app", \
     "-w", "1", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-b", "0.0.0.0:8000", \
     "--log-level", "info", \
     "--timeout", "300", \
     "--graceful-timeout", "10"]
