# Glow — API

Glow is source-available for academic, research, educational, and other noncommercial use under the [PolyForm Noncommercial License 1.0.0](./LICENSE).

Commercial use requires a separate written license from Purdue Research Foundation / Purdue University. Contact: ashok@learn-loop.org.

This repository contains the **API server** — the FastAPI backend that powers a Glow deployment. It is one of four components in the Glow platform:

| Component | What it is |
|---|---|
| **api** (this repo) | FastAPI backend, postgres, keycloak, blue/green deploy |
| [client](https://github.com/glow-academic/client) | Next.js frontend |
| [cli](https://github.com/glow-academic/cli) | Rust CLI — the canonical deploy + management tool |
| [docs](https://github.com/glow-academic/docs) | Nextra docs site |

## Running a Glow deployment

End users do not run this repo directly. The supported install path is the CLI:

```bash
brew tap glow-academic/tap
brew install glow
glow init       # interactive wizard writes ~/.glow/instances/default/glow-deploy.yaml
glow deploy     # pulls the api image, brings up the stack
```

See the [docs](https://glow-academic.github.io/docs/) for the full deployment guide.

## Local development

```bash
make setup       # creates .venv, installs deps
cp .env.example .env
make run         # starts redis + uvicorn + keycloak + database logs in foreground
```

## License

This project is licensed under the [PolyForm Noncommercial License 1.0.0](./LICENSE).

This is not an OSI-approved open-source license. It is intended to support academic and research dissemination while preserving separate commercial licensing rights.
