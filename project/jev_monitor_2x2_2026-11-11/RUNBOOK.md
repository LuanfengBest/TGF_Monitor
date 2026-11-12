# Runbook: not yet launched

This folder is the prepared new development experiment, not a completed result. Do not reuse any previous job permit or modify frozen inputs in place.

## Local checks

From the repository root:

```sh
python3 -m unittest jev_monitor_v1.test_protocol -v
python3 -m jev_monitor_v1.verify
```

`capacity_LOCAL.json` uses the exact pinned Qwen tokenizer files, whose SHA-256 hashes match the old native backend. The local Python environment under `.venv` was installed only for tokenizer checks and the Jev HTTP client. Recreate with `uv venv` and `uv pip install --python ... tokenizers==0.22.1 jinja2==3.1.6 requests==2.32.5` if needed; the GPU still uses the separately pinned cluster container.

## Unresolved live prerequisites

The user reported that the TypeSafe key is not configured. Obtain one from the [TypeSafe console](https://console.typesafe.ai/keys). Supply it through `TYPESAFE_API_KEY` in the running process, or use `--jev-key-file /absolute/private/path` with an owner-only file outside this repository. Do not put the secret in chat, experiment JSON, command-line arguments, Git or the transferred cluster bundle. No Jev key is needed on the cluster, because Jev runs locally.

The direct SSH check to `rz377@login1.bouchet.ycrc.yale.edu` timed out. A current authenticated cluster route, queue/account state, image availability and pinned asset availability must be checked before submitting. Local historical paths are provenance, not proof that remote assets still exist. The checked browser inventory had no open Bouchet/OnDemand session.

Recheck the [TypeSafe price and model limits](https://docs.typesafe.ai/models) if launch is delayed. Planned client cap is $0.20; planned GPU cap is one H200 job for at most 90 minutes. These limits cover only this 248-call development experiment. They do not include new Actor trajectories or a confirmation set.

## Execution order

1. Run four Jev interface calls locally:

```sh
project/jev_monitor_2x2_2026-11-11/.venv/bin/python -m jev_monitor_v1.run --model jev --phase smoke --jev-key-file /absolute/private/path
```

The code verifies the frozen manifest first and creates one dispatch claim before every call. Missing credentials cause zero dispatches. Interface failure stops progression; do not edit prompts based on formal answers.

2. Transfer a dedicated checkout containing all manifest-bound files plus `results/fixture*.C`, `results/fixture*.D` and `results/jev_smoke_passed.json`. Do not transfer `.venv`, tokenizer caches, secret files or other experiment directories. Keep the directory structure identical so source hashes and relative paths verify. The private reference files are separately named and are never input to a model; they are included only because this freeze verifies all experiment artifacts.

3. On the cluster, verify that the configured snapshot, container and dependency directory are present, inspect the user's queue/account, run the offline verifier, and create `logs/` in the dedicated checkout. Submit `jev_monitor_v1/run.sbatch` once with `--chdir` set to that checkout. Save the scheduler job ID and monitor it in the current chat until the requested condition. The batch script prevents reusing its allocation directory; the runner prevents a second model allocation. No automation is created.

The GPU job hashes the pinned Qwen assets, checks actual runtime versions, compiles the JSON grammar, checks every prompt's token IDs against the local seal, loads Qwen, runs four Qwen interface fixtures, and then (only if both smoke stages passed) runs the 120 Qwen development requests. A second GPU job is not part of this envelope.

4. Collect raw outputs, parsed outputs, dispatch claims, model-ready data and `allocation_finished.json`. Verify transport hashes and obtain `sacct` state, exit code, allocated GPU count and elapsed time. Queue time, startup/hash time and ready-model request latency are separate. No template submission wrapper currently bypasses this live check.

5. After the verified Qwen results and smoke receipt are restored locally, run the 120 Jev development requests:

```sh
project/jev_monitor_2x2_2026-11-11/.venv/bin/python -m jev_monitor_v1.run --model jev --phase development --jev-key-file /absolute/private/path
python3 -m jev_monitor_v1.analyze --output project/jev_monitor_2x2_2026-11-11/RESULTS.json
```

All failures and unstarted positions remain in the analysis. Fixture effects are excluded; fixture costs are included. The analysis output is diagnostic development evidence and must not be presented as a fresh confirmation set. Do not generate a success conclusion before this run has produced actual model results.

## Files

`PROTOCOL.md` fixes scope, estimands and limits. `requests.jsonl` holds all 248 slots and public states. `public_inputs.jsonl` contains the 60 formal public projections; `ledger.jsonl` includes the 60 formal ledgers and 2 fixture ledgers. `labels_PRIVATE.jsonl` and `provenance_PRIVATE.jsonl` hold evaluation-only metadata. `qwen_assets.json` holds the prior pinned weight inventory for fresh verification. `manifest.json` binds data, prompts, configuration, source code and preparation documents. `PREPARATION_REPORT.md` summarizes readiness and remaining prerequisites.
