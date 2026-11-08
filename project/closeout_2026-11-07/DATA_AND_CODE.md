# Data, code and CPU reproduction

The repository includes the inputs, original outputs, frozen configurations, analysis code and author-review artifacts needed for the principal results in the [final report](FINAL_REPORT.md). The November 7 evidence ZIP remains the original final-validation package; the additional earlier data are in the repository directories listed below.

## Reproduce the saved results after a fresh checkout

Run from the repository root using Python 3.10 or newer. The clean-environment check used Python 3.10.16 and the pinned CPU dependencies below.

```sh
python3 -m venv .venv-offline
.venv-offline/bin/python -m pip install -r project/closeout_2026-11-07/requirements-offline.txt
.venv-offline/bin/python -B project/closeout_2026-11-07/verify_all_results.py
```

Dependency installation uses the package index. The verification command itself is read-only and forbids network connections, child processes, file writes and model-runtime imports. It uses no GPU, API key, model weights, Bouchet access or new simulator episodes. It fails on missing/changed bound files or a result mismatch. Do not run with `python -O`, because the original validators use assertions.

The [entry point](verify_all_results.py) calls the original analysis functions and compares their complete returned objects with saved reports. For the two evidence-use probes only, the newly generated `created_at_utc` field is excluded from equality; predictions, failures, costs, paired contrasts and review identifiers are compared. The natural-collection check verifies recorded requests, receipts, state chains and reference evaluation against the saved review/coverage counts. It does not regenerate semantic annotations or certify them as human gold.

## Data and source map

| Result | Included data | Original code | Expected check |
| --- | --- | --- | --- |
| Earlier endpoint/failure accounting | [Aligned cohorts](../evaluation_alignment_2026-11-05/data/) | [Offline scorer](../evaluation_alignment_2026-11-05/offline_eval.py) | Both saved dev64 and natural24 reports match exactly; label namespaces stay separate |
| Natural actor collection | [48 records, raw states, requests and receipts](../new_data_collection_2026-11-05/cluster_results_32257283/campaign/), [frozen task specifications](../new_data_preparation_2026-11-05/frozen_specifications/), [author review](../new_data_collection_2026-11-05/author_review_2026-11-06/) | [Collector and audit](../../prospective_collection_v1/), [task preparation](../../prospective_data_v2/), [reference and simulator adapter](../../prospective_monitoring/) | 48 records, 155 actor calls, 107 recorded tool events; bank 1/23 and airline 6/18 violation/legal counts |
| Four-strategy comparison | [Frozen bundle](../airline_monitor_comparison_2026-11-06/bundle/), [raw comparison](../airline_monitor_comparison_2026-11-06/cluster_results_32354336/comparison/), [saved report](../airline_monitor_comparison_2026-11-06/report_32354336/) | [Protocol, campaign and analysis](../../airline_dev_v1/) | 96 judgments and 240 total calls; predictions and full report match exactly |
| Fixed-operation question comparison | [Frozen bundle](../anchored_question_diagnostic_2026-11-06/bundle/), [raw comparison](../anchored_question_diagnostic_2026-11-06/cluster_results_32374475/comparison/), [saved report](../anchored_question_diagnostic_2026-11-06/report_32374475/) | [Protocol, campaign and analysis](../../anchored_question_v1/) | 144 judgments and 288 total calls; predictions and full report match exactly |
| First evidence-use diagnostic | [Requests, labels, analyses and raw results](../evidence_use_diagnostic_2026-11-07/), [reference/source audit](../evidence_content_audit_2026-11-07/full_batch/) | [Preparation and Judge runtime](../../evidence_use_v1/), [analysis](../evidence_use_diagnostic_2026-11-07/analyze_results.py) | All 136 positions; 132 valid and 4 schema failures |
| Cumulative evidence and assertions | [Requests, labels, analyses and raw results](../evidence_claim_probe_2026-11-07/) | [Preparation and Judge runtime](../../evidence_use_v2/), [analysis](../evidence_claim_probe_2026-11-07/analyze_results.py) | All 60 positions; 58 valid and 2 truncations |
| Final controlled validation | [Frozen inputs, original results and reviews](validation/), [sealed AI review](ai_blind_review_2026-11-07/) | [Preparation, execution and analysis](../../closeout_validation_v1/), [final-only verifier](offline_verify.py) | All 120 positions; 105 valid, 14 truncations, 1 schema failure, 104 correct valid labels; AI reference agreement 12/12 |

Calls, judgments, records and independent task blocks are different denominators. Several comparisons reuse records, and the final 12 records are constructed simulator inputs. Do not sum these rows into an independent sample size or a pooled accuracy.

## What is preserved

- Original model outputs, failure statuses, request/native-prompt hashes, call receipts, frozen labels and budget/configuration files retain their bytes. The publication does not rerun, refill, relabel or tune the experiments.
- The original modules include preparation, runtime, export and submission code for provenance. Frozen manifests bind their versions. The CPU verifier exercises saved-result analysis only; publishing these files does not issue or renew a GPU execution permit.
- The model runtime's pinned revisions and versions remain in [the native adapter](../../prospective_monitoring/native_backend.py), cohort configurations and admission receipts. Full GPU inference requires the original Linux/CUDA/model assets and separate execution setup; the clean CPU check does not claim to validate another GPU run.
- `PRIVATE` and `LOCAL_ONLY` identify evaluation material withheld from experimental Judges. These are simulator research records, not a claim of independent human annotation.
- Tony's November 7 result snapshot and exact upstream commit remain in the [source index](evidence_index.json). This reproduction does not claim to independently rerun Tony's raw job.

The original report/PDF/Word and final-validation evidence ZIP are unchanged. Earlier intermediate drafts, screenshots, local caches, model weights and unrelated exploratory branches are not required for these checks.

The supplemental [publication and clean-checkout receipt](data_code_publication.json) records the added file hashes, environment, positive verification and missing/tampered-output checks. The initial [publication receipt](repository_publication.json) describes the preceding results/report snapshot; use each receipt with its recorded parent/commit context.
