# Current TGF results: reading and verification guide

This repository snapshot publishes the completed November 7 synthesis and its existing evidence. It does not initiate experiments, change frozen inputs, replace failed outputs, or submit a course assignment. Earlier dated plans and receipts retain their original historical state; the [final report](FINAL_REPORT.md) is the current synthesis.

## Read or present

1. [Final report](FINAL_REPORT.md), [PDF](deliverables/TGF_Report.pdf), or [editable Word](deliverables/TGF_Report.docx).
2. [Chinese speaker notes and discussion questions](deliverables/SPEAKER_NOTES_ZH.md).
3. [Final 120-call analysis](validation/analysis_32473668.json), [interpretation and cases](validation/interpretation_32473668.json), and [60-position output/source review](validation/output_reviews_32473668.json).
4. [Independent-context AI review summary](deliverables/AI_REVIEW_SUMMARY.md), [sealed judgments](ai_blind_review_2026-11-07/review_sealed.json), and [post-seal reconciliation](ai_blind_review_2026-11-07/reconciliation.json).

The editable 13-slide presentation is saved in the originating chat's Spaces Page. This repository includes its [identity and all speaker notes](deliverables/presentation_metadata.json); it does not claim to contain a portable PowerPoint export. The report and Chinese notes can be read without access to that Page. HTML result pages can be downloaded and opened locally.

## Conclusions to preserve

- On 24 airline development records, generic and targeted follow-up each detected all six violations; targeting added one false alarm. Holding the selected action fixed also found no question-content advantage across two seeds. The records were reused and the question conditions reached a ceiling; this does not establish equivalence or universal ineffectiveness.
- Some audited errors occurred despite available facts. Examples include applying the wrong authorization scope and citing text that does not support the verdict. Format validity, label accuracy and evidential support are different properties. Tony's source/format checks and the subsequent semantic audits address complementary parts of this problem.
- In the closing constructed-simulator extension, Qwen improved from 11/12 to 12/12 with cumulative totals, but only in one instance block, below the predeclared two-block criterion. Explicit budget comparisons added no further label gains. Valid true/false-assertion pairs had no verdict flips.
- All 120 calls remain in accounting: Qwen 60/60 valid and 59 labels correct; gpt-oss 45/60 valid and 45 labels correct, with 14 truncations and one schema failure. This is not a general model ranking.
- The 12 final reference labels received a separate-context AI blind review with 12/12 agreement before unblinding. It is not human annotation, does not cover all earlier records, and does not independently audit every Judge explanation.

These are bounded development comparisons and controlled diagnostic cases. The final inputs are scripted simulator records, not a new natural-actor collection or a targeted-versus-generic experiment. No untouched task-family generalization or internal-model mechanism is established.

## Verify the existing results

From the repository root, with Python 3 and `jsonschema` available:

```sh
python3 project/closeout_2026-11-07/offline_verify.py
```

This command reads existing files only. It verifies frozen hashes, all 120 planned/returned positions, the original result archive, and the AI review seal, then recomputes the saved analysis without networking or model execution. Expected totals are 105 valid, 14 truncated/nonstop, one invalid schema, 104 correct valid labels, and 192320 output tokens. The detailed [offline verification description](deliverables/OFFLINE_REPRODUCIBILITY.md) explains the scope.

The [publication inventory and verification receipt](repository_publication.json) records included file hashes and the isolated staged-snapshot check.

The original [portable evidence ZIP](deliverables/TGF_Closeout_Evidence.zip) is also preserved, together with its [receipt](deliverables/bundle_receipt.json). SHA256:

```text
5ec385100ef05ea43cc1e8a2f09d4007f1dbccbc35c116a5f860069175310a31
```

The archive contains 767 evidence/material files plus its manifest and start file. It supports full offline reanalysis of the final 120 outputs and includes selected earlier reports. The repository also includes linked earlier review material where available; it is not a copy of every historical campaign, local cache, preview, model weight or environment. Names such as `PRIVATE` and `LOCAL_ONLY` in frozen research artifacts designate material withheld from the experimental Judge, not human-certified labels.

## Earlier comparisons and cases

- [Natural collection and coverage](../new_data_collection_2026-11-05/REPORT_2026-11-06.md).
- [Four-strategy comparison](../airline_monitor_comparison_2026-11-06/REPORT_2026-11-06.md) and [case index](../airline_monitor_comparison_2026-11-06/semantic_review_32354336/CASE_INDEX.md).
- [Fixed-operation comparison](../anchored_question_diagnostic_2026-11-06/RESULTS_2026-11-07.md), [case reviews](../anchored_question_diagnostic_2026-11-06/author_review_32374475/case_reviews.json), and [review summary](../anchored_question_diagnostic_2026-11-06/author_review_32374475/REVIEW_SUMMARY.json).
- [Earlier cumulative-evidence interpretation](../evidence_claim_probe_2026-11-07/interpretation_32446760.json) and [output reviews](../evidence_claim_probe_2026-11-07/output_reviews_32446760.json).
- [Source index and hashes](evidence_index.json), including the frozen-commit source for Tony's recheck.

Historical files keep their original bytes for provenance, including some absolute workstation links. Use this guide and the final report's relative links for cross-machine navigation. Team confirmation of contributions/course format and formal course submission remain outstanding; additional experiments require separate authorization.
