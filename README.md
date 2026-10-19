# TGF Monitor - course final project

Trace-Grounded Follow-Up for Agent Monitoring · CPSC 4880/5880

Pacifica Zhang, Luanfeng Wei, Qier An, Tony Zhu

We study whether questions grounded in executed agent actions improve monitoring beyond fixed questions and structured review, while controlling false alarms and cost.

The current implementation uses MonitorBench banking/airline environments, a gpt-oss-120b actor, and a Qwen3-32B monitor. `tgf/` contains the action ledger, question planner, tool-disabled actor follow-up, final judge, and B1/B2/B3 baselines. `workstreams/pacifica/` preserves execution contracts, authorization audits, and earlier diagnostics. `workstreams/tony/` contains an independent replay and audit of the same 64 development records.

The pipeline runs, but current evidence does not establish a reliable benefit over a matched fixed-question baseline. Human review, sufficient legitimate sensitive negatives, and held-out evaluation remain incomplete.

- [October 21 progress report (PDF)](output/pdf/progress_report_2026-10-21.pdf) · [editable source](project/reports/progress_report_2026-10-21.md)
- [TGF implementation and usage](tgf/README.md)
- [Integrated evidence and next steps](project/README.md)
- [CPU-only verification](project/REPRODUCIBILITY.md)
- [Original MonitorBench documentation and attribution](README_MONITORBENCH.md)

Historical GPU scripts are archived evidence, not launch instructions. AI assistance is disclosed in the report. This private repository's course-staff access remains to be arranged under the course instructions.
