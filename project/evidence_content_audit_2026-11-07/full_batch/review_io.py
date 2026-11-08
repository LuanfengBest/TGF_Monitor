"""Store manually written response annotations and verify their quoted excerpts."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent


def save_batch(filename, rows, next_step):
    answers = {a['response_id']: a for a in json.loads((BASE / 'responses_masked.json').read_text())}
    new = []
    for row in rows:
        rid, scope, note, issues = row[:4]
        overrides = row[4] if len(row) > 4 else {}
        answer = answers[rid]
        parsed = []
        for kind, excerpt, detail, sources in issues:
            assert excerpt in answer['text'], (rid, excerpt)
            parsed.append(dict(type=kind, answer_excerpt=excerpt, finding_zh=detail, reference_sources=sources))
        item = dict(response_id=rid, case_id=answer['case_id'], review_origin='full_batch_source_audit',
                    requested_dimension_facts='sufficient_and_correct', primary_conclusion_for_claimed_scope='correct',
                    answer_scope=scope, review_zh=note, issues=parsed)
        item.update(overrides)
        new.append(item)
    path = BASE / filename
    assert not path.exists(), path
    existing = json.loads((BASE / 'answer_reviews.json').read_text())
    assert not ({x['response_id'] for x in existing} & {x['response_id'] for x in new})
    assert len({x['response_id'] for x in new}) == len(new)
    path.write_text(json.dumps(new, ensure_ascii=False, indent=2) + '\n')
    existing.extend(new)
    (BASE / 'answer_reviews.json').write_text(json.dumps(existing, ensure_ascii=False, indent=2) + '\n')
    status = json.loads((BASE / 'STATUS.json').read_text())
    status.update(answer_reviews_complete=len(existing), current_step=next_step)
    (BASE / 'STATUS.json').write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n')
    print('ANSWER_REVIEWS_COMPLETE', len(existing))
