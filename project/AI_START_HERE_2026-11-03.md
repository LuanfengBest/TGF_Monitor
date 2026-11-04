# TGF handoff: start here

Updated November 3, 2026. This handoff records Pacifica's bounded development run and offline diagnosis. It does not replace the teammate's pending four-case B2/revised-TGF comparison.

## Read in this order

1. [Short team update](PACIFICA_PROGRESS_2026-11-03.md).
2. [Offline diagnosis](prospective_monitoring/offline_diagnostic_2026-11-03/DIAGNOSIS.md) and [24-case matrix](prospective_monitoring/offline_diagnostic_2026-11-03/CASE_MATRIX.md).
3. [Four-case comparison worksheet](prospective_monitoring/offline_diagnostic_2026-11-03/TEAM_4_CASE_REVIEW.md). Its case IDs, outputs and comparability fields are genuinely pending.
4. [Current status](prospective_monitoring/STATUS.md), [experiment design](research_reset_2026-11-02/EXPERIMENT_PLAN_2026-11-03.md), and [implementation](../prospective_monitoring/README.md).

## Facts and interpretation

- Job31821684 completed in20m08s, with24 natural development trajectories and210 calls. All24 were legitimate sensitive executions, with30 covered writes. There are no positive violation cases or held-out test cases.
- P/C/F/T original valid judgments:9/24,3/24,3/24,4/24. F/T valid pairs:0/24. F actually asked3 follow-ups; T asked24. Both asked in3 cases, but no pair passed both final validations.
- C and F each failed21 initial reviews; those42 final judge calls never occurred. Another35 actual judge outputs failed citation validation. Missing output must remain missing.
- All77 failed arm results report `Unbound exact citation`. This does not mean all underlying reasoning was correct: four T raw scores rose to50/25/30/15 with unsupported authorization/timing concerns. Five further T rationales covered only part of the action record. Content annotations are non-blind diagnostic review, not independent human gold.
- The original scores, validation rule, results, raw evidence and failure denominators remain unchanged. Raw score extraction is not repaired efficacy evaluation.
- November3's design compares full selection-plus-questioning strategies. October21's planned matched diagnostic compared wording conditional on the same selected action. Do not silently treat these as the same estimand. Check what the teammate's actual configuration changes before interpreting its four cases.

## Safe offline reproduction

Run from the repository root with Python3.12+ (standard library only). No model downloads, credentials, inference, simulator actions, or Slurm submission are needed for these commands.

The committed results archive is `project/prospective_monitoring/shared_evidence/tgf_prospective_results_31821684.tar.gz` (14,129,265 bytes).
SHA-256: `bcfc9e2a9e382c128c3d8c22c6196b27a898e90d790d66108475143750d17053`.
It preserves all run outputs, GPU log, accounting, configuration, source snapshot and provenance. Model weights, caches, virtual environments and duplicate extracted trees are excluded.

```sh
python3 project/prospective_monitoring/reporting/unpack_shared_evidence.py --out /tmp/tgf-31821684-handoff
python3 project/prospective_monitoring/reporting/pilot_report.py --run /tmp/tgf-31821684-handoff/results_31821684/runs/development_20261103 --output /tmp/tgf-31821684-report
python3 project/prospective_monitoring/reporting/offline_diagnostic.py --run /tmp/tgf-31821684-handoff/results_31821684/runs/development_20261103 --output /tmp/tgf-31821684-diagnostic
```

Use fresh output directories. The unpacker verifies the archive and all1,405 recorded files. The diagnostics verify original run hashes and reproduce original validation before extracting raw scores. Preserve the extracted directory structure: archived protocol equality is checked. Source schema and synthetic tool data are intentionally retained for review; never expose private actor context to monitor prompts.

The qualitative files `judgment_content_review.json` and `data_yield_review.json` are saved review annotations. Deterministic scripts do not regenerate or independently validate their semantic judgments.

For implementation inspection, the full new `prospective_monitoring/` package is included. Only its needed legacy helpers are newly included from `matched_followup_v2` and `matched_followup_v3`; this is not a complete new export of the older v2/v3 experiments. The two public execution decoders and original simulated environments are already in repository history.

## What to do next

Use the worksheet when the teammate supplies the four-case artifacts. Verify the authorization endpoint and original event evidence, then compare questions, answers, score changes, evidence support and actual cost. Do not assume shared cases imply shared selection, judge inputs or budget. Keep that batch separate from this24-case development pilot.

No new study or rerun is authorized by this handoff. Job31821684's permit is consumed and `closed.json` says `retry_allowed=false`. Do not run `pilot.sbatch`, `campaign`, historical submission helpers, or issue a replacement permit. Do not expand to120 cases, train a new model, change old labels, or turn relaxed parsing into original success. Those require a separately agreed study after reviewing the existing evidence.

The project contains historical documents with earlier status text and machine-specific paths. This entrypoint and current STATUS supersede their operational instructions. The historical full32/64/8-case results, source snapshots and assumptions remain distinct evidence, not pooled new samples.
