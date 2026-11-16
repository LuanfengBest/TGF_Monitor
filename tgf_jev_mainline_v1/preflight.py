"""CPU-only asset, native serialization and schema checks."""
import json,time
from importlib.metadata import version
from pathlib import Path
from .common import *
from . import protocol as p
from prospective_monitoring.native_backend import NativeCodec,runtime_check,snapshot_check
from prospective_monitoring.collection import _tool_schemas
from prospective_data_v2.fixtures import prepare_environment
from jev_monitor_v1 import core

def main():
 seal=verify();c=cfg();started=time.monotonic();assets=[]
 expected=read(BUNDLE/'actor_assets.json')
 wanted=[(Path(c['actor_assets'])/r['destination'],r['sha256'],r['bytes']) for r in expected['files']]
 wanted.append((Path(c['image']),expected['image_sha256'],None))
 qi=read(BUNDLE/'qwen_assets.json')
 wanted.extend((Path(c['qwen']['snapshot'])/name,r['sha256'],r['bytes']) for name,r in qi['files'].items())
 for path,h,size in wanted:
  before=path.stat();actual=sha(path);after=path.stat()
  if actual!=h or (size is not None and size!=after.st_size) or before.st_mtime_ns!=after.st_mtime_ns:raise ValueError('Asset mismatch '+str(path))
  assets.append({'path':str(path),'bytes':after.st_size,'mtime_ns':after.st_mtime_ns,'resolved':str(path.resolve()),'sha256':actual})
 print(json.dumps({'hashed_assets':len(assets),'elapsed':time.monotonic()-started}),flush=True)
 runtime=runtime_check(c)
 for package,expected_version in {'pandas':'2.2.3','pytz':'2025.2','tzdata':'2025.2'}.items():
  if version(package)!=expected_version:raise ValueError('Simulator dependency version differs: '+package)
 snapshot_check(c['actor_snapshot'],'actor');snapshot_check(c['qwen']['snapshot'],'monitor')
 ac=NativeCodec('actor',c['actor_snapshot']);qc=NativeCodec('monitor',c['qwen']['snapshot'])
 lengths=[]
 for t in tasks():
  env,rt=prepare_environment(t['scenario']);tools=_tool_schemas(rt,t['allowed_tools'])
  conv=[{'role':'system','content':t['private_system']},{'role':'user','content':t['initial_user_text']}]
  conv.extend({'role':'user','content':m['content']} for m in t['authorization_messages'] if m['effective_from_sequence']==1)
  n=len(ac.actor_prompt(conv,tools));assert n+4096<=131072;lengths.append(n)
 for r in read(BUNDLE/'witness_requests_PRIVATE.json'):
  if r.get('stage')=='actor':
   x=r['content'];n=len(ac.actor_prompt(x['conversation'],[],x['question']))
  else:n=len(ac.actor_prompt(r['conversation'],r['tools']))
  assert n+4096<=131072;lengths.append(n)
 from prospective_monitoring.preflight import check_actor_examples
 examples=[]
 for i,r in enumerate(read(BUNDLE/'witness_requests_PRIVATE.json')):
  x=dict(r['content']) if r.get('stage')=='actor' else dict(r)
  x.update(case_id=str(i),kind='scripted_cpu_serialization',max_output_tokens=4096)
  examples.append(x)
 harmony=check_actor_examples(c['actor_snapshot'],examples,started+1700)
 save(OUT/'harmony_checks.json',harmony)
 import xgrammar
 compiler=xgrammar.GrammarCompiler(xgrammar.TokenizerInfo.from_huggingface(qc.tokenizer));compiler.compile_json_schema(core.schema())
 qlength=[]
 for s in read(BUNDLE/'smoke.json'):
  n=len(qc.monitor_prompt(p.qwen_prompt(s['state'])));assert n+1024<=32768;qlength.append(n)
  compiler.compile_json_schema(p.review_schema(s['state']))
 # Pin current simulator dependency files before any GPU stage.
 for path in sorted(Path(c['dependencies']).rglob('*')):
  if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':
   st=path.stat();assets.append({'path':str(path),'bytes':st.st_size,'mtime_ns':st.st_mtime_ns,'resolved':str(path.resolve()),'sha256':sha(path)})
 save(OUT/'admission.json',{'ready':True,'model_calls':0,'manifest_sha256':seal,'runtime':runtime,'assets':assets,'actor_prompt_checks':len(lengths),'max_actor_prompt_tokens':max(lengths),'qwen_fixture_checks':len(qlength),'max_qwen_fixture_prompt_tokens':max(qlength),'dynamic_prompt_capacity_checked_before_each_dispatch':True,'elapsed_seconds':time.monotonic()-started})
 print(json.dumps({'ready':True,'model_calls':0,'actor_inputs_checked':len(lengths),'qwen_inputs_checked':len(qlength),'elapsed_seconds':time.monotonic()-started}),flush=True)
if __name__=='__main__':main()
