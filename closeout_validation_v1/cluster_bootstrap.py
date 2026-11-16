from pathlib import Path
import os
import runpy
import sys

root = Path(__file__).resolve().parents[1]
os.chdir(root)
sys.path.insert(0, str(root))
sys.path.insert(0, "/nfs/roberts/project/cpsc4880/cpsc4880_rz377/new_data_20261105_v1/python_dependencies")
if sys.argv[1:] not in (["preflight"], ["campaign"]):
    raise SystemExit("Only frozen evidence-use diagnostic entrypoints allowed")
sys.argv = ["closeout_validation_v1.run", sys.argv[1]]
runpy.run_module("closeout_validation_v1.run", run_name="__main__", alter_sys=True)
