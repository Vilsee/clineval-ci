"""Regenerates public/landing-data.js from REAL runs so the landing-page
fragment shows true gate output. Run:  python scripts/build_landing_data.py"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from clineval.runner import run_suite
from clineval.schema import load_suite
from clineval.stats import compare

_, cases, shash = load_suite(ROOT / "suites/triage-core/cases.yaml")
base = run_suite(cases, "v1", 5)
out = {"suite_hash": shash, "agents": {}}
for name in ("v1", "v2"):
    run = base if name == "v1" else run_suite(cases, "v2", 5)
    cmp = compare(base, run)
    out["agents"][name] = {
        "verdict": cmp["verdict"], "summary": run["summary"],
        "safety": cmp["metrics"]["safety"], "overall": cmp["metrics"]["overall"],
        "n_new_critical": len(cmp["new_critical"]),
        "cases": [{"id": r["case_id"], "title": r["title"], "rate": r["pass_rate"],
                   "detections": [d["id"] for d in r["detections"]],
                   "final": r["trials"][0]["final"], "tools": r["trials"][0]["tools"]} for r in run["results"]],
        "report": __import__("clineval.stats", fromlist=["to_markdown"]).to_markdown(cmp),
    }
(ROOT / "public/landing-data.js").write_text("window.GATE_DATA = " + json.dumps(out, indent=1) + ";\n")
print("wrote landing-data.js")
