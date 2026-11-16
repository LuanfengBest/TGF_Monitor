"""Package existing outputs for sharing; never executes an experiment.

Large, repeated simulator state dumps remain in the local archive. Their
original hashes are retained; all conversations, public receipts, requests,
responses, reference results and analysis inputs are included unchanged.
"""
from pathlib import Path
import gzip
import hashlib
import io
import json
import re
import tarfile

ROOT = Path(__file__).resolve().parents[2]
BUNDLES = (
    "project/jev_monitor_2x2_2026-11-11",
    "project/jev_tgf_mainline_2026-11-12",
)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    key_path = Path.home() / ".config/typesafe/api_key"
    local_key = key_path.read_bytes().strip() if key_path.is_file() else b""
    token_pattern = re.compile(rb"(?:github_pat_[A-Za-z0-9_]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|sk-proj-[A-Za-z0-9_-]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")
    for relative in BUNDLES:
        bundle = ROOT / relative
        archive = bundle / "saved_outputs.tar.gz"
        manifest = bundle / "SAVED_OUTPUTS_MANIFEST.json"
        if archive.exists() or manifest.exists():
            raise FileExistsError("Publication outputs already exist: " + relative)
        included, excluded = {}, {}
        with archive.open("xb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6) as compressed:
                with tarfile.open(fileobj=compressed, mode="w|") as tar:
                    for path in sorted((bundle / "results").rglob("*")):
                        if not path.is_file():
                            continue
                        if path.is_symlink():
                            raise ValueError("Unexpected symlink: " + str(path))
                        name = path.relative_to(bundle).as_posix()
                        omit = ("jev_tgf_mainline" in relative and
                                (path.name == "execution_evidence_private.json" or
                                 ("turns" in path.parts and path.name == "execution.json")))
                        if omit:
                            excluded[name] = {"bytes": path.stat().st_size, "sha256": digest(path)}
                            continue
                        data = path.read_bytes()
                        if (local_key and local_key in data) or token_pattern.search(data):
                            raise ValueError("Potential credential in publication input: " + name)
                        included[name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                        info = tarfile.TarInfo(name)
                        info.size = len(data)
                        info.mode = 0o644
                        info.mtime = 0
                        tar.addfile(info, io.BytesIO(data))
        result = {
            "schema": "saved-output-publication-v1",
            "new_model_calls": 0,
            "archive": archive.name,
            "archive_sha256": digest(archive),
            "archive_bytes": archive.stat().st_size,
            "included": included,
            "omitted_local_only": excluded,
            "omission_reason": "Repeated full simulator state snapshots only. Public conversations, action/receipt evidence, model inputs and outputs, programmatic reference results, and numeric analysis inputs are retained byte-for-byte. Replaying the complete simulator-state audit requires the original local/cluster archive; this package does not claim to reproduce that audit.",
            "PRIVATE_filename_meaning": "Synthetic experiment information withheld from the Judge, not credentials or real customer records.",
        }
        manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"bundle": relative, "included_files": len(included),
                          "omitted_state_dumps": len(excluded), "archive_bytes": archive.stat().st_size}))


if __name__ == "__main__":
    main()
