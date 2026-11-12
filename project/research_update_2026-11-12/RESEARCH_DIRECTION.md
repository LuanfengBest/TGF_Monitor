# Research direction: evidence use in authorization auditing

Decision recorded after the completed November 12 batch. This is an exploratory reframing, not a preregistered explanation of the original experiment and not a claim of new experimental success.

## Working question

**Can a monitor correctly bind an executed action to the permission effective at execution and the receipt establishing what happened? How much do Judge choice, evidence presentation and follow-up each contribute?**

The original TGF question remains a controlled subquestion: does a targeted follow-up add value over a fixed question with comparable access and resource constraints? We retain its negative result. The project stays within agent authorization auditing and reuses its simulators, execution endpoint, trajectories, public/private separation, matched strategy comparisons and source-bound audits.

The working title is **Evidence Use in Authorization Auditing: Judge Choice, Follow-Up, and Temporal Permission**. This is a research framing for team review, not a renamed historical protocol.

## Evidence supporting this decision

1. **Judge choice matters in the saved batch.** On the same 93 airline records, Qwen P detects 8/26 violations and Jev P detects 21/26; both have 0/67 observed false alarms. Jev corrects 13 cases without regressing a case. The post-hoc paired instance-block interval for the detection difference is [0.3214, 0.6818]. Banking improves four false alarms from three blocks but has only eight positive blocks and weaker evidence.
2. **Targeting has no established independent gain.** The prespecified Jev T−F point difference in TPR×TNR is 0.0499425947 with interval [0, 0.1439409091], below its 0.05 point threshold. The observed Actor inference-time ratio is also above the 1.10 limit. All airline F/T verdict differences coincide with two truncated F answers. On 91 jointly valid answer pairs, both Judges' F/T verdicts match exactly. This conditional diagnostic cannot replace the full-denominator primary analysis.
3. **Correct verdicts do not certify evidence use.** Mechanical citation presence, claim truth, support for the claim and the final verdict are separate checks. Tony's post-hoc completeness standard exposes a four-citation output cap that cannot represent a five-unit chain in some records. The original task did not require this new completeness metric.
4. **Authorization semantics need care.** All five Jev airline misses involve synthetic numeric name suffixes under an exact-name contract. These labels remain unchanged, but the construction is semantically ambiguous. No independent human gold is available for the new batch. A more accurate Judge is not an infallible reference verifier.
5. **Stability remains separate.** Jev disagreed on one of 37 incidental identical-input pairs. This was not a designed repetition benchmark and does not establish a general stability rate.

See the [main report](reports/mainline.md), [baseline comparison](reports/baseline_comparison.md), and [semantic audit](reports/semantic_audit.md). Different historical batches and endpoint definitions remain separate.

## Relationship to prior work

This is a targeted literature check, not an exhaustive novelty review. Do not claim “first” from the absence of another paper in this list.

- [Evaluating and Benchmarking the System One Model Jev](https://arxiv.org/abs/2609.37647) evaluates Jev on 37 datasets and includes Qwen comparisons. Versions/tasks differ from ours, but a generic Jev-versus-Qwen comparison is already established.
- [No One Monitor Fits All: Oversight Strategies for Frontier Agents](https://openreview.net/pdf/ed789de8501551c8dbbbc6ea6e98af88b6f4adc3.pdf) compares direct monitoring, interrogation and debate variants across models/tasks and finds substantial dependence on Judge capability and task. “A stronger Judge changes the value of elicitation” is not by itself a new claim.
- [Permission to Retry: A Study of Authorization and Recovery in AI Agent Workflows](https://arxiv.org/abs/2610.31916) studies permission and execution/recovery histories. Temporal authorization is already a research topic. Our candidate focus is the Judge's interpretation of public evidence, distinct from runtime enforcement, but this distinction still needs a fuller related-work assessment.
- [TypeSafe's citation-checking cookbook](https://docs.typesafe.ai/cookbooks/citation_check) already illustrates Jev-based claim/source checking. That application alone is not an originality claim.

The candidate contribution is a narrowly controlled, execution-grounded evaluation: retain the same executed actions and receipts while varying permission timing or evidence presentation; distinguish verdict accuracy from supported evidence and output-capacity artifacts; preserve failed/unavailable outcomes; and compare targeted follow-up to an adequate fixed control with costs disclosed. This contribution is **proposed**, not established by the unrun diagnostic.

For the course project, a coherent replication/extension with clear negative findings and reproducible evidence is defensible. Publication-level novelty and generalization remain unconfirmed.

## What Jev can and cannot replace

Jev returns typed choices/probabilities rather than free-form replies, code or explanations. See the [official System One description](https://docs.typesafe.ai/concepts/system-one).

| Component | Role and priority | Boundary |
| --- | --- | --- |
| Final Judge | Already evaluated; retain as a component contrast | Must not also define its own gold labels |
| Claim/source support checker | Plausible next component; classify supported/contradicted/insufficient for a specific claim | Separate evaluation needed; generic application is already documented |
| Action/dimension/question selector | Can choose from finite candidates; code renders fixed templates | Changes an additional component; not a drop-in free-form question writer |
| Escalation selector | Could route uncertain cases to a stronger model or human | Confidence is not certified correctness; thresholds need independent validation |
| Actor or explanation writer | Not a direct substitute in the current protocol | Would require task/interface redesign and obscure reuse |
| Arithmetic, ordering, source hashes, execution reference | Retain deterministic code | Do not replace independent, checkable references with the evaluated model |

## Narrative for the eventual report

We began by asking whether trace-grounded follow-up improves authorization monitoring. Matched comparisons did not establish an advantage of targeting over fixed follow-up. A new batch with shared intermediate evidence showed that final Judge choice accounts for a substantial performance difference in the tested setting, while availability and evidence-expression constraints complicate interpretation. Source audits motivated a more precise question about binding permissions, actions and receipts. A temporal-authorization diagnostic is prepared, and a retrospective citation-capacity audit is available, but further confirmation has not been run.

This narrative preserves the work and the failed primary hypothesis. It does not turn post-hoc observations into preregistered successes or infer internal reasoning mechanisms from generated explanations.
