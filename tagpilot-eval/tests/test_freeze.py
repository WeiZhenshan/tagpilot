"""收尾第 6 项：冻结报告的机制测试（不依赖 L2 是否已完成）。"""
import json
from pathlib import Path

from tagpilot_eval.freeze import freeze

PACKAGE = Path(__file__).resolve().parents[1]
P0 = PACKAGE / 'data/p0-v2'
CAL = PACKAGE / 'data/calibration-v2'
REVIEWS = PACKAGE / 'reviews/independent-review-v1.jsonl'


def test_freeze_produces_report_with_required_sections(tmp_path):
    summary = freeze(P0, CAL, REVIEWS, PACKAGE / 'runs',
                     tmp_path / 'ledger.jsonl', tmp_path / 'report')
    text = (tmp_path / 'report/REPORT.md').read_text()
    for heading in ['## 1. 版本清单', '## 2. 收尾六项状态', '## 3. 独立复核（第 1 项）',
                    '## 4. 裁判与解析复核（第 2 项）', '## 5. 来源冲突处置（第 3 项）',
                    '## 6. 人工抽检（第 4 项）', '## 7. L1 检索与消歧',
                    '## 8. L2 Agent 方案（真实运行）', '## 9. L3 Java 执行',
                    '## 10. 残留缺口与未授权事项']:
        assert heading in text, heading
    assert summary['p2_authorized'] is False
    assert summary['l3'] == 'NOT_APPLICABLE'
    assert summary['cases'] == 200
    assert (tmp_path / 'report/report.html').exists()
    assert json.loads((tmp_path / 'report/acceptance.json').read_text())['l1_atomic_recall_at_k'] is not None


def test_freeze_records_human_ledger_when_present(tmp_path):
    ledger = tmp_path / 'ledger.jsonl'
    ledger.write_text(json.dumps({'case_id': 'CAL-001', 'decision': 'ACCEPT', 'comment': None,
                                  'reviewer': 'USER', 'reviewed_at': '2026-09-27',
                                  'calibration_sha256': 'x'}) + '\n')
    summary = freeze(P0, CAL, REVIEWS, PACKAGE / 'runs', ledger, tmp_path / 'report2')
    assert summary['human_review'] == 'RECORDED'
    text = (tmp_path / 'report2/REPORT.md').read_text()
    assert '## 6. 人工抽检（第 4 项）' in text
    assert "{'ACCEPT': 1}" in text


def test_freeze_refuses_to_overwrite(tmp_path):
    freeze(P0, CAL, REVIEWS, PACKAGE / 'runs', tmp_path / 'ledger.jsonl', tmp_path / 'r')
    import pytest
    with pytest.raises(ValueError, match='已存在'):
        freeze(P0, CAL, REVIEWS, PACKAGE / 'runs', tmp_path / 'ledger.jsonl', tmp_path / 'r')
