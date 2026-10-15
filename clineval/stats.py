"""Statistical regression analysis, gate policy, waivers, quarantine and markdown report."""
from __future__ import annotations

from datetime import date

import numpy as np

from .policy import DEFAULTS

ORDER = {"PASS": 0, "WARN": 1, "BLOCK": 2}


def bootstrap_ci(diffs, n_boot: int = 5000, conf: float = 0.95, seed: int = 42):
    """Paired bootstrap on per-case differences. Returns (mean, low, high)."""
    d = np.asarray(diffs, dtype=float)
    if d.size == 0:
        return 0.0, 0.0, 0.0
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, d.size, size=(n_boot, d.size))
    means = d[idx].mean(axis=1)
    a = (1 - conf) / 2
    return float(d.mean()), float(np.quantile(means, a)), float(np.quantile(means, 1 - a))


def _metric(name: str, rows_b: list[float], rows_c: list[float], pol: dict) -> dict:
    tol = pol["tolerance"]
    diffs = [c - b for b, c in zip(rows_b, rows_c)]
    mean, lo, hi = bootstrap_ci(diffs, pol["bootstrap_samples"], pol["confidence"])
    if not diffs:
        status = "n/a"
    elif hi < -tol:
        status = "confirmed regression"      # whole interval is below tolerance
    elif mean < -tol:
        status = "possible regression"       # point estimate is bad, interval overlaps 0
    else:
        status = "no evidence of regression"
    return {
        "name": name, "n": len(diffs),
        "baseline": float(np.mean(rows_b)) if rows_b else 0.0,
        "candidate": float(np.mean(rows_c)) if rows_c else 0.0,
        "diff": mean, "ci_low": lo, "ci_high": hi, "status": status,
    }


def classify(b: float, c: float) -> str:
    if c < b:
        return "regressed"
    if c > b:
        return "fixed"
    if c == 1.0:
        return "stable-pass"
    if c == 0.0:
        return "stable-fail"
    return "flaky"


def compare(baseline: dict, candidate: dict, policy: dict | None = None,
            waivers: list[dict] | None = None, today: str | None = None) -> dict:
    pol = {**DEFAULTS, **(policy or {})}
    today = today or date.today().isoformat()
    active = {w["case_id"]: w for w in (waivers or []) if str(w.get("expires_at", "9999-12-31")) >= today}

    b = {r["case_id"]: r for r in baseline["results"]}
    c = {r["case_id"]: r for r in candidate["results"]}
    shared = [i for i in c if i in b]
    new_cases = [i for i in c if i not in b]

    def is_safety(cid): return "safety-critical" in c[cid]["tags"]

    quarantined = [i for i in shared if pol["quarantine_flaky"] and 0 < b[i]["pass_rate"] < 1 and not is_safety(i)]
    waived_ids = [i for i in shared if i in active]
    gated = [i for i in shared if i not in quarantined and i not in waived_ids]

    cases = []
    for cid in shared:
        cases.append({
            "case_id": cid, "title": c[cid]["title"], "tags": c[cid]["tags"],
            "baseline": b[cid]["pass_rate"], "candidate": c[cid]["pass_rate"],
            "class": classify(b[cid]["pass_rate"], c[cid]["pass_rate"]),
            "quarantined": cid in quarantined, "waived": cid in waived_ids,
        })

    new_critical, waived_hits = [], []
    for cid in c:
        base_ids = {d["id"] for d in b[cid]["detections"]} if cid in b else set()
        for d in c[cid]["detections"]:
            if d["severity"] == "critical" and d["id"] not in base_ids:
                hit = {"case_id": cid, **d}
                if cid in active:
                    waived_hits.append({**hit, **{k: active[cid].get(k) for k in ("reason", "approver", "expires_at")}})
                else:
                    new_critical.append(hit)
    for cid in waived_ids:  # a waived plain regression is also worth showing
        if classify(b[cid]["pass_rate"], c[cid]["pass_rate"]) == "regressed" and not any(h["case_id"] == cid for h in waived_hits):
            waived_hits.append({"case_id": cid, "id": "regression", "severity": "major",
                                **{k: active[cid].get(k) for k in ("reason", "approver", "expires_at")}})

    def series(ids, key): return [(b if key == "b" else c)[i]["pass_rate"] for i in ids]

    safety_ids = [i for i in gated if is_safety(i)]
    metrics = {
        "overall": _metric("Overall pass rate", series(gated, "b"), series(gated, "c"), pol),
        "safety": _metric("Safety pass rate", series(safety_ids, "b"), series(safety_ids, "c"), pol),
    }
    tag_metrics = {}
    for tag in sorted({t for i in gated for t in c[i]["tags"]}):
        ids = [i for i in gated if tag in c[i]["tags"]]
        tag_metrics[tag] = _metric(tag, series(ids, "b"), series(ids, "c"), pol)

    bt = baseline["summary"].get("avg_tokens") or 0
    ct = candidate["summary"].get("avg_tokens") or 0
    token_ratio = (ct / bt) if bt else 1.0

    verdict, reasons = "PASS", []

    def raise_to(level: str, why: str):
        nonlocal verdict
        if ORDER[level] > ORDER[verdict]:
            verdict = level
        reasons.append(f"[{level}] {why}")

    if new_critical and pol["block_on_critical"]:
        raise_to("BLOCK", f"{len(new_critical)} new critical safety detection(s): "
                 + ", ".join(f"{x['case_id']} ({x['id']})" for x in new_critical))
    if metrics["safety"]["status"] == "confirmed regression":
        raise_to("BLOCK", f"safety pass rate dropped ({pol['confidence']:.0%} interval entirely below tolerance)")
    elif metrics["safety"]["status"] == "possible regression":
        raise_to("WARN", "safety pass rate dropped (point estimate), interval overlaps zero")
    if metrics["overall"]["status"] not in ("no evidence of regression", "n/a"):
        raise_to("WARN", f"overall pass rate: {metrics['overall']['status']}")
    if token_ratio > pol["max_token_ratio"]:
        raise_to("WARN", f"average tokens per trial is {token_ratio:.2f}x baseline (limit {pol['max_token_ratio']}x)")
    if len(gated) < pol["min_cases"]:
        raise_to("WARN", f"inconclusive: only {len(gated)} gated cases (need {pol['min_cases']})")
    if waived_hits:
        reasons.append(f"[INFO] {len(waived_hits)} waived finding(s): " + ", ".join(h["case_id"] for h in waived_hits))
    if quarantined:
        reasons.append(f"[INFO] quarantined flaky case(s) excluded from the gate: {', '.join(quarantined)}")
    if verdict == "PASS" and not any(r.startswith("[WARN") or r.startswith("[BLOCK") for r in reasons):
        reasons.insert(0, "[PASS] no regression detected")

    return {
        "verdict": verdict, "reasons": reasons, "metrics": metrics, "tags": tag_metrics, "cases": cases,
        "new_cases": new_cases, "new_critical": new_critical, "waived": waived_hits, "quarantined": quarantined,
        "token_ratio": token_ratio, "policy": pol,
        "baseline_agent": baseline.get("resolved_agent"), "candidate_agent": candidate.get("resolved_agent"),
    }


def to_markdown(cmp: dict) -> str:
    icon = {"PASS": "PASS", "WARN": "WARN", "BLOCK": "BLOCKED"}[cmp["verdict"]]
    lines = [f"# ClinEval-CI report: {icon}", "",
             f"Baseline agent: `{cmp['baseline_agent']}`  |  Candidate agent: `{cmp['candidate_agent']}`", ""]
    lines += [f"- {r}" for r in cmp["reasons"]]
    lines += ["", "| Metric | Baseline | Candidate | Diff (CI) | Status |", "|---|---|---|---|---|"]
    for m in list(cmp["metrics"].values()) + list(cmp["tags"].values()):
        lines.append(f"| {m['name']} | {m['baseline']:.1%} | {m['candidate']:.1%} | "
                     f"{m['diff']:+.1%} ({m['ci_low']:+.1%} to {m['ci_high']:+.1%}) | {m['status']} |")
    bad = [x for x in cmp["cases"] if x["class"] in ("regressed", "fixed", "flaky") or x["waived"]]
    if bad:
        lines += ["", "| Case | Baseline | Candidate | Class |", "|---|---|---|---|"]
        for x in bad:
            tag = " (waived)" if x["waived"] else " (quarantined)" if x["quarantined"] else ""
            lines.append(f"| {x['case_id']} | {x['baseline']:.0%} | {x['candidate']:.0%} | {x['class']}{tag} |")
    lines += ["", "_Passing this gate is not evidence of clinical safety or regulatory compliance._"]
    return "\n".join(lines)
