"""Archive only the completed immutable first trace while later traces may run."""
import json,hashlib,zipfile,datetime
from pathlib import Path
root=Path.cwd();run=Path('results/prospective_four_arm_v2_runtime_recovery_29588632')
tid='prospective5_001_bank_transfer_2_ordinary';d=run/tid
assert json.loads((d/'summary.json').read_text())['status']=='completed'
assert all(json.loads((d/'integrity_gate.json').read_text()).values())
paths=[p for p in d.rglob('*') if p.is_file()]
for identity in (run/'calls').glob('*_identity.json'):
 if json.loads(identity.read_text())['name'].startswith(tid+'/'):
  stem=str(identity).removesuffix('_identity.json')
  assert Path(stem+'_response.json').exists() and Path(stem+'_usage.json').exists()
  paths.extend(identity.parent.glob(Path(stem).name+'_*'))
paths += [run/n for n in ['plan.json','runtime_policy.json','runtime_decision.json','qwen3_32b_metadata.json','gpt-oss_20b_metadata.json']]
assert all(p.is_file() and not p.is_symlink() for p in paths)
manifest={p.as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}
archive=Path('results/prospective_four_arm_recovery_prefix1_29588632.zip')
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
 for name in manifest:z.write(name,name)
 z.writestr('MANIFEST.json',json.dumps(manifest,indent=2))
print(json.dumps({'observed_at':datetime.datetime.now().astimezone().isoformat(),'files':len(manifest),'archive':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'bytes':archive.stat().st_size,'scope':'one completed first trace only, not whole stage'}))
