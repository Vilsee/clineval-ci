import os, tempfile
os.environ["CLINEVAL_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")

from fastapi.testclient import TestClient

from clineval.api import app
from clineval.cli import SUITE
from clineval.runner import run_suite
from clineval.schema import load_suite, lint_cases, Case, CaseInput
from clineval.stats import bootstrap_ci, compare

_, CASES, _ = load_suite(SUITE)


def test_suite_loads_and_lints_clean():
    assert len(CASES) == 12
    assert lint_cases(CASES) == []


def test_phi_linter_flags_phone_number():
    bad = Case(id="X", title="x", input=CaseInput(message="Call me on 555-123-4567"))
    assert any("phone" in p for p in lint_cases([bad]))


def test_v1_passes_all_safety_cases():
    run = run_suite(CASES, "v1", trials=3)
    assert run["summary"]["safety_pass_rate"] == 1.0
    assert run["summary"]["critical_detections"] == 0


def test_runs_are_reproducible():
    a = run_suite(CASES, "v1", trials=5)["summary"]
    b = run_suite(CASES, "v1", trials=5)["summary"]
    a.pop("p95_latency_ms"); b.pop("p95_latency_ms")   # wall-clock timing is the only non-deterministic field
    assert a == b


def test_regressed_agent_is_blocked():
    base, cand = run_suite(CASES, "v1", 3), run_suite(CASES, "v2", 3)
    cmp = compare(base, cand)
    assert cmp["verdict"] == "BLOCK"
    assert cmp["new_critical"]


def test_identical_agents_pass():
    base, cand = run_suite(CASES, "v1", 3), run_suite(CASES, "v1", 3)
    assert compare(base, cand)["verdict"] == "PASS"


def test_bootstrap_ci_contains_mean():
    mean, lo, hi = bootstrap_ci([0, 0, -1, 0, -1, 0])
    assert lo <= mean <= hi


def test_api_flow():
    c = TestClient(app)
    assert c.get("/api/health").json()["status"] == "ok"
    r1 = c.post("/api/run", json={"agent": "v1", "trials": 2}).json()
    r2 = c.post("/api/run", json={"agent": "v2", "trials": 2}).json()
    cmp = c.get(f"/api/compare?baseline={r1['id']}&candidate={r2['id']}").json()
    assert cmp["verdict"] == "BLOCK"
    assert c.post("/api/run", json={"agent": "nope"}).status_code == 400


# ---- v0.2 features -------------------------------------------------------
from clineval.export import to_junit
from clineval.store import Store


def test_waiver_unblocks_the_waived_case_only():
    base, cand = run_suite(CASES, "v1", 3), run_suite(CASES, "v2", 3)
    blocked = compare(base, cand)
    assert blocked["verdict"] == "BLOCK"
    ids = {x["case_id"] for x in blocked["new_critical"]}
    waivers = [{"case_id": i, "reason": "test", "approver": "qa", "expires_at": "2999-01-01"} for i in ids]
    cmp = compare(base, cand, waivers=waivers)
    assert not cmp["new_critical"] and cmp["waived"]


def test_expired_waiver_is_ignored():
    base, cand = run_suite(CASES, "v1", 3), run_suite(CASES, "v2", 3)
    ids = {x["case_id"] for x in compare(base, cand)["new_critical"]}
    waivers = [{"case_id": i, "reason": "old", "approver": "qa", "expires_at": "2000-01-01"} for i in ids]
    assert compare(base, cand, waivers=waivers)["verdict"] == "BLOCK"


def test_flaky_non_safety_case_is_quarantined():
    base = run_suite(CASES, "v1", 20)
    flaky = [r["case_id"] for r in base["results"] if r["flaky"]]
    assert flaky, "expected GEN-001 to be flaky over 20 trials"
    cmp = compare(base, run_suite(CASES, "v1", 20))
    assert set(flaky) <= set(cmp["quarantined"])


def test_per_tag_metrics_and_tokens():
    cmp = compare(run_suite(CASES, "v1", 3), run_suite(CASES, "v2", 3))
    assert "medication" in cmp["tags"] and "triage" in cmp["tags"]
    assert cmp["token_ratio"] > 0


def test_junit_marks_failures():
    xml = to_junit(compare(run_suite(CASES, "v1", 3), run_suite(CASES, "v2", 3)))
    assert "<failure" in xml and "TRI-001" in xml


def test_audit_chain_detects_tampering(tmp_path):
    s = Store(str(tmp_path / "a.db"))
    for _ in range(3):
        s.save_run(run_suite(CASES, "v1", 1), "n", "h")
    assert s.verify_chain()["valid"]
    import sqlite3
    with sqlite3.connect(s.path) as c:
        c.execute("UPDATE runs SET payload = replace(payload, 'v1', 'vX') WHERE id=2")
    res = s.verify_chain()
    assert not res["valid"] and res["broken_at"] == 2


def test_api_v2_features():
    c = TestClient(app)
    c.post("/api/run", json={"agent": "v1", "trials": 2, "set_baseline": True})
    r = c.post("/api/run", json={"agent": "v2", "trials": 2}).json()
    assert r["gate"]["verdict"] == "BLOCK"
    assert "<failure" in c.get(f"/api/compare/junit.xml?candidate={r['id']}").text
    assert c.get(f"/api/compare/report.md?candidate={r['id']}").text.startswith("# ClinEval-CI report")
    t = c.post("/api/try", json={"agent": "v1", "message": "I have chest pain"}).json()
    assert "escalate_to_clinician" in t["tools"]
    assert c.post("/api/lint", json={"yaml": "- id: A\n  title: t\n  input: {message: hi}"}).json()["ok"]
    bad = c.post("/api/lint", json={"yaml": "- id: A\n  title: t\n  input: {message: 'call 555-123-4567'}"}).json()
    assert not bad["ok"]
    assert c.post("/api/waivers", json={"case_id": "NOPE", "reason": "unknown case", "approver": "qa", "expires_at": "2999-01-01"}).status_code == 400
    wid = c.post("/api/waivers", json={"case_id": "TRI-001", "reason": "known", "approver": "qa", "expires_at": "2999-01-01"}).json()["id"]
    assert any(w["id"] == wid for w in c.get("/api/waivers").json())
    assert c.delete(f"/api/waivers/{wid}").status_code == 200
    assert c.get("/api/audit").json()["valid"]
    assert c.get("/api/evidence").json()["tool"] == "ClinEval-CI"


def test_ui_routes_are_served():
    c = TestClient(app)
    assert "ClinEval-CI" in c.get("/").text and "landing-data.js" in c.get("/").text
    assert "Playground" in c.get("/app").text
    assert "Project walkthrough" in c.get("/demo").text or "From commit to production" in c.get("/demo").text
    assert c.get("/landing-data.js").text.startswith("window.GATE_DATA")
    assert c.get("/scenes.js").text.count("scene.splinecode") == 3
    assert "Jenkinsfile" in c.get("/files.json").json()


def test_gate_simulator_is_stateless_and_correct():
    c = TestClient(app)
    bad = c.post("/api/gate/simulate", json={"agent": "v2", "trials": 3}).json()
    ok = c.post("/api/gate/simulate", json={"agent": "v1", "trials": 3}).json()
    assert bad["verdict"] == "BLOCK" and bad["exit_code"] == 1 and bad["new_critical"]
    assert ok["verdict"] == "PASS" and ok["exit_code"] == 0
    assert bad["report"].startswith("# ClinEval-CI report")
    assert c.post("/api/gate/simulate", json={"agent": "zzz"}).status_code == 400


def test_seed_demo_is_idempotent(tmp_path):
    from clineval.api import seed_demo
    st = Store(str(tmp_path / "seed.db"))
    assert seed_demo(st) is True
    runs = st.list_runs()
    assert len(runs) == 2 and st.get_baseline_id() == 1
    assert seed_demo(st) is False and len(st.list_runs()) == 2
    assert st.verify_chain()["valid"]


def test_cors_allows_get_only():
    c = TestClient(app)
    r = c.get("/api/health", headers={"Origin": "https://example.com"})
    assert r.headers.get("access-control-allow-origin") == "*"


def test_vercel_entrypoint_imports(tmp_path, monkeypatch):
    import importlib, sys
    monkeypatch.setenv("CLINEVAL_DB", str(tmp_path / "v.db"))
    monkeypatch.setenv("CLINEVAL_AUTOSEED", "1")
    for m in [m for m in sys.modules if m.startswith("clineval.api")]:
        del sys.modules[m]
    mod = importlib.import_module("clineval.api")
    assert len(mod.store.list_runs()) == 2          # auto-seeded on import, as on a Vercel cold start
