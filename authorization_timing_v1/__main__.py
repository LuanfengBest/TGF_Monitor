"""Prepare, run, and score one bounded authorization-timing diagnostic."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from .protocol import THRESHOLD, build_requests


CASE_COUNT = 16
CALL_COUNT = 32
SEED = 17
TEMPERATURE = 0.6
OUTPUT_CAP = 2048
WALL_SECONDS = 3600
STARTUP_SECONDS = 1200
CALL_SECONDS = 120


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_public(directory):
    manifest = read_json(directory / "manifest.json")
    expected = {name: sha256(directory / name) for name in ("records.json", "requests.json")}
    if manifest != expected:
        raise ValueError("The public records or requests changed after preparation")
    records = read_json(directory / "records.json")
    requests = read_json(directory / "requests.json")
    if len(records) != CASE_COUNT or len(requests) != CALL_COUNT or requests != build_requests(records):
        raise ValueError("Expected the 16 public records and their exact 32 generated requests")
    return requests


def settings():
    from prospective_monitoring.native_backend import PINNED

    model = PINNED["monitor"]
    return {"model": model["model"], "revision": model["revision"], "seed": SEED,
            "temperature": TEMPERATURE, "top_p": model["top_p"], "max_output_tokens": OUTPUT_CAP,
            "threshold": THRESHOLD, "max_calls": CALL_COUNT, "wall_seconds": WALL_SECONDS,
            "startup_seconds": STARTUP_SECONDS, "call_seconds": CALL_SECONDS}


def prepare(directory):
    from .dataset import build_dataset

    if directory.exists():
        raise FileExistsError(directory)
    records, references = build_dataset()
    requests = build_requests(records)
    if len(records) != CASE_COUNT or len(references) != CASE_COUNT or len(requests) != CALL_COUNT:
        raise ValueError("Dataset did not produce the planned 8 pairs and 32 requests")
    public, private = directory / "public", directory / "private"
    directory.mkdir()
    public.mkdir()
    private.mkdir()
    files = {"public/records.json": records, "public/requests.json": requests,
             "private/references.json": references}
    for name, value in files.items():
        write_json(directory / name, value)
    write_json(public / "manifest.json", {name: sha256(public / name) for name in ("records.json", "requests.json")})
    write_json(directory / "manifest.json", {
        "study": "authorization-timing-v1", "origin": "scripted_simulator_pairs",
        "settings": settings(), "files": {name: sha256(directory / name) for name in files},
    })


def native_backend(snapshot):
    from closeout_validation_v1.run import worker
    from prospective_monitoring.native_backend import ProcessStageBackend

    spec = settings()
    config = {"models": {"monitor": spec["model"]}, "revisions": {"monitor": spec["revision"]},
              "temperature": TEMPERATURE, "seed": SEED, "stage_output_caps": {"judge": OUTPUT_CAP}}
    return ProcessStageBackend("monitor", config, snapshot, permit_live=True,
                               startup_timeout_seconds=STARTUP_SECONDS, _worker_target=worker)


def result_row(request_id, raw, error=None):
    return {"request_id": request_id, "text": raw.get("text"),
            "finish_reason": raw.get("finish_reason"), "prompt_tokens": raw.get("prompt_tokens"),
            "completion_tokens": raw.get("completion_tokens"), "error": error}


def run_judge(public, output, backend):
    requests = read_public(public)
    output.mkdir()
    run_path = output / "run.json"
    results_path = output / "results.jsonl"
    write_json(run_path, {"study": "authorization-timing-v1", "settings": settings(),
                          "requests_sha256": sha256(public / "requests.json")})
    deadline = time.monotonic() + WALL_SECONDS
    count = 0
    state = "interrupted"
    try:
        with results_path.open("x", encoding="utf-8") as stream:
            backend.start()
            for request in requests:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Campaign deadline reached before the next dispatch")
                native_request = {**request, "model_slot": "monitor", "seed": SEED,
                                  "max_output_tokens": OUTPUT_CAP}
                error = None
                try:
                    raw = backend.generate(native_request, min(CALL_SECONDS, remaining))
                except Exception as exc:
                    raw = getattr(exc, "raw", None) or {}
                    error = f"{type(exc).__name__}: {exc}"
                row = result_row(request["request_id"], raw, error)
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
                count += 1
                if error is not None:
                    raise RuntimeError(f"Judge stopped at {request['request_id']}: {error}")
        state = "completed"
    finally:
        try:
            backend.close()
        finally:
            write_json(output / "summary.json", {"state": state, "recorded_calls": count,
                                                 "results_sha256": sha256(results_path)})


def score(bundle, run, output):
    from .score import score_results

    requests = read_public(bundle / "public")
    manifest = read_json(bundle / "manifest.json")
    expected = {name: sha256(bundle / name) for name in
                ("public/records.json", "public/requests.json", "private/references.json")}
    run_metadata = read_json(run / "run.json")
    if manifest["files"] != expected or manifest["settings"] != settings():
        raise ValueError("The prepared dataset or settings changed")
    if run_metadata["requests_sha256"] != expected["public/requests.json"] or run_metadata["settings"] != settings():
        raise ValueError("Judge run does not match the prepared requests and settings")
    results_path = run / "results.jsonl"
    summary_path = run / "summary.json"
    if summary_path.exists() and read_json(summary_path)["results_sha256"] != sha256(results_path):
        raise ValueError("Saved Judge results changed")
    results = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines()]
    references = read_json(bundle / "private/references.json")
    report = score_results(requests, references, results)
    write_json(output, {"run": run_metadata, "metrics": report})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_cmd = commands.add_parser("prepare", help="Build paired records and frozen inputs on CPU")
    prepare_cmd.add_argument("--out", type=Path, required=True)
    judge_cmd = commands.add_parser("judge", help="Run the pinned Judge on an existing H200 allocation")
    judge_cmd.add_argument("--public", type=Path, required=True, help="The prepared public/ directory only")
    judge_cmd.add_argument("--out", type=Path, required=True)
    judge_cmd.add_argument("--snapshot", type=Path, required=True, help="Path to the pinned local Qwen3-32B snapshot")
    judge_cmd.add_argument("--execute", action="store_true", required=True, help="Explicitly start 32 model calls")
    score_cmd = commands.add_parser("score", help="Score saved outputs on CPU")
    score_cmd.add_argument("--bundle", type=Path, required=True)
    score_cmd.add_argument("--run", type=Path, required=True)
    score_cmd.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.out)
    elif args.command == "judge":
        run_judge(args.public, args.out, native_backend(args.snapshot))
    else:
        score(args.bundle, args.run, args.out)


if __name__ == "__main__":
    main()
