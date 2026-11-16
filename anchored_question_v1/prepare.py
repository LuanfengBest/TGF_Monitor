"""Freeze a new authorization and cohort without modifying historical artifacts."""
import argparse
from pathlib import Path
import shutil
from airline_dev_v1 import prepare as prior
from . import protocol as p

ROOT, read, write, sha, verify_files = prior.ROOT, prior.read, prior.write, prior.sha, prior.verify_files
OUTPUT = ROOT / "project/anchored_question_diagnostic_2026-11-06"
SOURCE = ROOT / "project/airline_monitor_comparison_2026-11-06/bundle"
SOURCE_MANIFEST = "41080c2031bdc6f905b0e8733e99183a2384d5181f40a6ce01d60be11cdfee73"


def config():
    return read(Path(__file__).with_name("config.json"))


def code_hashes():
    result = prior.code_hashes()
    for f in Path(__file__).parent.iterdir():
        if f.suffix in {".py", ".json", ".sh", ".sbatch"}:
            result[str(f.relative_to(ROOT))] = sha(f)
    return result


def load_bundle(path):
    path = Path(path)
    manifest = read(path / "manifest.json")
    if manifest["scope"] != config()["scope"] or manifest["source_manifest_sha256"] != SOURCE_MANIFEST:
        raise ValueError("Wrong new diagnostic scope or source")
    actual = {f.name for f in path.iterdir() if f.is_file() and f.name != "manifest.json"}
    if actual != set(manifest["files"]):
        raise ValueError("Unexpected/missing bundle files")
    verify_files(path, manifest["files"])
    if manifest["code_sha256"] != code_hashes() or read(path / "config.json") != config():
        raise ValueError("Frozen code/config changed")
    cases = [p.validate_case(c) for c in read(path / "cases_PRIVATE.json")]
    if len(cases) != 24 or len({c["case_id"] for c in cases}) != 24 or p.digest(cases) != manifest["cases_sha256"]:
        raise ValueError("All original 24 cases required")
    anchors = [{"case_id": c["case_id"], "anchor": p.anchor(c)} for c in cases]
    if read(path / "anchors.json") != anchors:
        raise ValueError("Fixed selection changed")
    return config(), cases, manifest


def prepare(out, authorization):
    if sha(SOURCE / "manifest.json") != SOURCE_MANIFEST:
        raise ValueError("Historical source manifest changed")
    _, cases, _ = prior.load_bundle(SOURCE)
    authority = read(authorization)
    cfg = config()
    if authority.get("authorized") is not True or authority.get("scope") != cfg["scope"]:
        raise ValueError("Explicit new-scope authorization required")
    if authority["authorized_limits"] != cfg["limits"] or authority["resource_envelope"] != cfg["resource_envelope"]:
        raise ValueError("Authorized envelope differs")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    for name in ("cases_PRIVATE.json", "references_PRIVATE.json", "public_inputs.json", "source_map_PRIVATE.json"):
        shutil.copyfile(SOURCE / name, out / name)
    refs = read(out / "references_PRIVATE.json")
    if sum(r["label"] for r in refs) != 6 or len({r["instance_id"] for r in refs}) != 12:
        raise ValueError("Source composition changed")
    write(out / "config.json", cfg)
    write(out / "authorization.json", authority)
    write(out / "anchors.json", [{"case_id": c["case_id"], "anchor": p.anchor(c)} for c in cases])
    write(out / "planned_positions.json", [{"case_id": c["case_id"], "seed": s, "arm": a,
        "status": "not_started"} for s in p.SEEDS for c in cases for a in p.ARMS])
    write(out / "frozen_prompts.json", [{"case_id": c["case_id"], "review": p.review_prompt(c),
        "questions": {a: p.question(c, a) for a in ("B", "C")}} for c in cases])
    write(out / "contract.json", {"scope": cfg["scope"], "arms": list(p.ARMS), "seeds": list(p.SEEDS),
        "threshold": 50, "required_final_positions": 144, "minimum_net_positive_blocks_each_seed": 2,
        "minimum_stable_gain_blocks": 2, "minimum_stable_gain_families": 2,
        "maximum_new_false_positives": 0, "cost_ratio_limit_C_to_B": 1.1,
        "analysis_unit": "original_instance_block", "formal_claim_permitted": False,
        "selection_posthoc": True, "references_sha256": p.digest(refs),
        "rule_type": "resource_go_no_go_not_significance_or_power"})
    write(out / "manifest.json", {"scope": cfg["scope"], "source_manifest_sha256": SOURCE_MANIFEST,
        "cases_sha256": p.digest(cases), "case_count": 24, "code_sha256": code_hashes(),
        "files": {f.name: sha(f) for f in out.iterdir() if f.is_file()},
        "formal_claim_permitted": False, "model_calls_during_preparation": 0})
    return load_bundle(out)[2]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, default=OUTPUT / "bundle")
    ap.add_argument("--authorization", type=Path, default=OUTPUT / "AUTHORIZATION.json")
    args = ap.parse_args()
    prepare(args.output, args.authorization)
    print(p.canonical({"bundle": str(args.output), "manifest_sha256": sha(args.output / "manifest.json")}))
