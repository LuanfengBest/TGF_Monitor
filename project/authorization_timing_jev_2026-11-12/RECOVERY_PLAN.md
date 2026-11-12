# Recovery proposal — not launched

The original v0.2 run ended during Qwen startup. Its frozen files and STOP receipt must remain intact. This document is a concrete engineering proposal; no recovery run, cache reuse or new allocation has been executed, and a recovery adapter has not yet been implemented.

**Recommended scope:** retain the same 16 records, public prompts, labels, model versions, token sequences, random seed, 32-slot formal order and metrics. Do not resample. Preserve the four completed Jev smoke calls and their costs. The remaining request ceiling is 68: four Qwen smoke, 32 Qwen formal, then 32 Jev formal. A formal request must still have at most one dispatch across both runs.

## Budget amendment required

The original 0.5 H200-hour ceiling leaves 563 seconds after the 1,237-second failed allocation, but its **one-allocation limit is consumed**. A possible amendment is one additional H200 allocation capped at **nine minutes (540 seconds)**: combined use would be at most 1,777 seconds = 0.493611 H200 hours. The original allocation and failure would remain in the denominator and resource ledger. This changes the allocation-count rule from one to two; the original user instruction does not authorize it. Do not submit before explicit authorization for that exception.

The Jev attempt limit stays 36 across both stages/runs, the total attempt limit stays 72, the API client cap stays $0.10, retries stay zero and the simulator booking count stays 16. Any CPU asset verification must fit the unused portion of the original 15-minute / four-core / 16-GiB preparation cap, with measured time recorded. If the remaining CPU or GPU allowance cannot support a safe startup, stop and report rather than expand it silently.

## Preparation before any new GPU submission

1. Create a separate amendment manifest referencing the failed run and preserving every old artifact. Record the eventual authorization, exact engineering changes and remaining budgets. Do not delete STOP, re-use a consumed submission claim or relabel the old allocation as successful.
2. Move full model-asset hashing to a bounded CPU preflight before the GPU allocation. Bind the resulting receipt to the pinned revision, paths, lengths, digests and file identity metadata; recheck identity before loading and stop if anything changed. Do not simply skip integrity checks.
3. Inventory and hash a copy of the completed development run's compiled cache. The observed cache factors and graph match, but the full artifacts have not been checked for portability. Keep the source cache untouched; record the copied files and validate runtime/model/device compatibility. Cache validation failure means stop, not an unbudgeted cold compile or an unrecorded switch to eager mode.
4. Implement and test the amended startup/dispatch gates offline, including expired preflight, changed assets, cache mismatch, missing budget, prior dispatch and forced timeout. Keep the same inference settings and xgrammar output schema. Make authorization false by default until the amendment is approved.
5. Verify an empty queue, exact Slurm limits and a clean no-network reproduction of the original archive. Review the resulting patch and resource ledger before submission.

## If the amendment is later authorized

Submit at most once with `--time=00:09:00`, one H200 and no requeue. Use a deadline that includes startup and cleanup; no nine-minute completion guarantee is claimed. Log an explicit readiness receipt before any dispatch. Stop at the first interface failure or time limit. Run the Jev formal phase only after all 36 required Qwen slots and its interface check finish. Keep undispatched or failed slots visible and report the two allocation receipts together.

This is an infrastructure-only continuation proposal. It cannot be used to tune prompts against outcomes, replace failed judgments, claim an independent replication, or pool this constructed diagnostic with the completed 189-trajectory mainline study.
