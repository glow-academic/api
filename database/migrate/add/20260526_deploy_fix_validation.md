# Validating the v1.0.6 deploy fix

Two changes ship together:

1. **Dockerfile** — bake seed assets at `/app/seed/uploads` (was `/app/uploads`).
2. **CI workflow** — publish a multi-arch manifest list (`linux/amd64,linux/arm64`).

Plus the **glow CLI compose template** (`glow-academic-cli/src/deploy/templates/api-compose.yml`)
switches `volume-init` to use the api image so it can read the new bake path.

## Test 1 — Issue 2 (copy-up collision) locally

You can validate without the CI rebuild by building the image locally on
an Apple Silicon host and pointing `glow deploy` at the local tag.

```bash
# 1. Build the new image locally (amd64 for now; same fix applies to arm64).
#    Use --platform linux/amd64 on Apple Silicon if you don't have buildx
#    arm64 native build set up yet.
cd ~/Coding/glow-academic-api
docker build --platform linux/amd64 -f core/Dockerfile -t glow-api-local:v1.0.6 .

# 2. Confirm the image's /app/uploads is empty and the bake landed at /app/seed/uploads.
docker run --rm --platform linux/amd64 --entrypoint sh glow-api-local:v1.0.6 \
  -c 'ls /app/uploads || echo EMPTY; ls /app/seed/uploads/themes 2>/dev/null | head -3'
# Expected: EMPTY (or the dir is empty), then themes content visible at /app/seed/uploads/themes

# 3. Rebuild the glow CLI from source so it picks up the new compose template.
cd ~/Coding/glow-academic-cli
cargo build --release

# 4. Fresh deploy targeting the local image. Repro the original failure
#    scenario from the bug report.
mkdir -p ~/.glow/instances/v106-test
sed -e 's#http://localhost:6060#http://localhost:6090#' \
    -e 's#api-version.*#api-version: local#' \
  ~/.glow/instances/f2-test/glow-deploy.yaml > ~/.glow/instances/v106-test/glow-deploy.yaml

# Force amd64 on Apple Silicon until multi-arch is published:
export DOCKER_DEFAULT_PLATFORM=linux/amd64
export API_REGISTRY=docker.io   # arbitrary; we'll point at the local tag
export API_IMAGE=glow-api-local
export API_VERSION=v1.0.6

target/release/glow deploy --name v106-test --api-version v1.0.6 -y
```

**Pass criteria:**
- `docker compose up -d` exits 0 (no `failed to mkdir … themes: file exists`)
- All containers reach `running`: `docker ps --filter name=glow-v106-test` shows green / blue server, keycloak, database, redis, pgbouncer, traefik
- Volume populated: `docker run --rm -v glow-v106-test-api_uploads:/v alpine ls /v/themes` lists the glow theme
- Keycloak login page renders the themed UI

**Cleanup:**

```bash
docker ps -aq --filter name=glow-v106-test | xargs -r docker rm -f
docker volume ls -q --filter name=glow-v106-test | xargs -r docker volume rm
docker network ls -q --filter name=glow-v106-test | xargs -r docker network rm
rm -rf ~/.glow/instances/v106-test
```

## Test 2 — Issue 1 (multi-arch publish)

This can only be fully validated via CI run (the workflow needs to push
to ghcr.io, which requires the secret). Local dry-run validation:

```bash
# Confirm the buildx build cross-compiles arm64 from an amd64 host
# (or vice versa). --load doesn't work for multi-arch; use --push to
# a registry, or --output type=oci,dest=...tar to inspect locally.
cd ~/Coding/glow-academic-api
docker buildx create --use --name multiarch-test 2>/dev/null || docker buildx use multiarch-test
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -f core/Dockerfile \
  -t glow-api-multiarch:test \
  --output type=oci,dest=/tmp/glow-api-multiarch.tar \
  .

# Inspect the manifest list (should show two manifests, one per platform)
tar -xf /tmp/glow-api-multiarch.tar -C /tmp/glow-multiarch-extract index.json
cat /tmp/glow-multiarch-extract/index.json | jq '.manifests[].platform'
# Expected: {"architecture":"amd64","os":"linux"} and {"architecture":"arm64","os":"linux"}
```

**Full validation:** push a v1.0.6-rc tag, watch the GitHub Actions
pipeline run, then on an Apple Silicon host:

```bash
docker pull --platform linux/arm64 ghcr.io/glow-academic/api:v1.0.6-rc
docker image inspect ghcr.io/glow-academic/api:v1.0.6-rc --format '{{.Os}}/{{.Architecture}}'
# Expected: linux/arm64
```

Once that works, an Apple Silicon `glow deploy --api-version v1.0.6` will
no longer need `DOCKER_DEFAULT_PLATFORM=linux/amd64` — the native arm64
manifest is pulled directly.

## Why no Python code changes

Earlier draft of this fix proposed adding a `SEED_ASSET_DIR` constant
to `core/app/infra/globals.py`. That turned out to be unnecessary:
`grep -rn "uploads/themes" core/ database/` shows no Python code reads
themes. The themes are consumed only by Keycloak (via the
`uploads:/opt/keycloak/data/uploads:ro` mount). The image bake's only
job is to populate the runtime named volume on first deploy — moving
the bake path doesn't require any Python knowledge of where it lives.
