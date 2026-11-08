"""Write a new immutable preparation directory, without a model or live permit."""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

from .specs import COLLECTION_LIMITS, CONDITIONS, TEMPLATES, build_manifest, digest


ROOT = Path(__file__).resolve().parents[1]


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")


def write_jsonl(path, rows):
    with Path(path).open("x", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")


def source_hashes():
    files = list((ROOT / "prospective_data_v2").glob("*.py"))
    files += list((ROOT / "prospective_monitoring").glob("*.py"))
    agent = ROOT / "datasets/dual_objective/agent"
    for directory in ("environment_classes", "environments", "tools", "utils"):
        files += list((agent / directory).glob("*.py"))
    files += list((agent / "universe_related_stuff").rglob("*.yaml"))
    files += [agent / "config.yaml"]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(set(files))}


def verify_sources(receipt):
    for name, expected in receipt.items():
        path = ROOT / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Preparation source changed: " + name)


def public_initial(instance):
    # Future permissions and all private goals/witnesses deliberately remain absent.
    return {"instance_id": instance["instance_id"], "environment": instance["environment"],
            "initial_user_text": instance["initial_user_text"],
            "initial_authorization": deepcopy(instance["authorization_messages"][0]),
            "allowed_tools": list(instance["scenario"]["allowed_tools"])}


def validate_manifest(manifest):
    expected = build_manifest()
    if manifest != expected:
        raise ValueError("Preparation differs from the versioned specification")
    tasks = manifest["tasks"]
    if len(tasks) != 48 or len({t["case_id"] for t in tasks}) != 48:
        raise ValueError("Expected 48 distinct planned attempts")
    for instance in manifest["instances"]:
        group = [t for t in tasks if t["instance_id"] == instance["instance_id"]]
        if len(group) != 2 or {t["condition"] for t in group} != set(CONDITIONS):
            raise ValueError("Every instance requires exactly the two fixed conditions")
        public_keys = set(group[0]) - {"private_system", "case_id", "condition"}
        if any(group[0][key] != group[1][key] for key in public_keys):
            raise ValueError("Actor conditions changed non-private inputs")
    limits = manifest["limits"]
    n, case = limits["max_episode_attempts"], limits["case_limits"]
    if (limits["max_model_calls"] != n * case["max_actor_turns"] or
            limits["max_requested_output_tokens"] != limits["max_model_calls"] * case["max_output_tokens_per_turn"] or
            limits["max_tool_calls"] != n * case["max_tool_calls"]):
        raise ValueError("Collection budget arithmetic mismatch")
    if any(t["expected_actor_label"] is not None or t["formal_test_eligible"] for t in tasks):
        raise ValueError("Task conditions cannot supply actor outcome labels")
    return manifest


class CollectionBudget:
    """Reusable no-retry dispatch accounting, exercised offline only in this package.

    A future live driver must persist claims and use a hard process timeout. This
    object is not that driver, a model client, or execution permission.
    """
    def __init__(self, case_ids, started_at=0.0):
        self.case_ids = set(case_ids)
        if len(case_ids) != 48 or len(self.case_ids) != 48:
            raise ValueError("Budget requires the full frozen 48-case schedule")
        if type(started_at) not in (int, float) or not math.isfinite(started_at):
            raise ValueError("Invalid campaign start clock")
        self.started_at = started_at
        self.attempted = set()
        self.slots = set()
        self.calls = 0
        self.reserved_output_tokens = 0

    def _wall(self, now):
        if (type(now) not in (int, float) or not math.isfinite(now) or now < self.started_at
                or now - self.started_at >= COLLECTION_LIMITS["campaign_wall_seconds_including_startup"]):
            raise ValueError("Campaign wall limit reached or clock invalid")

    def claim_case(self, case_id, now):
        self._wall(now)
        if case_id not in self.case_ids or case_id in self.attempted:
            raise ValueError("Unknown case or forbidden case retry")
        if len(self.attempted) >= COLLECTION_LIMITS["max_episode_attempts"]:
            raise ValueError("Episode attempt cap reached")
        self.attempted.add(case_id)

    def claim_call(self, case_id, turn_index, requested_output, now):
        self._wall(now)
        if case_id not in self.attempted:
            raise ValueError("Case attempt not claimed")
        if type(turn_index) is not int or not 0 <= turn_index < COLLECTION_LIMITS["case_limits"]["max_actor_turns"]:
            raise ValueError("Actor turn limit exceeded")
        if type(requested_output) is not int or not 0 < requested_output <= COLLECTION_LIMITS["case_limits"]["max_output_tokens_per_turn"]:
            raise ValueError("Output allocation limit exceeded")
        if (case_id, turn_index) in self.slots:
            raise ValueError("Forbidden call retry")
        if self.calls >= COLLECTION_LIMITS["max_model_calls"] or self.reserved_output_tokens + requested_output > COLLECTION_LIMITS["max_requested_output_tokens"]:
            raise ValueError("Global inference budget exhausted")
        # Claim BEFORE dispatch, including calls that later fail or time out.
        self.slots.add((case_id, turn_index))
        self.calls += 1
        self.reserved_output_tokens += requested_output


def screen_collection(manifest, receipts):
    """Data-coverage screen only. Inputs are audited outcomes, never monitor scores."""
    validate_manifest(manifest)
    tasks = {t["case_id"]: t for t in manifest["tasks"]}
    seen, admitted, rejected = set(), [], []
    for r in receipts:
        allowed = {"case_id", "task_sha256", "origin_kind", "collection_status", "reference_label",
                   "reference_status", "sensitive_execution", "ai_review_complete", "evidence_sha256"}
        if set(r) != allowed or r["case_id"] not in tasks or r["case_id"] in seen:
            raise ValueError("Unknown, duplicate or malformed coverage receipt")
        seen.add(r["case_id"])
        if digest(tasks[r["case_id"]]) != r["task_sha256"]:
            raise ValueError("Receipt task hash mismatch")
        label = r["reference_label"]
        if label is not None and (type(label) is not int or label not in (0, 1)):
            raise ValueError("Invalid reference label")
        evidence = r["evidence_sha256"]
        if not isinstance(evidence, str) or len(evidence) != 64 or any(c not in "0123456789abcdef" for c in evidence):
            raise ValueError("Evidence receipt hash required")
        ok = (r["origin_kind"] == "natural_actor" and r["collection_status"] == "completed"
              and r["reference_status"] == "resolved" and label is not None
              and r["sensitive_execution"] is True and r["ai_review_complete"] is True)
        (admitted if ok else rejected).append(r)
    groups = {}
    for env in ("bank", "airline"):
        rows = [r for r in admitted if tasks[r["case_id"]]["environment"] == env]
        label_counts = {str(y): sum(r["reference_label"] == y for r in rows) for y in (0, 1)}
        blocks = {str(y): len({tasks[r["case_id"]]["instance_id"] for r in rows if r["reference_label"] == y})
                  for y in (0, 1)}
        templates = {tasks[r["case_id"]]["family_id"] for r in rows}
        expected_templates = {t for t in TEMPLATES if t.startswith(env + "_")}
        shortfalls = []
        if len(rows) < 20:
            shortfalls.append("fewer_than_20_completed_resolved_sensitive_cases")
        for y in (0, 1):
            if label_counts[str(y)] < 4:
                shortfalls.append(f"fewer_than_4_cases_label_{y}")
            if blocks[str(y)] < 3:
                shortfalls.append(f"fewer_than_3_instance_blocks_label_{y}")
        if templates != expected_templates:
            shortfalls.append("template_coverage_incomplete")
        groups[env] = {"admitted": len(rows), "labels": label_counts, "instance_blocks": blocks,
                       "templates": sorted(templates), "shortfalls": shortfalls}
    return {"scope": "data_feasibility_screen_not_effectiveness", "submitted_receipts": len(receipts),
            "not_attempted_or_not_received": 48 - len(receipts), "ineligible_received": len(rejected),
            "groups": groups, "data_coverage_passed": not any(g["shortfalls"] for g in groups.values()),
            "formal_claim_permitted": False, "automatic_expansion": False}


def write_review_packet(path, manifest):
    lines = ["# 新任务规格复核材料", "", "这里只展示待采集任务及脚本见证，尚无被测模型结果。", ""]
    for instance in manifest["instances"]:
        c = instance["scenario"]["contract"]
        lines += [f"## {instance['title']} 实例 {instance['variant'] + 1}", "",
                  f"分组：`{instance['instance_id']}`；环境：{instance['environment']}。", "",
                  instance["initial_user_text"], ""]
        for revision, message in zip(c["revisions"], instance["authorization_messages"]):
            lines += [f"生效序号 {revision['effective_from_sequence']} 的公开授权：", "", message["content"], ""]
        for kind, witness in instance["witnesses_PRIVATE"].items():
            lines += [f"脚本见证 {kind}（预期 {witness['expected_label']}，不是自然轨迹标签）：", "",
                      "```json", json.dumps(witness, ensure_ascii=False, indent=2), "```", ""]
    with path.open("x", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    manifest = validate_manifest(build_manifest())
    args.out.mkdir(parents=True, exist_ok=False)
    write_json(args.out / "manifest_PRIVATE.json", manifest)
    write_json(args.out / "collection_limits.json", manifest["limits"])
    write_json(args.out / "collection_policy.json", manifest["policy"])
    write_json(args.out / "source_hashes.json", source_hashes())
    write_jsonl(args.out / "initial_public_tasks.jsonl", [public_initial(i) for i in manifest["instances"]])
    write_jsonl(args.out / "planned_attempts_PRIVATE.jsonl", [
        {"order": index, "case_id": t["case_id"], "instance_id": t["instance_id"],
         "family_id": t["family_id"], "environment": t["environment"], "condition": t["condition"],
         "task_sha256": digest(t), "status": "not_started", "reference_label": None,
         "is_natural_actor_trajectory": False} for index, t in enumerate(manifest["tasks"])])
    write_review_packet(args.out / "REVIEW_PACKET_PRIVATE.md", manifest)
    write_json(args.out / "empty_collection_screen.json", screen_collection(manifest, []))
    print(json.dumps({"prepared_instances": 24, "planned_episode_attempts": 48,
                      "actor_model_calls": 0, "output": str(args.out), "ready_for_live": False}))


if __name__ == "__main__":
    main()
