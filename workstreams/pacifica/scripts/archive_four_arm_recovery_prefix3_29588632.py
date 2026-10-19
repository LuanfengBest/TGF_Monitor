"""Archive the first three immutable completed traces, preserving the prior prefix."""
import json,hashlib,zipfile,datetime
from pathlib import Path
run=Path('results/prospective_four_arm_v2_runtime_recovery_29588632')
ids=['prospective5_001_bank_transfer_2_ordinary','prospective5_002_american_airlines_2_ordinary','prospective5_004_american_airlines_2_ordinary'];paths=[]
for tid in ids:
 d=run/tid
 assert json.loads((d/'summary.json').read_text())['status']=='completed'
 assert all(json.loads((d/'integrity_gate.json').read_text()).values())
 paths.extend(p for p in d.rglob('*') if p.is_file())
for identity in (run/'calls').glob('*_identity.json'):
 if json.loads(identity.read_text())['name'].split('/')[0] in ids:
  stem=str(identity).removesuffix('_identity.json')
  assert Path(stem+'_response.json').exists() and Path(stem+'_usage.json').exists()
  paths.extend(identity.parent.glob(Path(stem).name+'_*'))
paths.extend(run/n for n in ['plan.json','runtime_policy.json','runtime_decision.json','qwen3_32b_metadata.json','gpt-oss_20b_metadata.json'])
manifest={p.as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}
archive=Path('results/prospective_four_arm_recovery_prefix3_29588632.zip')
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
 for name in manifest:z.write(name,name)
 z.writestr('MANIFEST.json',json.dumps(manifest,indent=2))
print(json.dumps({'observed_at':datetime.datetime.now().astimezone().isoformat(),'files':len(manifest),'archive':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'bytes':archive.stat().st_size,'scope':'three completed traces only, not whole stage'}))
