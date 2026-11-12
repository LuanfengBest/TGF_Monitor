"""Local macOS CPU guard; no model/simulator imports in the supervising process."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def main():
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", TOKENIZERS_PARALLELISM="false")
    start, peak_kib = time.monotonic(), 0
    child = subprocess.Popen([sys.executable, "-m", "authorization_timing_jev_v2.prepare", "materialize"], env=env, start_new_session=True)
    stopped = None
    while child.poll() is None:
        result = subprocess.run(["ps", "-o", "rss=", "-p", str(child.pid)], capture_output=True, text=True)
        rss = int(result.stdout.strip() or 0)
        peak_kib = max(peak_kib, rss)
        if rss > 16*1024**2 or time.monotonic()-start > 900:
            stopped = "CPU preparation memory/wall cap"
            os.killpg(child.pid, signal.SIGKILL)
            break
        time.sleep(.1)
    code = child.wait()
    target = Path("project/authorization_timing_jev_2026-11-12/run_01/cpu_supervisor.json")
    with target.open("x") as f:
        json.dump({"exit_code": code, "peak_sampled_rss_kib": peak_kib, "elapsed_seconds": time.monotonic()-start,
                   "poll_interval_seconds": .1, "memory_cap_gib": 16, "wall_cap_seconds": 900, "stop": stopped}, f)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
