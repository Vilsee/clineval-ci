"""Vercel serverless entrypoint: exposes the FastAPI app as an ASGI function.

Vercel's filesystem is read-only except /tmp, so the SQLite file lives in /tmp and the app
re-seeds the demo runs on every cold start (runs are deterministic, so ids are stable).
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("CLINEVAL_DB", "/tmp/clineval.db")
os.environ.setdefault("CLINEVAL_AUTOSEED", "1")

from clineval.api import app  # noqa: E402,F401
