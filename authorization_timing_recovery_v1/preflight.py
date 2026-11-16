"""One CPU allocation hashes weights and prepares a provenance-bound cache copy."""
import ast
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import pprint
import resource
import shutil
import signal
import time
from .common import (ROOT, BUNDLE, OLD, CACHE_REL, FACTOR_SHA, GRAPH_SHA,
                     read, write_once, filehash, identity, sha_stream, verify_inputs)


def copy_cache(source, destination, deadline):
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise FileExistsError('Cache copy is single-use')
    backbone = source/CACHE_REL
    if filehash(backbone/'cache_key_factors.json') != FACTOR_SHA or filehash(backbone/'computation_graph.py') != GRAPH_SHA:
        raise ValueError('Source cache incompatible with prior attempted runtime')
    raw_map = ast.literal_eval((backbone/'vllm_compile_cache.py').read_text())
    if len(raw_map) != 65:
        raise ValueError('Expected 65 completed compiled subgraphs')
    before, changed = {}, {}
    for path in sorted(source.rglob('*')):
        if path.is_symlink():
            raise ValueError('Cache symlink requires separate review')
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        if not relative.parts or relative.parts[0] not in {'vllm','triton'}:
            continue
        if time.monotonic() > deadline:
            raise TimeoutError('Cache copy deadline')
        target = destination/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        original = identity(path)
        h = sha_stream(path,deadline)
        shutil.copy2(path,target)
        if sha_stream(target,deadline) != h or identity(path) != original:
            raise ValueError('Cache changed during copy')
        before[str(relative)] = {'source_identity':original,'sha256':h}
    rewritten = {}
    for key, handle in raw_map.items():
        if not (isinstance(key,tuple) and len(key)==3 and key[0]==(1,16384) and key[2]=='inductor_standalone'):
            raise ValueError('Unexpected cache map key')
        name, absolute = handle
        if Path(absolute) != backbone/name or '/' in name or not name.startswith('artifact_compile_range_1_16384_subgraph_'):
            raise ValueError('Cache handle outside verified source')
        if str(CACHE_REL/name) not in before:
            raise ValueError('Missing artifact')
        rewritten[key] = (name,str(destination/CACHE_REL/name))
    mapping = destination/CACHE_REL/'vllm_compile_cache.py'
    mapping.write_text(pprint.pformat(rewritten,sort_dicts=True)+'\n')
    changed[str(mapping.relative_to(destination))] = {'source_sha256':before[str(mapping.relative_to(destination))]['sha256'],
                                                     'new_sha256':filehash(mapping), 'reason':'absolute handles relocated to verified copy; artifacts unchanged'}
    files={str(p.relative_to(destination)):{'sha256':sha_stream(p,deadline),'identity':identity(p)} for p in sorted(destination.rglob('*')) if p.is_file()}
    return {'files':files,'source_files':before,'relocated':changed,'compiled_subgraphs':len(rewritten)}


def main():
    start=time.monotonic()
    def expired(*_): raise TimeoutError('CPU preflight hard deadline')
    signal.signal(signal.SIGALRM,expired);signal.alarm(820)
    resource.setrlimit(resource.RLIMIT_AS,(16*1024**3,16*1024**3))
    a,cfg,rows,seal=verify_inputs()
    if os.environ.get('SLURM_JOB_ACCOUNT')!='cpsc4880' or not os.environ.get('SLURM_JOB_ID'):
        raise PermissionError('CPU preflight requires course CPU allocation')
    write_once(BUNDLE/'cluster/cpu_preflight_claim.json',{'manifest_sha256':seal,'job_id':os.environ['SLURM_JOB_ID'],'started_at_epoch':time.time()})
    deadline=start+810
    snapshot=Path(cfg['qwen']['snapshot'])
    inventory=read(OLD/'qwen_assets.json')
    def check_asset(item):
        name,expected=item
        if '/' in name or '..' in name:raise ValueError('Unsafe asset name')
        path=snapshot/name; before=identity(path)
        if before['bytes']!=expected['bytes'] or sha_stream(path,deadline)!=expected['sha256'] or identity(path)!=before:
            raise ValueError('Model asset mismatch: '+name)
        print('verified_asset '+name,flush=True)
        return name,{'sha256':expected['sha256'],'identity':before}
    with ThreadPoolExecutor(max_workers=4) as pool:
        assets=dict(pool.map(check_asset,inventory['files'].items()))
    cache=copy_cache(a['source_runtime_cache'],ROOT/'runtime_cache',deadline)
    # The pinned container was already checked at admission; full token equality
    # and schema compilation remain checked before Qwen readiness/dispatch.
    result={'passed':True,'manifest_sha256':seal,'job_id':os.environ['SLURM_JOB_ID'],
            'assets':assets,'cache_files':cache['files'],'source_cache_files':cache['source_files'],
            'cache_relocations':cache['relocated'],'compiled_subgraphs':cache['compiled_subgraphs'],
            'cpu_wall_seconds':time.monotonic()-start,'finished_at_epoch':time.time(),
            'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'model_calls':0,'simulator_calls':0,'gpu_allocations':0,'workers':4}
    write_once(BUNDLE/'cluster/cpu_preflight.json',result)
    signal.alarm(0)
    print(json.dumps({k:v for k,v in result.items() if k not in {'assets','cache_files','source_cache_files','cache_relocations'}}),flush=True)


if __name__=='__main__':main()
