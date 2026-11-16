"""Export committed runtime and frozen inputs without requiring GitHub access."""
import json
import subprocess
import zipfile
from matched_followup.common import CONFIG, ROOT, file_digest, freeze_hashes, load
from matched_followup.public import load_cases


def build():
    config = load(CONFIG)
    cases = load_cases(config, include_review=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    paths = set(freeze_hashes()) | {config["source"], config["source_index"], "matched_followup/README.md"}
    paths.update(c["source_file"] for c in cases.values())
    handoff = ROOT / "project/matched_followup_v1"
    paths.update(str(p.relative_to(ROOT)) for p in handoff.iterdir() if p.is_file() and p.suffix in {".md", ".json", ".py", ".html"})
    manifest = {"source_commit": commit, "diagnostic_cases": config["cases"],
                "not_a_model_or_gpu_run": True, "files": {}}
    prefix = "TGF_cluster_" + commit[:7]
    output = ROOT / "dist" / (prefix + ".zip")
    output.parent.mkdir(exist_ok=True)
    tracked = set(subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines())
    if not paths <= tracked:
        raise ValueError("Commit all delivery files before packaging: " + str(paths - tracked))
    dirty = subprocess.check_output(["git", "diff", "HEAD", "--name-only", "--", *sorted(paths)], cwd=ROOT, text=True)
    if dirty.strip():
        raise ValueError("Package files differ from the recorded commit: " + dirty)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in sorted(paths):
            path = ROOT / relative
            if path.is_symlink() or not path.is_file():
                raise ValueError("Bundle only accepts regular files")
            manifest["files"][relative] = {"sha256": file_digest(path), "bytes": path.stat().st_size}
            archive.write(path, prefix + "/" + relative)
        archive.writestr(prefix + "/bundle_manifest.json", json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"archive": str(output), "bytes": output.stat().st_size,
                      "sha256": file_digest(output), "files": len(paths)}, indent=2))
    return output


if __name__ == "__main__":
    build()
