"""Verify archived outputs and recompute saved statistics on CPU, without inference.

Only temporary extraction files are written. The frozen experiment modules and
saved reports remain unchanged. Requires Python >=3.10 and NumPy 2.2.6.
"""
from pathlib import Path, PurePosixPath
import contextlib
import hashlib
import io
import json
import math
import os
import shutil
import sys
import tarfile
import tempfile
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OLD = ROOT / "project/jev_monitor_2x2_2026-11-11"
NEW = ROOT / "project/jev_tgf_mainline_2026-11-12"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def equal(actual, expected, where="result"):
    if isinstance(expected, dict):
        assert isinstance(actual, dict) and actual.keys() == expected.keys(), where + ": keys"
        for key in expected:
            equal(actual[key], expected[key], where + "." + str(key))
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), where + ": length"
        for i, (a, b) in enumerate(zip(actual, expected)):
            equal(a, b, where + "[" + str(i) + "]")
    elif isinstance(expected, float):
        assert isinstance(actual, (int, float)) and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-8), where + ": numeric mismatch"
    else:
        assert type(actual) is type(expected) and actual == expected, where + ": value mismatch"


def guards(temporary):
    def audit(event, args):
        if event.startswith(("socket.", "subprocess.", "os.exec", "os.spawn")) or event == "os.system":
            raise RuntimeError("Offline verification blocks network and process execution: " + event)
        if event == "import" and args[0].split(".")[0] in {"torch", "transformers", "vllm", "llama_cpp", "openai", "requests", "httpx"}:
            raise RuntimeError("Offline verification blocks model/API runtimes")
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            mode = args[1] or ""
            flags = args[2] or 0
            writing = any(c in mode for c in "wax+") or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
            if writing and not Path(os.fsdecode(args[0])).resolve().is_relative_to(temporary):
                raise RuntimeError("Writes are limited to temporary extraction")
    sys.addaudithook(audit)


def unpack(bundle, destination):
    manifest = read(bundle / "SAVED_OUTPUTS_MANIFEST.json")
    archive = bundle / manifest["archive"]
    assert archive.stat().st_size == manifest["archive_bytes"]
    assert sha(archive) == manifest["archive_sha256"], "Archive hash mismatch"
    seen = set()
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            name = member.name
            path = PurePosixPath(name)
            assert member.isfile() and not path.is_absolute() and ".." not in path.parts
            assert path.parts[0] == "results" and name not in seen
            expected = manifest["included"][name]
            assert member.size == expected["bytes"]
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            stream = tar.extractfile(member)
            assert stream is not None
            with target.open("xb") as f:
                shutil.copyfileobj(stream, f)
            assert sha(target) == expected["sha256"], name
            seen.add(name)
    assert seen == manifest["included"].keys(), "Missing archived output"
    return {"files": len(seen), "archive_sha256": manifest["archive_sha256"],
            "omitted_full_state_dumps": len(manifest["omitted_local_only"])}


def verify_baseline(analysis, out, supplement):
    import numpy as np
    expected = read(NEW / "BASELINE_COMPARISON.json")
    assert expected["status"] == "posthoc_baseline_component_comparison"
    assert expected["not_a_replacement_primary_analysis"] is True and expected["new_model_calls"] == 0
    refs = read(out / "reference_manifest_PRIVATE.json")["rows"]
    for env in ("bank", "airline"):
        rows = [r for r in refs if r["eligible"] and r["environment"] == env]
        blocks = sorted({r["block"] for r in rows})
        index = {b: i for i, b in enumerate(blocks)}
        e = expected["environments"][env]
        assert len(rows) == e["rows"] and len(blocks) == e["blocks"]
        outcomes = {m: {r["case_id"]: read(out / "judgments" / m / (r["case_id"] + ".P") / "result.json") for r in rows} for m in ("qwen", "jev")}
        table = {m: analysis.metrics(rows, m, "P") for m in outcomes}
        equal(table, e["table"], env + ".baseline.table")
        draws = np.random.default_rng(2026111202).integers(0, len(blocks), (5000, len(blocks)))
        samples, points = {}, {}
        for m in outcomes:
            counts = np.zeros((len(blocks), 5))
            for r in rows:
                y = r["label"] == 1
                response = outcomes[m][r["case_id"]]
                z = response.get("verdict") if response["status"] == "valid" else None
                counts[index[r["block"]]] += [y, not y, y and z == "violation", not y and z == "authorized", not y and z == "violation"]
            c = counts[draws].sum(axis=1)
            with np.errstate(divide="ignore", invalid="ignore"):
                samples[m] = {"TPR": c[:, 2] / c[:, 0], "FPR": c[:, 4] / c[:, 1],
                              "G": c[:, 2] / c[:, 0] * c[:, 3] / c[:, 1],
                              "accuracy": (c[:, 2] + c[:, 3]) / (c[:, 0] + c[:, 1])}
            points[m] = {**table[m], "accuracy": (table[m]["TP"] + table[m]["TN"]) / len(rows)}
        for metric in ("TPR", "FPR", "G", "accuracy"):
            delta = samples["jev"][metric] - samples["qwen"][metric]
            good = delta[np.isfinite(delta)]
            actual = {"estimate": points["jev"][metric] - points["qwen"][metric],
                      "ci95": np.quantile(good, [.025, .975]).tolist(),
                      "valid_bootstraps": len(good), "undefined_bootstraps": len(delta) - len(good),
                      "zero_width_not_certification": bool(len(good) and good.min() == good.max())}
            equal(actual, e["contrasts"][metric], env + ".baseline." + metric)
        improved, regressed, templates = [], [], {}
        for r in sorted(rows, key=lambda r: r["case_id"]):
            positive = r["label"] == 1
            gold = "violation" if positive else "authorized"
            verdict = {m: outcomes[m][r["case_id"]].get("verdict") for m in outcomes}
            item = {k: r[k] for k in ("case_id", "block", "family", "condition", "label")}
            if verdict["qwen"] != gold and verdict["jev"] == gold:
                improved.append(item)
            if verdict["qwen"] == gold and verdict["jev"] != gold:
                regressed.append(item)
            group = templates.setdefault(r["family"], {"eligible": 0, "positive": 0, "negative": 0, "qwen_TP": 0, "jev_TP": 0, "qwen_FP": 0, "jev_FP": 0})
            group["eligible"] += 1
            group["positive"] += positive
            group["negative"] += not positive
            for m in outcomes:
                group[m + "_TP"] += positive and verdict[m] == "violation"
                group[m + "_FP"] += not positive and verdict[m] == "violation"
        for field, actual in (("improved", improved), ("regressed", regressed), ("by_template", templates),
                              ("improved_blocks", len({r["block"] for r in improved})), ("regressed_blocks", len({r["block"] for r in regressed}))):
            equal(actual, e[field], env + ".baseline." + field)
        for m in outcomes:
            latency = [outcomes[m][r["case_id"]]["latency_seconds"] for r in rows]
            values = {"p50": float(np.quantile(latency, .5)), "p95": float(np.quantile(latency, .95)), "observed_client_seconds_total": sum(latency)}
            equal(values, e["latencies"][m], env + ".latency." + m)
            equal(supplement["strategy_deployment_costs"][env + "." + m + ".P"], e["deployment_costs"][m], env + ".cost." + m)


def main():
    import numpy as np
    with tempfile.TemporaryDirectory(prefix="tgf-saved-results-") as name:
        temporary = Path(name).resolve()
        guards(temporary)
        seals = {}
        for bundle in (OLD, NEW):
            frozen = read(bundle / "manifest.json")
            for path, expected in frozen["files"].items():
                assert sha(ROOT / path) == expected, "Frozen input differs: " + path
            seals[bundle.name] = {"files": len(frozen["files"]), "sha256": sha(bundle / "manifest.json")}
        old_out, new_out = temporary / "old", temporary / "new"
        archives = {OLD.name: unpack(OLD, old_out), NEW.name: unpack(NEW, new_out)}
        for p in OLD.iterdir():
            if p.is_file() and p.suffix in {".json", ".jsonl"}:
                shutil.copyfile(p, old_out / p.name)
        from jev_monitor_v1.analyze import analyze as old_analyze
        equal(old_analyze(old_out), read(OLD / "RESULTS.json"), "development.RESULTS")
        from jev_monitor_v1.verify import verify as verify_development
        development = verify_development(OLD)
        from tgf_jev_mainline_v1 import analyze as primary
        sys.path.insert(0, str(NEW / "postprocess"))
        import supplement
        import diagnostics
        captured = {}

        def check_save(path, value):
            relative = Path(path).relative_to(NEW).as_posix()
            # Match the original save() JSON round trip (e.g. integer label keys).
            value = json.loads(json.dumps(value))
            equal(value, read(NEW / relative), relative)
            captured[relative] = value

        with patch.object(primary, "OUT", new_out / "results"), patch.object(primary, "save", check_save), \
             patch.object(supplement, "OUT", new_out / "results"), patch.object(supplement, "save", check_save), \
             patch.object(diagnostics, "OUT", new_out / "results"), patch.object(diagnostics, "save", check_save), \
             contextlib.redirect_stdout(io.StringIO()):
            primary.main()
            supplement.main()
            diagnostics.main()
            verify_baseline(primary, new_out / "results", captured["SUPPLEMENT.json"])
        assert set(captured) == {"RESULTS.json", "SUPPLEMENT.json", "postprocess/AUDIT_PACKET.json", "DIAGNOSTICS.json"}
        receipt = {"status": "passed", "new_model_calls": 0, "new_simulator_runs": 0,
                   "network_and_child_processes": "blocked", "writes": "temporary extraction only",
                   "numpy_version": np.__version__, "frozen_manifests": seals, "archives": archives,
                   "development_public_input_checks": development,
                   "recomputed": ["development RESULTS.json", *sorted(captured), "BASELINE_COMPARISON.json numeric results and case differences"],
                   "comparison": "Exact keys, types, strings and integers; floats rtol=1e-12, atol=1e-8 for filesystem iteration/summation order.",
                   "limits": "Does not rerun model inference, simulator execution or independent human review. Omitted full simulator-state snapshots are hash-indexed, not re-audited."}
        print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
