"""Receive one authorized package, rejecting traversal, hash changes, and overwrites."""
import hashlib,json,zipfile,datetime
from pathlib import Path
root=Path.cwd().resolve()
package=root/'results/prospective_four_arm_v2_delivery_20261014.zip'
expected='9f241f82cd4a5b607e93e759f9bc8004f4f5307913317b0118c95cbcdd75c436'
assert hashlib.sha256(package.read_bytes()).hexdigest()==expected
new=[]
with zipfile.ZipFile(package) as z:
 manifest=json.loads(z.read('MANIFEST.json'));assert len(manifest)==12
 assert set(z.namelist())==set(manifest)|{'MANIFEST.json'}
 for n,h in manifest.items():
  target=(root/n).resolve();assert target.is_relative_to(root) and not target.is_symlink()
  content=z.read(n);assert hashlib.sha256(content).hexdigest()==h,n
  if target.exists():assert target.read_bytes()==content,'Existing source differs: '+n
  else:new.append(n)
 for n in new:
  target=root/n;target.parent.mkdir(parents=True,exist_ok=True)
  with target.open('xb') as f:f.write(z.read(n))
receipt={'received_at':datetime.datetime.now().astimezone().isoformat(),'package_sha256':expected,'verified':len(manifest),'created':new,'overwrites':0}
with (root/'results/prospective_four_arm_v2_sync_receipt.json').open('x') as f:json.dump(receipt,f,indent=2)
print(json.dumps(receipt))
