"""Gate policy and waiver loading."""
from __future__ import annotations

from pathlib import Path

import yaml

DEFAULTS = {
    "tolerance": 0.0, "confidence": 0.95, "bootstrap_samples": 5000, "min_cases": 5,
    "block_on_critical": True, "quarantine_flaky": True, "max_token_ratio": 1.5,
}


def load_policy(path: str | Path | None = None) -> dict:
    pol = dict(DEFAULTS)
    if path and Path(path).exists():
        pol.update(yaml.safe_load(Path(path).read_text()) or {})
    return pol


def load_waivers(path: str | Path | None = None) -> list[dict]:
    if path and Path(path).exists():
        data = yaml.safe_load(Path(path).read_text()) or {}
        return [{**w, "expires_at": str(w.get("expires_at", ""))} for w in data.get("waivers", [])]
    return []
