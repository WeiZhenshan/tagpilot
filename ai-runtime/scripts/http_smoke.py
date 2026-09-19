"""隔离真实 TCP 服务冒烟：Java 测试快照→HTTP 构建→加载→检索；不写业务库。"""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import httpx

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--java-snapshot', type=Path, required=True)
parser.add_argument('--embedding', type=Path)
parser.add_argument('--reranker', type=Path)
parser.add_argument('--output', type=Path)
args = parser.parse_args()
if bool(args.embedding) != bool(args.reranker):
    parser.error('--embedding 和 --reranker 必须同时提供')
root = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='tag-http-smoke-') as temp:
    folder = Path(temp)
    snapshots = folder / 'snapshots'; snapshots.mkdir()
    shutil.copyfile(args.java_snapshot, snapshots / 'JAVA-CONTRACT.jsonl')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    token = secrets.token_urlsafe(32)
    env = os.environ.copy()
    env.update(TAG_RUNTIME_TOKEN=token, TAG_SNAPSHOT_DIR=str(snapshots), TAG_INDEX_DIR=str(folder / 'index'), TAG_ALLOW_HASH_BASELINE='true')
    env.pop('TAG_EMBEDDING_PATH', None); env.pop('TAG_RERANKER_PATH', None)
    if args.embedding:
        env.update(TAG_EMBEDDING_PATH=str(args.embedding.resolve()), TAG_RERANKER_PATH=str(args.reranker.resolve()),
                   TAG_ALLOW_HASH_BASELINE='false', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    with (folder / 'runtime.log').open('w') as log:
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'tag_semantic.server:app', '--host', '127.0.0.1', '--port', str(port)], env=env, stdout=log, stderr=log)
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=120) as client:
                for _ in range(80):
                    try:
                        if client.get('/health').status_code == 200: break
                    except httpx.ConnectError: pass
                    if process.poll() is not None: raise RuntimeError('临时运行时启动失败')
                    time.sleep(.1)
                headers = {'Authorization': 'Bearer ' + token}
                assert client.get('/stats?build_id=network-b1').status_code == 401
                request = {'library_id': 107, 'snapshot_id': 'JAVA-CONTRACT', 'build_id': 'network-b1', 'store_type': 'LOCAL'}
                built = client.post('/build', json=request, headers=headers); assert built.status_code == 200, built.text
                stats = client.get('/stats', params={'build_id': 'network-b1'}, headers=headers).json(); assert stats['id_reconciled']
                assert client.post('/activate', json=request, headers=headers).json()['status'] == 'PREPARED'
                query = {'library_id': 107, 'build_id': 'network-b1', 'requirement': '性别信息', 'eligible_tag_ids': [1]}
                result = client.post('/retrieve', json=query, headers=headers).json()
                assert result['candidates'] and {c['tag_id'] for c in result['candidates']} == {1}
                query['eligible_tag_ids'] = []
                assert client.post('/retrieve', json=query, headers=headers).json()['candidates'] == []
                assert client.post('/build', json=request, headers=headers).status_code == 409
                report = {'scope': 'ISOLATED_REAL_HTTP_WITH_JAVA_TEST_SNAPSHOT', 'store_type': 'LOCAL',
                          'embedding_model': 'BAAI/bge-m3' if args.embedding else 'hash-v1',
                          'reranker_model': 'BAAI/bge-reranker-v2-m3' if args.reranker else None,
                          'doc_count': stats['doc_count'], 'artifact_hash': stats['artifact_hash'], 'content_hash': stats['content_hash'],
                          'passed': ['service_auth', 'http_build', 'stats_id_reconciliation', 'activate_prepared_only', 'retrieve_partial_whitelist', 'empty_whitelist', 'duplicate_build_rejected'],
                          'business_snapshot_published': False, 'java_http_orchestration_verified': False}
                (args.output or root / 'docs/validation/semantic-http-smoke.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
                print(json.dumps(report, ensure_ascii=False))
        finally:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait()
