"""Minimal mock Salesforce REST API for local development.

Serves the JSON the generator wrote under ``DATA_DIR`` (mounted read-only),
emulating the two things that make a real Salesforce extractor non-trivial:
  1. **incremental** pulls  -> ?since=<ISO8601> filters on SystemModstamp
  2. **pagination**         -> ?limit=&offset= with a nextRecordsUrl-style cursor

Auth is a token check (Authorization: Bearer <SF_API_TOKEN>) so the Phase 5
extractor exercises Secret Manager wiring. This is NOT Salesforce-accurate — it's
just faithful to the ingestion patterns we want to build and test.

Endpoints:
  GET /health
  GET /api/objects
  GET /api/<object>?since=&limit=&offset=
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from flask import Flask, jsonify, request

app = Flask(__name__)

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
API_TOKEN = os.environ.get("SF_API_TOKEN", "local-dev-token")
DEFAULT_LIMIT = 200

# generator entity file -> Salesforce-ish object name
OBJECTS = {
    "Customer": "customer",
    "Account": "account",
    "SalesRep": "sales_rep",
    "Credit": "credit",
}


def _latest_date_dir() -> Path | None:
    if not DATA_DIR.is_dir():
        return None
    dirs = sorted((p for p in DATA_DIR.iterdir() if p.is_dir()), reverse=True)
    return dirs[0] if dirs else None


def _load(entity_file: str) -> list[dict]:
    day = _latest_date_dir()
    if day is None:
        return []
    path = day / f"{entity_file}.json"
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("records", payload if isinstance(payload, list) else [])


def _authorized() -> bool:
    auth = request.headers.get("Authorization", "")
    return auth == f"Bearer {API_TOKEN}"


@app.get("/health")
def health():
    return jsonify(status="ok", data_dir=str(DATA_DIR), latest=str(_latest_date_dir()))


@app.get("/api/objects")
def objects():
    return jsonify(sorted(OBJECTS))


@app.get("/api/<object_name>")
def query(object_name: str):
    if not _authorized():
        return jsonify(error="unauthorized", message="Bearer token required"), 401
    if object_name not in OBJECTS:
        return jsonify(error="not_found", object=object_name, valid=sorted(OBJECTS)), 404

    records = _load(OBJECTS[object_name])

    since = request.args.get("since")
    if since:
        records = [r for r in records if str(r.get("SystemModstamp", "")) > since]

    try:
        limit = min(int(request.args.get("limit", DEFAULT_LIMIT)), 2000)
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return jsonify(error="bad_request", message="limit/offset must be integers"), 400

    page = records[offset : offset + limit]
    next_offset = offset + limit
    done = next_offset >= len(records)
    body = {
        "object": object_name,
        "totalSize": len(records),
        "done": done,
        "records": page,
    }
    if not done:
        body["nextRecordsUrl"] = (
            f"/api/{object_name}?since={since or ''}&limit={limit}&offset={next_offset}"
        )
    return jsonify(body)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
