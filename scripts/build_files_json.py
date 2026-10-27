"""Snapshots the project files shown on the /demo page into public/files.json.
Run after changing any of them:  python scripts/build_files_json.py"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = ["terraform/*.tf", "terraform/modules/*/*.tf", "terraform/modules/*/cloud-init.yaml", "terraform/bootstrap/*.tf",
            "terraform/*.example", "terraform/README.md", "Jenkinsfile", ".github/workflows/*.yml", "gate.yaml", "waivers.yaml",
            "Dockerfile", "vercel.json", "suites/triage-core/cases.yaml", "deploy/remote_deploy.sh", "clineval/stats.py"]
out = {}
for pat in PATTERNS:
    for f in sorted(ROOT.glob(pat)):
        out[f.relative_to(ROOT).as_posix()] = f.read_text(encoding="utf-8")
(ROOT / "public" / "files.json").write_text(json.dumps(out), encoding="utf-8")
print(f"wrote public/files.json with {len(out)} files, {sum(len(v) for v in out.values())//1024} KB")
