# Snapshot verification

Run from the repository root with Python 3.10+. These commands use the standard library and do not call models or execute simulator tools.

```bash
python3 -B project/verify_snapshot.py
python3 -B project/analyze_workstreams.py
```

`verify_snapshot.py` checks every imported file's size/SHA256, Tony's original bundle inventory, and Pacifica's read-only 64-source / 3,817-event acceptance script. `analyze_workstreams.py` recomputes Tony's audit in memory, checks it against the supplied audit, verifies v4 code and dev64 identity, and prints legacy-label B2/TGF statistics by run and domain. It does not overwrite original derived reports, repair model outputs, change labels, or write new scores.

The second script's saved output is [validation/workstream_analysis.json](validation/workstream_analysis.json). The import validation receipt is [validation/snapshot_verification.json](validation/snapshot_verification.json). These receipts document the integration check, not new inference or human review.

## Data identity and labels

- Base repository commit: `481fcd7985241601cf8ceae3833a36082d398898`.
- Shared dev64 SHA256: `2511ce6fad89cfc6900173e8cdffcc6c556f8f53caca8c7651f21974b5e1c0ca`.
- All 64 source JSON records for the authorization audit are included at their indexed relative paths.
- Full, tool-limit-2000, Tony's 64-record replay, and Tony's two-record smoke run reuse the same development pool. They are not independent data sets.
- Legacy scoring preserves null→50 and threshold `>=50` solely to reproduce historical results. The new authorization audit is a different endpoint; these scripts do not rescore legacy predictions against it.

## Imported assets and omissions

[import_manifest.json](import_manifest.json) lists exact source-relative provenance, byte sizes, hashes, and omitted categories. The local October 16 full handoff ZIP and Tony's input ZIP are identified by hash; neither duplicate archive is committed. Large historical collection state chains and downloaded public corpora remain external. Historical configs may reference these omitted files. Model weights and runtime installation are not included.

Tony's original 51-file bundle is retained intact. It includes the original and corrected reports: use `audit_30030723/corrected_metrics.md` for domain-specific token/failure counts. The archive's original claims and path spellings remain historical text; the project overview records the integration's current interpretation.

There were no edits to the root `tgf/` implementation in this integration. The fairness and endpoint issues described in [the story](STORYLINE_2026-10-19.md) remain research work; copying assets does not resolve them. Historical GPU submission scripts must not be run as a verification shortcut.
