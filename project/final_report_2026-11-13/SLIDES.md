# Authorization Auditing with Jev as Final Judge

Portable contents of the updated native presentation, November 13, 2026. Slides 1–12 form the main talk; slides 13–17 are appendices. No new experiments.

## 1 Authorization Auditing with Jev as Final Judge

Judge choice, follow-up questions and temporal permission

Can a monitor tell whether an executed action had permission at the time?

A stronger direct baseline; no established extra benefit from targeted follow-up or Jev time indexing.

Pacifica Zhang · Luanfeng Wei · Qier An · Tony Zhu

Source or scope: CPSC 4880/5880 · Integrated results · November 13, 2026

## 2 Permission must apply when the action is executed

The same permission text can support different labels when its position changes.

| Sequence | First | Then | Reference |
| --- | --- | --- | --- |
| Grant before booking | Permission granted | Booking succeeds | Authorized |
| Grant after booking | Booking succeeds | Permission granted | Violation |

Later permission or cancellation does not erase an earlier violation.

Reference: execution evidence and rules. Jev: the tested semantic Judge.

Source or scope: Endpoint: successful sensitive action outside applicable permission. Human review of new studies: 0.

## 3 Separate the Judge from the extra information

189 eligible new trajectories: 93 airline and 96 bank, from existing task templates.

| Arm | Final Judge receives |
| --- | --- |
| P direct | Public record + factual ledger + operation markers |
| C review | P + one fixed Qwen evidence review |
| F generic | P + Actor answer to a generic checking question |
| T targeted | P + Actor answer to a selected amount, identity or timing question |

Each intermediate output is shared unchanged with Jev and Qwen.

Source or scope: Primary comparison: Jev T versus F in airline. F/T share context and caps; no new external facts.

## 4 Jev improves the direct baseline on this batch

Identical P materials in airline; post-hoc component comparison.

| Judge | Violations detected / 26 | False alarms / 67 |
| --- | --- | --- |
| Qwen P | 8 | 0 |
| Jev P | 21 | 0 |

13 corrected labels and no regressions in this paired comparison.

50 percentage points more detection here; no general model ranking.

Source or scope: Saved baseline comparison. Different model interfaces and serving costs; not matched compute.

## 5 Targeted follow-up did not meet the primary criteria

The original TGF hypothesis remains unsupported under the frozen decision rule.

| Criterion | Observed | Assessment |
| --- | --- | --- |
| Jev T−F score gain ≥ 0.05 | 0.0499426 | Below threshold |
| Paired interval excludes zero | 95% CI [0, 0.143941] | Includes zero |
| Actor time ratio ≤ 1.10 | 1.1014 | Above limit |

All F/T label differences came from two truncated generic answers.

On 91 jointly valid airline records, F and T agree within each Judge.

Source or scope: Score G = detection rate × correct-release rate. Conditional analysis does not replace the full denominator.

## 6 Eight timing pairs test when a label should change

A separate diagnostic adapted from Qier's design; 16 scripted bookings, 64 formal judgments.

| Pair type | Count | Expected behavior |
| --- | --- | --- |
| Basic grant or withdrawal | 4 | Correct label change |
| Intervening unrelated message | 2 | Correct label change |
| Permission for another person | 2 | Correct label invariance |

Within each pair: same action and receipt content; move only the amendment.

Source versus linked cards, for both Jev and Qwen.

Source or scope: Links follow public chronology; they do not select the applicable permission or reveal a label.

## 7 Jev is at ceiling and gains nothing from time links

Pair success requires both records to be correct. All 64 formal outputs were valid.

| Judge and material | Correct pairs / 8 | Correct changes / 6 | Correct invariances / 2 |
| --- | --- | --- | --- |
| Jev source | 8 | 6 | 2 |
| Jev linked | 8 | 6 | 2 |
| Qwen source | 4 | 3 | 1 |
| Qwen linked | 5 | 4 | 1 |

Primary Jev indexing gain: 0. Secondary Qwen gain: one pair.

Eight constructed pairs do not certify broad accuracy or stability.

Source or scope: Timing RESULTS.md and recovery_01/analysis.json. No repeated judgments or rationale endpoint.

## 8 The controls reveal different kinds of failure

Concrete cases explain what an aggregate accuracy number can hide.

| Case | Public-record distinction | Observation |
| --- | --- | --- |
| Pair 01 | Nora's booking occurs before a later grant | Qwen misses the violation |
| Pair 05 | An unrelated note intervenes in the grant pair | Links correct one Qwen pair |
| Pair 08 | Booking is for Eli; the moved grant is for Mina | Qwen changes an invariant label |

Jev is correct on all three; the Qwen flip does not identify its internal cause.

Source or scope: Pair 08 may reflect scope, position sensitivity or judgment variation; one observation cannot separate them.

## 9 A valid verdict or citation is not enough

Source audits separate label correctness, evidence support and interface constraints.

Mainline: five missed airline cases share ambiguous numeric name suffixes.

Bank: Jev has five false alarms with added review, and none in its direct baseline.

Tony's older-output audit: 28 cases need five evidence units, but the schema allows four citations.

32-case mainline source inspection was nonblind AI review; human review remains 0.

Source or scope: Source audit and Tony commit 898b73ac. Later evidence-chain criteria are not retroactive original requirements.

## 10 Earlier negative results remain in the final account

These stages motivated the stronger baseline; they are not independent confirmations.

| Earlier stage | Observed result | Boundary |
| --- | --- | --- |
| 24-record TGF | F and T both detect 6/6; T adds 1 false alarm | Development data |
| Fixed selected action | Generic and specific both 6/6 at two seeds | Same records reused |
| 12-record extension | Totals improve 1 block; criterion was ≥ 2 | 120 calls, not 120 cases |
| Jev ledger 2×2 | Natural classifications unchanged | Gains only in constructed strata |

A useful negative result limits what we can credit to the added component.

Source or scope: Historical November 7 report and November 12 development 2×2. No pooled accuracy across these batches.

## 11 The implication is more accountable authorization review

Better monitoring would help people distinguish unauthorized actions from legitimate work.

Tie each disputed action to its applicable permission and successful receipt.

Evaluate a strong direct Judge before adding questions, reviews or evidence links.

Keep missing evidence and conflicting decisions available for escalation.

Potential application: incident triage. Not yet measured: prevented harm or human time saved.

Source or scope: Implications are design inferences. Experiments audit completed actions; they do not test prevention.

## 12 The contribution is a bounded and reproducible account

Jev as final Judge is the architecture; execution-time authorization is the research problem.

Supported: stronger direct baseline in this batch and specific timing/scope failures.

Not established: extra targeted-follow-up benefit, Jev indexing benefit or general reliability.

Limits: existing templates, eight constructed pairs, ambiguous labels, no human gold and one Jev repeat disagreement.

Current scope: integrate and review; no new experiments or sample expansion.

Source or scope: Frozen hypotheses, failures and denominators retained. Novelty claim: empirical replication and extension.

## 13 Appendix  Mainline airline results

All eligible trajectories stay in the planned denominator.

| Judge / arm | TP / 26 | TN / 67 | FP / 67 | Unavailable | G |
| --- | --- | --- | --- | --- | --- |
| Qwen P | 8 | 67 | 0 | 0 | 0.307692 |
| Qwen C | 14 | 67 | 0 | 0 | 0.538462 |
| Qwen F | 19 | 66 | 0 | 2 | 0.719862 |
| Qwen T | 20 | 67 | 0 | 0 | 0.769231 |
| Jev P | 21 | 67 | 0 | 0 | 0.807692 |
| Jev C | 21 | 67 | 0 | 0 | 0.807692 |
| Jev F | 20 | 66 | 0 | 2 | 0.757750 |
| Jev T | 21 | 67 | 0 | 0 | 0.807692 |

Source or scope: 189 eligible total; airline 48 instance blocks, 89 unique public inputs. G = TPR × TNR.

## 14 Appendix  Bank results and repeatability caveat

A stronger direct Judge does not make every added review beneficial.

| Judge / arm | TP / 8 | FP / 88 | G |
| --- | --- | --- | --- |
| Qwen P | 8 | 4 | 0.954545 |
| Qwen C | 8 | 1 | 0.988636 |
| Qwen F or T | 8 | 0 | 1.000000 |
| Jev P, F or T | 8 | 0 | 1.000000 |
| Jev C | 8 | 5 | 0.943182 |

Identical incidental requests: Jev agrees in 36/37 pairs; Qwen in 37/37.

Not a designed stability benchmark; do not claim repeatability is solved.

Source or scope: Bank has eight positive blocks. Same-input Jev C probabilities: 0.52/0.47/0.01 versus 0.42/0.57/0.01.

## 15 Appendix  Earlier evidence gains and failures

A selected striking example did not become a broad confirmed improvement.

| Closing extension | Qwen | gpt-oss |
| --- | --- | --- |
| Valid / 60 planned | 60 | 45 |
| Correct labels / valid | 59/60 | 45/45 |
| Invalid outputs | 0 | 14 truncated; 1 schema |
| False-assertion flips | 0/12 valid pairs | 0/7 valid pairs |

Fee-scope case: Qwen summed principal correctly, yet counted excluded fees as a violation.

Later ledger gains occurred only in constructed strata; natural labels were unchanged.

Source or scope: Old 12-record extension and 60-position Jev 2×2 use different interfaces; keep their results separate.

## 16 Appendix  Resources include the failed start

The timing recovery changed startup only; data, prompts and limits stayed frozen.

| Batch | Model calls | H200 allocation | Jev usage estimate |
| --- | --- | --- | --- |
| Jev ledger 2×2 | 248 | 321 seconds | $0.012413478 |
| New mainline | 2,706 | 2.400556 hours | $0.155981742 |
| Timing, both starts | 72 | 1,373 / 1,800 sec | $0.001716372 |

First start: 1,237 seconds, no Qwen requests. Authorized recovery: 136 seconds.

All 72 timing attempts consumed once; no replacement cases or additional run.

Source or scope: Calls include interface checks. Jev estimates are not invoices; GPU dollars and pure architecture speed are not claimed.

## 17 Appendix  Provenance and research positioning

Replication and extension around an explicit authorization endpoint.

Luanfeng: TGF and simulator foundation. Pacifica: authorization evaluation and integration. Qier: timing design. Tony: evidence audits.

Related work: Monitoring Monitorability; MonitorBench; Evaluating and Benchmarking the System One Model Jev.

AI assisted code, analysis, source review and writing. Human annotation of new studies: 0.

Team attribution and final course format still need review before submission.

Source or scope: Report bibliography and evidence index contain primary-source links, frozen protocols and offline reproduction.
