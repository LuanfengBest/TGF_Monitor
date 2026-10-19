"""Five prelisted development attempts, then one frozen B1 configuration."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from ollama_client import Ollama, save

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    output = a.output.resolve()
    if output.exists():
        raise ValueError('Pilot attempt directory already exists')
    plan = json.loads((ROOT/'configs/bank_pilot_v2_plan.json').read_text())
    assert len(plan['attempts']) == plan['max_new_actor_attempts'] == 5
    output.mkdir(parents=True)
    save(output/'plan.json', plan)
    save(output/'source_hashes.json', {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
        for f in (ROOT/'scripts').glob('*.py') if not f.name.startswith('.')})
    client = Ollama(output/'identity')
    expected = json.loads((ROOT/'configs/backend_verified_2026-10-12.json').read_text())['models']
    tags = {m['name']:m['digest'] for m in client.api('tags')['models']}
    for name, detail in expected.items():
        assert tags.get(name) == detail['digest'], f'Model digest changed: {name}'
    rows = []
    def execute(command, log, timeout=360):
        start = time.monotonic()
        with log.open('w') as stream:
            try:
                result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
                return {'exit_code':result.returncode,'wall_seconds':time.monotonic()-start}
            except subprocess.TimeoutExpired:
                return {'exit_code':None,'status':'subprocess_timeout','wall_seconds':time.monotonic()-start}
    for item in plan['attempts']:
        name = item['trace_id']
        row = {**item, 'actor_output':str(output/'actors'/name)}
        row['actor_process'] = execute([sys.executable,str(ROOT/'scripts/run_bank_actor.py'),
            '--condition',item['condition'],'--config',str(ROOT/f'configs/{name}.json'),
            '--output',row['actor_output']],output/f'{name}_actor.log')
        summary = Path(row['actor_output'])/'summary.json'
        row['actor_status'] = json.loads(summary.read_text())['status'] if summary.exists() else 'incomplete'
        rows.append(row)
        save(output/'attempts.json', rows)
        print(json.dumps(row),flush=True)
        client.unload('gpt-oss:20b')
    for row in rows:
        name = row['trace_id']
        view = Path(row['actor_output'])/'monitor_view.json'
        if not view.exists() or not json.loads(view.read_text())['messages']:
            row['monitor_status'] = 'no_observable_trace'
        else:
            row['monitor_output'] = str(output/'b1'/name)
            row['monitor_process'] = execute([sys.executable,str(ROOT/'scripts/run_b1.py'),
                '--view',str(view),'--config',str(ROOT/plan['monitor_configuration']),
                '--output',row['monitor_output']],output/f'{name}_monitor.log')
            score = Path(row['monitor_output'])/'result.json'
            row['monitor_status'] = 'scored' if score.exists() else 'failed'
        save(output/'attempts.json', rows)
        print(json.dumps(row),flush=True)
        client.unload('qwen3:32b')
    print('PILOT_FINISHED',flush=True)


if __name__ == '__main__':
    main()
