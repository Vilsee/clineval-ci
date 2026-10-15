"""Exports: JUnit XML (for Jenkins/GitHub) and the audit evidence bundle."""
from __future__ import annotations

import xml.etree.ElementTree as ET


def to_junit(cmp: dict) -> str:
    cases = cmp["cases"]
    failures = 0
    suite = ET.Element("testsuite", name="clineval-gate", tests=str(len(cases)))
    crit_by_case = {x["case_id"]: x for x in cmp["new_critical"]}
    for x in cases:
        tc = ET.SubElement(suite, "testcase", classname="clineval", name=f"{x['case_id']} {x['title']}")
        if x["waived"] or x["quarantined"]:
            ET.SubElement(tc, "skipped", message="waived" if x["waived"] else "quarantined (flaky)")
        elif x["case_id"] in crit_by_case:
            failures += 1
            d = crit_by_case[x["case_id"]]
            ET.SubElement(tc, "failure", type="critical", message=f"critical detection: {d['id']}").text = d.get("description", "")
        elif x["class"] == "regressed":
            failures += 1
            ET.SubElement(tc, "failure", type="regression",
                          message=f"pass rate {x['baseline']:.0%} -> {x['candidate']:.0%}")
    suite.set("failures", str(failures))
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(suite, encoding="unicode")


def evidence_bundle(*, suite: dict, policy: dict, baseline: dict | None, waivers: list[dict],
                    audit: dict, latest_comparison: dict | None) -> dict:
    return {
        "tool": "ClinEval-CI", "notice": "Synthetic demo data. Not evidence of clinical safety or regulatory compliance.",
        "suite": {k: suite[k] for k in ("name", "hash", "n_cases")},
        "policy": policy, "waivers": waivers, "audit_chain": audit,
        "baseline": None if not baseline else {"agent": baseline.get("resolved_agent"), "summary": baseline["summary"]},
        "latest_comparison": None if not latest_comparison else {
            k: latest_comparison[k] for k in ("verdict", "reasons", "metrics", "tags", "waived", "quarantined")},
    }
