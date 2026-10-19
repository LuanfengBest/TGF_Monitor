# Trace-Grounded Follow-Up for Agent Monitoring

We study whether trajectory-specific follow-up improves a fixed-weight monitor's detection of executed unauthorized actions relative to fixed questions and extra review. TGF is the method; G² = TPR × TNR is one metric.

Implemented: MonitorBench banking/airline actor rollouts, public/private observation separation, event/state logging, four comparison conditions, evidence audits, and a three-arm Qwen3-32B LoRA component diagnostic. Source and job configurations are frozen per batch. See `docs/` for protocols, `scripts/` for implementations, `tests/` for boundary checks, and `analysis/` plus `results/` for evidence.

As of October 16, 2026, the proposal's 30P/30N per environment is not met, independent human review is incomplete, and the latest data gate failed. Existing results are diagnostic, not proof of TGF benefit or the need for SFT. No new experiment is running under this handoff.

Do not run historical submission scripts automatically. Review source hashes, data eligibility, privacy separation, budgets, and actual job receipts before any separately approved experiment. Do not publish private reference answers, credentials, or cluster paths indiscriminately. Full model weights/adapters remain outside this handoff; their provenance is recorded.

This is a prepared README for the team's eventual project repository, not evidence that a repository has been created or published.
