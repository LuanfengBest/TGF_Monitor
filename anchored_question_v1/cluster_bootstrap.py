"""Use the existing pinned container and dependency directory for replay only."""
from pathlib import Path
import os
import runpy
import sys

root = Path(__file__).resolve().parents[1]
os.chdir(root)
sys.path.insert(0, str(root))
sys.path.insert(0, "/nfs/roberts/project/cpsc4880/cpsc4880_rz377/new_data_20261105_v1/python_dependencies")
if len(sys.argv) < 3 or sys.argv[1] != "-m" or sys.argv[2] not in {"anchored_question_v1.preflight", "anchored_question_v1.campaign"}:
    raise SystemExit("Only admitted airline preflight/comparison entrypoints are allowed")
module = sys.argv[2]
sys.argv = sys.argv[2:]
runpy.run_module(module, run_name="__main__", alter_sys=True)
