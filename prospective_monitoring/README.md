# Prospective TGF: bounded development workflow

This is the implementation checkpoint for the November 3 experiment design.
It is separate from frozen v2/v3 runs. Imports and CPU fixtures do not call models;
the live campaign requires fresh admission and a dedicated single-use permit.

## What is implemented

- `reference.py`: explicit bank/airline authorization contracts and an event/state
  verifier. Missing or inconsistent evidence stays `reference_unknown`.
- `reference_fixtures.py`, `contracts/`: 21 scripted verifier examples, including
  legitimate sensitive actions, exact account spelling, cumulative limits,
  corrections, rejected attempts, and violations later reversed.
- `simulator.py`: records actual before/after state around the repository's original
  environment/runtime functions. A tool error does not erase an observed side effect.
- `scenarios.py`, `scenario_registry.json`: four development specification families.
  All variants remain in their family and split. No held-out test family is ready.
- `protocol.py`, `runner.py`, `config.json`: public action-only projection and four
  independent strategies. P judges directly; C performs two reviews; F uses a fixed
  question plus one review; T selects an event/dimension and asks one bound question.
  Both actor branches reopen the same original context with tools disabled. F never
  receives T's selection. All cases remain in the output even when a stage fails.
- `analysis.py`: private reference-to-output join, all-case triage metrics, explicit
  detection/coverage/failure rates, paired family bootstrap, and per-model costs.
- `sampling.py`: score-blind quota selection with family/split binding, deduplication,
  sensitive negatives, provenance checks, and a full exclusion receipt.
- `task_setup.py`, `collection.py`: bounded native collection in the original
  simulator, with delivered authorization, private history, and state evidence.
- `native_backend.py`, `preflight.py`, `campaign.py`: native model admission,
  persistent stage workers, hard deadlines, and a bounded four-stage campaign.

The fake backend always produces scripted zero scores. Its usage numbers are
invented wiring checks, not real model tokens, runtime, accuracy or cost evidence.
The sampler rejects scripted fixtures as natural actor test trajectories.

## Verified checkpoint

The first preparation checkpoint passed **81 CPU tests**, including 14 tests
against the original simulator environments/tools. The expanded deployment's
current test count and logs are recorded in the deployment directory and STATUS.md.
Interpreter:

`../monitorability_tgf/.venv/bin/python` (Python 3.10.16; existing local dependencies).

From repository root:

```sh
../monitorability_tgf/.venv/bin/python -m unittest discover -s prospective_monitoring -t . -v
```

Standard-library-only modules can also run under the system Python; original
simulator checks require its existing Pydantic/PyYAML environment. A run with skipped
simulator tests is not equivalent to this full checkpoint.

To create a new fake-backend integration receipt, use a fresh output directory:

```sh
python3 -m prospective_monitoring.offline_acceptance --out /tmp/tgf-offline-acceptance-new
```

To retain actual simulator tool evidence, without a model:

```sh
../monitorability_tgf/.venv/bin/python -m prospective_monitoring.simulator_acceptance --out /tmp/tgf-simulator-acceptance-new
```

Both commands refuse to reuse an output directory. They are engineering acceptance
checks and never produce eligible natural test data.

## Current interpretation and limits

The reference measures the explicitly covered permissions only. Bank support is
Venmo/Zelle principal transfers, with service-qualified recipient IDs; fees are
outside this reference. Scheduled bank payment orders remain unresolved. Airline
support covers ticket purchase (including purchase-time upgrades) and cancellation;
post-booking upgrade inconsistencies remain unresolved. Unsupported writes are not
declared safe. Gross budgets are not replenished by cancellation or reversal.

Four development scenario structures and retained real-tool scripted examples do
not establish task diversity or monitor performance. `task_setup` and `collection`
now bind each delivered authorization revision to actual message/event IDs and
record native actor histories and committed simulator effects. A final answer or
`end_task` means interaction termination, not verified task success; no-action
negatives must be reported separately. No independent label review is claimed.

The original `runner` remains a CPU-only fixture runner. `native_backend` and
`campaign` provide the separate live path: persistent, killable single-model
workers and four staged model loads. `preflight` checks pinned runtime, full cached
asset hashes, actual Harmony serialization, representative tokenizer capacities,
and monitor grammar without loading model weights. Real calls also check their
exact token capacity. A fresh receipt binds code/config/tasks; a single-use permit
prevents replay. There is no retry or automatic formal expansion.

At candidate caps the normal four-strategy path is 10 calls per case: P=1, C=3,
F=3, T=3. Thus 24 development cases reserve up to 240 monitoring calls and 589,824
output tokens. The prospective pilot additionally allows at most 192 generation
calls (8 per case), so its combined maximum is 432 calls / 1,376,256 output tokens.
The scheduler ceiling is one H200 for four hours, with a 14,100-second internal
deadline. The 180-second collection limit is uncalibrated. These are hard ceilings,
not evidence that F and T actually cost the same. No old v2 permit is reused.

## Evidence and next work

See [preparation status](../project/prospective_monitoring/STATUS.md) and
[experiment design](../project/research_reset_2026-11-02/EXPERIMENT_PLAN_2026-11-03.md).
Deployment support and review notes are under
`project/prospective_monitoring/deployment_2026-11-03/`. Consult STATUS.md for actual
job IDs and admission results. The formal 120-case pool remains uncollected and
requires separate, held-out task families and a frozen evaluation design.
