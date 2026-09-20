"""不可变产物备份与重建。不会激活索引；激活统一经 Java 协议。"""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import time
from tag_semantic.index.builder import build_index, load_index, sha


def backup(build_dir: Path, target: Path):
    manifest = json.loads((build_dir / 'manifest.json').read_text())
    files = list(manifest['files']) + ['manifest.json']
    for name in files:
        if Path(name).name != name or (build_dir / name).is_symlink():
            raise ValueError('非法备份路径')
        if name != 'manifest.json' and sha(build_dir / name) != manifest['files'][name]:
            raise ValueError('备份前校验失败')
    with target.open('xb') as stream, tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for name in files:
            archive.add(build_dir / name, arcname=name)
    return {'build_id': manifest['build_id'], 'file': str(target), 'sha256': sha(target),
            'scope': 'ARTIFACTS_ONLY', 'external_requirements': ['ry.ts_* database backup', 'model weights matching manifest hashes', 'secret configuration stored separately']}


def rebuild(build_dir: Path, output: Path, build_id: str):
    started = time.monotonic()
    original = load_index(build_dir)
    manifest = original['manifest']
    result = build_index(original['catalog'], output, build_id, manifest['store_type'], original['embedder'], original['reranker'], manifest['retrieval_config'])
    fresh = result['manifest']
    for key in ('content_hash', 'doc_id_hash', 'embedding_model_hash', 'reranker_model_hash', 'retrieval_config_hash'):
        if fresh[key] != manifest[key]:
            raise ValueError('重建对账不一致: ' + key)
    return {'source_build_id': manifest['build_id'], 'build_id': build_id, 'seconds': time.monotonic() - started, 'reconciled': True, 'activated': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['backup', 'rebuild'])
    parser.add_argument('build_dir', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--build-id')
    args = parser.parse_args()
    if args.operation == 'rebuild' and not args.build_id:
        parser.error('重建需要新的 --build-id')
    result = backup(args.build_dir, args.output) if args.operation == 'backup' else rebuild(args.build_dir, args.output, args.build_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
