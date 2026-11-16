#!/bin/bash
#SBATCH --job-name=tgf_jev_actor192
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
export TGF_MAINLINE_START=$(date +%s)
mkdir actor_allocation_once
bash tgf_jev_mainline_v1/cluster_python.sh -m tgf_jev_mainline_v1.actor_stage
