"""本地P1进度库：仅记录待复核任务，重复导入不覆盖任何审核记录。"""
from pathlib import Path
import sqlite3

from .io import file_hash, read_jsonl
from .validation import verify_package


def initialize(calibration, output):
    calibration,output=Path(calibration),Path(output)
    if output.exists():
        raise ValueError('进度库已存在；禁止覆盖审核记录')
    verify_package(calibration)
    manifest_hash=file_hash(calibration/'manifest.json')
    cases=read_jsonl(calibration/'cases.jsonl')
    if len(cases)!=200 or len({c['case_id'] for c in cases})!=200 or any(c['phase']!='P1' or c['split']!='CALIBRATION' for c in cases):
        raise ValueError('只允许200个P1校准任务')
    output.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(output) as conn:
        conn.executescript("""
        CREATE TABLE package(manifest_sha256 TEXT PRIMARY KEY, phase TEXT CHECK(phase='P1'), formal_count INTEGER CHECK(formal_count=0));
        CREATE TABLE task(case_id TEXT PRIMARY KEY, manifest_sha256 TEXT NOT NULL REFERENCES package(manifest_sha256),
          ai_review TEXT NOT NULL CHECK(ai_review='NOT_RUN'), human_review TEXT NOT NULL CHECK(human_review IN ('PENDING','ACCEPT','REJECT')),
          reviewer TEXT, reviewed_at TEXT, comment TEXT,
          CHECK(human_review='PENDING' OR (reviewer IS NOT NULL AND reviewed_at IS NOT NULL)));
        """)
        conn.execute('INSERT INTO package VALUES (?, ?, ?)',(manifest_hash,'P1',0))
        conn.executemany('INSERT INTO task VALUES (?, ?, ?, ?, NULL, NULL, NULL)',
                         [(c['case_id'],manifest_hash,'NOT_RUN','PENDING') for c in cases])
    return {'tasks':len(cases),'human_review':'PENDING','ai_review':'NOT_RUN','formal_cases':0}
