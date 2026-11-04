# Pacifica's TGF handoff — November 3, 2026

Read [the short team update](PACIFICA_PROGRESS_2026-11-03.md), [diagnosis](DIAGNOSIS.md), and [four-case worksheet](TEAM_4_CASE_REVIEW.md).

This publication is a **Git handoff package**. Local command-line Git could not resolve github.com, so these files were submitted through the authenticated GitHub website. The full verified implementation and evidence are inside the Git bundle; they have not been silently merged into main.

## Restore the exact code and data

Clone the project repository normally, download `TGF_Pacifica_Handoff_2026-11-03.bundle` from this branch, and place it in the clone root. Then run:

```sh
git bundle verify TGF_Pacifica_Handoff_2026-11-03.bundle
git fetch ./TGF_Pacifica_Handoff_2026-11-03.bundle refs/heads/pacifica/diagnostic-handoff-2026-11-03:refs/heads/pacifica/diagnostic-handoff-2026-11-03
git switch pacifica/diagnostic-handoff-2026-11-03
```

Run these commands in a clean checkout. Do not reset or overwrite someone else's work. The bundle requires base commit `cc7ac7563d583f3b941d91c6f3dbf4430327968f`, which was the observed remote main when prepared. It restores source commit **91acf5e177bf2c5b51103f54a1bda0dd7aa373c0**, including the67-file handoff change and its three previously local preparation ancestors.

Bundle SHA-256: `bfb18fd96aed5ea00360861c5169ff7281b31a12ca5a722bc0b5007ca65c8de5`. Size: 15,270,268 bytes.

After restoring, read **`project/AI_START_HERE_2026-11-03.md`**. It contains offline-only verification, extraction and report commands. The original14.13MB results archive is included in the bundle. All1,405 archived files were verified; reports were reproduced from a fresh staged checkout.159 CPU tests and12 reporting tests passed.

## Scientific status and next step

Job31821684 completed24 development trajectories with210 calls. All24 are legitimate sensitive executions; no violation positives. Original valid P/C/F/T counts are9/3/3/4 out of24; F/T valid pairs remain0.42 final judgments never ran because C/F initial reviews failed. Raw scores and semantic review are supplementary diagnosis, not replacement results.

Four T raw outputs question timing/authorization despite explicit prior permission; one reaches threshold50. This is a failure-case observation, not proof of causal harm or a general claim that TGF is worse.

A teammate's separate four-case B2/revised-TGF comparison is pending. Its exact case IDs, configuration and outputs are unknown. Use the worksheet to check evidence and comparability when those arrive. Do not assume the same cases imply the same selection or budget. Do not pool this24-case pilot with the teammate's batch.

**No new inference, training, Slurm submission, rerun, automatic expansion, or replacement permits are authorized.** The original permit is consumed. Code and artifacts are for inspection and CPU-only reporting. The Git bundle contains historical executable files; their presence is not permission to run them.

Links inside the detailed diagnosis/worksheet may refer to the restored repository tree. Those referenced JSON files and raw evidence are included in the bundle, not omitted from the handoff.
