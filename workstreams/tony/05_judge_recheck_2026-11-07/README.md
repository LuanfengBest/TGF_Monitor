# Workstream C | Four-case Judge recheck

On November 7, 2026, the compact Judge recheck (Bouchet job `32376521`) finished in 9m 30s. All eight outputs passed the run's format and reference checks. Both arms scored all four development cases **0 (authorized)**, with zero abstentions. The [case review](CASE_REVIEW.md) checks the original records for the selected action in each pair and identifies gaps in the Judge's reasons.

| Result | v1 job 32353048 | v2.1 job 32376521 |
| --- | ---: | ---: |
| Judge outputs generated | 8/8 | 8/8 |
| Outputs passing each run's validator | 3/8 | 8/8 |
| Pairs with both outputs passing | 0/4 | 4/4 |

Each arm used the same underlying all-messages case record and selected action. B2 used one generic follow-up and the TGF arm used one follow-up that had been manually revised. This run reused the eight answers from job `31232708` and made zero Actor calls. Qwen3-32B (revision `9216db5781bf21249d130ec9da846c4624c16137`) ran with vLLM 0.13.0, xgrammar 0.1.27, thinking enabled, seed 42, temperature 0.6, top-p 0.95, a 131,072-token context, and an 8,192-token output cap. The first pair was the longest-input case. Both outputs had to pass the same format gate before the remaining six calls could run.

The new Judge prompt uses typed sources and fixed action slots, and decoding enforces a compact JSON schema. The CPU preflight exposed a JSON separator mismatch in v2. The v2.1 run passed after the fixture and schema serialization were aligned. Across the 226 action rows (113 slots evaluated in two arms), 160 listed only the user request and policy as model-supplied evidence, and 66 listed a tool source as well. The validator checks source IDs and timing. It does not check whether the cited content supports the verdict.

This was a development diagnostic on four reused cases. The Judge prompt and output constraints changed between runs, so the pass counts describe each run under its own protocol. The four tied scores give no evidence of an advantage for either question style. Independent whole-trajectory human labels are pending, so accuracy, TPR and FPR are unreported. This run is separate from the team's 24-case action-only pilot.

## Offline verification

[results.json](results.json) contains the per-call scores, token counts and totals. [judge_contract.py](judge_contract.py) is the exact validation code from the execution packet. With both original archives available locally, use Python 3.10+ to regenerate the eight decisions from the saved completions, verify the frozen prompt and token ID hashes, and check the summary against the published numbers. No GPU or model download is needed.

```bash
python -B verify_run.py /path/to/Tony_TGF_judge_recheck_v2_1_20261106.zip /path/to/Tony_TGF_judge_results_32376521.zip
```

| Local archive | SHA-256 |
| --- | --- |
| Execution packet | `7d663e9e66c4113c5eb6a4edb9e2f0f76867572ce09e169272dc77e5a4a35951` |
| Result archive | `f198ff679b9e24b0df780a56a2866ec3771915f28e2753f4469c5e3445f0016f` |

The public files contain summary data, source locators, and code. The full case records, prompts, follow-up answers, and completions are retained in the original local archives.

Reporting workflow reference: Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M. (2026). [Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents](https://arxiv.org/abs/2609.00065).
