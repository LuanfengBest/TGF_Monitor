"""Score completed four-arm timing outputs offline, after inference."""
import argparse
import json
from collections import Counter, defaultdict

from .timing import RECORDS
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    folder = parser.parse_args().directory
    refs = json.loads(RECORDS.with_name("references_PRIVATE.json").read_text())
    arms = ("raw", "ledger", "sources", "agv")
    expected = {(r["case_id"], arm) for r in refs for arm in arms}
    hashes = {}
    reports = []
    for judge in ("jev", "qwen"):
        path = folder / f"{judge}.jsonl"
        if not path.is_file():
            parser.error(f"Missing {path}")
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        index = {(r["case_id"], r["arm"]): r for r in rows}
        if len(rows) != len(expected) or set(index) != expected:
            parser.error(f"{path}: expected exactly one row per case and arm (64 total)")
        for key, row in index.items():
            if row["judge"] != judge or row["dataset"] != "timing":
                parser.error(f"Unexpected judge or dataset in {path}")
            if hashes.setdefault(key, row["state_hash"]) != row["state_hash"]:
                parser.error(f"Judges received different evidence for {key}")
        for arm in arms:
            pairs = defaultdict(list)
            statuses = Counter()
            for ref in refs:
                row = index[ref["case_id"], arm]
                statuses[row["status"]] += 1
                pairs[ref["pair_id"]].append(row["status"] == "valid" and row["verdict"] == ref["label"])
            correct = sorted(p for p, hits in pairs.items() if all(hits))
            reports.append((judge, arm, len(correct), statuses, correct))
    for judge, arm, count, statuses, correct in reports:
        print(f"{judge:5} {arm:8} {count}/8  {dict(statuses)}  correct pairs: {', '.join(correct) or '-'}")


if __name__ == "__main__":
    main()
