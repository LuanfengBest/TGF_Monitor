import json,zipfile,hashlib
from pathlib import Path
root=Path.cwd();base=Path('results/prospective_actor_v5_29585413');paths=[]
for name in ['prospective5_001_bank_transfer_2_ordinary','prospective5_002_american_airlines_2_ordinary']:
 case=base/name
 assert json.loads((case/'rollout/summary.json').read_text())['status']!='running'
 assert (case/'rollout/oracle/final_state.json').is_file()
 paths.extend(p for p in case.rglob('*') if p.is_file())
manifest={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
target=Path('results/prospective_v5_prefix2_29585413.zip')
with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as z:
 for n in manifest:z.write(n,n)
 z.writestr('MANIFEST.json',json.dumps(manifest,indent=2))
print(json.dumps({'files':len(manifest),'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}))
