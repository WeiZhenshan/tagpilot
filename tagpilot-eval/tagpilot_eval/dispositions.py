"""来源冲突处置记录（收尾清单第 3 项）。

用户声明该项已完成；本模块把已完成的源头处置固化为可审计的 disposition 记录，
并据此生成 p0-v2 事实包。处置只做两件事之一：
1. 有依据地在源头修正（RESOLVED_IN_SOURCE_*）——修改的是语义层 bootstrap 与码值 SQL，
   尚未重新发布快照，因此当前 ACTIVE 快照上的金标仍保持 GAP；
2. 明确接受为提示项或排除出可执行金标，绝不推断口径。
"""
import json
from pathlib import Path

from .io import file_hash, fresh_directory, read_jsonl, write_json, write_jsonl

SCHEMA_VERSION = 'p0-dispositions.v1'

# 来源冲突处置造成的码值分母漂移：工作树已前移，已发布快照未变。
SOURCE_DRIFT = {
    'code_fields': {'published': 177, 'working_tree': 178},
    'code_values': {'published': 1723, 'working_tree': 1725},
    'moved': [{'field': 'CUR_EQUITY_ASSET_UNDER_ALLOCATED_FLAG', 'tag_id': 637,
               'added_codes': ['1', '0'],
               'note': '布尔字段 129→130；快照未重发布，故已发布侧码值仍为 1723。'}],
    'evidence_refs': ['sql/indiv_cust/03_insert_L_INDVCST_LABEL_CODE_MAP_BOOL.sql'],
    'policy': '事实包记录观测时的已发布状态（177/1723）；工作树前移只作处置记录，不回填事实包。',
}

# 源头已修正但未重新发布快照的 9 个 ERROR 阻断项。
_BLOCKING = {
    'P0-0032': ('BUSINESS_SEMANTIC_TYPE_CONFLICT', 637,
                '当前权益类资产缺配标志判为 BOOL（statistic=FLAG），并补齐两条码值；'
                '布尔字段 129→130。',
                ['tagpilot-semantic/tag_semantic/bootstrap/rule_init.py:classify_semantic_type',
                 'tagpilot-semantic/tag_semantic/bootstrap/expert_review.py:review_tag',
                 'sql/indiv_cust/03_insert_L_INDVCST_LABEL_CODE_MAP_BOOL.sql']),
    'P0-0185': ('RATIO_COUNT_CONFLICT', 1073,
                '个贷免息券使用张数是计数不是比例，改判 NUM_COUNT。',
                ['tagpilot-semantic/tag_semantic/bootstrap/expert_review.py:COUPON_COUNT_FIELDS']),
    'P0-0187': ('RATIO_COUNT_CONFLICT', 1076,
                '个贷免息券使用张数是计数不是比例，改判 NUM_COUNT。',
                ['tagpilot-semantic/tag_semantic/bootstrap/expert_review.py:COUPON_COUNT_FIELDS']),
    'P0-0233': ('CONCEPT_MAXIMUM_CONFLICT', 1187,
                '最高/最低属同一指标的不同统计口径；共享概念改为中性名「工薪贷提款利率」，'
                '不再偏向「最高」。',
                ['tagpilot-semantic/tag_semantic/bootstrap/concept_cluster.py:REVIEWED_CONCEPT_OVERRIDES']),
}
# 6 个 CONCEPT_MAXIMUM_CONFLICT 共享同一处置方式。
for _issue, _tag in [('P0-0306', 1282), ('P0-0310', 1291), ('P0-0314', 1305),
                     ('P0-0317', 1308), ('P0-0318', 1311)]:
    _BLOCKING[_issue] = ('CONCEPT_MAXIMUM_CONFLICT', _tag,
                         '期间累计金额与单笔最高金额共享概念；概念改为中性名「同名/异名跨行转入金额」，'
                         '最高/累计由标签 statistics 区分。',
                         ['tagpilot-semantic/tag_semantic/bootstrap/concept_cluster.py:TRANSFER_IN_CONCEPT_OVERRIDES'])

# 期间累计字段：源头已置 statistic=SUM 的 5 个字段。
_ESTAT_PERIOD_RESOLVED = {
    'CUR_YEAR_SAME_NAME_INTERBANK_TRANSFER_IN_AMT',
    'LAST_30_DAYS_DIFF_NAME_INTERBANK_TRANSFER_IN_AMT',
    'LAST_7_DAYS_DIFF_NAME_INTERBANK_TRANSFER_IN_AMT',
    'CUR_MONTH_SAME_NAME_INTERBANK_TRANSFER_IN_AMT',
    'LAST_7_DAYS_SAME_NAME_INTERBANK_TRANSFER_IN_AMT',
}

# 非阻断提示项的类别级处置。
_WARNING_CLASSES = {
    'FIXTURE_DICTIONARY_DRIFT': (
        'ACCEPTED_AS_WARNING_NON_BLOCKING',
        '旧字段字典的 NULL 率与当前仓库 SQL 不一致；fixture SQL 是执行真值来源，'
        '旧字典不是。仅记录差异，不改写来源定义，不据此判定标签错误。'),
    'PERIOD_AMOUNT_STATISTIC_REVIEW': (
        'PARTIALLY_RESOLVED_IN_SOURCE',
        '期间金额的 EOP/SUM 口径需区分。5 个跨行转入金额字段已在源头置 SUM；'
        '其余到期/消费金额字段保持 EOP 并继续登记，不自动改为 SUM。'),
    'NONTRIVIAL_UNIT_SCALE': (
        'EXCLUDED_FROM_AUTO_GOLD',
        'unit_scale=10000 的字段在自动金标里被排除（seeds.good()），'
        '避免把隐含万元倍率当作默认；本题集不生成这些字段的可执行 READY 金标。'),
}


def dispositions(p0_v1):
    """把 p0-v1 的 issue 逐条附上处置结论。"""
    p0_v1 = Path(p0_v1)
    facts = {r['tag_id']: r for r in read_jsonl(p0_v1 / 'facts.jsonl')}
    resolved = []
    for issue in read_jsonl(p0_v1 / 'issues.jsonl'):
        record = {'issue_id': issue['issue_id'], 'tag_id': issue['tag_id'],
                  'code': issue['code'], 'severity': issue['severity']}
        if issue['issue_id'] in _BLOCKING:
            _, tag, rationale, refs = _BLOCKING[issue['issue_id']]
            if tag != issue['tag_id']:
                raise ValueError(f"处置记录与 issue 不一致: {issue['issue_id']}")
            record.update(disposition='RESOLVED_IN_SOURCE_PENDING_REPUBLICATION',
                          rationale=rationale, evidence_refs=refs,
                          gold_impact='仍为 CAPABILITY_GAP：源头修正未重新发布快照，'
                                      '不得据此把校准金标改为 READY')
        elif issue['code'] == 'PERIOD_AMOUNT_STATISTIC_REVIEW':
            field = facts[issue['tag_id']]['field_name']
            if field in _ESTAT_PERIOD_RESOLVED:
                record.update(disposition='RESOLVED_IN_SOURCE_PENDING_REPUBLICATION',
                              rationale='期间累计金额字段已在源头置 statistic=SUM。',
                              evidence_refs=['tagpilot-semantic/tag_semantic/bootstrap/rule_init.py:'
                                             'PERIOD_TRANSFER_IN_AMOUNT_FIELDS'],
                              gold_impact='仍为原口径：快照未重发布。')
            else:
                record.update(disposition=_WARNING_CLASSES['PERIOD_AMOUNT_STATISTIC_REVIEW'][0],
                              rationale=_WARNING_CLASSES['PERIOD_AMOUNT_STATISTIC_REVIEW'][1],
                              evidence_refs=[], gold_impact='不生成 EOP/SUM 二义性的可执行金标。')
        else:
            disposition, rationale = _WARNING_CLASSES[issue['code']]
            record.update(disposition=disposition, rationale=rationale,
                          evidence_refs=[], gold_impact='不阻断；保持提示。')
        resolved.append(record)
    return resolved


def build_p0_v2(p0_v1, output):
    """生成 p0-v2：facts 不变，issues 附处置，新增 dispositions.jsonl 与新版 manifest。"""
    p0_v1, output = Path(p0_v1), Path(output)
    if output.exists():
        raise ValueError('输出目录已存在，请使用新的版本目录')
    for name, sha in json.loads((p0_v1 / 'manifest.json').read_text())['files'].items():
        if file_hash(p0_v1 / name) != sha:
            raise ValueError('p0-v1 工件被修改: ' + name)
    records = dispositions(p0_v1)
    by_issue = {r['issue_id']: r for r in records}
    blocking = [r for r in records if r['severity'] == 'ERROR']
    if len(blocking) != 9:
        raise ValueError('阻断项数量变化，必须重新审查处置记录')
    fresh_directory(output)
    facts = read_jsonl(p0_v1 / 'facts.jsonl')
    issues = []
    for issue in read_jsonl(p0_v1 / 'issues.jsonl'):
        record = by_issue[issue['issue_id']]
        issues.append({**issue, 'status': 'DISPOSED', 'disposition': record['disposition'],
                       'disposition_rationale': record['rationale'],
                       'evidence_refs': record['evidence_refs']})
    write_jsonl(output / 'facts.jsonl', facts)
    write_jsonl(output / 'issues.jsonl', issues)
    write_jsonl(output / 'dispositions.jsonl', records)
    write_json(output / 'source-drift.json', SOURCE_DRIFT)
    (output / 'summary.json').write_text((p0_v1 / 'summary.json').read_text())
    (output / 'live-observation.json').write_text((p0_v1 / 'live-observation.json').read_text())
    source_dir = output / 'sources'
    source_dir.mkdir()
    for gz in sorted((p0_v1 / 'sources').glob('*.gz')):
        (source_dir / gz.name).write_bytes(gz.read_bytes())
    old_manifest = json.loads((p0_v1 / 'manifest.json').read_text())
    manifest = {**old_manifest, 'schema_version': 'p0.v2',
                'supersedes': {'schema_version': old_manifest['schema_version'],
                               'manifest_sha256': file_hash(p0_v1 / 'manifest.json')},
                'dispositions_schema_version': SCHEMA_VERSION,
                'blocking_dispositions': len(blocking),
                'disposition_codes': sorted({r['disposition'] for r in records}),
                'source_drift': SOURCE_DRIFT,
                'files': {p.name: file_hash(p) for p in output.iterdir() if p.is_file()}}
    write_json(output / 'manifest.json', manifest)
    return {'facts': len(facts), 'issues': len(issues), 'dispositions': len(records),
            'blocking': len(blocking)}
