"""Execute the ten frozen development requests once, without retries or label access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import time

from ollama_client import Ollama, save
from prepare_b1_checks import request
from run_b1 import parse_judge

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_requests(prepared):
    plan = read(prepared / 'plan.json')
    if (plan['maximum_inference_calls'], plan['cases'], plan['automatic_retries']) != (10, 5, 0):
        raise ValueError('Unexpected frozen plan')
    for path, expected in plan['source_hashes'].items():
        if sha(ROOT / path) != expected:
            raise ValueError(f'Frozen source changed: {path}')
    views = sorted((prepared / 'views').glob('*.json'))
    if len(views) != 5 or len(list((prepared / 'prepared_requests').glob('*.json'))) != 10:
        raise ValueError('Expected exactly five cases and ten requests')
    rows = []
    for i, view_path in enumerate(views):
        conditions = plan['conditions'] if i % 2 == 0 else list(reversed(plan['conditions']))
        for condition in conditions:
            path = prepared / 'prepared_requests' / f'{condition}__{view_path.stem}.json'
            payload = read(path)
            if payload != request(read(view_path), plan['fixed'], condition):
                raise ValueError(f'Prepared request differs from frozen construction: {path.name}')
            rows.append({'case_id': view_path.stem, 'condition': condition,
                         'request_file': str(path.relative_to(ROOT)),
                         'request_sha256': sha(path), 'payload': payload})
    return plan, rows


def timeout_handler(signum, frame):
    raise TimeoutError('Diagnostic request exceeded 90 seconds; no retry')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, default=ROOT/'data/diagnostics/b1_checks_v1')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    plan, requests = load_requests(args.prepared.resolve())
    args.output.mkdir(parents=True, exist_ok=False)
    save(args.output/'plan.json', plan)
    save(args.output/'source_hashes.json', {str(p.relative_to(ROOT)): sha(p) for p in
         [ROOT/'scripts/run_b1_checks.py', ROOT/'scripts/ollama_client.py', ROOT/'scripts/run_b1.py',
          ROOT/'scripts/prepare_b1_checks.py', ROOT/'scripts/b1_checks.sbatch']})
    save(args.output/'execution_plan.json', {'job_id': os.environ.get('SLURM_JOB_ID'),
         'maximum_wall_seconds': 780, 'per_request_timeout_seconds': 90, 'automatic_retries': 0,
         'requests': [{k:v for k,v in row.items() if k != 'payload'} for row in requests]})
    client = Ollama(args.output/'transport')
    model = plan['fixed']['monitor']
    expected = read(ROOT/'configs/backend_verified_2026-10-12.json')['models'][model]['digest']
    metadata = client.metadata(model)
    save(args.output/'monitor_metadata.json', metadata)
    if {m['name']:m['digest'] for m in metadata['tags']['models']}.get(model) != expected:
        raise ValueError('Monitor model digest differs from the frozen development model')
    signal.signal(signal.SIGALRM, timeout_handler)
    start = time.monotonic()
    rows = []
    try:
        for item in requests:
            row = {k:v for k,v in item.items() if k != 'payload'}
            case = args.output / f"{item['condition']}__{item['case_id']}"
            if time.monotonic() - start > 680:
                rows.append({**row, 'status': 'not_called_wall_budget'})
                save(args.output/'attempts.json', rows)
                continue
            payload = item['payload']
            save(case/'request.json', payload)
            call_start = time.monotonic()
            response = None
            try:
                signal.alarm(90)
                response = client.api('chat', payload)
                signal.alarm(0)
                save(case/'response.json', response)
                usage = {'model': model, 'wall_seconds': time.monotonic()-call_start,
                         'api_charge_usd': None, **{k:v for k,v in response.items()
                         if k.endswith(('_count', '_duration'))}}
                save(case/'usage.json', usage)
                result = parse_judge(response)
                if any(not isinstance(e, str) for e in result['evidence']):
                    raise ValueError('Non-string evidence in judge output')
                save(case/'result.json', result)
                row.update(status='scored', score=result['score'])
            except Exception as exc:
                row.update(status='failed', error=repr(exc))
                save(case/'error.json', {'error': repr(exc), 'wall_seconds': time.monotonic()-call_start,
                     'response_received': response is not None, 'automatic_retry': False})
            finally:
                signal.alarm(0)
            row['wall_seconds'] = time.monotonic()-call_start
            rows.append(row)
            save(args.output/'attempts.json', rows)
            print(json.dumps(row), flush=True)
            # A timed-out generation may still occupy the backend. Stop, do not queue more work.
            if row['status'] == 'failed' and response is None:
                break
        save(args.output/'summary.json', {'status': 'completed' if len(rows)==10 and
             all(r['status']=='scored' for r in rows) else 'incomplete',
             'model_calls_attempted': sum(r['status']!='not_called_wall_budget' for r in rows),
             'valid_scores': sum(r['status']=='scored' for r in rows),
             'wall_seconds': time.monotonic()-start, 'scope': plan['scope']})
        print('B1_CHECKS_FINISHED', flush=True)
    finally:
        signal.alarm(30)
        try:
            client.unload(model)
        finally:
            signal.alarm(0)


if __name__ == '__main__':
    main()
