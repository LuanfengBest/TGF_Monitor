# November 12 research checkpoint

This checkpoint publishes completed work and the updated research direction. The separately frozen timing v0.2 diagnostic is now complete after an explicitly authorized bounded startup recovery: all 64 formal outputs are valid, with Jev 8→8 and Qwen 4→5 correct pairs under source→linked presentation. The primary Jev contrast is zero. [Timing results](../authorization_timing_jev_2026-11-12/RESULTS.md) and [current execution status](../authorization_timing_jev_2026-11-12/RUN_STATUS.md) supersede preparation-time no-launch and initial-failure-only statements. The previous November 7 report remains intact; the [November 13 package](../final_report_2026-11-13/README.md) is now the integrated manuscript and presentation.

## Read in this order

1. [Team handoff (中文)](TEAM_HANDOFF.md): what changed, what each contribution supports, and what remains open.
2. [Research direction](RESEARCH_DIRECTION.md): the revised question, evidence, originality boundaries, and possible Jev roles.
3. [Mainline results](reports/mainline.md), [semantic audit](reports/semantic_audit.md), and [post-hoc baseline comparison](reports/baseline_comparison.md).
4. [Earlier Jev 2×2 development report](reports/development_2x2.md): a separate, smaller diagnostic using reused data.
5. [AI source re-review and unfilled human packet](source_review/README.md): 32 existing cases / 27 distinct records, nonblind AI work; zero human reviews.
6. [Completed timing results](../authorization_timing_jev_2026-11-12/RESULTS.md), [frozen protocol](../authorization_timing_jev_2026-11-12/PROTOCOL.md), [eight-pair blueprint](../authorization_timing_jev_2026-11-12/PAIR_SPEC.json) and [metrics](../authorization_timing_jev_2026-11-12/METRICS.md): four basic / two intervening-message / two irrelevant-permission pairs. All 64 formal decisions are valid; report absolute correctness, correct changes/invariance and unwanted flips alongside the null Jev primary contrast. The [initial failure](../authorization_timing_jev_2026-11-12/RUN_REPORT.md) and [authorized amendment](../authorization_timing_jev_2026-11-12/recovery_01/AMENDMENT.json) remain separately documented within the original aggregate budget.
7. [Research implications (中文)](IMPLICATIONS.md) and [next-work inventory](NEXT_STEPS.md): what the work can support and what remains.

The [November 13 integrated final report and presentation](../final_report_2026-11-13/README.md) now combine these completed findings with the earlier negative results and timing diagnostic. The November 7 manuscript remains unchanged as history; its existing live presentation Page has been updated in place. No new experiment or expansion accompanied integration.

The readable reports above are publication copies with repository-relative links. Original reports, frozen protocols, raw outputs and numerical results retain their original bytes. A dated sentence such as “not yet published” in an original report describes its creation-time state.

## Published material

| Location | Contents |
| --- | --- |
| [`jev_monitor_v1/`](../../jev_monitor_v1/) | Original Jev/Qwen × raw/ledger implementation and analysis |
| [`tgf_jev_mainline_v1/`](../../tgf_jev_mainline_v1/) | Original new-data collection, P/C/F/T construction, final Judges and frozen primary analysis |
| [`jev_monitor_2x2_2026-11-11/`](../jev_monitor_2x2_2026-11-11/) | Protocol, frozen requests/labels, results, figures, execution receipts and saved-output archive |
| [`jev_tgf_mainline_2026-11-12/`](../jev_tgf_mainline_2026-11-12/) | Protocol, task specifications, primary/secondary results, baseline analysis, source audits, costs and saved-output archive |
| [`PUBLICATION_SCOPE.json`](PUBLICATION_SCOPE.json) | Explicit publication file list and exclusions from the dirty local workspace |
| [`VERIFICATION.json`](VERIFICATION.json) | Offline reproduction receipt from a checkout containing only published files |

Older helper modules included in this publication are dependencies bound by the frozen manifests. Their inclusion does not reactivate earlier campaigns. Historical runbooks and execution permits are records of completed runs, not instructions to submit again.

The later preparation update added a source-bound, explicitly nonblind AI re-review and the timing protocol. Its [v0.2 revision](../authorization_timing_jev_2026-11-12/DESIGN_REVISION.md) added controls before execution while preserving eight pairs, the primary contrast and all aggregate resource caps. `PUBLICATION_SCOPE.json` and `VERIFICATION.json` above describe the original 203-file publication. [PREPARATION_VERIFICATION.json](PREPARATION_VERIFICATION.json) records preparation-time checks and hashes. Run `python3 -B project/research_update_2026-11-12/verify_preparation.py` to check preserved source bindings, symbolic plan logic, label balance and budgets offline. Those preparation artifacts and the original failed run remain historical snapshots; human review remains pending.

The completed continuation has its own [224-file input seal](../authorization_timing_jev_2026-11-12/recovery_01/manifest.json), [226-file result seal](../authorization_timing_jev_2026-11-12/recovery_01/RESULT_HASHES.json), [publication scope](../authorization_timing_jev_2026-11-12/recovery_01/PUBLICATION_SCOPE.json) and [clean verification receipt](../authorization_timing_jev_2026-11-12/recovery_01/VERIFICATION.json). Run `python3 -B project/authorization_timing_jev_2026-11-12/verify_completed_recovery.py` for a standard-library-only reproduction of all timing counts, raw response parsing, pair details and both allocation ledgers. No network, models, GPU or API key is needed. [The original saved-run verifier](../authorization_timing_jev_2026-11-12/verify_saved_run.py) still reproduces the preserved failure archive. The [recovery proposal](../authorization_timing_jev_2026-11-12/RECOVERY_PLAN.md) is now explicitly historical; the actual amendment and completed run supersede its future-tense statements.

## Reproduce saved statistics on CPU

Use Python 3.10 or newer. The verification environment used NumPy 2.2.6.

```sh
git clone --branch pacifica/jev-research-update-2026-11-12 https://github.com/LuanfengBest/TGF_Monitor.git
cd TGF_Monitor
python3 -m venv .venv-offline
.venv-offline/bin/python -m pip install -r project/research_update_2026-11-12/requirements-offline.txt
.venv-offline/bin/python -B project/research_update_2026-11-12/verify_saved_results.py
```

Dependency installation accesses the package index. The verifier itself blocks network connections, child processes and model/API-runtime imports. It extracts saved output files into a temporary directory and removes them afterward. It does not contact Jev, load model weights, execute the simulators, submit a job, or overwrite any saved result. Allow approximately 200 MB of temporary disk space.

The check verifies both frozen input manifests, hashes every shared output, runs the original development/primary/supplementary analysis functions, and checks the saved post-hoc baseline comparison. It checks exact structure and non-floating values; floating sums use `rtol=1e-12, atol=1e-8` because filesystem iteration order can change the last rounding bits.

## Archive scope and limitations

Each experiment directory contains `saved_outputs.tar.gz` and `SAVED_OUTPUTS_MANIFEST.json`. The development archive contains all 749 result files. The mainline archive contains 13,210 files: original public records, conversations, calls/receipts, model requests/responses, follow-ups, reviews, programmatic reference results, and analysis inputs.

The mainline publication omits 615 repeated full simulator-state dump files (`execution_evidence_private.json` and per-turn `execution.json`), approximately 883 MB uncompressed. Their original paths, sizes and SHA-256 hashes are retained in the manifest. Original full archives remain local/on the cluster. **The shared package reproduces the saved statistical results; it does not claim to rerun the complete simulator-state reference audit without those omitted files.**

Files named `PRIVATE` contain synthetic hidden-task/reference information withheld from the evaluated Judge; they are not real customer records. Public Judge inputs and reference material remain separately identifiable. Credentials, virtual environments, downloaded tokenizer/model assets, duplicate transport ZIPs, browser screenshots and unrelated historical local drafts are excluded. No key is needed for offline verification.

Qier's and Tony's latest additions are linked at exact commits in the handoff and are not silently merged. Their attribution and original result boundaries remain visible.
