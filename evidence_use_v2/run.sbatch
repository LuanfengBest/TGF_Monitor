#!/bin/bash
#SBATCH --job-name=tgf_evidence_claim
#SBATCH --account=cpsc4880
#SBATCH --partition=gpu_h200
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus=h200:1
#SBATCH --cpus-per-task=6
#SBATCH --mem=160G
#SBATCH --time=01:30:00
#SBATCH --no-requeue
#SBATCH --output=logs/%x_%j.log
set -euo pipefail
export TGF_ALLOCATION_START=$(date +%s)
cd /nfs/roberts/project/cpsc4880/cpsc4880_rz377/evidence_claim_20261107_v2
mkdir allocation_once
trap 'python3 evidence_use_v2/export.py' EXIT
image=/nfs/roberts/project/cpsc4880/cpsc4880_rz377/authorization_cpsc4880_20261105_879a8821d635/runtime_assets/vllm_0.13.0.sif
python3 airline_dev_v1/verify_image.py "$image"
bash evidence_use_v2/cluster_python.sh preflight
bash evidence_use_v2/cluster_python.sh campaign
