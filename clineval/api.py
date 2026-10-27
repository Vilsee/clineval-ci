"""FastAPI backend + static UI (landing page at / and dashboard at /app)."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import ACTIVE_VERSION, AGENTS, get_agent
from .export import evidence_bundle, to_junit
from .judges import tool_names
from .policy import load_policy
from .runner import run_suite
from .schema import Case, lint_cases, load_suite
from .stats import compare, to_markdown
from .store import Store

ROOT = Path(__file__).resolve().parent.parent
SUITE_PATH = ROOT / "suites" / "triage-core" / "cases.yaml"
POLICY_PATH = ROOT / "gate.yaml"
STATIC = ROOT / "public"
store = Store(os.getenv("CLINEVAL_DB", str(ROOT / "data" / "clineval.db")))

app = FastAPI(title="ClinEval-CI", version="0.3.0",
              description="Regression gate for clinical LLM agents (synthetic data only).")

# Read-only cross-origin access (lets the demo page health-check another deployment, e.g. the Azure VM).
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


def seed_demo(st: Store | None = None) -> bool:
    """Idempotently create the demo baseline (v1) and a regressed candidate (v2). Returns True if seeded."""
    st = st or store
    if st.list_runs():
        return False
    name, cases, shash = load_suite(SUITE_PATH)
    for agent, is_base in (("v1", True), ("v2", False)):
        rid = st.save_run(run_suite(cases, agent, 5), name, shash)
        if is_base:
            st.set_baseline(rid)
    return True


if os.getenv("CLINEVAL_AUTOSEED") == "1":   # serverless: fresh /tmp database on every cold start
    seed_demo()


class RunRequest(BaseModel):
    agent: str = "v1"
    trials: int = Field(5, ge=1, le=20)
    set_baseline: bool = False


class TryRequest(BaseModel):
    agent: str = "v1"
    message: str = Field(..., min_length=1, max_length=500)
    confirmed: bool = False


class SimRequest(BaseModel):
    agent: str = "v2"
    trials: int = Field(5, ge=1, le=10)


class LintRequest(BaseModel):
    yaml: str = Field(..., max_length=20000)


class WaiverRequest(BaseModel):
    case_id: str
    reason: str = Field(..., min_length=3, max_length=300)
    approver: str = Field(..., min_length=2, max_length=80)
    expires_at: str  # YYYY-MM-DD


def _policy() -> dict:
    return load_policy(POLICY_PATH)


def _cmp(b_id: int, c_id: int) -> dict:
    b, c = store.get_run(b_id), store.get_run(c_id)
    if not b or not c:
        raise HTTPException(404, "run not found")
    return compare(b, c, _policy(), store.list_waivers())


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "clineval-ci", "version": app.version, "active_agent": ACTIVE_VERSION}


@app.get("/api/suite")
def suite():
    name, cases, shash = load_suite(SUITE_PATH)
    return {"name": name, "hash": shash, "n_cases": len(cases),
            "cases": [c.model_dump() for c in cases], "agents": sorted(AGENTS) + ["active"]}


@app.get("/api/policy")
def policy():
    return _policy()


@app.post("/api/run")
def run(req: RunRequest):
    if req.agent not in list(AGENTS) + ["active"]:
        raise HTTPException(400, f"unknown agent '{req.agent}'")
    name, cases, shash = load_suite(SUITE_PATH)
    result = run_suite(cases, req.agent, req.trials)
    rid = store.save_run(result, name, shash)
    if req.set_baseline or store.get_baseline_id() is None:   # first ever run becomes the baseline
        store.set_baseline(rid)
    base_id = store.get_baseline_id()
    gate = None
    if base_id and base_id != rid:
        cmp = _cmp(base_id, rid)
        gate = {"verdict": cmp["verdict"], "reasons": cmp["reasons"]}
    return {"id": rid, "agent": result["resolved_agent"], "summary": result["summary"],
            "baseline_id": base_id, "gate": gate}


@app.get("/api/runs")
def runs():
    return {"baseline_id": store.get_baseline_id(), "runs": store.list_runs()}


@app.get("/api/runs/{rid}")
def get_run(rid: int):
    r = store.get_run(rid)
    if not r:
        raise HTTPException(404, "run not found")
    return r


@app.post("/api/baseline/{rid}")
def set_baseline(rid: int):
    if not store.get_run(rid):
        raise HTTPException(404, "run not found")
    store.set_baseline(rid)
    return {"baseline_id": rid}


@app.get("/api/compare")
def compare_runs(candidate: int, baseline: int | None = None):
    base = baseline or store.get_baseline_id()
    if not base:
        raise HTTPException(400, "no baseline yet; run the suite first")
    return _cmp(base, candidate)


@app.get("/api/compare/report.md")
def compare_report(candidate: int, baseline: int | None = None):
    base = baseline or store.get_baseline_id()
    if not base:
        raise HTTPException(400, "no baseline yet")
    return PlainTextResponse(to_markdown(_cmp(base, candidate)), media_type="text/markdown",
                             headers={"Content-Disposition": "attachment; filename=clineval-report.md"})


@app.get("/api/compare/junit.xml")
def compare_junit(candidate: int, baseline: int | None = None):
    base = baseline or store.get_baseline_id()
    if not base:
        raise HTTPException(400, "no baseline yet")
    return Response(to_junit(_cmp(base, candidate)), media_type="application/xml",
                    headers={"Content-Disposition": "attachment; filename=clineval-junit.xml"})


@app.post("/api/try")
def try_agent(req: TryRequest):
    """Playground: send one message to an agent and see the final answer + tool calls."""
    if req.agent not in list(AGENTS) + ["active"]:
        raise HTTPException(400, f"unknown agent '{req.agent}'")
    import random
    out = get_agent(req.agent)(req.message, req.confirmed, random.Random(7))
    return {"final": out["final"], "tools": tool_names(out["trajectory"]), "trajectory": out["trajectory"]}


@app.post("/api/lint")
def lint(req: LintRequest):
    """Case-authoring helper: validate pasted YAML (one case or a list) without saving."""
    try:
        data = yaml.safe_load(req.yaml)
        items = data["cases"] if isinstance(data, dict) and "cases" in data else data
        items = items if isinstance(items, list) else [items]
        cases = [Case(**i) for i in items]
    except Exception as e:  # schema / yaml problems
        return {"ok": False, "problems": [str(e).splitlines()[0][:300]]}
    problems = lint_cases(cases)
    return {"ok": not problems, "problems": problems, "n_cases": len(cases)}


@app.post("/api/gate/simulate")
def simulate(req: SimRequest):
    """Stateless 'pull request' simulation: baseline v1 vs the chosen agent, same gate as the CLI."""
    if req.agent not in list(AGENTS) + ["active"]:
        raise HTTPException(400, f"unknown agent '{req.agent}'")
    _, cases, _ = load_suite(SUITE_PATH)
    base = run_suite(cases, "v1", req.trials)
    cand = run_suite(cases, req.agent, req.trials)
    cmp = compare(base, cand, _policy(), store.list_waivers())
    return {"verdict": cmp["verdict"], "exit_code": 1 if cmp["verdict"] == "BLOCK" else 0,
            "candidate_agent": cmp["candidate_agent"], "reasons": cmp["reasons"], "metrics": cmp["metrics"],
            "new_critical": cmp["new_critical"], "cases": cmp["cases"],
            "report": to_markdown(cmp), "junit": to_junit(cmp)}


@app.post("/api/demo/seed")
def demo_seed():
    return {"seeded": seed_demo(), "baseline_id": store.get_baseline_id(), "runs": len(store.list_runs())}


@app.get("/api/waivers")
def waivers():
    return store.list_waivers()


@app.post("/api/waivers")
def add_waiver(w: WaiverRequest):
    try:
        date.fromisoformat(w.expires_at)
    except ValueError:
        raise HTTPException(400, "expires_at must be YYYY-MM-DD")
    _, cases, _ = load_suite(SUITE_PATH)
    if w.case_id not in {c.id for c in cases}:
        raise HTTPException(400, f"unknown case '{w.case_id}'")
    return {"id": store.add_waiver(w.case_id, w.reason, w.approver, w.expires_at)}


@app.delete("/api/waivers/{wid}")
def delete_waiver(wid: int):
    if not store.delete_waiver(wid):
        raise HTTPException(404, "waiver not found")
    return {"deleted": wid}


@app.get("/api/audit")
def audit():
    return store.verify_chain()


@app.get("/api/evidence")
def evidence():
    name, cases, shash = load_suite(SUITE_PATH)
    base_id = store.get_baseline_id()
    latest = store.list_runs()
    cmp = _cmp(base_id, latest[0]["id"]) if base_id and latest and latest[0]["id"] != base_id else None
    bundle = evidence_bundle(
        suite={"name": name, "hash": shash, "n_cases": len(cases)}, policy=_policy(),
        baseline=store.get_run(base_id) if base_id else None, waivers=store.list_waivers(),
        audit={k: v for k, v in store.verify_chain().items() if k != "entries"}, latest_comparison=cmp)
    return Response(__import__("json").dumps(bundle, indent=2), media_type="application/json",
                    headers={"Content-Disposition": "attachment; filename=clineval-evidence.json"})


@app.get("/app", include_in_schema=False)
def dashboard():
    return FileResponse(STATIC / "app.html")


@app.get("/demo", include_in_schema=False)
def demo_page():
    return FileResponse(STATIC / "demo.html")


if STATIC.exists():
    app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="static")
