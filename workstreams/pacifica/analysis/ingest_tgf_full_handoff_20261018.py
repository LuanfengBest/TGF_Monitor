"""Offline, standard-library-only intake. Never execute supplied bundle code."""
from pathlib import Path, PurePosixPath
from collections import Counter
from datetime import datetime
import hashlib
import json
import stat
import zipfile

PROJECT = Path(__file__).resolve().parents[1]
SOURCE = Path('/Users/a1234/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_or3y48s99gs422_e1dd/msg/file/2026-10/TGF进度2026-10-17.zip')
DEST = PROJECT / 'data/external_handoffs/tgf_progress_20261017_full'
RECEIPT = PROJECT / 'results/tgf_full_handoff_intake_20261018.json'

def sha(b):
    return hashlib.sha256(b).hexdigest()

def main():
    if DEST.exists() or RECEIPT.exists():
        raise SystemExit('Intake destination or receipt already exists; inspect instead of overwriting.')
    archive_hash = sha(SOURCE.read_bytes())
    assert archive_hash == '20d7b9f6caa53cc5e3d6df8f43b22dc922ab27f2856260f9d688eb0ad926601d'
    with zipfile.ZipFile(SOURCE) as z:
        infos = [i for i in z.infolist() if not i.is_dir()]
        assert len({i.filename for i in infos}) == len(infos), 'Duplicate ZIP member'
        for i in infos:
            p = PurePosixPath(i.filename)
            assert not p.is_absolute() and '..' not in p.parts and '\\' not in i.filename
            assert not stat.S_ISLNK(i.external_attr >> 16), 'ZIP symlink'
        assert z.testzip() is None, 'CRC failure'
        roots = {PurePosixPath(i.filename).parts[0] for i in infos if not i.filename.startswith('__MACOSX/')}
        assert len(roots) == 1
        root = roots.pop()
        members = {i.filename[len(root)+1:]: i for i in infos if i.filename.startswith(root+'/')}
        manifest = json.loads(z.read(members['06_verification/manifest.json']))
        checks = []
        for entry in manifest['files']:
            declared = entry['path']
            actual = declared if declared in members else declared.replace('/04_code_and_results/', '/03_code_and_results/')
            row = dict(entry, declared_path=declared, actual_path=actual)
            if actual not in members:
                row['status'] = 'missing'
            else:
                b = z.read(members[actual])
                row.update(actual_bytes=len(b), actual_sha256=sha(b))
                row['status'] = 'matched' if row['actual_bytes']==entry['bytes'] and row['actual_sha256']==entry['sha256'] else 'mismatch'
            checks.append(row)
        # Only the known report PDF differs; no science-data mismatch is silently accepted.
        assert [r['actual_path'] for r in checks if r['status']=='mismatch'] == ['01_overview/TGF_project_overview_zh.pdf']
        assert sorted(r['declared_path'] for r in checks if r['status']=='missing') == ['01_overview/TGF_project_overview_zh.md', '02_progress_report/repo_README_draft.md']
        extracted = []
        skipped = []
        DEST.mkdir(parents=True)
        for i in infos:
            if i.filename.startswith('__MACOSX/') or PurePosixPath(i.filename).name == '.DS_Store':
                skipped.append(i.filename)
                continue
            assert i.filename.startswith(root+'/')
            rel = i.filename[len(root)+1:]
            out = DEST / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            b = z.read(i)
            with out.open('xb') as f:
                f.write(b)
            assert sha(out.read_bytes()) == sha(b)
            extracted.append({'path': rel, 'archive_member': i.filename, 'bytes':len(b), 'sha256':sha(b)})
    receipt = {
        'checked_at': datetime.now().astimezone().isoformat(),
        'source_path': str(SOURCE), 'source_bytes':SOURCE.stat().st_size,
        'source_sha256':archive_hash, 'destination':str(DEST),
        'source_root_as_decoded_by_zipfile':root,
        'zip_non_directory_members':len(infos), 'crc_ok':True,
        'extracted_file_count':len(extracted), 'skipped_metadata_count':len(skipped),
        'manifest_declared_files':len(checks),
        'manifest_status_counts':dict(Counter(r['status'] for r in checks)),
        'manifest_path_relocations_matched':sum(r['status']=='matched' and r['declared_path']!=r['actual_path'] for r in checks),
        'manifest_checks':checks, 'extracted_files':extracted, 'skipped_metadata':skipped,
        'scientific_data_byte_verification_passed':True,
        'entire_manifest_exactly_matches':False,
        'semantic_labels_review_complete':False,
        'model_calls':0, 'gpu_seconds':0, 'attached_scripts_executed':False,
        'notes':[
            'Root renamed only for local readability; original archive and extracted file bytes preserved.',
            'Manifest has stale 04_code_and_results paths; actual directory is 03_code_and_results.',
            'Overview PDF differs from its declared hash; overview Markdown and README draft are absent.',
            'These document packaging discrepancies are not evidence of corrupted raw trajectories.',
            'This is the newly supplied 59MB package, not the previously read 229724-byte email attachment.',
        ],
    }
    with RECEIPT.open('x') as f:
        json.dump(receipt,f,ensure_ascii=False,indent=2)
        f.write('\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in {'manifest_checks','extracted_files','skipped_metadata'}},ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
