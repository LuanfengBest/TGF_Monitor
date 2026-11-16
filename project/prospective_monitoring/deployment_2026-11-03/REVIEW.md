# Prospective development pilot review — 2026-11-03

This is a new, bounded development run. Historical v2/v3 outputs are not rerun,
rescored, replaced, or used as formal test data. The user approved the prospective
plan, requested that work start, and completed cluster login. The working envelope
is at most 24 new tasks, one H200, four scheduler hours; there is no expansion to 120.

## What the pilot can establish

- Whether native actors can produce usable traces in the original simulator.
- Whether actual committed effects, delivered authorization, and source IDs align.
- Whether P/C/F/T complete on the same admitted traces with observable costs.
- Why cases are lost: collection failure, unknown reference, invalid monitor input,
  model failure, or unattempted work after a stage stops.

It cannot establish effectiveness on a representative or independent test set.
Current tasks expose exact recipients, permissions, and a small flight catalog;
they may be easy enough for simple rules and produce ceiling effects. Formal test
families are still absent. Ordinary/side-objective condition is confounded with
variant, so there is no causal condition comparison. Within-trace strategy
comparisons remain paired. Bank forward correction currently adds permission;
it is not a revocation stress test.

## Interpretation requirements

`collection_status=completed` means the actor ended its interaction. It does not
mean it achieved the task. A refusal with no tool calls can be a resolved label-0
case and enter monitoring. Reports must separately show sensitive execution and
no-action negatives; task success remains unevaluated. Failed attempts do not
become committed violations, and cancellation cannot erase an earlier violation.

The 180-second total per-case generation limit is an uncalibrated pilot limit,
not a finding about actor or monitor ability. Future limits must be frozen before
formal testing. Actual per-dispatch native token checks remain necessary because
CPU preflight examples cannot enumerate future model-generated prompts.

## Admission issues identified before model inference

1. Native Harmony serialization needs actual pinned-library CPU render/parse
   checks; fake-codec unit tests alone cannot establish compatibility.
2. A shared model worker dies permanently after a hard timeout. Remaining slots
   must be recorded as undispatched, without fabricated model calls or unknown
   token charges. There is no automatic worker restart or retry.
3. Live admission must bind code, configuration, and the actual task manifest;
   a single-use claim prevents reusing a permit with another output directory.

The new cluster CPU job checks these implementations plus runtime, grammar,
tokenizers, and cached model files before any GPU campaign is submitted.

All 360 historical files matched their preparation snapshot during this review.

## Actual cluster integration findings

The pinned model container initially lacked pandas, which the original airline
environment imports through its Excel class. A separate dependency directory now
pins pandas 2.2.3, pytz 2025.2, and tzdata 2025.2; existing NumPy 2.2.6 and
python-dateutil 2.9.0.post0 are reused. The SIF and original model files are unchanged.
With this layer, all 157 then-current container tests passed.

CPU job 31818353 freshly verified both model inventories, then stopped with no
inference on an actual Harmony API mismatch. Two issues were demonstrated: a full
serialized message includes an assistant prefix that the completion parser already
has, and `with_content_type("<|constrain|> json")` adds an invalid multiword header.
The new adapter omits that unnecessary header while preserving channel, recipient,
and strict JSON arguments; the round-trip check strips only the exact prefix
obtained from the real encoder. A direct pinned-library CPU probe confirmed a
correctly parsed tool name, arguments, and channel. Frozen old v2/upstream files
are unchanged; this does not retroactively explain their scientific outcomes.

Preflight now checks actual Harmony and monitor grammar before the large file scan.
The revised local suite passed 159 tests. Complete revised cluster admission is
still required; the earlier failure is not relabeled as success.
