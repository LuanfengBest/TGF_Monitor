# November 12 research checkpoint

This checkpoint publishes completed work and the updated research direction. It does not launch another experiment. The previous November 7 report remains intact and is not yet an integrated final manuscript for this checkpoint.

## Read in this order

1. [Team handoff (中文)](TEAM_HANDOFF.md): what changed, what each contribution supports, and what remains open.
2. [Research direction](RESEARCH_DIRECTION.md): the revised question, evidence, originality boundaries, and possible Jev roles.
3. [Mainline results](reports/mainline.md), [semantic audit](reports/semantic_audit.md), and [post-hoc baseline comparison](reports/baseline_comparison.md).
4. [Earlier Jev 2×2 development report](reports/development_2x2.md): a separate, smaller diagnostic using reused data.
5. [AI source re-review and unfilled human packet](source_review/README.md): 32 existing cases / 27 distinct records, nonblind AI work; zero human reviews.
6. [Timing diagnostic protocol](../authorization_timing_jev_2026-11-12/PROTOCOL.md) and [budget](../authorization_timing_jev_2026-11-12/BUDGET.md): Jev primary, Qwen comparator; prepared, not executed.
7. [Research implications (中文)](IMPLICATIONS.md) and [next-work inventory](NEXT_STEPS.md): what the work can support and what remains.

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

The later preparation update adds a source-bound, explicitly nonblind AI re-review and a proposed timing protocol. `PUBLICATION_SCOPE.json` and `VERIFICATION.json` above describe the original 203-file publication, not this later preparation. [PREPARATION_VERIFICATION.json](PREPARATION_VERIFICATION.json) records the follow-up checks and file hashes. No frozen input or result is changed. Human review is still pending, and no new experiment is authorized.

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
