"""Test-case schema, loader and linter for ClinEval-CI."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

SEVERITIES = {"critical", "major", "minor"}
FORBIDDEN_TYPES = {"phrase", "tool", "tool_without_confirmation"}

# Very small PHI heuristic: the linter refuses cases that look like real patient data.
PHI_PATTERNS = {
    "phone number": re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b"),
    "MRN": re.compile(r"\bMRN[:#\s]*\d{5,}\b", re.I),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
}


class Forbidden(BaseModel):
    id: str
    severity: str = "major"
    type: str
    value: str = ""
    description: str = ""


class Expected(BaseModel):
    must_include: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)  # ordered subsequence


class CaseInput(BaseModel):
    message: str
    user_confirmed: bool = False


class Case(BaseModel):
    id: str
    title: str
    tags: list[str] = Field(default_factory=list)
    input: CaseInput
    expected: Expected = Field(default_factory=Expected)
    forbidden: list[Forbidden] = Field(default_factory=list)


def lint_cases(cases: list[Case]) -> list[str]:
    """Return a list of human-readable problems (empty list = clean)."""
    problems: list[str] = []
    seen: set[str] = set()
    for c in cases:
        if c.id in seen:
            problems.append(f"{c.id}: duplicate case id")
        seen.add(c.id)
        for f in c.forbidden:
            if f.severity not in SEVERITIES:
                problems.append(f"{c.id}/{f.id}: severity must be one of {sorted(SEVERITIES)}")
            if f.type not in FORBIDDEN_TYPES:
                problems.append(f"{c.id}/{f.id}: type must be one of {sorted(FORBIDDEN_TYPES)}")
        for label, pat in PHI_PATTERNS.items():
            if pat.search(c.input.message):
                problems.append(f"{c.id}: input looks like it contains a {label} (synthetic data only)")
    return problems


def load_suite(path: str | Path) -> tuple[str, list[Case], str]:
    """Load a suite YAML. Returns (name, cases, content_hash)."""
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    cases = [Case(**c) for c in data["cases"]]
    problems = lint_cases(cases)
    if problems:
        raise ValueError("Suite failed lint:\n- " + "\n- ".join(problems))
    return data.get("name", p.parent.name), cases, hashlib.sha256(raw.encode()).hexdigest()[:12]
