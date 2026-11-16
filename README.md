# Authorization Auditing with Jev as Final Judge

**Current entry · November 16, 2026 · completed evidence, no new experiments.**

We study whether a monitor can match a successful agent action to the permission effective when it executed. Jev-1.14.0 is the primary final Judge; Qwen3-32B is the comparator. “Monitor” means the whole audit process, with the Judge producing its final classification. Reference labels come from separately specified rules and simulator records, with disclosed AI review; they are not independent human gold.

大白话：Agent 把事情办成了，不等于它有权这么做。我们检查“当时有没有许可”，并区分换 Judge、整理证据和追加追问各自带来了什么。当前主线是 **Jev as Final Judge 的执行时授权审计**。Jev 的直接基线在这一批材料上更好，但追加追问和时间索引的主要增益都没有得到支持。

## Start here

| Purpose | Entry |
| --- | --- |
| Understand the completed study | [Integrated report](project/final_report_2026-11-13/FINAL_REPORT.md), [PDF](project/final_report_2026-11-13/deliverables/Authorization_Auditing_Report.pdf), [Word](project/final_report_2026-11-13/deliverables/Authorization_Auditing_Report.docx) |
| Prepare the stage report in a new session | [Session handoff](project/SESSION_HANDOFF.md) |
| Present the evidence | [17-slide text](project/final_report_2026-11-13/SLIDES.md), [Chinese notes](project/final_report_2026-11-13/SPEAKER_NOTES_ZH.md), [deliverable guide](project/final_report_2026-11-13/README.md) |
| Reproduce saved analyses without inference | [CPU reproduction](REPRODUCE.md); `python3 -B verify.py` in the prepared environment |
| Find earlier experiments and failures | [Archive registry](archive/README.md) |
| Understand AGV's status | [Optional extensions](extensions/README.md): proposed ablation, no published AGV effectiveness result |

## Findings and their boundaries

| Comparison | Saved result | Interpretation |
| --- | --- | --- |
| Same direct material, airline | Jev 21/26 vs Qwen 8/26 violations detected; both 0/67 false alarms | Post-hoc component comparison on one batch, not a general model ranking |
| Jev targeted vs generic follow-up | Score difference 0.0499425947, paired 95% interval [0, 0.1439409091]; latency ratio 1.1014 | Failed the prespecified 0.05 gain and 1.10 latency criteria |
| Both airline follow-up answers valid | Within each Judge, F/T classifications agree on all 91 records | Full-denominator differences come from two generic-answer truncations; retain these failures in the primary analysis |
| Eight-pair timing diagnostic | Jev 8/8 → 8/8; Qwen 4/8 → 5/8 with time links | Primary Jev indexing gain zero; Qwen one-pair gain is secondary |
| Earlier controls and evidence audits | No established targeted-follow-up advantage; cumulative evidence fixed only one of six blocks | Negative results and output failures remain part of the study |

The mainline has **189 eligible trajectories** from existing task templates. The timing study has **8 constructed pairs / 16 scripted simulator records**, with 64 formal judgments and 8 smoke calls. Calls, conditions and repeated records are not independent samples. These studies are reported separately.

The contribution is a reproducible empirical separation of Judge choice, evidence presentation, follow-up and output availability. Timing/scope controls and citation audits expose specific failure modes beyond an aggregate score. A useful implication is to establish a strong direct baseline before adding steps to a monitor. We have not demonstrated prevented harm, human time savings, calibration or deployment reliability.

Independent human review of the new studies is **0**. The 32-case mainline review is nonblind AI work. Numeric-name ambiguity, limited template coverage, ceiling effects and one observed Jev disagreement on identical requests remain explicit limitations. The revised narrative is a post-hoc synthesis; it does not replace the original hypotheses or their negative outcomes.

## Repository policy

This README owns the current narrative and navigation. The [project index](project/README.md) locates evidence; the [session handoff](project/SESSION_HANDOFF.md) owns remaining presentation work. Historical “current”, “pending” and “next experiment” statements apply only to their dated snapshots.

Earlier experiments are **archived in place**. Their module paths are still imported by later code and sealed in frozen manifests, so moving or deduplicating them would damage reproducibility. Raw inputs, outputs, references, failures, manifests and historical reports remain at their original paths. Redundant narrative checkpoints are under [archive/checkpoints](archive/checkpoints/2026-11-13/), with redirects at their former coordination paths. Archive status is not permission to rerun a launcher.

AGV remains on Luanfeng's separately pinned branch as an **optional extension with no completed ablation in this report**. The immediate task is stage-report preparation and team review, with no new inference, GPU allocation or sampling.

## Team and provenance

The proposal lists Pacifica Zhang, Luanfeng Wei, Qier An and Tony Zhu. Luanfeng provides the original TGF/simulator work and optional AGV code; Pacifica's workstream develops explicit authorization evaluation, shared-material comparisons and integration; Qier provides the timing-design source; Tony contributes execution, interface and evidence-support audits. [The report](project/final_report_2026-11-13/FINAL_REPORT.md#7-relation-to-prior-work-and-team-contributions) records the limits of this provenance-based attribution and AI assistance. Final attribution and course requirements still need team confirmation.

The project builds on [MonitorBench](https://github.com/ASTRAL-Group/MonitorBench) and the repository's agent simulators. Preserve [upstream documentation](MONITORBENCH_UPSTREAM.md), the [repository license](LICENSE) and [agent simulator license](datasets/dual_objective/agent/LICENSE). Upstream benchmark results are not this project's results.
