"""CPU-only full asset hashes and current-task Harmony capacity admission."""
import json
from pathlib import Path
import time

from .runner import ROOT, DEP, inputs, config, save, sha
from prospective_data_v2.fixtures import prepare_environment
from prospective_monitoring.collection import _tool_schemas
from prospective_monitoring.native_backend import NativeCodec, runtime_check, snapshot_check
from prospective_monitoring.preflight import _sha_file, check_actor_examples


def main():
    start = time.monotonic()
    permit, manifest, runtime = inputs()
    out = ROOT / "admission"
    out.mkdir(exist_ok=False)
    deadline = start + 1800
    found_runtime = runtime_check(config())
    snapshot_check(runtime["snapshot"], "actor")
    expected = json.loads((DEP / "expected_actor_assets.json").read_text())
    verified = []
    for row in expected["files"]:
        path = Path(runtime["assets"]) / row["destination"]
        before = path.stat()
        checksum = _sha_file(path, deadline)
        after = path.stat()
        if (before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns
                or after.st_size != row["bytes"] or checksum != row["sha256"]):
            raise ValueError("Runtime asset byte mismatch: " + row["destination"])
        verified.append({"path": str(path), "resolved_path": str(path.resolve()),
                         "bytes": after.st_size, "mtime_ns": after.st_mtime_ns, "sha256": checksum})
    image = Path(runtime["image"])
    image_before = image.stat()
    image_sha = _sha_file(image, deadline)
    image_after = image.stat()
    if (image_sha != expected["image_sha256"] or
            (image_before.st_ino, image_before.st_size, image_before.st_mtime_ns) !=
            (image_after.st_ino, image_after.st_size, image_after.st_mtime_ns)):
        raise ValueError("Pinned vendor container mismatch")
    verified.append({"path": str(image), "resolved_path": str(image.resolve()), "bytes": image_after.st_size,
                     "mtime_ns": image_after.st_mtime_ns, "sha256": image_sha})
    codec = NativeCodec("actor", runtime["snapshot"])
    lengths = []
    for task in manifest["tasks"]:
        env, engine = prepare_environment(task["scenario"])
        tools = _tool_schemas(engine, task["allowed_tools"])
        conv = [{"role":"system", "content":task["private_system"]},
                {"role":"user", "content":task["initial_user_text"]}]
        conv.extend({"role":"user", "content":m["content"]}
                    for m in task["authorization_messages"] if m["effective_from_sequence"] <= 1)
        ids = codec.actor_prompt(conv, tools)
        if len(ids) + 4096 > 131072:
            raise ValueError("Initial task exceeds pinned model context")
        lengths.append({"case_id":task["case_id"], "input_tokens":len(ids)})
    # Exercise actual legal/violating fixture histories, including revision/tool messages.
    fixture_lengths, examples = [], []
    for path in sorted((DEP / "witness_requests").glob("*.json")):
        req = json.loads(path.read_text())
        ids = codec.actor_prompt(req["conversation"], req["tools"])
        if len(ids) + req["max_output_tokens"] > 131072:
            raise ValueError("Fixture continuation exceeds context")
        fixture_lengths.append(len(ids))
        examples.append({**req, "case_id":path.stem, "kind":"scripted_cpu_fixture"})
    if not fixture_lengths:
        raise ValueError("Missing frozen witness continuation requests")
    examples.append({**examples[-1], "kind":"explicit_CPU_end_tool_roundtrip",
        "conversation":examples[-1]["conversation"] + [{"role":"assistant", "channel":"commentary",
            "content":"", "tool_calls":[{"function":"end_task", "args":{}}]}]})
    harmony = check_actor_examples(runtime["snapshot"], examples, deadline)
    save(out / "harmony_checks.json", harmony)
    for path in sorted((ROOT / "python_dependencies").rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            stat = path.stat()
            verified.append({"path":str(path), "resolved_path":str(path.resolve()), "bytes":stat.st_size,
                             "mtime_ns":stat.st_mtime_ns, "sha256":_sha_file(path,deadline)})
    save(out / "preflight.json", {"ready_for_live":True, "model_calls":0,
         "permit_sha256":sha(DEP / "execution_permit.json"), "runtime_location":runtime,
         "runtime":found_runtime, "verified_files":verified,
         "initial_prompt_lengths":lengths, "witness_prompt_count":len(fixture_lengths),
         "max_witness_prompt_tokens":max(fixture_lengths),
         "future_dynamic_prompt_check_required":True, "elapsed_seconds":time.monotonic()-start})
    print(json.dumps({"ready_for_live":True, "model_calls":0, "initial_prompts":len(lengths),
                      "witness_prompts":len(fixture_lengths), "assets_hashed":len(verified)}), flush=True)


if __name__ == "__main__":
    main()
