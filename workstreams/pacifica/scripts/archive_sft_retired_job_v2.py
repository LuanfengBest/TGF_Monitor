"""Archive a terminal job retired from squeue without changing frozen v2 sources.
Only the exact Invalid job id response may use a fresh user queue query.
The original archiver still independently requires a terminal sacct state.
"""
import hashlib
from pathlib import Path
import runpy
import subprocess
from unittest.mock import patch

ORIGINAL_SHA = '4a78192d717b59aea64934a1eb17ef73b38da88258bf540f897626aaa861d997'


def queue_compatible_check_output(real, args, **kwargs):
    try:
        return real(args, **kwargs)
    except subprocess.CalledProcessError as exc:
        exact_query = (len(args) == 4 and args[:2] == ['squeue', '-j']
                       and args[2].isdigit() and args[3] == '-h')
        if not exact_query:
            raise
        check = subprocess.run(args, text=True, capture_output=True, timeout=20)
        if check.returncode != 1 or check.stdout.strip() or check.stderr.strip() != 'slurm_load_jobs error: Invalid job id specified':
            raise exc
        fresh = real(['squeue', '-u', 'hpcllm_rz377', '-h', '-o', '%i|%T'], text=True, timeout=20)
        matching = [line for line in fresh.splitlines() if line.split('|')[0].strip() == args[2]]
        return '\n'.join(matching)


def main():
    path = Path(__file__).with_name('archive_sft_stage_v2.py')
    assert hashlib.sha256(path.read_bytes()).hexdigest() == ORIGINAL_SHA
    real = subprocess.check_output
    with patch.object(subprocess, 'check_output', side_effect=lambda args, **kw: queue_compatible_check_output(real, args, **kw)):
        runpy.run_path(str(path), run_name='__main__')


if __name__ == '__main__':
    main()
