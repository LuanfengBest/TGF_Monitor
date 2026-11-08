"""Verify the existing vendor image on CPU before executing any code inside it."""
import hashlib
from pathlib import Path
import sys
digest = hashlib.sha256()
with Path(sys.argv[1]).open("rb") as stream:
    for block in iter(lambda: stream.read(8*1024*1024), b""):
        digest.update(block)
if digest.hexdigest() != "d0de33398bb53793eaf2187384cba44bc1219ea004aa679fac11d70b4a75e8b7":
    raise SystemExit("Pinned container mismatch")
print("Existing vendor image hash verified", flush=True)
