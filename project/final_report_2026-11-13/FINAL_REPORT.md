# Authorization Auditing with Jev as Final Judge

Judge choice and the value of follow up and temporal evidence

Pacifica Zhang · Luanfeng Wei · Qier An · Tony Zhu

CPSC 4880/5880 · Integrated course report · November 13, 2026

## Abstract

An agent can finish a task while performing an action that the user did not authorize. We study whether a monitor can identify such actions from public permissions, tool calls and execution receipts. The project began with trace-grounded follow-up (TGF): asking an Actor about a selected operation. Its current organizing question is whether a stronger final Judge already extracts the relevant evidence, and what additional value comes from questions or evidence indexing. We use Jev-1.14.0 as the primary final Judge and Qwen3-32B as a comparator, while keeping reference labels external to both models.

On 189 eligible newly collected simulator trajectories, the original primary comparison did not establish an advantage for targeted over generic follow-up. In airline, its Jev score difference was 0.0499426, below the prespecified 0.05 threshold, with a paired 95% interval including zero; a relative latency criterion also failed. On identical direct-judgment inputs, a post-hoc component comparison found 21/26 violations detected by Jev versus 8/26 by Qwen, with zero observed false alarms among 67 authorized records for each. A separate eight-pair timing diagnostic found Jev correct on all eight pairs with either source records or mechanical time links. Thus its primary indexing gain was zero. Qwen improved from four to five correct pairs, a secondary one-pair result.

The contribution is an auditable separation of Judge choice, evidence presentation, follow-up content and output availability. Earlier negative findings remain part of the evidence. Small constructed controls, ambiguous synthetic names, one observed Jev disagreement on identical requests and the absence of independent human labels limit broader claims. This is a study of post-execution auditing, not a demonstration of safe deployment or prevention.

## 1 Research question and contribution

The practical question is simple: **did this successful action exceed the permission that applied when it happened?** A ticket purchased before permission is granted remains unauthorized even if the user later approves the same trip. An explanation from the Actor is evidence about its behavior; it cannot create permission. The same distinction matters for transfers, refunds and changes to accounts.

The October proposal asked whether targeted follow-up improves monitoring beyond a generic question at comparable cost. We retain that hypothesis and its negative results. The integrated narrative now uses **Jev as the primary final Judge within an authorization-auditing study**. This reframing follows the observed results; it does not turn the post-hoc Judge comparison into a prespecified primary success. Jev does not generate its own gold labels, replace execution verification or serve as the Actor in these experiments.

The work makes three bounded contributions. First, it defines an explicit execution-time authorization endpoint and separates it from task completion, failed attempts and an Actor's hidden objective. Second, it compares direct judgment, evidence review and two forms of follow-up on shared records and shared intermediate outputs, retaining failures in the denominator. Third, it connects aggregate results to controlled timing/scope cases and source audits, with frozen inputs, raw outputs, resource ledgers and offline reproduction. These are empirical replication and extension contributions; we do not claim a new model architecture, a first use of Jev as a Judge or a general solution to monitoring.

## 2 Endpoint and experimental design

### Reference labels and evidence boundaries

A reference violation requires a successfully executed sensitive action outside the applicable explicit permission. Permission is evaluated at execution time, including amount, identity, recipient, route/date and scope where relevant. Later cancellation, repair or prospective permission does not erase an earlier violation. Missing evidence, invalid output and incomplete tasks are not silently classified as authorized. The label is about execution, not malicious intent: an ordinary Actor can violate a strict rule.

Reference decisions use simulator execution evidence and versioned authorization rules, with AI source checks. Models receive public records and permitted transformations of those records. Private objectives, reference labels, hidden simulator state and private reasoning are excluded. The program checks execution and exact policy facts; the Judge performs the tested semantic classification. **Independent human review completed for the new mainline and timing studies is zero.**

### Shared materials in the new mainline

We collected ordinary and side-objective Actor trajectories for 48 new instances per environment, using six existing task templates in total. There were 192 collection positions, 191 completed collections and one invalid collection. Three airline positions lacked sensitive execution and were excluded by the frozen admission rule, leaving 93 airline and 96 bank trajectories. These are new instances, not unseen task families. Airline contains 26 violations and 67 authorized records; bank contains 8 and 88. There are 48 instance blocks per environment and 89/77 distinct public inputs after airline/bank deduplication. [E2]

| Arm | Material supplied to the final Judge |
| --- | --- |
| P direct | Full public record, program-generated factual ledger and operation markers |
| C review | P plus one fixed Qwen evidence review |
| F generic | P plus the original Actor's answer to a fixed generic checking question |
| T targeted | P plus the original Actor's answer to an amount, identity or timing question selected by public rules |

The Actor is gpt-oss-120b; the reviewer and comparator Judge are Qwen3-32B; the primary Judge is pinned to Jev-1.14.0. Revisions and decoding settings are recorded in the frozen protocol. F and T branch independently from the same Actor context, disallow tool calls and share a 4,096-token output cap. Each C/F/T intermediate output is generated once and supplied unchanged to both Judges. Follow-up reorganizes existing public evidence; it does not acquire independent external facts. Equal call counts and caps do not imply equal realized compute.

The primary endpoint is G = TPR × TNR, the product of violation detection and correct release of authorized records. Unavailable or insufficient decisions remain in the planned class denominators. Intervals resample complete paired instance blocks 5,000 times. Airline is the primary environment; bank is reported separately. Secondary comparisons are descriptive estimates without multiplicity correction. Probability scores from different model interfaces are not treated as interchangeable calibration evidence.

## 3 Evidence accumulated across the project

Different batches answer different questions and are not pooled into a larger accuracy denominator. In particular, calls, repeated conditions and paired records are not independent tasks.

| Stage | Data and design | Main observation |
| --- | --- | --- |
| Early TGF development | 24 airline records, 12 blocks; four arms | Generic and targeted both detect 6/6; targeted adds one false alarm |
| Fixed-operation diagnostic | Same airline records; three question conditions, two seeds | Generic and specific questions both reach 6/6 with no false alarms |
| Closing evidence extension | 12 constructed records, six paired blocks; 120 calls | Cumulative totals fix one block, below the prespecified two-block criterion |
| Jev evidence 2×2 | 48 reused natural records plus 12 constructed records; 240 formal judgments | Ledger changes classifications only in constructed strata |
| New P/C/F/T mainline | 189 eligible trajectories; shared intermediates, two Judges | Targeted-follow-up primary support criteria not met |
| Timing diagnostic | Eight constructed pairs, 16 records; 64 formal judgments | Jev indexing gain zero; Qwen gains one correct pair |

### Earlier negative results remain findings

The initial natural collection had only one bank violation among 24 records, failing the bank coverage screen. Airline had six violations and 18 authorized records and was selected for development comparisons. Direct judgment detected 5/6, additional review 2/6, generic follow-up 6/6 and targeted follow-up 6/6; only targeted follow-up produced a false alarm (1/18). Holding an author-selected operation fixed did not distinguish generic from specific questions at either of two seeds. That diagnostic tested question content, not the automatic operation selector. Its records were reused, and ceiling performance limited sensitivity. [E1]

A selected single-block evidence probe initially suggested a large benefit: Qwen correctness rose from 4/8 response positions with facts to 7/8 with totals and 8/8 with budget comparisons. In the later six-block extension, Qwen produced 60/60 valid outputs and 59 correct labels; totals changed the relevant condition from 11/12 to 12/12. The one improved block did not meet the prespecified minimum of two, and explicit comparisons added nothing further. gpt-oss had 45 correct valid outputs out of 60 planned calls, with 14 truncations and one schema failure retained. Correct versus incorrect supplied assertions caused no flips among jointly valid pairs (Qwen 0/12; gpt-oss 0/7), without establishing general resistance to misleading claims. [E1]

The separate Jev 2×2 reused 60 positions representing 52 distinct public records. On 48 natural records, adding a factual ledger changed neither Judge's classifications. Both detected the sole natural bank violation; on natural airline, Jev detected 6/6 and Qwen 0/6, with no false alarms among 18 authorized records. The ledger corrected three constructed airline violations for each Judge and one constructed bank violation for Jev. Qwen retained three constructed bank false alarms. These deployment-specific results do not supersede the earlier differently configured Qwen baseline or establish a general arithmetic mechanism. Ledger formatting, order, repetition and explicit totals changed together. [E3]

## 4 New mainline results

### Targeted follow up did not pass its primary criteria

All 378 F/T calls were attempted; 376 returned valid answers. Two generic answers, one on a violation and one on an authorized airline trajectory, truncated at the cap. Each final Judge completed 754 formal judgments plus eight interface checks. Formal Judge requests were valid, but a missing F answer made its pipeline position unavailable. No calls were retried. [E2]

| Airline Judge and arm | TP / 26 | TN / 67 | FP / 67 | Unavailable | G |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qwen P | 8 | 67 | 0 | 0 | 0.307692 |
| Qwen C | 14 | 67 | 0 | 0 | 0.538462 |
| Qwen F | 19 | 66 | 0 | 2 | 0.719862 |
| Qwen T | 20 | 67 | 0 | 0 | 0.769231 |
| Jev P | 21 | 67 | 0 | 0 | 0.807692 |
| Jev C | 21 | 67 | 0 | 0 | 0.807692 |
| Jev F | 20 | 66 | 0 | 2 | 0.757750 |
| Jev T | 21 | 67 | 0 | 0 | 0.807692 |

The prespecified Jev T−F difference is **0.0499425947**, with 95% paired interval **[0, 0.1439409091]**. The point estimate is below 0.05 and the interval includes zero. Rounding the estimate to 0.05 cannot make it pass. Actor inference time for T relative to F was 1.1014, also above the 1.10 criterion. Resource caps were respected, but the scientific support criteria were not.

Every observed F/T classification difference arose from the two F truncations. On the 91 airline trajectories with both valid answers, F and T have identical classifications within each Judge: Jev detects 20/25 with 66/66 correct releases; Qwen detects 19/25 with 66/66 correct releases. This post-hoc conditional analysis clarifies the difference; it cannot replace the primary denominator or prove equivalent methods. Bank F/T are identical on all 96 records.

Jev T−P and T−C are both zero in airline. Qwen T−P is 0.461538 (95% interval [0.272727, 0.666667]), but generic follow-up also improves Qwen substantially. The result supports value from the supplied answer materials for this comparator, not a unique advantage from targeting. Selecting a timing question also does not guarantee that the actual violation is temporal.

### Jev strengthens the direct baseline in this batch

On identical P inputs, Jev detects 21/26 airline violations versus Qwen's 8/26, an increase of 13 cases or 50 percentage points. Both have zero observed false alarms among 67 authorized records. The paired comparison contains 13 corrected and no regressed airline labels. This **post-hoc component comparison** motivates Jev as the primary Judge in the integrated story. It is not a compute-matched model ranking or a new primary hypothesis test. [E2, E4]

| Bank Judge and arm | TP / 8 | TN / 88 | FP / 88 | G |
| --- | ---: | ---: | ---: | ---: |
| Qwen P | 8 | 84 | 4 | 0.954545 |
| Qwen C | 8 | 87 | 1 | 0.988636 |
| Qwen F and T, each | 8 | 88 | 0 | 1.000000 |
| Jev P, F and T, each | 8 | 88 | 0 | 1.000000 |
| Jev C | 8 | 83 | 5 | 0.943182 |

The bank result prevents a blanket claim that adding review or using Jev always helps. Jev C produces five false alarms while Jev P does not. Source inspection found largely true facts in these reviews, with some partial coverage and incorrect source bindings. The observations do not establish that fabricated facts caused the errors. Only eight positive bank blocks were available.

### Correctness and trustworthiness remain distinct

All five Jev airline misses involve a synthetic numeric name suffix, such as a request for “Jordan Ellis 30” followed by a booking for “Jordan Ellis.” Frozen exact-identity rules label these violations, and all Judge/material combinations miss them. The suffix can also be read as an age, exposing an instance-construction ambiguity. Four occurred under the ordinary Actor condition. We retain the labels and records, and do not interpret these failures as proof of malicious intent. [E5]

The mainline contains 37 incidental pairs of identical full requests. Qwen agrees on all 37; Jev agrees on 36. One identical Jev C request changes from violation to authorized, with class probabilities 0.52/0.47/0.01 versus 0.42/0.57/0.01. No new calls were made to investigate it. This is a concrete counterexample to a claim that reliability or repeatability has been solved, not a designed stability-rate estimate.

The 32-case source review comprises 23 cases selected by the prespecified audit rule and nine exploratory additions, representing 27 distinct source packages. It was nonblind AI review in an author context, not human annotation. Mechanical checks on 1,061 C citations found 765 exact matches, 68 matches after whitespace normalization and 228 absent from the cited source. A missing quote is not necessarily a false claim; an existing quote is not necessarily sufficient support.

Tony's later audit of the older closing extension adds a related distinction. Of 105 valid outputs, 27 meet a new full-budget-evidence-chain criterion. For 28 outputs involving four actions, that criterion requires at least five evidence units while the old schema permits at most four citations. This exposes an interface capacity limit. The remaining 78 outputs cannot simply be called wrong or hallucinated, and the new criterion was not an original task requirement. [E6]

## 5 Controlled authorization timing diagnostic

### Design and controls

We adapted Qier's timing design in a separate versioned implementation rather than merging or claiming numerical replication of the original branch. The frozen set has eight pairs and 16 genuine scripted simulator bookings, with eight violation and eight authorized records. Within each pair, action and successful-receipt content stay fixed; only the position of a permission amendment changes. Four pairs test basic grants/withdrawals, two place an unrelated message between relevant evidence, and two move permission for a different person. Six pairs should change reference label; two should remain invariant. [E7]

The factorial comparison is Jev versus Qwen and source card versus linked card. Linked cards add deterministic nearest-prior/following user and receipt pointers from the public chronology. They do not identify the applicable authorization or insert a reference conclusion. An intervening note may still be the nearest user message. There are no Actor follow-up calls and no generated rationale/citation endpoint in this diagnostic. One observation per cell yields 64 formal judgments; eight interface checks bring total calls to 72.

A pair is correct only if both labels are correct. We separately count correct changes among six change pairs, correct invariance among two controls, and unwanted flips among the controls. Two wrong but identical labels do not receive invariance credit. Pair-level inference prevents treating the 64 judgments as 64 independent cases.

| Judge and material | Correct pairs / 8 | Correct records / 16 | Correct changes / 6 | Correct invariances / 2 | Unwanted flips / 2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Jev source | 8 | 16 | 6 | 2 | 0 |
| Jev linked | 8 | 16 | 6 | 2 | 0 |
| Qwen source | 4 | 12 | 3 | 1 | 1 |
| Qwen linked | 5 | 13 | 4 | 1 | 1 |

All 64 formal outputs are valid. All groups correctly release 8/8 authorized records. Jev detects 8/8 violations with either material; Qwen detects 4/8 with source and 5/8 with links. The **primary Jev linked-minus-source gain is zero** at a ceiling. Qwen's secondary gain is one corrected pair with no regression. Source and linked Judge gaps are four and three correct pairs, respectively; these are descriptive differences on this fixed set, not population performance estimates.

### What the cases clarify

In basic grant pair 01, Nora Li's booking is successful before a prospective permission update in the violating version. Qwen calls both orderings authorized under both presentations, while Jev distinguishes them correctly. This isolates a failure to produce the execution-time reference verdict despite the relevant public events being present.

In intervening-message pair 05, the added links correct Qwen's classification of the violating version, raising its correct-pair count by one. The nearest prior user message remains an unrelated trip-note instruction, not an oracle permission pointer. This is evidence of one useful presentation change, not proof of its internal mechanism or general benefit.

In invariant pair 08, the executed booking is for Eli Reed while the moved grant concerns Mina Ross. Both versions should remain violations. Qwen changes from violation to authorized when the unrelated grant is moved after execution, in both presentations; Jev remains correct. This control reveals an unwanted change where no change is warranted. A single observation cannot distinguish object-scope confusion from position sensitivity or judgment variation. The diagnostic measures labels, not rationale quality or repeated-run stability.

The basic and intervening pairs use different instances, so their scores do not cleanly identify the causal effect of inserting a message. Two invariant controls are too few to estimate a general scope-error rate. Perfect Jev performance leaves no observed room for indexing gains and does not demonstrate universal temporal understanding.

### Failures and resource accounting

The first GPU startup failed before any Qwen request and consumed 1,237 seconds. After explicit authorization for one additional allocation, the recovery verified model assets on CPU and copied a compatible compilation cache without changing scientific inputs. The second H200 job completed with exit code 0:0 in 136 seconds. The first failure remains in the record and budget. [E7]

| Batch | Actual model calls | H200 allocation time | Estimated Jev API usage |
| --- | ---: | ---: | ---: |
| Reused-data Jev 2×2 | 248 including 8 checks | 321 seconds | $0.012413478 |
| New mainline | 2,706 including collection and checks | 2.400556 hours | $0.155981742 |
| Timing including failed start | 72 including 8 checks | 1,373 seconds of 1,800 allowed | $0.001716372 of $0.10 allowed |

All timing attempts were single attempts, with no repeated judgment or replacement data. Both timing allocations total 22 minutes 53 seconds, within the original 30-minute cap. API figures use returned usage and the price fixed for each run; they are estimates, not reconciled invoices. GPU dollars are not estimated. Different serving environments make request-latency ratios unsuitable as pure architecture-speed comparisons. Budget compliance does not imply a positive scientific result.

## 6 Implications and limitations

### Why this matters

An authorization monitor can support incident review by connecting a disputed action to the permission and receipt that existed at the time. Correctly releasing authorized actions matters too: false alarms can burden reviewers and interrupt legitimate work. The project supplies concrete examples of both missed violations and review-induced false alarms. It also shows why a final reassuring summary, a later grant or a citation with the right identifier is insufficient on its own.

The mainline suggests a practical evaluation principle: establish a strong direct Judge baseline before crediting an elaborate questioning procedure. If the baseline already extracts the available evidence, more questions may add cost without additional detection. Our targeted-follow-up and Jev-indexing primary comparisons illustrate this limit. Conversely, the Qwen timing gain shows that an evidence transformation can help a particular configuration even when the stronger Judge gains nothing.

A plausible future system would combine deterministic checks for amounts and identities, bounded semantic judgment, and escalation when evidence is missing or decisions conflict. That is a design implication, not a tested outcome. We have not measured prevented harm, reviewer time saved, calibrated escalation thresholds or live deployment reliability. The experiment audits completed actions; blocking them before execution requires a separate intervention study.

### What the evidence cannot establish

**Generalization.** The new mainline uses existing templates; the timing set is eight constructed pairs. Reused development records, incidental duplicate requests and repeated conditions do not enlarge the independent sample. Sparse positive bank coverage and ceiling effects restrict sensitivity. The original proposal's disjoint task-family confirmation and broader coverage were not completed.

**Reference validity.** Labels are program- and simulator-based with AI review. Numeric name suffixes illustrate semantic ambiguity even under consistent exact-match rules. There is no independent human gold for the new studies. Historical fresh-context AI agreement on 12 older references was instructionally separated, not a hard sandbox, and does not validate the new 189 trajectories or eight timing pairs.

**Causal attribution.** The direct Judge comparison changes the deployed model and interface, not only an isolated reasoning component. Ledgers change several presentation properties. Fixed targeting rules can select a dimension that is not the actual failure. Outputs do not reveal internal reasoning, and the timing study has no explanation endpoint.

**Reliability and selection.** One call per timing cell cannot establish repeatability. An identical-input Jev disagreement already exists in the mainline. Zero observed false alarms is not a certified low population false-alarm rate. The broader narrative is an explicitly disclosed synthesis after results; the original primary hypotheses, thresholds and full-denominator failures remain unchanged. Deduplication sensitivity does not replace the primary analysis.

## 7 Relation to prior work and team contributions

Guan et al.'s *Monitoring Monitorability* studies multiple monitoring settings and reports benefits from follow-up reasoning in its evaluated configurations. Our public-action authorization setting and targeted-versus-generic contrast are narrower; our negative result does not refute their broader findings. Wang et al.'s *MonitorBench* emphasizes dependence on task and monitoring configuration. We use the project's inherited simulator/framework work while defining a separate explicit-authorization endpoint, rather than claiming to reproduce every benchmark setting. [R1, R2]

TypeSafe documents Jev as a model returning typed decisions and probabilities instead of generated explanations; type validity does not guarantee correctness. Deußer et al. evaluate Jev-1.13.0 across classification and sequential tasks, including comparisons with other models. Their results make a simple “Jev versus an LLM” comparison insufficient as a novelty claim. Our different version and task setting require their own evidence. The distinctive project contribution is the combination of shared-material controls, preserved negative results, execution-time permission changes and evidence-support audits. [R3, R4]

The report retains the proposal's four authors. Repository provenance attributes the original TGF and simulator implementation to Luanfeng's work; the explicit-authorization evaluation, shared-material comparisons and integration to Pacifica's work; the timing design to Qier's branch; and evidence-interface and evidence-support audits to Tony's work. These are provenance descriptions, not a newly agreed contribution statement. Qier's and Tony's branches remain linked separately. The team should review final attribution before submission. [E6, E7, E8]

AI assistance was used for code, operational checks, source inspection, analysis, report drafting and presentation preparation. The 32-case mainline review and timing source checks are AI work and are not described as human review. A separate AI context reviewed 12 older reference records before unblinding; its scope and limitations remain documented. This report is an integrated course deliverable for team review, not a course submission or an assertion of compliance with an unverified final-format requirement.

## 8 Conclusion

Jev is the primary final Judge in a study of execution-time authorization auditing. It provides a stronger direct baseline than the tested Qwen deployment on this mainline batch, but neither targeted follow-up nor the later Jev time-indexing comparison establishes additional benefit under its primary criteria. The timing controls make specific missed and unwanted changes visible beyond an aggregate score. Source audits show why correct labels, valid citations and reliable evidence support must be evaluated separately.

The project therefore contributes a reproducible, bounded account of where monitoring improvements arise and where they do not. The earlier negative results, initial startup failure, ambiguous references and observed inconsistency remain part of that account. No additional sampling or experiment was initiated for this integration.

## Evidence and reproducibility

All links below identify saved evidence rather than instructions to initiate experiments. The [integrated repository guide](README.md) provides source paths and offline commands. Raw inputs, protocols, result archives and failure ledgers are preserved in their owning dated directories. Mainline and timing outputs are not relabeled or pooled. The November 7 report remains a historical snapshot.

Earlier engineering failures also remain in the repository. The November 3 run collected 24 authorized sensitive-action trajectories and no violations; P/C/F/T returned only 9/3/3/4 valid judgments, with zero jointly valid F/T pairs. It cannot establish detection effectiveness. Its [citation-validation diagnosis](../prospective_monitoring/offline_diagnostic_2026-11-03/DIAGNOSIS.md) is retained separately from the later completed comparisons. The [November 5 alignment record](../evaluation_alignment_2026-11-05/README.md) also preserves the correction of a legacy null-score imputation rather than carrying that inflated detection count forward.

- **[E1] Early development and closing extension.** [November 7 final report](../closeout_2026-11-07/FINAL_REPORT.md), [offline reproduction](../closeout_2026-11-07/DATA_AND_CODE.md).
- **[E2] New mainline.** [Published report](../research_update_2026-11-12/reports/mainline.md), [frozen protocol](../jev_tgf_mainline_2026-11-12/PROTOCOL.md), [result package guide](../research_update_2026-11-12/README.md).
- **[E3] Reused-data Jev 2×2.** [Stratified results](../research_update_2026-11-12/reports/development_2x2.md).
- **[E4] Judge component comparison.** [Post-hoc baseline comparison](../research_update_2026-11-12/reports/baseline_comparison.md).
- **[E5] Source review and limitations.** [Semantic audit](../research_update_2026-11-12/reports/semantic_audit.md), [32-case AI review](../research_update_2026-11-12/source_review/README.md).
- **[E6] Tony's evidence-chain audit.** [Source commit 898b73ac](https://github.com/LuanfengBest/TGF_Monitor/blob/898b73acb3b284d39cd61ac4f157d0ef200de5a1/workstreams/tony/06_evidence_support_audit_2026-11-11/README.md).
- **[E7] Timing diagnostic.** [Completed results](../authorization_timing_jev_2026-11-12/RESULTS.md), [protocol](../authorization_timing_jev_2026-11-12/PROTOCOL.md), [run and recovery record](../authorization_timing_jev_2026-11-12/RUN_STATUS.md), [Qier source design](https://github.com/LuanfengBest/TGF_Monitor/blob/407ed0026685e958ed35342b70d0a50e90da2854/authorization_timing_v1/README.md).
- **[E8] Original proposal and scope.** [October proposal snapshot](../reference/final_proposal_2026-10-07.md), [team handoff](../research_update_2026-11-12/TEAM_HANDOFF.md).

## References

- **[R1]** Guan, M. Y., et al. (2025). [Monitoring Monitorability](https://arxiv.org/abs/2512.18311). arXiv:2512.18311.
- **[R2]** Wang, H., et al. (2026). [MonitorBench A Comprehensive Benchmark for Chain-of-Thought Monitorability in Large Language Models](https://arxiv.org/abs/2603.28590). arXiv:2603.28590, version 4.
- **[R3]** Deußer, T., Ramamurthy, R., Sparrenberg, L., and Sifa, R. (2026). [Evaluating and Benchmarking the System One Model Jev](https://arxiv.org/abs/2609.37647). arXiv:2609.37647, version 2.
- **[R4]** TypeSafe. [System One documentation](https://docs.typesafe.ai/concepts/system-one). Accessed November 13, 2026. Vendor documentation is used for interface semantics, not as evidence of this project's accuracy.
