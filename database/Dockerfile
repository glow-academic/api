# syntax=docker/dockerfile:1.7
FROM postgres:18-alpine

# ──────────────────────────────────────────────────────────
# 1️⃣  Extra packages (bash and nodejs) – put in one RUN layer
# ──────────────────────────────────────────────────────────
RUN apk add --no-cache bash nodejs npm util-linux

# ──────────────────────────────────────────────────────────
# 2️⃣  Non-root user (optional, Postgres runs as postgres:999 by default)
# ──────────────────────────────────────────────────────────
# PostgreSQL official image already runs as postgres user (uid=999, gid=999)
# Uncomment below if you need a different user setup
# RUN addgroup -S db && adduser -S db -G db
# USER db

# ──────────────────────────────────────────────────────────
# 3️⃣  Runtime directories & volume
# ──────────────────────────────────────────────────────────
WORKDIR /database
RUN mkdir -p /database/history
VOLUME ["/var/lib/postgresql"]

# ──────────────────────────────────────────────────────────
# 4️⃣  Seed & helper scripts
# ──────────────────────────────────────────────────────────
# • Every file ending in .sql, .sql.gz, or .sh placed inside
#   /docker-entrypoint-initdb.d is executed *once* on first-time
#   container start (not on restart). No extra entrypoint needed.
# Copy seeds directory (creates /database/seeds/ automatically)
# If seeds/ doesn't exist in build context, this will fail
# Ensure seeds/ directory exists in database/ folder before building
COPY schema.sql /database/schema.sql
COPY seeds/ /database/seeds/
COPY scripts/sql-helpers.sh         /docker-entrypoint-initdb.d/
COPY scripts/custom-entrypoint.sh   /usr/local/bin/custom-entrypoint.sh

# Make scripts executable in a single layer
RUN chmod +x /usr/local/bin/custom-entrypoint.sh && \
    chmod +x /docker-entrypoint-initdb.d/sql-helpers.sh && \
    chown -R postgres:postgres /docker-entrypoint-initdb.d/ && \
    chown -R postgres:postgres /database/ && \
    chown -R postgres:postgres /database/seeds/

# Set default environment variables for development
# (These can be overridden at runtime via docker run -e or docker-compose)
ENV POSTGRES_USER=myuser
ENV POSTGRES_PASSWORD=mypassword
ENV POSTGRES_DB=mydb
ENV HISTORY_DIR=/database/history

# If you still need logic that must run on every start (not just first-time init)
ENTRYPOINT ["custom-entrypoint.sh"]     # delegates to postgress entrypoint
CMD ["postgres"]

# ──────────────────────────────────────────────────────────
# 5️⃣  Health-check with runtime variable support
# ──────────────────────────────────────────────────────────
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=5 \
  CMD pg_isready -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-postgres}"