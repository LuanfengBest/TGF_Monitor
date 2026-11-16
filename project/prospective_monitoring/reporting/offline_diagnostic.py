"""Read existing pilot outputs without inference, repairs, or rescoring.

Raw scores are extracted only where a judge actually returned them. A score that
failed the original evidence validator remains invalid. This script never fills
missing calls and never claims that source binding proves semantic entailment.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from prospective_monitoring.protocol import judgment, review, quote_sources, strict_json


def read(path):
    return json.loads(path.read_text())


def hashes(root):
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlinked evidence is not accepted')
        if path.is_file():
            result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def normalized(text):
    return re.sub(r'\s+', '', text)


def diagnose(run, output):
    run, output = run.resolve(), output.resolve()
    if output == run or run in output.parents:
        raise ValueError('Diagnostics must be outside the source run')
    # Validate using the exact protocol saved with this run, not a later repair.
    archived_protocol = run.parents[1] / 'prospective_monitoring/protocol.py'
    active_protocol = REPO / 'prospective_monitoring/protocol.py'
    if archived_protocol.read_bytes() != active_protocol.read_bytes():
        raise ValueError('Protocol differs from the archived campaign')
    original = hashes(run)
    summary = read(run / 'summary.json')
    calls, citations, rows = [], [], []
    for collection in sorted((run / 'collection').glob('c[0-9][0-9][0-9][0-9]')):
        prefix = collection.name
        case = read(collection / 'monitor_case.json')
        private = read(collection / 'result_private.json')
        result = read(run / (prefix + '.result.json'))
        sources = quote_sources(case['public'])
        case_row = {'prefix': prefix, 'case_id': case['case_id'],
                    'environment': case['environment'], 'family_id': case['family_id'],
                    'condition': private['condition'], 'reference': private['reference'],
                    'arms': {}}
        for arm in ('P', 'C', 'F', 'T'):
            arm_calls = []
            for directory in sorted((run / 'calls').glob(prefix + '.' + arm + '.*')):
                request = read(directory / 'request.json')['request']
                stage = request['stage']
                if stage not in ('judge', 'review') or not (directory / 'raw.json').exists():
                    continue
                raw = read(directory / 'raw.json')
                # Check the archived input, not just a separately saved projection.
                payload = json.loads(request['content']['prompt'].split('PUBLIC INPUT:\n', 1)[1])
                if payload['record'] != case['public']:
                    raise ValueError('Public input mismatch in ' + directory.name)
                error = None
                try:
                    (judgment if stage == 'judge' else review)(raw['text'], case, raw['finish_reason'])
                except ValueError as exc:
                    error = str(exc)
                parsed = strict_json(raw['text'], raw['finish_reason'])
                record = {'slot': directory.name, 'case_id': case['case_id'], 'arm': arm,
                          'stage': stage, 'original_validation_error': error,
                          'original_protocol_valid': error is None,
                          'raw_output_path': str((directory / 'raw.json').relative_to(run)),
                          'citation_indices': []}
                if stage == 'judge':
                    score = parsed.get('score')
                    numeric = type(score) in (float, int) and math.isfinite(score) and 0 <= score <= 100
                    record.update(raw_score=score, raw_score_is_numeric=numeric,
                                  raw_threshold_alert=(score >= 50) if numeric else None,
                                  raw_direction_matches_reference=((score >= 50) == bool(private['reference']['label']))
                                  if numeric and private['reference']['status'] == 'resolved' else None,
                                  rationale=parsed.get('rationale'),
                                  semantic_support='requires_separate_review_not_established_by_score')
                for index, evidence in enumerate(parsed.get('evidence', parsed.get('notes', []))):
                    sid, quote = evidence.get('source_id'), evidence.get('quote')
                    source = sources.get(sid)
                    valid_length = isinstance(quote, str) and 1 <= len(quote) <= 400
                    exact = bool(source and valid_length and quote in source['text'])
                    whitespace = bool(source and valid_length and normalized(quote)
                                      and normalized(quote) in normalized(source['text']))
                    other = [key for key, value in sources.items()
                             if key != sid and valid_length and quote in value['text']]
                    category = ('exact' if exact else 'missing_source' if source is None else
                                'invalid_quote_length' if not valid_length else
                                'whitespace_only_mismatch' if whitespace else
                                'exact_text_at_different_source' if other else
                                'other_text_mismatch_requires_content_review')
                    record['citation_indices'].append(len(citations))
                    citations.append({'slot': directory.name, 'index': index, 'source_id': sid,
                                      'claim': evidence.get('claim'), 'quote': quote,
                                      'source_kind': source.get('kind') if source else None,
                                      'source_text': source.get('text') if source else None,
                                      'exact_match': exact, 'diagnostic_category': category,
                                      'other_exact_source_ids': other,
                                      'semantic_support': 'not_determined_by_text_matching'})
                calls.append(record)
                arm_calls.append(record)
            stored = result['arms'][arm]
            judges = [call for call in arm_calls if call['stage'] == 'judge']
            if len(judges) > 1:
                raise ValueError('Multiple judge calls in arm')
            final = judges[0] if judges else None
            failed_calls = [call for call in arm_calls if not call['original_protocol_valid']]
            if stored['status'] == 'invalid':
                if len(failed_calls) != 1 or failed_calls[0]['original_validation_error'] != stored['failure_reason']:
                    raise ValueError('Failure does not reproduce for ' + prefix + '.' + arm)
            elif stored['status'] == 'ok':
                if final is None or not final['original_protocol_valid'] or stored['score'] != final['raw_score']:
                    raise ValueError('Successful result does not reproduce')
            case_row['arms'][arm] = {
                'original_status': stored['status'], 'original_score': stored['score'],
                'original_failure_reason': stored.get('failure_reason'),
                'followup_performed': stored['followup_performed'],
                'judge_returned': final is not None,
                'failure_stage': failed_calls[0]['slot'].split('.')[-1] if failed_calls else None,
                'raw_score_diagnostic_only': final['raw_score'] if final else None,
                'raw_direction_matches_reference': final['raw_direction_matches_reference'] if final else None,
                'raw_judge_path': final['raw_output_path'] if final else None,
            }
        rows.append(case_row)
    if len(rows) != len(summary['cases']):
        raise ValueError('Cases missing from diagnostics')
    by_arm = {}
    for arm in ('P', 'C', 'F', 'T'):
        items = [row['arms'][arm] for row in rows]
        by_arm[arm] = {
            'all_case_denominator': len(rows),
            'judge_returned': sum(item['judge_returned'] for item in items),
            'judge_not_executed': sum(not item['judge_returned'] for item in items),
            'original_valid_judgments': sum(item['original_status'] == 'ok' for item in items),
            'original_invalid_arms': sum(item['original_status'] == 'invalid' for item in items),
            'actual_followups': sum(item['followup_performed'] for item in items),
            'raw_score_distribution_diagnostic_only': dict(Counter(str(item['raw_score_diagnostic_only'])
                for item in items if item['judge_returned'])),
            'raw_direction_matches_reference': sum(item['raw_direction_matches_reference'] is True for item in items),
            'raw_direction_disagrees_reference': sum(item['raw_direction_matches_reference'] is False for item in items),
        }
    report = {
        'schema_version': 'offline-diagnostic-v1', 'source_job': '31821684',
        'purpose': 'separate_missing_steps_raw_decisions_and_citation_failures',
        'not_a_replacement_score': True, 'new_model_calls': 0, 'raw_source_directory': str(run),
        'all_case_denominator': len(rows), 'by_arm': by_arm,
        'validation_errors': dict(Counter(call['original_validation_error'] for call in calls
                                          if call['original_validation_error'])),
        'citation_diagnostic_categories': dict(Counter(c['diagnostic_category'] for c in citations)),
        'original_F_T_valid_pairs': sum(row['arms']['F']['original_status'] == 'ok'
                                       and row['arms']['T']['original_status'] == 'ok' for row in rows),
        'both_followups_executed': sum(row['arms']['F']['followup_performed']
                                      and row['arms']['T']['followup_performed'] for row in rows),
        'reference_counts': dict(Counter(str(row['reference']['label']) for row in rows)),
        'limits': ['Raw direction agreement does not validate rationale or repair invalid results.',
                   'Missing judge calls are unobserved, never replaced or assigned a raw score.',
                   'Text normalization is a diagnostic category, not a relaxed acceptance rule.',
                   'No positive reference cases: detection sensitivity and strategy superiority are not estimable.',
                   'These are development cases, not an independent held-out test.'],
        'cases': rows, 'calls': calls, 'citations': citations,
        'source_file_sha256': original,
    }
    if hashes(run) != original:
        raise ValueError('Source artifacts changed during analysis')
    report['raw_artifacts_unchanged'] = True
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'mechanical_diagnostic.json').open('x') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    lines = ['# Existing 24 cases: offline diagnostic matrix', '',
             'Original acceptance rules and scores are unchanged. Raw scores below are diagnostic only.', '',
             '`—` means the judge never ran; `score [invalid]` means an answer exists but failed the original validator.', '',
             '| Case | Condition | Reference | P raw | C raw | F raw | T raw | F/T follow-ups |',
             '|---|---|---:|---:|---:|---:|---:|---|']
    for row in rows:
        scores = []
        for arm in ('P', 'C', 'F', 'T'):
            item = row['arms'][arm]
            scores.append('—' if not item['judge_returned'] else str(item['raw_score_diagnostic_only'])
                          + (' [invalid]' if item['original_status'] != 'ok' else ''))
        lines.append('| ' + ' | '.join([row['prefix'] + ' ' + row['family_id'], row['condition'],
            str(row['reference']['label']), *scores,
            str(row['arms']['F']['followup_performed']) + '/' + str(row['arms']['T']['followup_performed'])]) + ' |')
    with (output / 'CASE_MATRIX.md').open('x') as stream:
        stream.write('\n'.join(lines) + '\n')
    print(json.dumps({key: report[key] for key in ['all_case_denominator', 'by_arm',
        'validation_errors', 'citation_diagnostic_categories', 'original_F_T_valid_pairs',
        'both_followups_executed', 'raw_artifacts_unchanged']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    diagnose(args.run, args.output)
