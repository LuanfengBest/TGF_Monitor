"""Verify the transfer set runs without unbundled workspace dependencies."""
import os,shutil,subprocess,tempfile,sys
from pathlib import Path
from .prepare import source_files
from .common import ROOT,BUNDLE,save

def main():
 with tempfile.TemporaryDirectory(prefix='tgf-mainline-isolation-') as td:
  target=Path(td)
  for f in source_files():
   d=target/f.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,d)
  code='''from pathlib import Path
import tempfile
from tgf_jev_mainline_v1.common import BUNDLE,read
from tgf_jev_mainline_v1 import specs
from tgf_jev_mainline_v1.actor_stage import audit
from prospective_data_v2.fixtures import WitnessActor,prepare_environment
from prospective_monitoring.collection import collect_case
m=read(BUNDLE/'tasks_PRIVATE.json')
for inst in m['instances'][:6]:
 for kind in ('legal','violation'):
  task=specs.build_task(inst,'ordinary')
  with tempfile.TemporaryDirectory() as td:
   r=collect_case(task,WitnessActor(inst['witnesses_PRIVATE'][kind]['actions']),Path(td)/'c',specs.CASE_LIMITS,environment_factory=prepare_environment)
  assert r['status']=='completed',r['stop_reason']
  assert audit(task,r)
print('ISOLATED_12_WITNESSES_PASSED')
'''
  r=subprocess.run([sys.executable,'-c',code],cwd=target,env=dict(os.environ,PYTHONPATH=str(target)),capture_output=True,text=True,timeout=90)
  print(r.stdout);print(r.stderr[-2000:]);assert r.returncode==0
  save(BUNDLE/'ISOLATION_CHECK.json',{'passed':True,'copied_files':len(source_files()),'simulator_witnesses':12,'model_calls':0,'stdout':r.stdout})
if __name__=='__main__':main()
