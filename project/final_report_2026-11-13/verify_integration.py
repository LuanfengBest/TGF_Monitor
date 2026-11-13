"""Check publication numbers against saved analyses without model/runtime imports."""
from pathlib import Path
import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
main = json.loads((PROJECT / 'jev_tgf_mainline_2026-11-12/RESULTS.json').read_text())
timing = json.loads((PROJECT / 'authorization_timing_jev_2026-11-12/recovery_01/analysis.json').read_text())
outcome = json.loads((PROJECT / 'authorization_timing_jev_2026-11-12/recovery_01/FINAL_OUTCOME.json').read_text())
slides = json.loads((HERE / 'SLIDES.json').read_text())['slides']
manuscript = (HERE / 'FINAL_REPORT.md').read_text()

def must(value, message):
    if not value: raise AssertionError(message)

tables = []
for block in re.findall(r'(?:^\|.*\n)+', manuscript, re.M):
    rows = [[c.strip() for c in line.strip().strip('|').split('|')] for line in block.splitlines()]
    tables.append([row for row in rows if not all(re.fullmatch(r':?-+:?', c) for c in row)])

airline = next(t for t in tables if t[0][0] == 'Airline Judge and arm')
for row in airline[1:]:
    model, arm = row[0].split()
    v = main['environments']['airline']['table'][f'{model.lower()}.{arm}']
    expected = [str(v[k]) for k in ('TP', 'TN', 'FP', 'invalid_or_unavailable')] + [f"{v['G']:.6f}"]
    must(row[1:] == expected, f'airline manuscript mismatch {row[0]}')
    must(row in slides[12]['table']['values'], f'airline slide mismatch {row[0]}')

bank = next(t for t in tables if t[0][0] == 'Bank Judge and arm')
bank_mapping = [('qwen', ['P']), ('qwen', ['C']), ('qwen', ['F', 'T']), ('jev', ['P', 'F', 'T']), ('jev', ['C'])]
for row, (model, arms) in zip(bank[1:], bank_mapping, strict=True):
    for arm in arms:
        v = main['environments']['bank']['table'][f'{model}.{arm}']
        must(row[1:] == [str(v[k]) for k in ('TP', 'TN', 'FP')] + [f"{v['G']:.6f}"], f'bank manuscript mismatch {model}.{arm}')
for row, (model, arms) in zip(slides[13]['table']['values'][1:], bank_mapping, strict=True):
    for arm in arms:
        v = main['environments']['bank']['table'][f'{model}.{arm}']
        must(row[1:] == [str(v[k]) for k in ('TP', 'FP')] + [f"{v['G']:.6f}"], f'bank slide mismatch {model}.{arm}')

timing_table = next(t for t in tables if t[0][0] == 'Judge and material')
for row in timing_table[1:]:
    model, material = row[0].lower().split()
    v = timing['groups'][f'{model}.{material}_card']
    c, behavior = v['counts'], v['behavior_counts']
    expected = [c['pair_correct'], c['correct'], behavior['change'].get('correct_flip', 0), behavior['invariant'].get('correct_same', 0)]
    # Every invariant control is binary-valid; unwanted flips are the differing-label cases.
    unwanted = sum(n for label, n in behavior['invariant'].items() if label not in ('correct_same', 'wrong_same'))
    must(row[1:] == [str(x) for x in expected + [unwanted]], f'timing manuscript mismatch {row[0]}')
    must([row[0], row[1], row[3], row[4]] in slides[6]['table']['values'], f'timing slide mismatch {row[0]}')

primary = main['environments']['airline']['comparisons']['jev.T-F']['G']
must(f"{primary['estimate']:.10f}" in manuscript, 'primary estimate missing')
must(f"{primary['ci95'][1]:.10f}" in manuscript, 'primary interval missing')
must(primary['estimate'] < .05 and primary['ci95'][0] == 0, 'primary interpretation changed')
must(outcome['primary_effect'] == 0 and outcome['formal_valid'] == 64, 'timing outcome changed')
must(outcome['human_reviews'] == 0, 'human review status changed')
resources = slides[15]['table']['values']
must(resources[2][3] == f"${main['costs']['jev']['estimated_api_usd']:.9f}", 'mainline cost mismatch')
must(resources[3][3] == f"${outcome['jev_estimated_api_usd']:.9f}", 'timing cost mismatch')
must(resources[3][1] == str(outcome['all_dispatched']), 'timing call count mismatch')
must(str(outcome['aggregate_gpu_seconds']) in resources[3][2].replace(',', ''), 'timing allocation mismatch')

checked_links = 0
for path in HERE.glob('*.md'):
    for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', path.read_text()):
        target = target.strip('<>')
        if target.startswith(('https://', 'http://', '#')): continue
        dest = (path.parent / target.split('#')[0]).resolve()
        must(dest.exists(), f'broken local link in {path.name}: {target}')
        checked_links += 1

ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
with zipfile.ZipFile(HERE / 'deliverables/Authorization_Auditing_Report.docx') as z:
    xml = ET.fromstring(z.read('word/document.xml'))
    doc_text = ' '.join(t.text or '' for t in xml.findall('.//w:t', ns))
    relationships = z.read('word/_rels/document.xml.rels').decode()
    must('file://' not in relationships and '/Users/' not in relationships, 'nonportable DOCX links')
    must(len(xml.findall('.//w:tbl', ns)) == len(tables), 'DOCX table count')
for table in tables:
    for row in table:
        for cell in row: must(cell in doc_text, f'DOCX missing table cell {cell}')
for phrase in ('Independent human review', 'post-hoc component comparison', 'primary indexing gain', 'prespecified audit rule'):
    must(phrase in doc_text, f'DOCX missing disclosure {phrase}')
must('*Monitoring Monitorability*' not in doc_text, 'unrendered Markdown emphasis')

notes = (HERE / 'SPEAKER_NOTES_ZH.md').read_text()
portable = (HERE / 'SLIDES.md').read_text()
for i, slide in enumerate(slides, 1):
    must(slide['notes'] in notes, f'notes mismatch at slide {i}')
    must(slide['title'] in portable, f'portable title missing at slide {i}')
    for row in slide.get('table', {}).get('values', []):
        must('| ' + ' | '.join(row) + ' |' in portable, f'portable table mismatch at slide {i}')

source_paths = [
    PROJECT / 'jev_tgf_mainline_2026-11-12/RESULTS.json',
    PROJECT / 'jev_tgf_mainline_2026-11-12/BASELINE_COMPARISON.json',
    PROJECT / 'authorization_timing_jev_2026-11-12/recovery_01/analysis.json',
    PROJECT / 'authorization_timing_jev_2026-11-12/recovery_01/FINAL_OUTCOME.json',
]
print(json.dumps({
    'status': 'passed', 'report_tables': len(tables), 'slides': len(slides),
    'local_links_checked': checked_links, 'model_calls': 0, 'simulator_calls': 0,
    'checks': ['mainline table counts and G', 'timing pair and behavior counts', 'primary interval and null result', 'cost and allocation figures', 'local links', 'DOCX table content and portable links', 'portable slide tables and Chinese notes'],
    'source_sha256': {str(p.relative_to(PROJECT.parent)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths},
}, indent=2))
