"""P2 分区：按谱系把母案例分配给 DEV / REGRESSION / HOLDOUT，并做跨分区污染检查。

方案 §二.4：分区在表达扩写**之前**完成；隔离单位是**母案例谱系**，不是问题行。
跨分区发现近重复时整组重新分配，证据不删除，只发 supersede 链。

沿用方案的「谱系 + 标准语义签名」口径，并把它做严一层：隔离键是
`(谱系组, 话术模板签名)`。只看谱系组的话，同一套话术模板（例如「当前时点AUM至少X，并且Y为否」）
会散落到不同分区，留出集就不再与开发集独立；把模板族整体分配到同一分区，留出集才成立。
"""
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from .io import digest, file_hash, fresh_directory, read_jsonl, write_json, write_jsonl
from .validation import verify_package

SPLITS = (('DEV', 0.70), ('REGRESSION', 0.20), ('HOLDOUT', 0.10))
NEAR_DUP_THRESHOLD = 0.82
MIN_REGRESSION_MOTHERS = 100
_DIGITS = re.compile(r'\d+')
# 模板中的量词与判定词：只换这些词不改变条件结构，属方案 §二.4 的「同一条件结构仅换数字」，
# 因此一并遮罩，避免同一话术模板跨分区。
_TEMPLATE_FILLERS = ('不超过', '不少于', '不晚于', '及以上', '或以上', '恰好', '至少', '超过',
                     '不足', '大于', '小于', '等于', '早于', '晚于', '为否', '为是')


def trajectory(case):
    return ' '.join([case['requirement'], *[turn['user_message'] for turn in case['turns']]])


def template_signature(case, names):
    """把目标/辨析标签名、数字以及量词判定词替换成占位符，得到话术模板签名。"""
    text = trajectory(case)
    for tag_id in sorted(set(case['target_tag_ids']) | set(case['forbidden_tag_ids'])):
        name = names.get(tag_id)
        if name:
            text = text.replace(name, '«标签»')
    text = _DIGITS.sub('#', text)
    for word in sorted(_TEMPLATE_FILLERS, key=len, reverse=True):
        text = text.replace(word, '«量»')
    return text


def isolation_keys(cases, names):
    """隔离键：谱系组 + 话术模板签名。同键的案例必须落在同一分区。"""
    return {case['case_id']: (case['lineage_group'], template_signature(case, names))
            for case in cases}


def assign_splits(keys, proportions=SPLITS):
    """按隔离键摘要排序后按比例切分；确定、可复现、比例精确。

    REGRESSION 取上整，保证回归集不因四舍五入掉到下限以下；HOLDOUT 取剩余。
    """
    ordered = sorted(set(keys), key=lambda key: digest(str(key)))
    total = len(ordered)
    dev_end = round(total * 0.70)
    regression_end = min(total, dev_end + math.ceil(total * 0.20))
    assigned = {}
    for key in ordered[:dev_end]:
        assigned[key] = 'DEV'
    for key in ordered[dev_end:regression_end]:
        assigned[key] = 'REGRESSION'
    for key in ordered[regression_end:]:
        assigned[key] = 'HOLDOUT'
    return assigned


def _shingles(text, size=3):
    stripped = ''.join(text.split())
    return {stripped[i:i + size] for i in range(max(0, len(stripped) - size + 1))}


def similarity(left, right):
    left_shingles, right_shingles = _shingles(left), _shingles(right)
    if not left_shingles or not right_shingles:
        return 0.0
    return len(left_shingles & right_shingles) / len(left_shingles | right_shingles)


def cross_partition_checks(cases, keys, threshold=NEAR_DUP_THRESHOLD):
    """跨分区检查：结构泄漏（必须为零）与模板相似（诊断）。

    隔离键相同却落在不同分区即结构性泄漏；话术模板相同但真值不同的案例，仍按词面相似度诊断记录。
    """
    buckets = defaultdict(list)
    for case in cases:
        buckets[case['split']].append(case)
    leaks, template_pairs, compared = [], [], 0
    names = sorted(buckets)
    for index, left_name in enumerate(names):
        for right_name in names[index + 1:]:
            for left in buckets[left_name]:
                for right in buckets[right_name]:
                    compared += 1
                    if keys[left['case_id']] == keys[right['case_id']]:
                        leaks.append({'left': left['case_id'], 'right': right['case_id'],
                                      'left_split': left_name, 'right_split': right_name})
                        continue
                    score = similarity(trajectory(left), trajectory(right))
                    if score >= threshold:
                        template_pairs.append({'left': left['case_id'], 'right': right['case_id'],
                                               'left_split': left_name, 'right_split': right_name,
                                               'similarity': round(score, 4)})
    return {'pairs_compared': compared, 'cross_partition_key_leaks': leaks,
            'cross_partition_template_similar_pairs': template_pairs}


def partition(p0, mothers, output, authorization):
    mothers, output = Path(mothers), Path(output)
    manifest = verify_package(mothers)
    facts = {r['tag_id']: r for r in read_jsonl(Path(p0) / 'facts.jsonl')}
    names = {tag_id: fact['name'] for tag_id, fact in facts.items()}
    cases = read_jsonl(mothers / 'cases.jsonl')
    if any(case['split'] != 'UNPARTITIONED' for case in cases):
        raise ValueError('母案例包已含分区，不能重复分区')
    keys = isolation_keys(cases, names)
    key_split = assign_splits(set(keys.values()))
    for case in cases:
        case['split'] = key_split[keys[case['case_id']]]

    checks = cross_partition_checks(cases, keys)
    if checks['cross_partition_key_leaks']:
        raise ValueError('隔离键跨分区，必须整组重新分配: '
                         + json.dumps(checks['cross_partition_key_leaks'][:5], ensure_ascii=False))

    by_split = Counter(case['split'] for case in cases)
    mothers_by_split = Counter(c['split'] for c in {c['mother_id']: c for c in cases}.values())
    lineage_by_split = Counter(c['split'] for c in {c['lineage_group']: c for c in cases}.values())
    categories = {name: dict(Counter(c['category'] for c in cases if c['split'] == name))
                  for name, _ in SPLITS}
    if mothers_by_split['REGRESSION'] < MIN_REGRESSION_MOTHERS:
        raise ValueError(f"REGRESSION 母案例不足 {MIN_REGRESSION_MOTHERS}：{mothers_by_split['REGRESSION']}")

    partition_index = digest(sorted((str(key), split) for key, split in key_split.items()))
    output = fresh_directory(output)
    write_jsonl(output / 'cases.jsonl', cases)
    # 分区不改写真值：无答案输入与离线真值原样带过来，保持包自洽。
    for carried in ('inputs.jsonl', 'oracle-results.jsonl'):
        if (mothers / carried).exists():
            (output / carried).write_bytes((mothers / carried).read_bytes())
    write_json(output / 'partition.json', {
        'schema_version': 'p2-partition.v1',
        'proportions_target': {name: share for name, share in SPLITS},
        'isolation_key': 'lineage_group + masked template signature',
        'isolation_keys': len(key_split),
        'split_by_isolation_key': {str(key): split for key, split in sorted(key_split.items(), key=lambda kv: str(kv[0]))},
        'cases_by_split': dict(by_split),
        'mothers_by_split': dict(mothers_by_split),
        'lineage_groups_by_split': dict(lineage_by_split),
        'categories_by_split': categories,
        **checks,
        'near_duplicate_threshold': NEAR_DUP_THRESHOLD,
        'partition_sha256': partition_index})
    write_json(output / 'manifest.json', {
        'schema_version': 'p2-split.v1', 'phase': 'P2', 'status': 'PARTITIONED',
        'mother_cases': len(cases), 'case_count': len(cases), 'formal_cases': 0,
        'split': 'ASSIGNED', 'splits': sorted(by_split),
        'quotas': manifest['quotas'], 'p0_manifest_sha256': manifest['p0_manifest_sha256'],
        'partition_sha256': partition_index, 'isolation_keys': len(key_split),
        'supersedes': {'schema_version': manifest['schema_version'],
                       'description': '分区是母案例之上的确定分配，不改写任何真值'},
        'authorization': authorization,
        'files': {p.name: file_hash(p) for p in output.iterdir() if p.is_file()}})
    return {'cases': len(cases), 'splits': dict(by_split), 'mothers_by_split': dict(mothers_by_split),
            'lineage_groups_by_split': dict(lineage_by_split), 'isolation_keys': len(key_split),
            'partition_sha256': partition_index,
            'cross_partition_key_leaks': len(checks['cross_partition_key_leaks']),
            'template_similar_pairs': len(checks['cross_partition_template_similar_pairs']),
            'pairs_compared': checks['pairs_compared']}
