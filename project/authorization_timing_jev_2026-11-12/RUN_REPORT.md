# Timing v0.2 run report — startup failure

The eight-pair diagnostic was prepared, frozen and started on November 12, 2026. **It produced no formal Judge decisions.** This is an infrastructure failure report, not evidence for or against the timing hypothesis, a model ranking, or a null presentation effect. The previous completed mainline findings remain unchanged.

## What completed

The separate implementation materialized the fixed four basic-timing, two intervening-message and two irrelevant-permission pairs. Exactly 16 genuine simulator bookings generated the receipts; each pair reuses its two successful calls and changes only the position of one permission amendment. The 16 record labels are balanced: eight violation and eight authorized. Six pairs require a correct change, and two require a correct invariant decision. No Actor, follow-up, training or resampling was used.

The [offline checks](run_01/OFFLINE_CHECKS.json) passed before freezing: deterministic references and a narrow public-template check agree, all public/private boundaries are enforced, chronological links do not reveal applicable permission, and missing/failed outputs retain their denominators. The [AI source review](run_01/AI_SOURCE_REVIEW.json) is nonblind and author-context; **human review remains zero**.

Jev-1.14.0 returned four valid interface-smoke responses on two separate hand-authored fixtures. They are not simulator-backed scientific examples and do not enter accuracy statistics. All 32 Jev formal requests remained undispatched.

## What stopped, and what the evidence supports

The only GPU allocation was `33137525`, one H200, six CPUs and 160 GiB, with a 30-minute scheduler limit and no requeue. [Final accounting](run_01/cluster/accounting_final.json) records `FAILED|1:0|00:20:37`; the queue was empty at export. [STOP.json](run_01/results/STOP.json) records `NativeTimeout`, zero completed Qwen slots and no retry. There is no Qwen ready/finished receipt and no Qwen request dispatch.

The implementation set a **1,200-second Qwen startup deadline**, within the 30-minute allocation. This was an implementation choice, not an additional user-requested 20-minute Qwen budget. It included the full SHA-256 check of 65,524,387,618 bytes of pinned model assets, tokenizer checks, model loading and compilation. The recorded observations put roughly eleven minutes before the engine logs began. The [saved log](run_01/cluster/logs/timing_33137525.log) then shows successful loading of 17 weight shards in 13.30 seconds, followed by vLLM compilation. Its last progress message is the Dynamo bytecode transform at 13:08:07 ET; no ready message precedes the timeout.

The run used a fresh compilation cache. [Read-only cache inspection](run_01/results/recovery_cache_inventory.json) found only the factors and computation graph in the new cache, while two earlier completed campaigns each had 68 files including compiled artifacts. The old development cache and new cache have [matching factor and graph hashes](run_01/results/recovery_cache_compatibility.json). This supports cold compilation and the combined startup budget as the recovery targets. It does **not** establish a deadlock, prove why compilation took that long, or demonstrate that reusing the older cache will succeed. No cache was copied or executed during this inspection.

The implementation underestimated startup overhead. The stop policy then worked: Qwen sent zero inference requests, and the dependent Jev formal phase was not started.

## Coverage and usage

| Item | Observed | Preserved limit |
| --- | ---: | ---: |
| Genuine simulator bookings | 16 | 16 |
| Jev interface smoke | 4 valid / 4 attempted | 4 |
| Qwen interface smoke | 0 attempted | 4 |
| Jev formal decisions | 0 / 32 | 32 |
| Qwen formal decisions | 0 / 32 | 32 |
| All model request attempts | 4 | 72 |
| H200 allocations | 1 | 1; consumed |
| H200 time | 20:37 = 0.343611 hours | 30:00 = 0.5 hours |
| Jev input tokens | 2,950 | 32,768 reserved per attempt |
| Estimated Jev API cost | $0.0001239 | $0.10 |
| Jev conservative request reservation | $0.008 | $0.10 |

The Jev estimate uses returned input usage and the [official model price](https://docs.typesafe.ai/models) checked on November 12: $0.042 per million input tokens, output free. This is an API estimate, not an invoice or a GPU dollar price. Local simulator preparation took 4.218 seconds under the external wall/RSS supervisor. Two earlier macOS memory-limit setup failures occurred before any simulator booking or model request; [the preparation receipt](run_01/preparation_recovery.json) preserves them. No generated record was replaced.

## Analysis and reproducibility

[analysis.json](run_01/analysis.json) is the unchanged frozen scorer's full-denominator output. Each of its four groups has 16 missing decisions; all eight pairs in each group are unavailable. Its numerical zeros for correct counts and differences are bookkeeping consequences of missing data. **Do not report them as 0% measured accuracy, equal Judge performance, stable decisions or a zero treatment effect.** [RUN_OUTCOME.json](run_01/RUN_OUTCOME.json) explicitly records `primary_effect: null` and `scientific_conclusion_available: false`.

The remote archive SHA-256 is `f78a461283955d268627f612c793bdcef39c84a6622ffe2cd78492033ee218ef`. All 24 payload files matched the remote hash map; the 15 existing local smoke files were identical and were not overwritten. [Download verification](run_01/cluster/DOWNLOAD_VERIFICATION.json) and [result hashes](run_01/RESULT_HASHES.json) bind the saved evidence.

```sh
python3 -B project/authorization_timing_jev_2026-11-12/verify_saved_run.py
```

This standard-library verifier blocks network access and child processes. It verifies frozen inputs, raw responses, dispatches, failure accounting and the saved analysis; it also checks the earlier 31-file and 480-file input manifests. A passing verifier means archive integrity, **not a successful experiment**. One local account/balance receipt is omitted from publication with its original hash preserved; all scientific inputs and all returned model responses are shared.

## What this changes in the project

The diagnostic implementation and eight pairs are now available to the team. The empirical question remains open: can a Judge correctly change its verdict when effective permission changes, while preserving the right verdict when an irrelevant permission moves? This failed startup adds no evidence about that question and does not weaken or strengthen the existing Jev baseline comparison. No expansion or new sampling is justified by an infrastructure failure.

The [recovery proposal](RECOVERY_PLAN.md) preserves the dataset, metrics, request order and previous evidence. It is not a new launch authorization. The original single-allocation limit is consumed.
