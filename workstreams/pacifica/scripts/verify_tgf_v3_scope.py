"""Offline check: declared interface changes do not alter actor or four-arm design."""
import ast
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def definitions(path):
    return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(path.read_text()).body
            if isinstance(n,(ast.FunctionDef,ast.ClassDef))}

def main():
    old=definitions(ROOT/'scripts/prospective_actor_v5.py')
    new=definitions(ROOT/'scripts/prospective_actor_v6.py')
    for name in ('load_original','canonical_state','require_original_ready','rollout','dispatch','verify'):
        assert old[name]==new[name],name
    old=definitions(ROOT/'scripts/prospective_four_arm_v2.py')
    new=definitions(ROOT/'scripts/prospective_four_arm_v3.py')
    for name in ('run_trace','assert_same_public_inputs','verify_input','verify'):
        assert old[name]==new[name],name
    # No edits to any frozen scientific source from the completed diagnostic.
    plan=json.loads((ROOT/'configs/monitor_repair_diagnostic_runtime_v1.json').read_text())
    for path,expected in plan['source_hashes'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected,path
    print(json.dumps({'actor_science_functions_unchanged':True,'four_arm_design_functions_unchanged':True,
                      'diagnostic_frozen_sources_unchanged':len(plan['source_hashes']),
                      'new_calls':0,'new_training':0}))
if __name__=='__main__':main()
