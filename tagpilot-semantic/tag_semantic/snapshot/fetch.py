"""下载授权快照。字节与规范化内容分别校验，成功后才发布本地文件。"""
import hashlib
import os
from pathlib import Path
from urllib.parse import quote
import httpx
from tag_semantic.snapshot.loader import load_catalog


def fetch_snapshot(base_url: str, snapshot_id: str, token: str, destination: Path,
                   expected_hash: str | None = None) -> Path:
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError('目标快照已存在，禁止覆盖')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(destination.name + '.' + os.urandom(6).hex() + '.tmp')
    try:
        with httpx.Client(timeout=60, follow_redirects=False) as client:
            with client.stream('GET', f"{base_url.rstrip('/')}/taglibrary/semantic/snapshot/{quote(snapshot_id, safe='')}/download",
                               headers={'Authorization': f'Bearer {token}'}) as response:
                response.raise_for_status()
                digest = hashlib.sha256()
                with temp.open('xb') as out:
                    size = 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > 256 * 1024 * 1024:
                            raise ValueError('快照超过下载大小限制')
                        digest.update(chunk)
                        out.write(chunk)
                if digest.hexdigest() != response.headers.get('X-Content-Sha256'):
                    raise ValueError('快照文件字节校验失败')
                catalog_hash = response.headers.get('X-Catalog-Content-Hash')
                if not catalog_hash or (expected_hash and expected_hash != catalog_hash):
                    raise ValueError('快照内容哈希头不匹配')
                catalog = load_catalog(temp, catalog_hash)
                if catalog.meta.get('snapshot_id') != snapshot_id:
                    raise ValueError('返回了错误快照')
        os.link(temp, destination)  # 原子创建且不覆盖
        return destination
    finally:
        temp.unlink(missing_ok=True)
