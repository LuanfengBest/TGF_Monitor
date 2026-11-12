# Next-work inventory — preparation completed, execution on hold

Updated November 12 after the user selected the authorization-audit narrative and requested source review plus a prepared Qier timing diagnostic. The user explicitly requested **no new experiments**. No model calls, simulator execution, training, retries or cluster allocation occurred in this preparation update.

## Completed preparation

| Work | Concrete artifact | Interpretation |
| --- | --- | --- |
| Revisit original authorization evidence | [32-case AI source review](source_review/README.md), source IDs and archive hashes | Existing author context, known labels/results, nonblind and not independent; no human review |
| Separate strict labels from construction concerns | Five synthetic numeric-name warnings; original labels unchanged | Task realism needs attention, not silent relabeling |
| Prepare human materials | 27 distinct full records, separate mapping and empty forms | Material ready; completed human reviews = 0 |
| Specify Qier extension | [Versioned protocol](../authorization_timing_jev_2026-11-12/PROTOCOL.md), [machine config](../authorization_timing_jev_2026-11-12/config.json) | Jev primary, Qwen comparator; two presentations; pair accuracy primary |
| Set resource limits | [Budget](../authorization_timing_jev_2026-11-12/BUDGET.md) | 64 formal / 72 total calls maximum, $0.10 API, 0.5 H200 hours; proposed, not spent |
| Explain why the question matters | [Implications](IMPLICATIONS.md) | Better attribution and auditability are supported; real-world harm prevention remains untested |

## Remaining work in order

1. **Team reading and real human review.** Have actual people complete the blank review forms and record who saw earlier labels. Review strict-name construction, permission updates and receipt support. These are suggested review tasks, not accepted assignments. Do not report human validation until it exists.
2. **Prepare the execution implementation when needed.** Keep Qier's original version intact. Add a separately versioned Jev/Qwen adapter, fixed-slot scorer, attempt ledger, disabled retries and budget stops. Static/offline checks must verify public/private separation, shared instructions, unavailable outcomes and denominators. The current protocol is reviewable but not an executable campaign.
3. **Keep the current no-launch instruction in force.** Do not run Qier's `prepare`, generator or its simulator-backed tests now. Only after a later launch instruction, check live resources, produce exactly eight pairs and disjoint interface fixtures, verify the references independently of Jev, then freeze inputs and requests before inference. Full preflight items are in [READINESS.json](../authorization_timing_jev_2026-11-12/READINESS.json).
4. **If later executed, report every planned slot and stop at the caps.** Preserve missing/failed decisions; no automatic replenishment or expansion. Describe the full eight-pair table rather than claiming general effectiveness from 64 calls.
5. **Integrate the final report and slides.** Keep original TGF negative findings, the post-hoc Judge comparison, this source review, Tony's evidence-capacity audit and any future timing diagnostic separate. Students should check the course's final-writing and AI-disclosure requirements; these planning notes are not the final student-written report.

## Keep these boundaries visible

- Do not relabel or replace difficult cases inside the completed frozen batch and present the revised score as the original result.
- Do not combine reused natural data, scripted diagnostics and the 189 eligible new trajectories into one accuracy number.
- Do not treat the two F truncations as proof that targeted wording improves valid-answer content.
- Do not infer malicious intent from every strict authorization violation, or treat model confidence as a correctness guarantee.
- Do not use Jev both to supply the reference label and to demonstrate its own superiority.
- Do not label AI work as human annotation; do not claim this plan establishes runtime safety, stability, calibration or production readiness.
- Do not merge teammate branches without reviewing differences in endpoints, interfaces and output budgets.

The current deliverable is a source review and a concrete, budgeted diagnostic plan. No teammate branch has been merged and no new run is underway.
