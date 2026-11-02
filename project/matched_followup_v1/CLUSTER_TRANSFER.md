# Cluster transfer without GitHub

2026-11-02. The user reports Yale login complete. The current assistant session
cannot control that browser, and command-line DNS lookups still fail. No remote
command, model download, preflight or GPU submission has been completed today.

`build_cluster_bundle.py` exports committed code, the byte-identical frozen dev64,
13 original source records, reference files and runbook. Each file has a SHA-256
entry in `bundle_manifest.json`. It excludes model weights, credentials and local
environments. It is a runtime subset, not a complete Git checkout. The diagnostic
implementation and its limits are unchanged.

Build locally from the repository root, using the existing PyYAML environment:

```bash
PYTHONPATH=. python project/matched_followup_v1/build_cluster_bundle.py
```

Upload the resulting `dist/TGF_cluster_<commit>.zip` through the logged-in portal's
file manager into the project workspace. Extract into a new directory; do not
overwrite an older deployment. From the extracted directory, run:

```bash
python3 project/matched_followup_v1/cluster_inventory.py > cluster_inventory.json
```

The inventory reads identity, queue, account associations, the H200 partition,
current Python package metadata and a bounded list of candidate asset paths. It
does not import models, fetch weights, create a job or reserve a GPU. Its default
search roots are Pacifica's previously recorded course project and scratch paths;
an incomplete/missing scan is not proof the assets are absent. Use `--asset-root`
only for an existing authorized project location when one is known.

Use the inventory to resolve two existing deployment uncertainties:

- Tony's historical runtime used an Apptainer image and `cpsc4710` account. Those
  paths and account permissions have not been verified for Pacifica's course login.
- Tony's archived model launcher used receipt-verified flat weight directories.
  The new preflight currently requires exact Hugging Face cache snapshot paths.
  Do not bypass validation or redownload 122 GiB to hide a layout mismatch; inspect
  the actual cache/receipt and adapt with equivalent provenance if needed.

Only after locating and verifying the real runtime, assets and H200 association
should the [preflight command](../../matched_followup/README.md) run. A successful
inventory is not a successful preflight. The existing single 60-minute allocation,
72-call cap, fixed eight cases and zero-retry policy remain in force.
