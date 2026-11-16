"""Package existing evidence and final materials, without running experiments."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'deliverables'
VAL=HERE/'validation'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((VAL/'manifest.json').read_text())
paths=set()
for group,base in [('files',ROOT),('local_reference_files',VAL),('preparation_code',ROOT),('simulator_provenance',VAL)]:
    for name,digest in manifest[group].items():
        p=base/name;assert sha(p)==digest,(group,name);paths.add(p)
paths.update(p for p in (VAL/'cluster_results_32473668').rglob('*') if p.is_file())
paths.update(p for p in (HERE/'ai_blind_review_2026-11-07').iterdir() if p.is_file())
paths.update(p for p in OUT.iterdir() if p.is_file() and p.suffix in ('.pdf','.docx','.md','.json') and p.name not in ('bundle_receipt.json',))
for rel in ['manifest.json','analysis_32473668.json','output_reviews_32473668.json','interpretation_32473668.json',
            'completion_verification_32473668.json','collection_receipt_32473668.json','collected_files_sha256_32473668.json',
            'submission_receipt_LOCAL.json','closeout_validation_results_32473668.zip','final_scheduler_observation_32473668.txt',
            'completion_remote_observation_32473668.txt','STATUS.json']:
    paths.add(VAL/rel)
for rel in ['FINAL_REPORT.md','overview.html','README.md','RESUME.txt','STATUS.json','evidence_index.json','offline_verify.py',
            'reconcile_ai_review.py','results_32473668.html','build_report_docx.py','build_presentation.mjs']:
    paths.add(HERE/rel)
for v in json.loads((HERE/'evidence_index.json').read_text()).values():
    if isinstance(v,dict) and 'path' in v:paths.add(ROOT/v['path'])
for href in re.findall(r'\[[^\]]+\]\(([^)]+)\)',(HERE/'FINAL_REPORT.md').read_text()):
    if not re.match(r'https?://',href):paths.add((HERE/href.split('#')[0]).resolve())
inventory={}
for p in sorted(paths):
    assert p.is_file() and p.resolve().is_relative_to(ROOT),p
    inventory[str(p.relative_to(ROOT))]=sha(p)
target=OUT/'TGF_Closeout_Evidence.zip'
with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(paths):z.write(p,'TGF_closeout/'+str(p.relative_to(ROOT)))
    z.writestr('TGF_closeout/BUNDLE_MANIFEST.json',json.dumps(inventory,indent=2)+'\n')
    z.writestr('TGF_closeout/START_HERE.txt','Read project/closeout_2026-11-07/deliverables/README.md.\nRead-only verification: python3 project/closeout_2026-11-07/offline_verify.py\nRequires jsonschema. No GPU or network. Do not run submission or campaign scripts.\nThe saved Spaces presentation is linked by identity in presentation_metadata.json.\n')
receipt={'created_at_utc':datetime.now(timezone.utc).isoformat(),'bundle':target.name,'sha256':sha(target),
         'bytes':target.stat().st_size,'evidence_and_material_files':len(inventory),'total_zip_members':len(inventory)+2,
         'model_calls':0,'external_transmission':False,'scope':'Full offline reanalysis of final 120 existing outputs, final materials, sealed AI review, and selected earlier evidence. Earlier raw campaigns and model weights are not included.'}
(OUT/'bundle_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
