# Reproduce the saved results on CPU

This entry runs existing offline verifiers. It does not rerun an Actor, Judge, simulator, training job or cluster allocation. Passing means saved evidence reproduces the reported analyses; it does not provide new observations or independent human validation.

## Set up once

Use Python 3.13 (verified for this closeout) and an isolated environment. Dependency installation requires a package source; verification itself uses local files only.

```sh
python3 -m venv .venv-offline
.venv-offline/bin/python -m pip install -r project/closeout_2026-11-07/requirements-offline.txt -r project/research_update_2026-11-12/requirements-offline.txt
.venv-offline/bin/python -B verify.py
```

Pinned requirements are reused from the original packages. No GPU, API key, model weights or root `requirements.txt` installation is needed. The wrapper resolves its repository root, stops on the first failed verifier, and prints the error instead of skipping missing dependencies or files.

## What is checked

| Verifier | Scope |
| --- | --- |
| [November 7 verifier](project/closeout_2026-11-07/verify_all_results.py) | Earlier collection, aligned labels, controls, evidence diagnostics and closing negative results |
| [Jev verifier](project/research_update_2026-11-12/verify_saved_results.py) | 31/480-file frozen manifests, shared archives, development/mainline statistics and post-hoc baseline analysis |
| [Timing verifier](project/authorization_timing_jev_2026-11-12/verify_completed_recovery.py) | 224 continuation inputs, 226 saved result/accounting files, first failure, authorized recovery and pair statistics |
| [Report verifier](project/final_report_2026-11-13/verify_integration.py) | Six report tables, 17 portable slides, DOCX contents, source numbers and local report links |

`verify.py` only dispatches those four fixed scripts with the current Python interpreter. Individual commands remain available for diagnosis. It never discovers or executes experiment launchers or AGV scripts.

The [November 12 guide](project/research_update_2026-11-12/README.md) describes archive omissions. The shared mainline export omits repeated full simulator-state dumps; hashes remain, but CPU reproduction is not a rerun or re-audit of every omitted state. [Older reproduction limits](project/closeout_2026-11-07/DATA_AND_CODE.md) still apply. Frozen data, schemas, budgets, labels and denominators are never rewritten to make a check pass.

## Rebuild the report only

The Markdown report is the content source. `project/final_report_2026-11-13/build_report_docx.py` uses `python-docx` to rebuild Word; PDF export needs a document renderer. These optional authoring dependencies are not required for offline result checks. After an edit, rebuild Word/PDF, inspect every rendered page and run the integration verifier before publishing. No model experiment is part of a document rebuild.
