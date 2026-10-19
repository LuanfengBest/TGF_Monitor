#!/bin/bash
#SBATCH --job-name=tony_tgf_runtime_v2
#SBATCH --account=cpsc4710
#SBATCH --partition=education
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=tony_runtime_v2_%j.log

# CPU only. Keep a completed image even if its Python/dependency check fails.
set -euo pipefail
: "${SLURM_JOB_ID:?Run as a Slurm job, not directly on the login node}"
cd "${SLURM_SUBMIT_DIR:?Submit from the package root}"
[[ -f TONY_SOURCE_LOCK.json && -f run_replay.py ]] || { echo "Wrong submission directory"; exit 2; }
command -v apptainer
apptainer --version
[[ "$(uname -m)" = x86_64 ]] || { echo "This image is pinned for linux/amd64"; exit 2; }

image=containers/vllm_0.13.0_1ae45c63e057.sif
image_source=docker://vllm/vllm-openai@sha256:1ae45c63e0578cf8ea690299c20b6a32a5c3ddf659e92ea15c0ae6b8040ba741
[[ ! -L containers && ! -L "$image" ]] || { echo "Refusing a symlink image/directory"; exit 2; }
mkdir -p containers

if [[ ! -e "$image" ]]; then
    temp_root="$(realpath -e -- "${SLURM_TMPDIR:-/tmp}")"
    local_dir="$(mktemp -d -- "$temp_root/tgf-image-${SLURM_JOB_ID}.XXXXXX")"
    cleanup() {
        local resolved
        resolved="$(realpath -e -- "$local_dir")" || return
        if [[ "$resolved" = "$local_dir" && "$resolved" = "$temp_root"/tgf-image-"$SLURM_JOB_ID".* && ! -L "$local_dir" ]]; then
            rm -rf -- "$resolved"
            echo "Removed only this job's temporary cache; project images are not removed."
        fi
    }
    trap cleanup EXIT
    local_kib="$(df -Pk "$local_dir" | awk 'NR == 2 {print $4}')"
    project_kib="$(df -Pk . | awk 'NR == 2 {print $4}')"
    [[ "$local_kib" =~ ^[0-9]+$ && "$project_kib" =~ ^[0-9]+$ ]] || { echo "Cannot determine free space"; exit 2; }
    (( local_kib >= 80 * 1024 * 1024 && project_kib >= 40 * 1024 * 1024 )) || { echo "Need >=80 GiB temporary and >=40 GiB project headroom"; exit 2; }
    export APPTAINER_TMPDIR="$local_dir/tmp"
    export APPTAINER_CACHEDIR="$local_dir/cache"
    mkdir -p "$APPTAINER_TMPDIR" "$APPTAINER_CACHEDIR"
    # Build into a job-specific project file; no copy-before-validation race.
    # If interrupted, leave it visibly incomplete rather than reuse it as final.
    partial="${image}.building-${SLURM_JOB_ID}"
    [[ ! -e "$partial" && ! -L "$partial" ]] || { echo "Partial image already exists; stopping"; exit 2; }
    apptainer build "$partial" "$image_source"
    mv --no-clobber -- "$partial" "$image"
    [[ ! -e "$partial" ]] || { echo "Destination appeared; retained built image at $partial"; exit 2; }
    echo "IMAGE_SAVED: $image (not yet dependency-validated)"
else
    [[ -f "$image" && -s "$image" ]] || { echo "Existing image is not a nonempty regular file"; exit 2; }
    echo "REUSING_IMAGE: checking existing image without rebuilding/overwriting"
fi

echo "SOURCE_REFERENCE: $image_source"
sha256sum "$image"
# The v0.13.0 final Docker stage installs /usr/bin/python3, not a python alias.
# An absolute path also avoids accidentally selecting the host's Python.
apptainer exec --cleanenv "$image" /usr/bin/python3 -I -c 'import json, sys; from importlib.metadata import version; import openai_harmony; versions={n:version(n) for n in ("vllm","torch","transformers","openai-harmony")}; assert versions["vllm"] == "0.13.0", versions; print(json.dumps({"python":sys.version,"executable":sys.executable,"versions":versions,"harmony_import":"ok"}, indent=2))'
echo "RUNTIME_IMAGE_PREPARED: CPU imports/versions only; GPU model execution still unvalidated."
