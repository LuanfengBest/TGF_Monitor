# Pacifica workstream — curated snapshot, October 19, 2026

This directory imports useful progress from the local `monitorability_tgf` workspace through October 18. Copied files retain their original bytes; the exact inventory and hashes are in [import_manifest.json](../../project/import_manifest.json). The newest cross-workstream conclusions are in [the project overview](../../project/README.md).

## Start here

1. [Full64 authorization audit](docs/tgf_full64_authorization_audit_2026-10-18.md) and [review contract](docs/tgf_full48_authorization_review_contract_2026-10-18.md).
2. [Current proposed experiment](docs/tgf_experiment_plan_team_v2_2026-10-18.md).
3. [Case labels](analysis/tgf_full48_authorization_20261018/case_labels.csv), event review, and state checks in the same directory.
4. [SFT component results](docs/sft_three_arm_results_2026-10-15.md) and [repaired-interface diagnostic](docs/sft_format_diagnostic_and_next_steps_2026-10-15.md).

## Included

- Historical scripts, tests, configurations, scientific notes, and derived analyses.
- All 64 raw source records required by the read-only full64 validator, retaining their relative source paths.
- Luanfeng's complete `ctx128k_v4` and `ctx128k_v4_tl2000` run directories.
- Raw three-arm SFT, repaired-interface, and selected natural four-arm outputs, plus small scientific acceptance records.
- Component training/evaluation data and the pinned MonitorBench source used by local components. The nested upstream checkout is a plain source snapshot without `.git`, at `b6229e4b8ea9abcec38d61159c9cbd0f577ddf35`.

## Scope and portability

This is a curated research snapshot, not the full multi-GB working directory. Downloaded public corpora, large historical collection state chains, annotation duplicates, transport archives, model weights/tokenizers, virtual environments, personal operation logs, email drafts, and screenshots are omitted. Their historical references may remain in unchanged notes and frozen configuration inventories. Some historical scripts therefore need original external assets or a cluster environment; importing them does not make every historical run independently executable from this checkout.

Use only the documented CPU checks in [REPRODUCIBILITY.md](../../project/REPRODUCIBILITY.md) to validate this handoff. Original absolute HPC paths and old job/budget records are provenance, not new authorization. The eight-case / 72-call / 60-H200-minute diagnostic is still a proposal.

Files marked `PRIVATE`, raw simulator states, hidden goals, labels, and review judgments are offline reference material. Monitors must receive a validated public projection, never this whole snapshot. Existing benchmark credential-shaped strings belong to the upstream simulated environment; no local environment files or live account credentials are included.
