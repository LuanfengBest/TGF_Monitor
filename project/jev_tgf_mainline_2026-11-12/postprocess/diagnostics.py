"""Explicitly secondary diagnostics; primary frozen denominators stay unchanged."""
import collections
from supplement import BUNDLE, OUT, read, save, verify, paired, outcome


def main():
    verify()
    assert read(OUT/'jev_summary.json')['complete']
    refs = read(OUT/'reference_manifest_PRIVATE.json')['rows']
    plan = read(OUT/'judge_plan.json')
    result = {'status': 'post-hoc diagnostic, never replaces the frozen primary analysis',
              'complete_answers': {}, 'repeated_inputs': {}, 'unavailable_followups': []}
    for env in ('bank', 'airline'):
        eligible = [r for r in refs if r['eligible'] and r['environment']==env]
        rows = []
        for row in eligible:
            good = True
            for arm in ('F', 'T'):
                slot = OUT/'followups'/f"{row['case_id']}.{arm}"
                response = read(slot/'result.json')
                if response['status']!='valid':
                    good = False
                    raw = read(slot/'raw.json') if (slot/'raw.json').exists() else {}
                    result['unavailable_followups'].append({'case_id': row['case_id'], 'arm': arm,
                        'environment': env, 'reference': row['label'], 'block': row['block'],
                        'finish_reason': raw.get('finish_reason'), 'output_tokens': raw.get('completion_tokens'),
                        'judgments': {m+'.'+a: outcome(m, row['case_id'], a)
                                      for m in ('qwen', 'jev') for a in ('P', 'C', 'F', 'T')}})
            if good:
                rows.append(row)
        result['complete_answers'][env] = {'method': 'Keep eligible cases with valid original F and T Actor answers; no replacement or new inference.',
            'excluded_ids': sorted({r['case_id'] for r in eligible}-{r['case_id'] for r in rows}),
            'labels': dict(collections.Counter(r['label'] for r in rows)), 'analysis': paired(rows)}
    for model in ('qwen', 'jev'):
        groups = collections.defaultdict(list)
        for row in plan:
            if row['status']=='ready':
                groups[row['arm'], row['state_sha256']].append(row)
        repeats = []
        for (arm, state_hash), rows in groups.items():
            if len(rows)<2:
                continue
            values = [outcome(model, r['case_id'], arm) for r in rows]
            repeats.append({'arm': arm, 'state_sha256': state_hash,
                'request_ids': [r['request_id'] for r in rows], 'verdicts': values,
                'all_verdicts_same': len(set(values))==1})
        result['repeated_inputs'][model] = {'method': 'Incidental repeated identical full public inputs in this run. Descriptive only, not a separate stability benchmark.',
            'repeat_groups': len(repeats), 'same_verdict_groups': sum(r['all_verdicts_same'] for r in repeats),
            'repeated_slots': sum(len(r['request_ids']) for r in repeats), 'groups': repeats}
    save(BUNDLE/'DIAGNOSTICS.json', result)
    print({env: {'cases_with_both_answers': data['analysis']['rows'],
        'jev_T_minus_F_G': data['analysis']['contrasts']['jev.T-F']['G'],
        'qwen_T_minus_F_G': data['analysis']['contrasts']['qwen.T-F']['G']}
        for env, data in result['complete_answers'].items()})


if __name__ == '__main__':
    main()
