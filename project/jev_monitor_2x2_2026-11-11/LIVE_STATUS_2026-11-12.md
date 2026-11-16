# Live status — 2026-11-12

**Completed.** All 248 planned model calls returned valid results: 124 Qwen and 124 Jev, including 8 interface fixtures and 240 development judgments. There were no retries, missing results, abstentions or new Actor calls. The final analysis is in `RESULTS_REPORT.md`, with full statistics in `RESULTS.json` and per-case predictions in `CASE_RESULTS.json`.

Qwen job **33071622** completed successfully with exit code **0:0**, using one H200 for **321 seconds**. All raw/parsed results, prompt hashes and usage passed verification before the remaining 120 Jev development calls were started. Jev API cost including fixtures is estimated at **$0.012413478**.

Ledger-induced corrections were confined to constructed cases: three corrections for Qwen and four for Jev, with no new classification errors. Neither model changed a natural-record classification when the ledger was added. In the six reference-positive natural airline cases, Jev detected all six while Qwen detected none. These are reused development data with inherited AI-reviewed reference labels, not human-gold confirmation results.

- Organization: Pacifica Research.
- API key name: `jev-2x2-2026-11-12`; the console showed Active.
- Local credential file: `/Users/a1234/.config/typesafe/api_key`, permissions `0600`, parent directory `0700`.
- The runner reads the credential with `--jev-key-file /Users/a1234/.config/typesafe/api_key`.
- Read-only authentication check: `GET /v1/models`, HTTP 200.
- Planned Jev smoke: four calls, four valid responses, all returned `jev-1.14.0`.
- Usage: 4,371 input tokens and 170 output tokens. Estimated API cost: $0.000183582 at the verified $0.042 per million input tokens; output tokens are free. This is a usage-based estimate, not a billing receipt.
- Smoke receipt: `results/jev_smoke_passed.json`; per-request dispatch, raw response and parsed result files are retained under `results/fixture*.C` and `results/fixture*.D`.
- Frozen manifest SHA-256: `a65595380ebfa9fe4a8342c1f906215ec940599573f085d301e7d0478a570b63`; preflight verification passed without changing the frozen files.

The user completed a $5 credit purchase; the console showed $5.00 available before the smoke calls. Auto-recharge was Off.

## Cluster admission and submission

The user reauthenticated through the course Bouchet OnDemand portal. The verified live account is `cpsc4880_rz377`, with Slurm account `cpsc4880` and `normal` QOS. Use this authenticated browser route for this deployment; the earlier local SSH check used a different login name and did not establish a usable route.

- Fresh checks found no pre-existing user jobs; H200 partition availability and course account association were verified.
- Course project quota: 1,850 GiB used of 4,096 GiB; snapshot dated Nov. 12 by the quota service.
- All 19 pinned model assets were present with matching sizes. Tokenizer hashes and exact Python, vLLM, Torch, Transformers and Harmony runtime versions passed the CPU admission check. Full weight hashing, grammar compilation and exact prompt-token checks still run inside the GPU allocation before inference.
- The 45-file isolated archive passed transfer SHA-256, frozen manifest and Jev smoke receipt verification. It contains no API key.
- Remote experiment directory: `/nfs/roberts/project/cpsc4880/cpsc4880_rz377/jev_2x2_20261112_a6559538`.
- Actual submitted job: **33071622**, submitted Nov. 12 at 00:52:49 America/New_York. One H200, six CPUs, 160 GiB RAM, maximum 90 minutes, no requeue.
- Job number 33071569 appeared only in `sbatch --test-only` scheduling admission. It was not a submitted allocation.
- Initial state was PENDING because suitable nodes were unavailable. Final accounting: start 00:56:47, end 01:02:08 on Nov. 12 America/New_York; 3 minutes 58 seconds queued, 5 minutes 21 seconds allocated. Main, batch and extern records all report COMPLETED and exit 0:0.

Local evidence is in `deployment/cluster_admission_OBSERVED.json`, `deployment/submission_OBSERVED.json`, `deployment/queue_33071622_initial.txt`, and `deployment/transfer_receipt_LOCAL.json`. Check current state in the existing OnDemand shell with:

```sh
python3 /home/cpsc4880_rz377/jev_deploy_20261112.py status
```

The four Qwen fixtures and 120 Qwen development requests completed. Their result archive was downloaded through OnDemand and all 394 payload files passed SHA-256 checks; the complete 124-call Qwen audit also passed locally. The 120 Jev development requests then completed locally. The frozen manifest is unchanged. `FINAL_RECEIPT.json` and `FINAL_RESULT_FILES.json` seal the completed artifacts and result files. Qwen emitted nanobind cleanup warnings after its last valid result; no traceback, ERROR, missing output or failed scheduler step was observed. The warning is retained in the report and raw log.

No further calls or GPU jobs are scheduled. Do not resubmit this job or repeat requests. The fixed $0.20 API and one-H200/90-minute limits were respected. Human review of the reference labels and a future held-out confirmation set remain separate research work, outside this completed run.

This status note records live progress after the freeze. The frozen preparation documents remain the original pre-run record. Passing these fixtures establishes API/interface usability, not experiment effectiveness.
