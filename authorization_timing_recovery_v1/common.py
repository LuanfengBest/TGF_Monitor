"""Shared immutable-input, aggregate-budget and asset-identity checks."""
import hashlib
import json
from pathlib import Path
import time
from jev_monitor_v1.run import read, write_once, filehash
from authorization_timing_jev_v2.run import planned, ensure_smoke

ROOT = Path(__file__).resolve().parents[1]
REL = Path('project/authorization_timing_jev_2026-11-12/recovery_01')
BUNDLE = ROOT / REL
OLD = ROOT / 'project/authorization_timing_jev_2026-11-12/run_01'
OLD_SEAL = '5be987887c181dbab8e9b5fb0d48f2fc83efaf237ed1708ff63bacd808154c35'
FACTOR_SHA = '6b996b654e8a1c514734a54cf66f5bc1e4ad87d82173c463a7a042785a996b46'
GRAPH_SHA = 'b5eacc68e11bff78c61e07daa13f2a42ba4b6d664286b77b60fe6346634cfd27'
CACHE_REL = Path('vllm/torch_compile_cache/6a75c27718/rank_0_0/backbone')


def identity(path):
    path = Path(path)
    stat = path.stat()
    return {'resolved_path': str(path.resolve()), 'inode': stat.st_ino,
            'bytes': stat.st_size, 'mtime_ns': stat.st_mtime_ns, 'ctime_ns': stat.st_ctime_ns}


def check_identity(path, expected):
    if identity(path) != expected:
        raise ValueError('Asset identity changed: ' + str(path))


def check_fresh(receipt, now=None):
    age = (time.time() if now is None else now) - receipt['finished_at_epoch']
    if age < -60 or age > 7200:
        raise ValueError('CPU preflight older than two hours or clock mismatch')


def sha_stream(path, deadline=None):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        while chunk := f.read(8 * 1024**2):
            if deadline is not None and time.monotonic() > deadline:
                raise TimeoutError('CPU preflight deadline')
            h.update(chunk)
    return h.hexdigest()


def validate_amendment(a):
    if a.get('execution_authorized') is not True:
        raise PermissionError('Recovery not authorized')
    if a['original_manifest_sha256'] != OLD_SEAL:
        raise ValueError('Wrong original experiment')
    if a['prior_gpu_seconds'] != 1237 or a['second_gpu_wall_seconds'] != 540:
        raise ValueError('GPU accounting changed')
    if a['prior_gpu_seconds'] + a['second_gpu_wall_seconds'] > 1800:
        raise ValueError('Aggregate GPU budget exceeded')
    if a['max_total_gpu_allocations'] != 2 or a['max_additional_gpu_allocations'] != 1:
        raise ValueError('Allocation-count amendment exceeded')
    if a['cpu_preflight_wall_seconds'] != 840 or a['prior_cpu_preparation_seconds'] + 840 > 900:
        raise ValueError('CPU preparation budget exceeded')
    expected = {'all_attempts':72, 'jev_attempts':36, 'qwen_attempts':36,
                'formal_attempts':64, 'simulator_bookings':16, 'jev_usd':.1,
                'qwen_output_tokens':18432, 'retries':0}
    if a['aggregate_caps'] != expected:
        raise ValueError('Scientific/call/API cap changed')


def verify_inputs():
    seal = filehash(BUNDLE / 'manifest.json')
    for name, expected in read(BUNDLE / 'manifest.json')['files'].items():
        if filehash(ROOT / name) != expected:
            raise ValueError('Frozen continuation input changed: ' + name)
    a = read(BUNDLE / 'AMENDMENT.json')
    validate_amendment(a)
    if filehash(OLD / 'manifest.json') != OLD_SEAL:
        raise ValueError('Original manifest changed')
    omitted = 'project/authorization_timing_jev_2026-11-12/run_01/LOCAL_READINESS.json'
    for name, expected in read(OLD / 'manifest.json')['files'].items():
        if name == omitted and not (ROOT/name).exists():
            continue
        if filehash(ROOT/name) != expected:
            raise ValueError('Original frozen file changed: ' + name)
    stop = read(OLD / 'results/STOP.json')
    if stop['error_type'] != 'NativeTimeout' or stop['completed_slots'] != 0:
        raise ValueError('Unexpected original failure')
    old_attempts = [read(p) for p in (OLD/'results').glob('*/dispatch.json')]
    if len(old_attempts) != 4 or any(d['model'] != 'jev' or d['phase'] != 'smoke' for d in old_attempts):
        raise ValueError('Original attempt ledger changed')
    ensure_smoke(OLD, 'jev', OLD_SEAL)
    rows = planned(OLD)
    return a, read(OLD/'config.json'), rows, seal


def attempts_and_admit(rows, active, seal):
    by_id = {r['request_id']: r for r in rows}
    attempts = []
    for folder, expected_seal in [(OLD/'results', OLD_SEAL),(BUNDLE/'results',seal)]:
        for path in folder.glob('*/dispatch.json'):
            d = read(path)
            if d['manifest_sha256'] != expected_seal or d['request_id'] not in by_id:
                raise ValueError('Foreign attempt')
            attempts.append(d)
    ids = [d['request_id'] for d in attempts]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate request across runs')
    if set(ids) & {r['request_id'] for r in active}:
        raise RuntimeError('Previously dispatched slot; no retry')
    return attempts


def verify_preflight(seal):
    receipt = read(BUNDLE/'cluster/cpu_preflight.json')
    claim = read(BUNDLE/'cluster/gpu_submission_claim.json')
    if receipt['manifest_sha256'] != seal or claim['manifest_sha256'] != seal:
        raise ValueError('CPU/GPU receipt has wrong manifest')
    if filehash(BUNDLE/'cluster/cpu_preflight.json') != claim['cpu_preflight_sha256']:
        raise ValueError('CPU preflight receipt changed')
    check_fresh(receipt)
    for item in receipt['assets'].values():
        check_identity(item['identity']['resolved_path'], item['identity'])
    for relative, item in receipt['cache_files'].items():
        check_identity(ROOT/'runtime_cache'/relative, item['identity'])
    if receipt['cpu_wall_seconds'] > 820 or receipt['passed'] is not True:
        raise ValueError('CPU preflight did not pass within its limit')
    return receipt
