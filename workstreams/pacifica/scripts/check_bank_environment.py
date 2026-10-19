"""Load the official simulated bank and exercise a read-only tool. No LLM calls."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output:
        args.output = args.output.resolve()
    project = Path(__file__).resolve().parents[1]
    repo = project / "third_party" / "MonitorBench"
    agent_dir = repo / "datasets" / "dual_objective" / "agent"
    sys.path.insert(0, str(agent_dir))
    os.chdir(agent_dir)

    from utils.path_utils import set_project_root
    set_project_root(agent_dir)
    from task_pairs.bank_transfer_2.task_definition import TaskDefinition
    from tools.financial_transfer import get_balance

    task = TaskDefinition()
    environment = task.environment
    balance = get_balance(environment.bank_account)
    if not task.user_query.strip() or not environment.available_tools:
        raise RuntimeError("The task or its tool list is empty")
    if not isinstance(balance, (int, float)):
        raise RuntimeError("The simulated get_balance tool returned a non-numeric value")

    result = {
        "check": "bank_environment_initialization_only",
        "status": "passed",
        "environment": "bank_transfer_2",
        "upstream_commit": subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
        ).strip(),
        "python_version": sys.version.split()[0],
        "available_tool_count": len(environment.available_tools),
        "get_balance_returned_number": True,
        "model_calls": 0,
        "actor_rollouts": 0,
        "baseline_scored": False,
        "note": "Only a simulated environment check; not a model or baseline result.",
    }
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
