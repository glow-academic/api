# GLOW API

Backend services and test infrastructure for the GLOW application.

## Local Setup

Use the repository Make targets as the canonical interface:

```bash
make setup
make setup-venv
make install
make test
```

The test suite uses Docker-backed testcontainers for PostgreSQL and Redis.
