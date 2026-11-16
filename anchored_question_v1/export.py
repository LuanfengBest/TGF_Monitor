"""Export only frozen dependencies, study documents and the exact replay cohort."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

from .prepare import ROOT, OUTPUT, load_bundle, sha, write


def export(bundle, output):
    _, _, manifest = load_bundle(bundle)
    paths = {ROOT / name for name in manifest["code_sha256"]}
    paths.update(Path(bundle).glob("*.json"))
    paths.update(OUTPUT / name for name in ("README.md", "AUTHORIZATION.json", "RUNBOOK.md"))
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)}
    inventory = OUTPUT / "deployment/FILES.json"
    write(inventory, hashes)
    paths.add(inventory)
    with tarfile.open(output, "x:gz") as archive:
        for path in sorted(paths):
            archive.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)
    receipt = {"archive": str(Path(output).resolve()), "sha256": sha(output), "bytes": Path(output).stat().st_size,
               "files": len(paths), "bundle_manifest_sha256": sha(Path(bundle) / "manifest.json"),
               "model_calls": 0, "weights_included": False}
    write(OUTPUT / "deployment/export_receipt.json", receipt)
    return receipt


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bundle", type=Path, default=OUTPUT / "bundle")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    print(json.dumps(export(args.bundle, args.output)))
