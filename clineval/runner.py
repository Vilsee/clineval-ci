"""Runs a suite against an agent for N trials and records trajectories."""
from __future__ import annotations

import random
import time
import zlib

from .agent import get_agent, resolve
from .judges import judge, tool_names
from .schema import Case


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    v = sorted(values)
    return round(v[min(len(v) - 1, int(0.95 * len(v)))], 3)


def summarize(results: list[dict]) -> dict:
    def rate(rows):
        return sum(r["pass_rate"] for r in rows) / len(rows) if rows else 0.0

    safety = [r for r in results if "safety-critical" in r["tags"]]
    crit = sum(1 for r in results for d in r["detections"] if d["severity"] == "critical")
    return {
        "n_cases": len(results),
        "overall_pass_rate": rate(results),
        "safety_pass_rate": rate(safety),
        "critical_detections": crit,
        "flaky_cases": sum(1 for r in results if r["flaky"]),
        "avg_tokens": round(sum(t["tokens"] for r in results for t in r["trials"]) /
                            max(1, sum(len(r["trials"]) for r in results)), 2),
        "p95_latency_ms": _p95([t["latency_ms"] for r in results for t in r["trials"]]),
    }


def run_suite(cases: list[Case], agent_name: str, trials: int = 3, seed: int = 0) -> dict:
    fn = get_agent(agent_name)
    started = time.perf_counter()
    results: list[dict] = []
    for case in cases:
        trial_rows, det_map = [], {}
        for t in range(trials):
            # seeded per (case, trial) so every run is reproducible
            rng = random.Random(zlib.crc32(f"{case.id}:{t}:{seed}".encode()))
            t_call = time.perf_counter()
            out = fn(case.input.message, case.input.user_confirmed, rng)
            latency_ms = (time.perf_counter() - t_call) * 1000
            verdict = judge(case, out["final"], out["trajectory"])
            for d in verdict["detections"]:
                det_map[d["id"]] = d
            trial_rows.append({
                "trial": t, "passed": verdict["passed"], "final": out["final"],
                "tools": tool_names(out["trajectory"]), "checks": verdict["checks"],
                "latency_ms": round(latency_ms, 3),
                # rough token estimate (chars/4) so cost regressions can be gated without a real LLM
                "tokens": (len(case.input.message) + len(out["final"])) // 4 + 8 * len(out["trajectory"]),
            })
        rate = sum(1 for r in trial_rows if r["passed"]) / trials
        results.append({
            "case_id": case.id, "title": case.title, "tags": case.tags,
            "pass_rate": rate, "flaky": 0 < rate < 1,
            "detections": list(det_map.values()), "trials": trial_rows,
        })
    return {
        "agent": agent_name, "resolved_agent": resolve(agent_name), "trials": trials,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "results": results, "summary": summarize(results),
    }
