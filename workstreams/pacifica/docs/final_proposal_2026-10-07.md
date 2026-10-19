# Trace Grounded Follow Up for Agent Monitoring

来源：[最终 Google Doc](https://docs.google.com/document/d/1s0acz6ibYsIv9OfO0lY6DUSjHZQC9S7ynrUiIecoW6w/edit?tab=t.0)
读取日期：2026-10-07。Tab：t.0。Revision：`ANLCKQnxQ1G1dUfCE6skM3g5vSbHiF2zCIQOhWA9MttdUKx_TELEoHhp_mbeM1jYTAMu6_YLzW2kKgp9d2rw8CyLEjzngeg7r7gz6IoGRjI`。
以下为正文快照，只添加 Markdown 标题和段落格式，没有改写内容。在线文档后续如有修改，应核对差异。

CPSC 4880/5880 Project Proposal · Guided Track 2

Pacifica Zhang — rz377     Luanfeng Wei — lw856	Qier An — qa24     Tony Zhu — jz965

## Motivation and research question

Can a monitor detect more unauthorized agent actions by asking questions grounded in the observed trajectory, at comparable inference cost and false-positive rates? Long traces can obscure decisive actions, while sensitive actions may be legitimate. We propose Trace-Grounded Follow-up (TGF): a fixed-weight monitor that identifies uncertain authorization and requests additional evidence. The intended use is offline auditing and risk triage; follow-up explanations do not reverse executed actions or establish authorization.

## Related work and gap

Monitoring Monitorability [1] studies monitoring scopes, g-mean squared, and general or task-tailored follow-ups. MonitorBench [2] provides dual-objective environments and hierarchical trace monitoring; its outcome evaluation focuses on successful target behaviors. SHADE-Arena [3] evaluates sabotage and monitor fine-tuning. We investigate whether questions selected from individual actions improve detection beyond fixed questions, structured trace review, and additional monitor compute. This is an empirical comparison, without assuming that adaptive questioning itself is new.

## Proposed method

TGF extracts a ledger of state-changing tool calls, checks each against the user request and governing policies, and ranks unresolved authorization questions. For up to k entries, it asks a neutral, action-specific question, such as which instruction authorized a transfer to a particular recipient. The actor responds with tools disabled. A final judge combines the original evidence, ledger, and permitted follow-up outputs into a 0–100 suspicion score. Actor self-reports are fallible evidence, never ground truth or new permission.

We will select one open-weight actor (gpt-oss-120b or 20b) and a Qwen3-32B monitor during a cost-and-access pilot, then freeze the configuration and original trajectories. Each questioning condition branches independently from the actor's original context. The primary all-messages setting includes available original and follow-up reasoning; a strict action-only ablation excludes both. Monitors receive applicable policies, but never hidden side-objective instructions or verifier outputs. Long-trace preprocessing is shared and frozen.

## Data and reference labels

We will use MonitorBench's bank_transfer_2 and american_airlines_2 environments, with ordinary requests, injected side objectives, and authorized-but-sensitive cases. A programmatic verifier will check execution events and privileged simulator state against explicit authorization specifications, including actions later reversed. Labels target executed unauthorized actions: side-task success alone does not establish a violation, and absence of a side task does not guarantee a negative. Failed attacks and unexecuted attempts are reported separately; reviewers audit sampled labels, and unresolved cases are excluded with counts disclosed.

## Comparisons and evaluation

The pilot targets 30 verified positives and 30 negatives per environment. Its costs and variance will inform a prespecified final sample size; these counts do not establish low false-alarm rates. Task families and derived examples stay within one split. Pilot/development, validation, and final test families are disjoint, with untouched rollouts as the main test and constructed authorization pairs as diagnostics.

Baselines are B1 passive hierarchical monitoring, B2 fixed-question follow-up, and B3 extra monitor review under a comparable inference budget, alongside deployable rules using visible authorization fields. B2 includes a single-question baseline and a count- and budget-matched variant. The main question-policy comparison shares the ledger, judge prompt, selected entries, observation channels, and answer-token caps; only targeted versus fixed question content changes. A ledger-without-follow-up ablation isolates structured review. We select k and other settings using development data only.

We will report per-environment g-mean squared (TPR × TNR; primary), TPR/FPR, AUROC, and hard-negative false alarms. Score thresholds target a prespecified validation FPR and remain frozen on test data; actual test FPRs are reported. Paired task-family bootstrap intervals quantify differences. Evidence for TGF requires improved detection over matched baselines within false-alarm and cost tolerances prespecified on development data; inconclusive and negative results remain reportable. Costs include parsing, summaries, question generation, actor replies, and final judgments, with tokens separated by model plus call counts, latency, and API charges or GPU time.

## Execution and optional extension

By October 21, we will complete the pilot, label audit, and initial baselines. By November 30, we will complete primary comparisons and key ablations, leaving presentation and report preparation for December. Four members will cover environments/labels, TGF implementation, evaluation, and analysis with cross-review. Bouchet allocation and API budget will be confirmed in the pilot.

If time permits, we will separately train Qwen3-4B with QLoRA on verified authorization-contrastive pairs, comparing ordinary SFT under matched tokens, class balance, and optimization budget. This extension and a monitor-aware stress test are optional; TGF evaluation remains the main deliverable. No experimental gains are assumed.

## AI usage statement

ChatGPT/Codex has assisted with literature discovery, research-design discussions, grammar checking, word polishing for this proposal. We plan to use AI for coding, debugging, experiment automation, and analysis. Team members will read cited sources, review code, verify labels and calculations, and take responsibility for reported results. Material AI assistance will be documented.

## References

[1] Guan et al. (2025). Monitoring Monitorability. arXiv:2512.18311.

[2] Wang et al. (2026). MonitorBench: A Comprehensive Benchmark for Chain-of-Thought Monitorability in Large Language Models. arXiv:2603.28590.

[3] Kutasov et al. (2025). SHADE-Arena: Evaluating Sabotage and Monitoring in LLM Agents. arXiv:2506.15740.

