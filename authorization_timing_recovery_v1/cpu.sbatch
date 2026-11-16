#!/bin/bash
#SBATCH --job-name=timing_recover_cpu
#SBATCH --account=cpsc4880
#SBATCH --partition=day
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:14:00
#SBATCH --no-requeue
#SBATCH --output=logs/timing_cpu_%j.log
set -euo pipefail
mkdir cpu_allocation_once
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python3 -B -m authorization_timing_recovery_v1.preflight
