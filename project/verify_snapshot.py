"""Read-only verification of the curated research snapshot; standard library only."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / "project/import_manifest.json").read_text())
    seen = set()
    total = 0
    for entry in manifest["files"]:
        rel = entry["path"]
        path = ROOT / rel
        if rel in seen or path.is_symlink() or ROOT not in path.resolve().parents:
            raise ValueError(f"Unsafe or repeated path: {rel}")
        seen.add(rel)
        data = path.read_bytes()
        if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError(f"Imported bytes differ: {rel}")
        total += len(data)
    checks = {}
    for name, rel in {
        "tony_bundle": "workstreams/tony/04_verification/verify_bundle.py",
        "full64_authorization": "workstreams/pacifica/analysis/validate_tgf_full64_audit_20261018.py",
    }.items():
        result = subprocess.run([sys.executable, "-B", str(ROOT / rel)], cwd=ROOT,
                                check=True, capture_output=True, text=True)
        checks[name] = result.stdout.strip()
    print(json.dumps({"status": "passed", "imported_files": len(seen), "imported_bytes": total,
                      "checks": checks, "new_model_calls": 0, "human_review": False}, indent=2))


if __name__ == "__main__":
    main()
