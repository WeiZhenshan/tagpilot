"""同机多进程共享租约；清理等待所有在途请求释放。"""
from contextlib import contextmanager
from pathlib import Path
import fcntl
import re

@contextmanager
def build_lease(root: Path, build_id: str, exclusive=False):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', build_id):
        raise ValueError('build_id 非法')
    leases = root / '.leases'
    leases.mkdir(parents=True, exist_ok=True)
    with (leases / (build_id + '.lock')).open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)
