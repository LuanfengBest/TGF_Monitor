"""Read-only verification of existing results. No networking or model execution.

Uses the exact frozen validator and analysis functions via AST extraction so the
GPU runtime and simulator modules are never imported. Requires jsonschema.
"""
import ast
from collections import Counter, defaultdict
from pathlib import Path
import hashlib
import json
import jsonschema  # Fail explicitly if the one external dependency is absent.

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'validation'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
manifest=read(OUT/'manifest.json')
checked={}
for group,base in [('files',ROOT),('local_reference_files',OUT),('preparation_code',ROOT),('simulator_provenance',OUT)]:
    for name,digest in manifest[group].items():
        path=base/name
        assert path.is_file() and sha(path)==digest,(group,name)
    checked[group]=len(manifest[group])
assert sha(OUT/'manifest.json')=='d84d8f9f94a3b2fced77ee2f96385bdaf5e173652467c52fd715a45e79cbf5f8'
assert sha(OUT/'closeout_validation_results_32473668.zip')=='fccc44910adb08f98ac7af2d8efe8a02d207c5403c1b2e6fba799e6c38f9670a'
assert (OUT/'analysis_32473668.json').is_file(),'Existing analysis required; this command will not create it.'

def prohibited_write(*args,**kwargs):
    raise RuntimeError('Read-only offline verification may not write analysis or run experiments')

env={'ROOT':ROOT,'OUT':OUT,'read':read,'sha':sha,'write':prohibited_write,'json':json,
     'hashlib':hashlib,'Counter':Counter,'defaultdict':defaultdict,
     'CONDITIONS':('atoms_only','running_total','comparison_only','correct_assertion','incorrect_assertion')}
for filename,names in [('run.py',{'validate_output'}),('analyze.py',{'score_position','summarize','analyze'})]:
    path=ROOT/'closeout_validation_v1'/filename
    tree=ast.parse(path.read_text())
    funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert {n.name for n in funcs}==names
    exec(compile(ast.Module(body=funcs,type_ignores=[]),str(path),'exec'),env)
summary=env['analyze']('32473668')
review_dir=HERE/'ai_blind_review_2026-11-07'
seal=read(review_dir/'seal.json')
assert sha(review_dir/'anonymous_records.html')==seal['input_sha256']
assert sha(review_dir/'review_sealed.json')==seal['output_sha256']
reconciliation=read(review_dir/'reconciliation.json')
assert reconciliation['sealed_review_sha256']==seal['output_sha256']
assert reconciliation['reference_reviews_sha256']==sha(OUT/'reference_reviews_LOCAL_ONLY.json')
analysis=read(OUT/'analysis_32473668.json')
statuses=Counter(r['status'] for r in analysis['positions'])
summary.update({'read_only':True,'model_calls_this_verification':0,'network_calls':0,
                'frozen_hash_groups_verified':checked,'output_status_counts':dict(statuses),
                'correct_valid_labels':sum(r['correct'] for r in analysis['positions']),
                'ai_review_agreement':reconciliation['agreements'],
                'independent_human_review_completed':False})
print(json.dumps(summary,indent=2))
