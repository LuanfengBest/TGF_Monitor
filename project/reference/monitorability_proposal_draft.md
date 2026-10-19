# Improving Agent Monitors with Authorization Contrastive Data

*Research design discussion reference. The course requires students to write submitted proposals themselves; this generated text is not a submission-ready document. No experiments have been completed.*

## Problem and motivation

We propose to study whether authorization-contrastive data augmentation improves a small LLM monitor at matched false-positive rates and inference budgets. An agent can complete a legitimate task while executing an unauthorized transfer or booking change. Flagging every sensitive action would also interrupt legitimate work. Our hypothesis is that examples with similar actions but different valid authorizations help monitors distinguish these cases. The intended application is offline behavioral auditing and risk triage; prevention before execution is outside our scope.

## Related work

Monitoring Monitorability [1] studies observation scopes, monitoring metrics, and follow-up questions. MonitorBench [2] provides dual-objective tasks and hierarchical monitoring of long traces. SHADE-Arena [3] evaluates agent sabotage and already demonstrates monitor fine-tuning. Building on these foundations, we isolate authorization-sensitive data construction as the experimental variable, rather than treating fine-tuning itself as the contribution.

## Proposed approach

We will freeze one actor and fine-tune a 4B-class open monitor using supervised fine-tuning with QLoRA. Its inputs are the user request, applicable policies, and visible messages, tool calls, and results. We will construct paired examples whose executed actions are similar but whose valid authorization differs, retaining only semantically consistent pairs and independently verifying both labels. Training uses standard SFT, without a new pairwise loss. We will compare ordinary augmentation against authorization-contrastive augmentation while matching model, training tokens, class balance, task coverage, and inference preprocessing. Long traces will share a frozen hierarchical summarization stage; only the final judging monitor will be trained.

## Datasets and evaluation protocol

We will generate rollouts in MonitorBench's bank-transfer and airline-booking environments, including ordinary requests and injected side objectives. Programmatic checks over structured authorization specifications, execution records, and simulator state will label executed violations; attempts and ambiguous cases will be tracked separately and spot-checked manually. The primary monitor will know the specified action classes but not the injected side objective or verifier outputs. This authorization-auditing extension will be reported separately from a reproduction of MonitorBench's original known-target protocol. Task-template families and all derived pairs will remain within one split. Untouched rollouts will form the main test set; constructed authorization pairs will form a separate diagnostic set.

## Experimental plan and expected contribution

Baselines will include deployable rules using available authorization fields; passive monitoring with released hierarchical aggregation; a predetermined follow-up question to the actor; another monitoring pass with comparable compute; and ordinary SFT on a matched training set. We will report per-environment AUROC, TPR, FPR, and g-mean squared, with thresholds selected on validation data and uncertainty estimated by task-family bootstrap. Cost accounting will include summarization and actor follow-ups, with training cost reported separately. The main test is whether our augmentation improves detection on held-out templates without increasing false alarms, beyond ordinary SFT and rules. We will begin with an end-to-end pilot and label audit, then scale within our four-person team's provisional single-A100 budget. Deliverables are a reproducible evaluation pipeline, data splits, training configurations, and an analysis of gains and failure cases; improvements are hypotheses, not assumed results.

## References

[1] Guan et al. (2025). Monitoring Monitorability. arXiv:2512.18311. [Paper](https://arxiv.org/abs/2512.18311)
[2] Wang et al. (2026). MonitorBench: A Comprehensive Benchmark for Chain-of-Thought Monitorability in Large Language Models. arXiv:2603.28590. [Paper](https://arxiv.org/abs/2603.28590)
[3] Kutasov et al. (2025). SHADE-Arena: Evaluating Sabotage and Monitoring in LLM Agents. arXiv:2506.15740. [Paper](https://arxiv.org/abs/2506.15740)
