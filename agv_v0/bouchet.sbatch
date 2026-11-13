#!/bin/bash
#SBATCH --job-name=agv-v0
#SBATCH --account=cpsc4880
#SBATCH --partition=day
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=02:00:00
#SBATCH --no-requeue
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?submit from repository root}"
python3 -B -m unittest agv_v0.test_smoke
python3 -B -m agv_v0.run "$@"
