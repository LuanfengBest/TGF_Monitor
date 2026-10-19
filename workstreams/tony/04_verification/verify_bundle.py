"""Verify this bundle's inventory, without running experiments or changing files."""
import hashlib
import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    manifest = json.loads((root / "04_verification/manifest.json").read_text(encoding="utf-8"))
    files = manifest["files"]
    expected = {entry["path"] for entry in files}
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    assert len(expected) == len(files), "Duplicate paths in inventory"
    assert actual == expected | {"04_verification/manifest.json"}, "Missing or unexpected files"
    for entry in files:
        path = (root / entry["path"]).resolve()
        assert root in path.parents and not (root / entry["path"]).is_symlink(), "Unsafe path"
        assert path.stat().st_size == entry["bytes"], entry["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"], entry["path"]
    print(f"VERIFIED: {len(files)} files match size/SHA256 inventory. No experiment executed.")


if __name__ == "__main__":
    main()
