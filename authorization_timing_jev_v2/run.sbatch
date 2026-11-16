#!/bin/bash
#SBATCH --job-name=timing_jev_v02
#SBATCH --account=cpsc4880
#SBATCH --partition=gpu_h200
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus=h200:1
#SBATCH --cpus-per-task=6
#SBATCH --mem=160G
#SBATCH --time=00:30:00
#SBATCH --no-requeue
#SBATCH --output=logs/timing_%j.log
set -euo pipefail
export TIMING_ALLOCATION_START=$(date +%s)
mkdir allocation_once_timing_v02
bash authorization_timing_jev_v2/cluster_python.sh
