# Optional extensions

**AGV is optional future work. No new experiment is part of this closeout.** Jev remains the final Judge in the completed authorization study. Reference generation, offline scoring and a proposed rule helper serve different purposes; they are not a chain of models judging one another.

## AGV source and current evidence

Luanfeng's reviewed branch is pinned at [76013e4aa57290eddaeee98b02f33623c3f76099](https://github.com/LuanfengBest/TGF_Monitor/tree/76013e4aa57290eddaeee98b02f33623c3f76099). [AGV code](https://github.com/LuanfengBest/TGF_Monitor/tree/76013e4aa57290eddaeee98b02f33623c3f76099/agv_v0) adds partial authorization checks and source pointers to the public record. The complete record remains available to the Judge. The rule layer returns violation or unresolved; unresolved does not certify authorization.

The [holdout builder](https://github.com/LuanfengBest/TGF_Monitor/blob/76013e4aa57290eddaeee98b02f33623c3f76099/agv_holdout/design.py) scripts 8 pairs / 16 records: four airline pairs, four bank pairs, four expected changes and four invariances. It writes action receipts and labels directly. These are prepared fixtures, not new Actor trajectories or simulator executions, and are distinct from the completed timing study's 8 pairs.

No committed AGV model outputs, formal scores or actual-cost ledger were found at that version. This does not establish whether someone ran an unpublished local experiment. Offline inspection found all 16 holdout records unresolved by the partial rules. That measures coverage only, not Jev/Qwen performance. The holdout runner has Qwen raw/agv/agv_split conditions (48 planned positions); it does not implement the controlled ablation below. Slurm time requests are code settings, not approved budgets.

## Should the report call it an ablation

**Only as a proposed, unrun ablation in future work.** The useful question is whether explicit rule conclusions help a fixed Judge beyond giving it the same record and evidence sources.

| Proposed condition | Material and purpose |
| --- | --- |
| Rule conclusions removed | Full public record + identical ledger + identical source bindings; reference Judge condition |
| Rule conclusions added | Same material plus partial rule conclusions; isolates the additional rule information |
| Rule-only diagnostic | Assess coverage, errors and unresolved cases; identify what the program decides without a Judge |

Keep model/version, decision protocol, case-order policy and inference settings fixed. Raw versus full AGV changes formatting, evidence selection and rule content together. AGV pointers may select permission through rule logic; they differ from the completed study's neutral time links. Freeze identical pointers across the proposed paired comparison to estimate the value of conclusions conditional on those pointers. Studying the whole source-selection mechanism needs a separate contrast.

Report full-denominator Judge detection, false alarms, invalid outputs, correct pair changes/invariances, rule coverage/error rates and cost. Inspect rule-only gains before crediting Jev. Do not treat unresolved as authorized or drop it to improve a score. Assess reference labels independently of the rule implementation; author-written cases and labels do not supply independent human gold.

This is a design sketch, not a frozen protocol. Before a separately authorized run, settle uncovered cases, reference review, scorer, output preservation, sample/attempt counts and total budget. Current authorization is documentation and offline verification only.

## Other teammate sources

- [Qier's design at 407ed002](https://github.com/LuanfengBest/TGF_Monitor/tree/407ed0026685e958ed35342b70d0a50e90da2854/authorization_timing_v1) informed the completed [Jev timing adaptation](../project/authorization_timing_jev_2026-11-12/RESULTS.md); this is not a claim that Qier's original runner produced those scores.
- [Tony's audit at 898b73ac](https://github.com/LuanfengBest/TGF_Monitor/tree/898b73acb3b284d39cd61ac4f157d0ef200de5a1/workstreams/tony/06_evidence_support_audit_2026-11-11) examines saved outputs. Its post-hoc citation-capacity metric differs from the original correctness endpoint. [Draft PR #1](https://github.com/LuanfengBest/TGF_Monitor/pull/1) remains separate.

See the [report discussion](../project/final_report_2026-11-13/FINAL_REPORT.md#optional-agv-ablation-for-future-work).
