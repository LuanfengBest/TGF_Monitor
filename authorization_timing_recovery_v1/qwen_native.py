"""Same inference backend; CPU-bound asset receipt and mandatory warm cache."""
import hashlib
import json
import os
import time
from prospective_monitoring import native_backend as native
from jev_monitor_v1 import core
from authorization_timing_jev_v2 import protocol
from authorization_timing_jev_v2.qwen_native import worker
from .common import BUNDLE, OLD, read, filehash, verify_preflight


def start_backend(cfg, rows, seal, timeout):
    begin=time.monotonic()
    receipt=verify_preflight(seal)
    if os.environ.get('TIMING_REQUIRE_WARM_CACHE')!='1':
        raise PermissionError('Warm-cache import guard not enabled')
    runtime=native.runtime_check(cfg['qwen'])
    path=native.snapshot_check(cfg['qwen']['snapshot'],'monitor')
    codec=native.NativeCodec('monitor',path)
    import xgrammar
    compiler=xgrammar.GrammarCompiler(xgrammar.TokenizerInfo.from_huggingface(codec.tokenizer))
    compiler.compile_json_schema(core.schema())
    capacity={}
    hashes={r['request_id']:r['prompt_sha256'] for r in read(OLD/'capacity_LOCAL.json')['requests']}
    for row in rows:
        if row['model']!='qwen':continue
        ids=codec.monitor_prompt(protocol.qwen_prompt(row['state']))
        h=hashlib.sha256(native.canonical(ids).encode()).hexdigest()
        if h!=hashes[row['request_id']] or len(ids)>30000 or len(ids)+512>32768:
            raise ValueError('Pinned token sequence/context differs')
        capacity[row['request_id']]={'prompt_tokens':len(ids),'reserved_output_tokens':512,'prompt_sha256':h}
    remaining=min(350,timeout)-(time.monotonic()-begin)
    if remaining<=0:raise TimeoutError('Startup allowance exhausted before engine')
    backend=native.ProcessStageBackend('monitor',cfg['qwen'],str(path),permit_live=True,
        startup_timeout_seconds=remaining,_worker_target=worker)
    try:
        backend.start()
        hits=[]
        for p in (BUNDLE/'results').glob('cache_hits_*.jsonl'):
            hits.extend(json.loads(s) for s in p.read_text().splitlines())
        unique={(x['graph_index'],x['range_start'],x['range_end']) for x in hits}
        if unique!={(i,1,16384) for i in range(65)}:
            raise ValueError('Engine ready without all 65 verified compiled subgraphs')
        ready={'runtime':runtime,'model':'Qwen/Qwen3-32B','revision':cfg['qwen']['revisions']['monitor'],
               'capacity':capacity,'seed':17,'temperature':0,'enable_thinking':False,'max_output_tokens':512,
               'startup_seconds':time.monotonic()-begin,'cpu_preflight_sha256':filehash(BUNDLE/'cluster/cpu_preflight.json'),
               'verified_compiled_subgraphs':65,'cold_compile_allowed':False,'job_id':os.environ['SLURM_JOB_ID']}
        return backend,ready
    except BaseException:
        backend.close()
        raise
