#!/bin/bash
#SBATCH --job-name=airline_replay24
#SBATCH --account=cpsc4880
#SBATCH --partition=gpu_h200
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus=h200:1
#SBATCH --cpus-per-task=6
#SBATCH --mem=160G
#SBATCH --time=02:00:00
#SBATCH --no-requeue
#SBATCH --output=logs/%x_%j.log
set -euo pipefail
export TGF_ALLOCATION_START=$(date +%s)
cd /nfs/roberts/project/cpsc4880/cpsc4880_rz377/airline_comparison_20261106_v1
mkdir gpu_attempt
bash airline_dev_v1/cluster_python.sh -m airline_dev_v1.campaign \
  --bundle project/airline_monitor_comparison_2026-11-06/bundle \
  --preflight admission/preflight.json --permit permit.json --output comparison
