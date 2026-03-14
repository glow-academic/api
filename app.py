"""Minimal GLOW API test service — health + echo endpoints."""

import json
import os
from pathlib import Path

from fastapi import FastAPI, Query

app = FastAPI(title="GLOW API", version="0.1.0")

CONFIG_PATH = Path(".learnloop/config.json")


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {}


@app.get("/health")
def health():
    config = _load_config()
    return {
        "status": "ok",
        "service": "glow-api",
        "deployment": config.get("deployment_name", "unknown"),
    }


@app.get("/echo")
def echo(msg: str = Query(default="hello")):
    return {"echo": msg}


@app.get("/config")
def get_config():
    return _load_config()
