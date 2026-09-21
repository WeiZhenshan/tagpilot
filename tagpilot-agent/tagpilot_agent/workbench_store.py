"""单机持久运行记录：加密载荷、原子领取、事件游标；可独立恢复图检查点。"""
from __future__ import annotations
import base64
import hashlib
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from cryptography.fernet import Fernet
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer


class CipherSerializer:
    def __init__(self, secret):
        self.cipher = Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))
        self.inner = JsonPlusSerializer()

    def dumps_typed(self, value):
        kind, data = self.inner.dumps_typed(value)
        return kind, self.cipher.encrypt(data)

    def loads_typed(self, value):
        kind, data = value
        return self.inner.loads_typed((kind, self.cipher.decrypt(data)))


class RunStore:
    def __init__(self, path, secret):
        root = Path(path).resolve().parent
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(path, check_same_thread=False)
        os.chmod(path, 0o600)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.cipher = CipherSerializer(secret).cipher
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS wb_runs (
          id TEXT PRIMARY KEY, owner TEXT NOT NULL, thread TEXT NOT NULL,
          status TEXT NOT NULL, payload BLOB NOT NULL, result BLOB, error TEXT,
          updated REAL NOT NULL, UNIQUE(owner, thread, id));
        CREATE TABLE IF NOT EXISTS wb_events (
          seq INTEGER PRIMARY KEY AUTOINCREMENT, run TEXT NOT NULL, payload BLOB NOT NULL);
        CREATE INDEX IF NOT EXISTS wb_event_run ON wb_events(run,seq);
        ''')
        # 进程重启后不冒充仍在执行；用户可明确从检查点恢复。
        self.db.execute("UPDATE wb_runs SET status='INTERRUPTED' WHERE status='RUNNING'")
        self.db.commit()

    def pack(self, obj):
        return self.cipher.encrypt(json.dumps(obj, ensure_ascii=False).encode())

    def unpack(self, data):
        return json.loads(self.cipher.decrypt(data)) if data else None

    def create(self, rid, request):
        with self.lock, self.db:
            row = self.db.execute('SELECT * FROM wb_runs WHERE id=?', (rid,)).fetchone()
            if row:
                if row['owner'] != request['owner_id'] or row['thread'] != request['thread_id']:
                    raise ValueError('运行标识已被使用')
                if self.unpack(row['payload']) != request:
                    raise ValueError('重复请求内容不一致')
                return False
            active = self.db.execute("SELECT 1 FROM wb_runs WHERE owner=? AND thread=? AND status IN ('RUNNING','WAITING')",
                                     (request['owner_id'], request['thread_id'])).fetchone()
            if active:
                raise ValueError('当前会话已有未完成运行')
            self.db.execute('INSERT INTO wb_runs VALUES(?,?,?,?,?,?,?,?)',
                            (rid, request['owner_id'], request['thread_id'], 'RUNNING', self.pack(request), None, None, time.time()))
            return True

    def get(self, rid, owner):
        with self.lock:
            row = self.db.execute('SELECT * FROM wb_runs WHERE id=? AND owner=?', (rid, owner)).fetchone()
            if row is None:
                raise KeyError('运行不存在')
            return {**dict(row), 'payload': self.unpack(row['payload']), 'result': self.unpack(row['result'])}

    def status(self, rid, status, result=None, error=None):
        with self.lock, self.db:
            self.db.execute("UPDATE wb_runs SET status=?,result=?,error=?,updated=? WHERE id=? AND status!='CANCELLED'",
                            (status, self.pack(result) if result is not None else None, error, time.time(), rid))

    def claim(self, rid, owner):
        with self.lock, self.db:
            return self.db.execute("UPDATE wb_runs SET status='RUNNING',result=NULL,error=NULL,updated=? WHERE id=? AND owner=? AND status IN ('WAITING','INTERRUPTED','FAILED')",
                                   (time.time(), rid, owner)).rowcount == 1

    def cancel(self, rid, owner):
        with self.lock, self.db:
            self.db.execute("UPDATE wb_runs SET status='CANCELLED',updated=? WHERE id=? AND owner=? AND status IN ('RUNNING','WAITING','INTERRUPTED','FAILED')",
                            (time.time(), rid, owner))

    def emit(self, rid, event):
        with self.lock, self.db:
            self.db.execute('INSERT INTO wb_events(run,payload) VALUES(?,?)', (rid, self.pack({**event, 'occurred_at': time.time()})))

    def events(self, rid, after=0):
        with self.lock:
            return [{'seq': row['seq'], **self.unpack(row['payload'])} for row in self.db.execute(
                'SELECT seq,payload FROM wb_events WHERE run=? AND seq>? ORDER BY seq LIMIT 500', (rid, after))]
