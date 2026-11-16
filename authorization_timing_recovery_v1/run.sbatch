#!/bin/bash
#SBATCH --job-name=timing_recover_gpu
#SBATCH --account=cpsc4880
#SBATCH --partition=gpu_h200
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus=h200:1
#SBATCH --cpus-per-task=6
#SBATCH --mem=160G
#SBATCH --time=00:09:00
#SBATCH --no-requeue
#SBATCH --output=logs/timing_gpu_%j.log
set -euo pipefail
export TIMING_ALLOCATION_START=$(date +%s)
mkdir gpu_allocation_once
bash authorization_timing_recovery_v1/cluster_python.sh
