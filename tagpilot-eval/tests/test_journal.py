from pathlib import Path
import sqlite3
import pytest
from tagpilot_eval.journal import initialize

CAL=Path(__file__).resolve().parents[1]/'data/calibration-v1'


def test_journal_starts_pending_and_preserves_review(tmp_path):
    path=tmp_path/'progress.sqlite3'
    assert initialize(CAL,path)['tasks']==200
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT count(*) FROM task WHERE ai_review='NOT_RUN' AND human_review='PENDING'").fetchone()[0]==200
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE task SET human_review='ACCEPT' WHERE case_id='CAL-001'")
        conn.execute("UPDATE task SET human_review='REJECT',reviewer='test',reviewed_at='2026-09-26',comment='preserve' WHERE case_id='CAL-001'")
    with pytest.raises(ValueError,match='禁止覆盖'):initialize(CAL,path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT comment FROM task WHERE case_id='CAL-001'").fetchone()[0]=='preserve'
