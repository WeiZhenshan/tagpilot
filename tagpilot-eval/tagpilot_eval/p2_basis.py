"""P2 前置：重验 P0 基准是否仍然成立，并如实记录工作树漂移。

区分两件事，不能混为一谈：
- **已发布快照与索引**：被测 Agent 实际读到的视图，也是 L0/L1/L2 的评测基准。
- **标签库工作树**：来源语义表、码值表。它可以领先于已发布快照（P1 第③项的处置即在源头改，
  但未重新发布快照）。工作树漂移不改变 Agent 的已发布视图，因此不阻断 P2，但必须记录。

只有已发布快照/索引本身发生变化时，才需要新出 P0 版本。
"""
import json
from pathlib import Path

from .io import file_hash, fresh_directory, read_jsonl, write_json
from .validation import verify_package

VOLATILE_OBSERVATION_KEYS = ('observed_at',)


def _strip(value, volatile=VOLATILE_OBSERVATION_KEYS):
    if isinstance(value, dict):
        return {k: _strip(v, volatile) for k, v in value.items() if k not in volatile}
    if isinstance(value, list):
        return [_strip(v, volatile) for v in value]
    return value


def published_artifacts(p0_manifest, root):
    """比对已发布快照与索引的磁盘字节与 P0 冻结值。"""
    root = Path(root)
    sources = p0_manifest['sources']
    checks = []
    for name, expected in (('snapshot', p0_manifest['active_snapshot']['file_sha256']),
                           ('index_manifest', p0_manifest['active_build'].get('artifact_hash'))):
        path = root / sources[name]['path']
        actual = file_hash(path) if path.exists() else None
        checks.append({'source': name, 'path': str(sources[name]['path']),
                       'expected_sha256': expected, 'actual_sha256': actual,
                       'unchanged': actual == expected})
    return {'checks': checks, 'unchanged': all(c['unchanged'] for c in checks)}


def observation_diff(frozen, fresh):
    """逐表比较只读观测；忽略时间戳。返回漂移明细，不做「相等/不等」的模糊结论。"""
    database_frozen, database_fresh = frozen['database'], fresh['database']
    result = {'idempotent_ignoring_timestamp': _strip(fresh) == _strip(frozen),
              'sections': {}, 'codes_added': [], 'semantics_changed': [], 'tags_changed': []}
    for section in sorted(set(database_frozen) | set(database_fresh)):
        old, new = database_frozen.get(section), database_fresh.get(section)
        result['sections'][section] = (old == new)
        if old == new:
            continue
        if section == 'codes':
            key = lambda row: (row.get('field_name'), row.get('code'))
            added = {key(r) for r in new} - {key(r) for r in old}
            removed = {key(r) for r in old} - {key(r) for r in new}
            result['codes_added'] = sorted([{'field_name': f, 'code': c} for f, c in added],
                                           key=lambda r: (r['field_name'], r['code']))
            if removed:
                raise ValueError('码值被删除，已发布来源不一致: ' + repr(sorted(removed)))
        elif section in ('semantics', 'tags'):
            old_by_id = {r.get('tag_id'): r for r in old}
            new_by_id = {r.get('tag_id'): r for r in new}
            if set(old_by_id) != set(new_by_id):
                raise ValueError(f'{section} 标签集合发生变化，必须新出 P0 版本')
            bucket = result['semantics_changed'] if section == 'semantics' else result['tags_changed']
            for tag_id in sorted(old_by_id):
                before, after = old_by_id[tag_id], new_by_id[tag_id]
                if before != after:
                    fields = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
                    bucket.append({'tag_id': tag_id, 'changed_fields': fields,
                                   'before': {k: before.get(k) for k in fields},
                                   'after': {k: after.get(k) for k in fields}})
        else:
            raise ValueError(f'{section} 观测差异未分类，需人工确认')
    return result


def collect_observation(root, output_path):
    """调用只读本机观测；需要 PyYAML 与本机 mysql 客户端。"""
    from .live import collect
    output_path = Path(output_path)
    if output_path.exists():
        raise ValueError('观测输出已存在')
    output_path.write_text(json.dumps(collect(Path(root)), ensure_ascii=False))
    return output_path


def verify_basis(p0, root, output, observation=None, authorization=None):
    p0, root, output = Path(p0), Path(root), Path(output)
    manifest = verify_package(p0)
    facts = {r['tag_id']: r for r in read_jsonl(p0 / 'facts.jsonl')}
    issues = {r['issue_id']: r for r in read_jsonl(p0 / 'issues.jsonl')} \
        if (p0 / 'issues.jsonl').exists() else {}

    published = published_artifacts(manifest, root)
    frozen = json.loads((p0 / 'live-observation.json').read_text())
    record = {'schema_version': 'p2-basis.v1',
              'p0_manifest_sha256': file_hash(p0 / 'manifest.json'),
              'active_snapshot': manifest['active_snapshot']['snapshot_id'],
              'active_build': manifest['active_build']['build_id'],
              'published_artifacts': published,
              'frozen_observed_at': frozen.get('observed_at')}

    drifted_tag_ids = []
    fresh = None
    if observation is not None:
        fresh = json.loads(Path(observation).read_text())
        diff = observation_diff(frozen, fresh)
        drifted_tag_ids = sorted({r['tag_id'] for r in diff['semantics_changed']}
                                 | {r['tag_id'] for r in diff['tags_changed']}
                                 | {t for r in diff['codes_added'] for t in _tag_ids_for_field(facts, r['field_name'])})
        record['live_observation'] = {'observed_at': fresh.get('observed_at'),
                                      'idempotent_ignoring_timestamp': diff['idempotent_ignoring_timestamp']}
        record['working_tree_drift'] = {'sections': diff['sections'], 'codes_added': diff['codes_added'],
                                        'semantics_changed': diff['semantics_changed'],
                                        'tags_changed': diff['tags_changed']}
    else:
        record['live_observation'] = None
        record['working_tree_drift'] = None

    record['drifted_tag_ids'] = drifted_tag_ids
    record['drifted_p0_issues'] = [
        {'tag_id': tag_id,
         'issue_ids': sorted(facts.get(tag_id, {}).get('issue_ids', [])),
         'dispositions': sorted({issues[i].get('disposition') for i in facts.get(tag_id, {}).get('issue_ids', [])
                                 if i in issues})}
        for tag_id in drifted_tag_ids]

    if not published['unchanged']:
        record['conclusion'] = 'BASIS_CHANGED_REQUIRES_NEW_P0'
    elif drifted_tag_ids:
        record['conclusion'] = 'PUBLISHED_BASIS_UNCHANGED_WORKING_TREE_DRIFT_RECORDED'
    elif observation is not None:
        record['conclusion'] = 'PUBLISHED_AND_WORKING_TREE_UNCHANGED'
    else:
        record['conclusion'] = 'PUBLISHED_BASIS_UNCHANGED_WORKING_TREE_NOT_OBSERVED'
    record['explanation'] = ('已发布快照/索引与 P0 冻结值一致，被测 Agent 视图未变；'
                             '工作树漂移仅记录，不作为「未解决事实已解决」的依据，'
                             '除非先重新发布快照与索引。')
    record['authorization'] = authorization

    output = fresh_directory(output)
    if fresh is not None:
        write_json(output / 'live-observation.json', fresh)
    write_json(output / 'verification.json', record)
    write_json(output / 'manifest.json', {
        'schema_version': 'p2-basis.v1', 'phase': 'P2', 'status': 'VERIFIED',
        'p0_manifest_sha256': record['p0_manifest_sha256'],
        'conclusion': record['conclusion'], 'authorization': authorization,
        'files': {p.name: file_hash(p) for p in output.iterdir() if p.is_file()}})
    return record


def _tag_ids_for_field(facts, field_name):
    return [tid for tid, fact in facts.items() if fact.get('field_name') == field_name]
