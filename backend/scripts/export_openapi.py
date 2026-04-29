#!/usr/bin/env python3
"""Export the bxChange OpenAPI schema to stdout as JSON.

Usage:
    # From the repo root
    python backend/scripts/export_openapi.py > openapi.json

    # Import into Postman / Insomnia / OpenAPI Generator
    openapi-generator generate -i openapi.json -g python -o sdk/python

The script provides minimal stub env vars so the Settings class does not
fail at import time. Real DB/Redis connections are never made.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://localhost/bxchange_db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "export-placeholder-not-used")
os.environ.setdefault("ENCRYPTION_KEY", "a" * 64)

from app.main import app  # noqa: E402

if __name__ == "__main__":
    schema = app.openapi()
    json.dump(schema, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
