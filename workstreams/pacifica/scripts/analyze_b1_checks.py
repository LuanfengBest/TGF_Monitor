"""Verify frozen diagnostic inputs and summarize all attempted calls offline."""
import argparse
import hashlib
import json
from pathlib import Path
from ollama_client import save
from run_b1 import parse_judge

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text())


def analyze(run):
    execution = read(run/'execution_plan.json')
    attempts = read(run/'attempts.json')
    table = []
    cost = {'attempted_calls': 0, 'responses': 0, 'valid_scores': 0,
            'prompt_tokens': 0, 'completion_tokens': 0, 'wall_seconds': 0,
            'missing_usage_calls': 0, 'api_charge_usd': None, 'gpu_charge_usd': None}
    checks = []
    for planned in execution['requests']:
        name = planned['condition']+'__'+planned['case_id']
        folder = run/name
        if not (folder/'request.json').exists():
            table.append({**planned, 'status': 'not_called'})
            continue
        cost['attempted_calls'] += 1
        original = ROOT/planned['request_file']
        if hashlib.sha256(original.read_bytes()).hexdigest() != planned['request_sha256']:
            raise ValueError('Local prepared request changed: '+name)
        if read(folder/'request.json') != read(original):
            raise ValueError('Runtime payload differs from frozen request: '+name)
        row = {**planned, 'status': 'failed', 'request_matches_frozen': True}
        checks.append({'name': name, 'request_matches_frozen': True})
        if (folder/'response.json').exists():
            response = read(folder/'response.json')
            cost['responses'] += 1
            usage = read(folder/'usage.json')
            for dest, source in [('prompt_tokens','prompt_eval_count'),
                                 ('completion_tokens','eval_count'),('wall_seconds','wall_seconds')]:
                if source not in usage:
                    raise ValueError('Missing measured usage: '+name+' '+source)
                cost[dest] += usage[source]
            try:
                parsed = parse_judge(response)
                if parsed != read(folder/'result.json'):
                    raise ValueError('Saved parsed result differs from raw response')
                row.update(status='scored', **parsed)
                cost['valid_scores'] += 1
            except (ValueError, KeyError, FileNotFoundError) as exc:
                row['error'] = repr(exc)
        else:
            cost['missing_usage_calls'] += 1
        if (folder/'error.json').exists():
            row['error_record'] = read(folder/'error.json')
        table.append(row)
    summary = read(run/'summary.json')
    assert cost['attempted_calls'] == summary['model_calls_attempted']
    assert cost['valid_scores'] == summary['valid_scores']
    report = {'job_id': execution['job_id'], 'scope': 'Development diagnostics only; no threshold calibration or held-out metric',
              'input_checks': checks, 'cost': cost, 'rows': table, 'attempt_records': attempts}
    save(run/'offline_analysis.json', report)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    a = p.parse_args()
    result = analyze(a.run)
    print(json.dumps({'cost': result['cost'], 'rows': [
        {k: r[k] for k in ['case_id','condition','status','score','summary'] if k in r}
        for r in result['rows']]}, ensure_ascii=False, indent=2))
