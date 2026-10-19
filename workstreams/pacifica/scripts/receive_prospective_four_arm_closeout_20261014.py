import hashlib,json,zipfile,datetime,subprocess
from pathlib import Path
root=Path.cwd().resolve()
package=root/'results/prospective_four_arm_closeout_delivery_20261014.zip'
expected='87555e412ba2a0b63d855fd025825c945ae1402d08b294951aae71278e91e59a'
assert hashlib.sha256(package.read_bytes()).hexdigest()==expected
new=[]
with zipfile.ZipFile(package) as z:
 m=json.loads(z.read('MANIFEST.json'));assert len(m)==23 and set(z.namelist())==set(m)|{'MANIFEST.json'}
 for n,h in m.items():
  q=(root/n).resolve();assert q.is_relative_to(root) and not q.is_symlink();b=z.read(n);assert hashlib.sha256(b).hexdigest()==h
  if q.exists():assert q.read_bytes()==b,'Existing file differs: '+n
  else:new.append(n)
 for n in new:
  q=root/n;q.parent.mkdir(parents=True,exist_ok=True)
  with q.open('xb') as f:f.write(z.read(n))
receipt={'received_at':datetime.datetime.now().astimezone().isoformat(),'package_sha256':expected,'verified':len(m),'new_files':len(new),'overwrites':0,'squeue':subprocess.check_output(['squeue','--me','--noheader'],text=True),'snapshot':'handoff/prospective_four_arm_closeout_20261014'}
with (root/'results/prospective_four_arm_closeout_sync_receipt_20261014.json').open('x') as f:json.dump(receipt,f,indent=2)
print(json.dumps(receipt))
