"""Verify and save an isolated immutable handoff snapshot, with no original overwrite."""
from pathlib import Path
import json,zipfile,hashlib,datetime,subprocess
p=Path('results/four_arm_recovery_handoff_20261014.zip')
assert hashlib.sha256(p.read_bytes()).hexdigest()=='8c36db56601b8cc7020a26375e9b9175fde4754e293319b0388a705cbda57afc'
d=Path('handoff/four_arm_v2_recovery_20261014');assert not d.exists()
with zipfile.ZipFile(p) as z:
 m=json.loads(z.read('MANIFEST.json'));assert len(m)==35
 for n,h in m.items():
  q=Path(n);assert not q.is_absolute() and '..' not in q.parts
  assert hashlib.sha256(z.read(n)).hexdigest()==h
 d.mkdir(parents=True)
 for n in m:
  q=d/n;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(z.read(n))
 (d/'MANIFEST.json').write_text(json.dumps(m,indent=2))
x={'observed_at':datetime.datetime.now().astimezone().isoformat(),'status':'verified_and_saved','files':len(m),'overwrites':0,'destination':str(d),'archive_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'queue':subprocess.check_output(['squeue','-u','hpcllm_rz377','--noheader'],text=True)}
with Path('results/four_arm_recovery_handoff_sync_receipt_20261014.json').open('x') as f:json.dump(x,f,indent=2)
print(json.dumps(x))
