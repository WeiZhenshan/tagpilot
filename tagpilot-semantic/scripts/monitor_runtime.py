"""只读存活/行集巡检，失败退出 1；可交由现有监控执行，脚本不发送外部通知。"""
import argparse
import os
import sys
import httpx

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url', default='http://127.0.0.1:8091')
parser.add_argument('--build-id', required=True)
args = parser.parse_args()
token = os.environ.get('TAG_RUNTIME_TOKEN')
if not token:
    sys.exit('缺少 TAG_RUNTIME_TOKEN')
try:
    with httpx.Client(base_url=args.url, headers={'Authorization': 'Bearer ' + token}, timeout=15, follow_redirects=False) as client:
        health = client.get('/health'); health.raise_for_status()
        response = client.get('/stats', params={'build_id': args.build_id}); response.raise_for_status()
        stats = response.json()
        if not stats.get('id_reconciled') or stats.get('build_id') != args.build_id:
            raise ValueError('索引行集或身份对账失败')
        metrics = client.get('/metrics'); metrics.raise_for_status()
        print({'status': 'OK', 'build_id': args.build_id, 'doc_count': stats['doc_count'], 'metrics': metrics.json()})
except Exception as exc:
    print('语义索引巡检失败: ' + type(exc).__name__, file=sys.stderr)
    sys.exit(1)
