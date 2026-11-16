#!/bin/bash
#SBATCH --job-name=tgf_jev_preflight
#SBATCH --account=cpsc4880
#SBATCH --partition=day
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --mem=24G
#SBATCH --time=00:30:00
#SBATCH --no-requeue
#SBATCH --output=logs/%x_%j.log
set -euo pipefail
bash tgf_jev_mainline_v1/cluster_python.sh -m tgf_jev_mainline_v1.preflight
