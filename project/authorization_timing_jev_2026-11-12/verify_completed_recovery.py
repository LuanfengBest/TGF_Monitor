"""No-network verification of the saved continuation and original run archives."""
import ast
import json
import math
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(HERE))


def same(a,b):
    if isinstance(a,dict):
        assert isinstance(b,dict) and set(a)==set(b)
        for k in a:same(a[k],b[k])
    elif isinstance(a,list):
        assert isinstance(b,list) and len(a)==len(b)
        for x,y in zip(a,b):same(x,y)
    elif isinstance(a,float):assert math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-8),(a,b)
    else:assert a==b,(a,b)


def main():
    from analyze_saved_recovery import analyze,details
    analysis,outcome=analyze()
    from authorization_timing_recovery_v1.common import BUNDLE,OLD,read,filehash
    for relative,expected in read(BUNDLE/'RESULT_HASHES.json').items():
        assert filehash(BUNDLE/relative)==expected,relative
    same(analysis,read(BUNDLE/'analysis.json'));same(outcome,read(BUNDLE/'FINAL_OUTCOME.json'))
    same(details(),read(BUNDLE/'DETAILS.json'))
    assert outcome['status']=='completed' and outcome['formal_returned']==64
    # Verify the downloaded export independently of the local result seal.
    prefix='project/authorization_timing_jev_2026-11-12/recovery_01/'
    for relative,expected in read(BUNDLE/'cluster/export_hashes.json').items():
        path=BUNDLE/'cluster'/relative if relative.startswith('logs/') else BUNDLE/relative.removeprefix(prefix)
        assert relative.startswith('logs/') or relative.startswith(prefix)
        assert filehash(path)==expected,relative
    accounting=read(BUNDLE/'cluster/accounting_final.json')
    for kind in ['cpu','gpu']:
        assert accounting[kind]['job_id']==read(BUNDLE/f'cluster/{kind}_submission.json')['job_id']
    ready=read(BUNDLE/'results/qwen_ready.json')
    assert ready['job_id']==accounting['gpu']['job_id']
    assert ready['cpu_preflight_sha256']==filehash(BUNDLE/'cluster/cpu_preflight.json')
    assert ready['cpu_preflight_sha256']==read(BUNDLE/'cluster/gpu_submission_claim.json')['cpu_preflight_sha256']
    # Exact hashes of original archived output files, including the failed run,
    # remain valid. Original 31/480-file inputs retain their original manifests.
    for relative,expected in read(OLD/'RESULT_HASHES.json').items():
        assert filehash(OLD/relative)==expected,relative
    older={}
    for name in ['jev_monitor_2x2_2026-11-11','jev_tgf_mainline_2026-11-12']:
        folder=ROOT/'project'/name
        manifest=next(p for p in [folder/'manifest.json',folder/'freeze.json'] if p.exists())
        x=read(manifest)
        for relative,expected in x['files'].items():assert filehash(ROOT/relative)==expected,relative
        older[name]={'sha256':filehash(manifest),'files':len(x['files'])}
    cpu=read(BUNDLE/'cluster/cpu_preflight.json');assets=read(OLD/'qwen_assets.json')['files']
    assert set(cpu['assets'])==set(assets)
    for name,item in assets.items():assert cpu['assets'][name]['sha256']==item['sha256']
    assert cpu['compiled_subgraphs']==65 and len(cpu['cache_relocations'])==1
    for name,source in cpu['source_cache_files'].items():
        if name not in cpu['cache_relocations']:assert source['sha256']==cpu['cache_files'][name]['sha256']
    for p in (ROOT/'authorization_timing_recovery_v1').rglob('*.py'):ast.parse(p.read_text())
    receipt={'passed':True,'scope':'saved_results_only_no_network_no_subprocess_no_models',
             'new_manifest_sha256':filehash(BUNDLE/'manifest.json'),
             'frozen_continuation_files':len(read(BUNDLE/'manifest.json')['files']),
             'result_files_verified':len(read(BUNDLE/'RESULT_HASHES.json')),
             'all_attempts':outcome['all_dispatched'],'formal_returned':outcome['formal_returned'],
             'aggregate_gpu_seconds':outcome['aggregate_gpu_seconds'],
             'analysis_reproduced':True,'old_manifests':older,'human_reviews':0}
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
