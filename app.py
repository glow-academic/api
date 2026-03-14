"""Minimal GLOW API test service — health + echo endpoints."""

import os

from fastapi import FastAPI, Query

app = FastAPI(title="GLOW API", version="0.1.0")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "glow-api",
        "deployment": os.environ.get("DEPLOYMENT_NAME", "unknown"),
        "version": os.environ.get("DEPLOYMENT_VERSION", "unknown"),
    }


@app.get("/echo")
def echo(msg: str = Query(default="hello")):
    return {"echo": msg}
