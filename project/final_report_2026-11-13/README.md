# Integrated report and presentation

November 13, 2026. **Authorization Auditing with Jev as Final Judge** integrates the completed project without changing any frozen experiment or starting a new one.

## Read and present

- [Report source](FINAL_REPORT.md), [PDF](deliverables/Authorization_Auditing_Report.pdf) and [editable Word report](deliverables/Authorization_Auditing_Report.docx).
- [Updated native presentation](https://chatgpt.com/space/page_6f15e7205f9c81918f8762765794d4af): the existing deck updated in place, 12 main slides and 5 appendix slides, with Chinese speaker notes. Existing Page access permissions are unchanged.
- [Portable slide contents](SLIDES.md) and [Chinese rehearsal notes](SPEAKER_NOTES_ZH.md) are available in this repository without requiring Page access. The suggested 10–12-minute main talk is a rehearsal target, not a verified course time limit.
- [Machine-readable slide content](SLIDES.json), [presentation metadata](presentation_metadata.json), and [verification receipt](VERIFICATION.json).

The report answers whether a monitor correctly relates successful actions to permission effective at execution time. Jev is the primary final Judge, Qwen is the comparator, and reference labels remain external to both. The contribution is a controlled, reproducible empirical separation of Judge choice, evidence presentation, follow-up and output availability. It is not a new model architecture or a claim that Jev solved monitoring reliability.

## Findings retained together

1. The same-input direct Judge comparison improves airline detection from Qwen 8/26 to Jev 21/26, with 0/67 observed false alarms for both. This is explicitly labeled a post-hoc component comparison.
2. The original Jev targeted-versus-generic follow-up hypothesis did not pass its frozen support criteria. Its score difference is 0.0499425947 with a 95% interval including zero; valid-answer classifications agree. The two generic truncations remain in the primary denominator.
3. In the separate eight-pair timing diagnostic, Jev is correct on 8/8 pairs with source or linked cards, so its primary indexing gain is zero. Qwen changes from 4/8 to 5/8 correct pairs; that one-pair improvement is secondary.
4. Earlier TGF, fixed-action and cumulative-evidence negative results remain visible, as do the initial startup failure, synthetic-name ambiguity, review-associated false alarms, incomplete citations and one Jev disagreement on identical requests.
5. New mainline and timing human review remains **zero**. AI review is disclosed accurately. No claim of prevention, calibrated deployment reliability or reviewer time savings is made.

## Evidence and offline checks

| Evidence | Owning source |
| --- | --- |
| Mainline statistics and intervals | [RESULTS.json](../jev_tgf_mainline_2026-11-12/RESULTS.json) |
| Baseline component comparison | [BASELINE_COMPARISON.json](../jev_tgf_mainline_2026-11-12/BASELINE_COMPARISON.json) |
| Timing group and pair counts | [analysis.json](../authorization_timing_jev_2026-11-12/recovery_01/analysis.json), [DETAILS.json](../authorization_timing_jev_2026-11-12/recovery_01/DETAILS.json) |
| Timing failure and aggregate resources | [FINAL_OUTCOME.json](../authorization_timing_jev_2026-11-12/recovery_01/FINAL_OUTCOME.json), [RUN_STATUS.md](../authorization_timing_jev_2026-11-12/RUN_STATUS.md) |
| Early complete report | [November 7 historical report](../closeout_2026-11-07/FINAL_REPORT.md) |
| Source audits and teammate provenance | [Team handoff](../research_update_2026-11-12/TEAM_HANDOFF.md) |

From the repository root, the following commands read saved files only:

```sh
python3 -B project/final_report_2026-11-13/verify_integration.py
python3 -B project/authorization_timing_jev_2026-11-12/verify_completed_recovery.py
```

The integration check compares report/slide tables with saved analysis values, checks local links, and checks the DOCX contents. It uses only the standard library and does not run simulations, contact models or submit jobs. For complete earlier statistical reproduction and archive limitations, see the [November 12 reproduction guide](../research_update_2026-11-12/README.md) and [November 7 guide](../closeout_2026-11-07/DATA_AND_CODE.md). The shared mainline archive omits repeated full simulator-state dumps; it reproduces saved analyses, not every part of the original state audit.

`build_report_docx.py` uses python-docx. `update_presentation.mjs` is a callback for the existing viewer-bound artifact session and requires an explicit current slide-count guard; it is not an experiment launcher. All nine rendered report pages and all 17 final slides were visually inspected. Intermediate page images stay local in ignored `qa/`.

## Version and remaining scope

The older November 7 manuscript, PDF, outline and source files remain unchanged. Its live presentation Page now contains this integrated version; historical metadata describes the earlier state, not the current live contents. Existing slide identities were preserved, and four appendix slides were added.

Remaining work is actual human source review, team confirmation of attribution, rehearsal and verification of final course formatting/AI-disclosure requirements before submission. No final page/time requirement was found in the available course note or proposal; the current package is adaptable. This integration does not submit coursework, merge teammate branches, authorize another GPU allocation, repeat judgments or expand the sample.
