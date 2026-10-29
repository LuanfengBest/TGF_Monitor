"""Small, CPU-only serialization and provenance helpers."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "matched_followup/config.json"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def records(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def freeze_hashes():
    paths = list((ROOT / "matched_followup").glob("*.py")) + list((ROOT / "matched_followup").glob("*.sbatch")) + [CONFIG]
    paths += [ROOT / "workstreams/pacifica/scripts" / name for name in
              ("observed_execution_v1.py", "observed_airline_execution_v1.py")]
    return {str(p.relative_to(ROOT)): file_digest(p) for p in sorted(paths)}
