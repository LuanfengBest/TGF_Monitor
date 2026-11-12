"""Offline failure-injection tests. No models, simulators, network or jobs."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch
from . import common,preflight,cache_guard,run,qwen_native
from authorization_timing_jev_v2.run import admission


def rejects(fn):
    try:fn()
    except (ValueError,RuntimeError,PermissionError,TimeoutError,FileExistsError):return
    raise AssertionError('Expected fail-closed rejection')


def main():
    start=time.monotonic();checks=[]
    a=common.read(common.BUNDLE/'AMENDMENT.json');common.validate_amendment(a)
    for key,value in [('execution_authorized',False),('second_gpu_wall_seconds',600),('max_additional_gpu_allocations',2)]:
        b=deepcopy(a);b[key]=value;rejects(lambda:common.validate_amendment(b))
    checks.append('authorization_and_aggregate_GPU_CPU_caps')
    rejects(lambda:common.check_fresh({'finished_at_epoch':0},now=7201))
    common.check_fresh({'finished_at_epoch':1},now=7200)
    checks.append('expired_CPU_receipt_rejected')
    cfg=common.read(common.OLD/'config.json');rows=common.planned(common.OLD)
    for model in ['jev','qwen']:
        admission(cfg,[{'model':model}]*35,model)
        rejects(lambda:admission(cfg,[{'model':model}]*36,model))
    checks.append('original_request_and_API_caps_retained')
    with tempfile.TemporaryDirectory() as d:
        root=Path(d);source=root/'source';dest=root/'runtime_cache';backbone=source/common.CACHE_REL;backbone.mkdir(parents=True)
        (backbone/'cache_key_factors.json').write_text('{}')
        (backbone/'computation_graph.py').write_text('# synthetic fixture\n')
        mapping={}
        for i in range(65):
            name=f'artifact_compile_range_1_16384_subgraph_{i}'
            (backbone/name).write_text('synthetic compiled artifact '+str(i))
            mapping[((1,16384),i,'inductor_standalone')]=(name,str(backbone/name))
        (backbone/'vllm_compile_cache.py').write_text(repr(mapping))
        factor=common.filehash(backbone/'cache_key_factors.json');graph=common.filehash(backbone/'computation_graph.py')
        before={p.name:common.filehash(p) for p in backbone.iterdir()}
        with patch.object(preflight,'FACTOR_SHA',factor),patch.object(preflight,'GRAPH_SHA',graph):
            copied=preflight.copy_cache(source,dest,time.monotonic()+30)
            rejects(lambda:preflight.copy_cache(source,dest,time.monotonic()+30))
        assert before=={p.name:common.filehash(p) for p in backbone.iterdir()}
        assert copied['compiled_subgraphs']==65 and len(copied['relocated'])==1
        modified=dest/common.CACHE_REL/'artifact_compile_range_1_16384_subgraph_0'
        old_identity=common.identity(modified);modified.write_text('changed')
        rejects(lambda:common.check_identity(modified,old_identity))
        checks.extend(['cache_copy_keeps_source_unchanged','all_65_handles_relocated','changed_asset_identity_rejected','cache_copy_cannot_repeat'])
        class FakeManager:
            def load(self,*args):return self.result
        FakeManager.cache_dir=str(dest/common.CACHE_REL)
        FakeManager.result=object()
        with patch.object(cache_guard,'ROOT',root),patch.object(cache_guard,'BUNDLE',root/'receipt'),patch.object(cache_guard,'FACTOR_SHA',factor):
            cache_guard.install(FakeManager); manager=FakeManager()
            assert manager.load(None,None,0,SimpleNamespace(start=1,end=16384)) is manager.result
            manager.result=None
            rejects(lambda:manager.load(None,None,0,SimpleNamespace(start=1,end=16384)))
            manager.result=object();manager.cache_dir=str(source/common.CACHE_REL)
            rejects(lambda:manager.load(None,None,0,SimpleNamespace(start=1,end=16384)))
        checks.append('cache_miss_or_key_mismatch_cannot_fall_back_to_compile')
        old=root/'old';new=root/'new';(old/'results').mkdir(parents=True);(new/'results').mkdir(parents=True)
        rid=rows[0]['request_id'];slot=old/'results'/rid;slot.mkdir()
        common.write_once(slot/'dispatch.json',{'manifest_sha256':common.OLD_SEAL,'request_id':rid})
        with patch.object(common,'OLD',old),patch.object(common,'BUNDLE',new):
            rejects(lambda:common.attempts_and_admit(rows,[rows[0]],'recovery-seal'))
            copied_slot=new/'results'/rid;copied_slot.mkdir()
            common.write_once(copied_slot/'dispatch.json',{'manifest_sha256':'recovery-seal','request_id':rid})
            rejects(lambda:common.attempts_and_admit(rows,[],'recovery-seal'))
        checks.append('cross_run_duplicate_and_prior_dispatch_rejected')
    # A failed native startup must persist STOP before any request dispatch.
    with tempfile.TemporaryDirectory() as d:
        b=Path(d);(b/'results').mkdir()
        with patch.object(run,'BUNDLE',b),patch.object(run,'verify_inputs',return_value=(a,cfg,rows,'offline-seal')),patch.object(run,'ensure_smoke'),patch.object(run,'attempts_and_admit',return_value=[]),patch.object(qwen_native,'start_backend',side_effect=TimeoutError('synthetic startup timeout')) as start_backend,patch.dict(os.environ,{'SLURM_JOB_ID':'offline-fixture','SLURM_JOB_ACCOUNT':'cpsc4880','TIMING_ALLOCATION_START':str(time.time())}):
            try:run.run('qwen',None)
            except SystemExit as e:assert e.code==1
            assert common.read(b/'results/STOP.json')['completed_slots']==0
            assert not list((b/'results').glob('*/dispatch.json'))
            rejects(lambda:run.run('qwen',None))
            assert start_backend.call_count==1
        checks.append('startup_timeout_zero_dispatch_and_no_restart')
    # Jev continuation consumes original smoke ledger and never tries to recreate it.
    with tempfile.TemporaryDirectory() as d:
        b=Path(d);(b/'results').mkdir();key=b/'offline_key';key.write_text('offline-placeholder');key.chmod(0o600)
        common.write_once(b/'results/qwen_all_finished.json',{'completed_slots':36})
        with patch.object(run,'BUNDLE',b),patch.object(run,'verify_inputs',return_value=(a,cfg,rows,'offline-seal')),patch.object(run,'ensure_smoke'),patch.object(run,'attempts_and_admit',return_value=[{'model':'jev'}]*4+[{'model':'qwen'}]*36),patch.object(run,'http_jev',return_value={'http_status':429,'body':None}) as http:
            try:run.run('jev',key)
            except SystemExit as e:assert e.code==1
            assert http.call_count==1 and len(list((b/'results').glob('*/dispatch.json')))==1
            rejects(lambda:run.run('jev',key));assert http.call_count==1
        checks.append('Jev_formal_uses_prior_smoke_and_first_HTTP_failure_stops')
    # Exercise sitecustomize in a fresh interpreter against a fake vLLM module.
    with tempfile.TemporaryDirectory() as d:
        fake=Path(d);module=fake/'vllm/compilation';module.mkdir(parents=True)
        (fake/'vllm/__init__.py').write_text('');(module/'__init__.py').write_text('')
        (module/'backends.py').write_text('class CompilerManager:\n def load(self,*args): return None\n')
        env=dict(os.environ,PYTHONPATH=os.pathsep.join([str(common.ROOT/'authorization_timing_recovery_v1/guard_bootstrap'),str(fake),str(common.ROOT)]),TIMING_REQUIRE_WARM_CACHE='1')
        subprocess.run([sys.executable,'-B','-c','from vllm.compilation.backends import CompilerManager; assert CompilerManager._timing_warm_only'],env=env,check=True,capture_output=True)
    checks.append('lazy_import_guard_installs_in_fresh_process')
    receipt={'passed':True,'checks':checks,'model_calls':0,'simulator_calls':0,'new_GPU_allocations':0,'fake_HTTP_calls':1,'wall_seconds':time.monotonic()-start}
    common.write_once(common.BUNDLE/'OFFLINE_CHECKS.json',receipt)
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
