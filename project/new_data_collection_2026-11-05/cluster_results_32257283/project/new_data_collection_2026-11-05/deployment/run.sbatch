#!/bin/bash
#SBATCH --job-name=newdata_actor48
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
cd /nfs/roberts/project/cpsc4880/cpsc4880_rz377/new_data_20261105_v1
mkdir native_attempt
bash project/new_data_collection_2026-11-05/deployment/cluster_python.sh -m prospective_collection_v1.runner
