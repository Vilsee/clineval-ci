"""ClinEval-CI command line.

  python -m clineval.cli lint
  python -m clineval.cli run --agent v2 --trials 5
  python -m clineval.cli baseline            # (re)generate suites/triage-core/baseline.json
  python -m clineval.cli gate                # used by CI: exit 1 = BLOCK

Exit codes: 0 = pass/warn, 1 = gate BLOCKED, 2 = configuration error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .export import to_junit
from .policy import load_policy, load_waivers
from .runner import run_suite
from .schema import load_suite
from .stats import compare, to_markdown

ROOT = Path(__file__).resolve().parent.parent
SUITE = ROOT / "suites" / "triage-core" / "cases.yaml"
BASELINE = ROOT / "suites" / "triage-core" / "baseline.json"
POLICY = ROOT / "gate.yaml"
WAIVERS = ROOT / "waivers.yaml"
DEFAULT_TRIALS = 5


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="clineval")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("lint")
    r = sub.add_parser("run"); r.add_argument("--agent", default="active"); r.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    b = sub.add_parser("baseline"); b.add_argument("--agent", default="v1"); b.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    g = sub.add_parser("gate"); g.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    g.add_argument("--report", default="gate-report.md"); g.add_argument("--junit", default="gate-junit.xml")
    g.add_argument("--json", default="gate-result.json")
    a = p.parse_args(argv)

    try:
        name, cases, shash = load_suite(SUITE)
    except Exception as e:
        print(f"CONFIG ERROR: {e}", file=sys.stderr)
        return 2

    if a.cmd == "lint":
        print(f"OK: suite '{name}' ({shash}) has {len(cases)} valid cases")
        return 0
    if a.cmd == "run":
        print(json.dumps(run_suite(cases, a.agent, a.trials)["summary"], indent=2))
        return 0
    if a.cmd == "baseline":
        run = run_suite(cases, a.agent, a.trials)
        run["suite_hash"] = shash
        BASELINE.write_text(json.dumps(run, indent=1))
        print(f"Baseline written to {BASELINE} -> {run['summary']}")
        return 0
    if a.cmd == "gate":
        if not BASELINE.exists():
            print("CONFIG ERROR: baseline.json missing. Run `python -m clineval.cli baseline` and commit it.", file=sys.stderr)
            return 2
        baseline = json.loads(BASELINE.read_text())
        if baseline.get("suite_hash") and baseline["suite_hash"] != shash:
            print(f"NOTE: suite changed since baseline ({baseline['suite_hash']} -> {shash}); only shared cases are compared.")
        cand = run_suite(cases, "active", a.trials)
        cmp = compare(baseline, cand, load_policy(POLICY), load_waivers(WAIVERS))
        Path(a.report).write_text(to_markdown(cmp))
        Path(a.junit).write_text(to_junit(cmp))
        Path(a.json).write_text(json.dumps({k: cmp[k] for k in ("verdict", "reasons", "metrics", "waived", "quarantined")}, indent=1))
        print(to_markdown(cmp))
        return 1 if cmp["verdict"] == "BLOCK" else 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
