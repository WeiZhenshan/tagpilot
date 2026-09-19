"""可重复开发基线报告；试点为仓库 SQL 合成 fixture，不是在线业务验收。"""
import json
from pathlib import Path
import tempfile
from tag_semantic.tests.test_pipeline import _pilot_bundle
from tag_semantic.eval.gold import GOLD_DEV
from tag_semantic.eval.acceptance import evaluate
from tag_semantic.index.maintenance import backup, rebuild

root = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='tag-dev-eval-') as temp:
    folder = Path(temp)
    service, catalog, _ = _pilot_bundle(folder)
    manifest = json.loads((folder / 'b1/manifest.json').read_text())
    cases = []
    for row in GOLD_DEV:
        case = {'id': row['id'], 'query': row['query'], 'eligible_tag_ids': list(catalog.tags),
                'atomic_conditions': [{'accept_tag_ids': row['accept_tag_ids']}], 'must_clarify': row.get('must_clarify', False)}
        if row.get('inexpressible_approx'):
            case.update(inexpressible=True, must_clarify=False)
        if row.get('accept_code'):
            case.update(expected_codes=[row['accept_code']], expected_code_tag_id=row['accept_tag_ids'][0])
        cases.append(case)
    report = evaluate(service, cases, manifest, scope='DEVELOPMENT_SYNTHETIC_PILOT')
    report.update(embedding_model=manifest['embedding_model'], sealed_cases=0, production_acceptance=False,
                  limitations=['20 development cases from SQL pilot fixture', 'No BGE A/B evidence', 'No 600 sealed cases', 'No full-library quality conclusion'])
    (root / 'docs/validation/retrieval-eval-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    recovery = rebuild(folder / 'b1', folder / 'recovered', 'recovered')
    archive = backup(folder / 'b1', folder / 'backup.tar.gz')
    recovery.update(scope='SYNTHETIC_PILOT_LOCAL_REBUILD', backup_sha256=archive['sha256'], production_rto=False)
    (root / 'docs/validation/semantic-rebuild-report.json').write_text(json.dumps(recovery, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'cases': len(cases), 'metrics': report['metrics'], 'failures': report['failures'], 'rebuild': recovery}, ensure_ascii=False))
