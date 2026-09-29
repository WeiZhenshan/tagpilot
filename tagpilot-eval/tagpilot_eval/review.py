"""独立复核引擎（收尾清单第 1 项）。

两类产出，彼此分离：
- 机械证据：确定性检查，逐题给出可比对的绑定/口径/阈值/码值/资格证据；
- 复核结论：独立复核人（与编写 Agent 不同上下文）对每题给出的 ACCEPT/REVISE/
  QUARANTINE 判定与理由，作为数据文件保存，不由代码自动"宣布正确"。

apply_reviews 只在复核结论为 REVISE 时按显式 patch 改写，QUARANTINE 则移出可执行集。
"""
import json
import re
from collections import Counter
from pathlib import Path

from .contracts import EvalCase
from .io import file_hash, fresh_directory, read_jsonl, write_json, write_jsonl
from .oracle import references

VERDICTS = {'ACCEPT', 'REVISE', 'QUARANTINE'}
_STRIP = re.compile(r'[\s（）()\[\]【】"“”\'’、，,。.：:；;－\-/]')
_PAREN = re.compile(r'[（(][^）)]*[）)]')
# 口径前缀/后缀与标签名的通用尾词；只用于独立复核时的宽松对齐。
_AFFIX = re.compile(r'(当前|历史|未来|最新|本月|上月|上月末|本年|上年|去年|上12个月|近12个月|'
                    r'近\d+天|近\d+个月|T-\d+月末|近\d+年|最近一次|首次|第[一二三四五六七八九十\d]+次)')
_TAIL = re.compile(r'(标志|等级|名称|文本|列表|信息|状态|编号)$')


def _core(text, tail=False):
    value = _STRIP.sub('', _PAREN.sub('', str(text)))
    value = _AFFIX.sub('', value)
    return _TAIL.sub('', value) if tail else value


def _lcs_ratio(core, said):
    """名字核心在话术里按序出现的比例；对插入词、改写语序宽容。"""
    if not core:
        return 1.0
    cursor, hit = 0, 0
    for ch in core:
        found = said.find(ch, cursor)
        if found >= 0:
            hit += 1
            cursor = found + 1
    return hit / len(core)


def _name_rebound(name, requirement):
    """独立复核：原话里能否找到被绑定标签名的核心，而不是信任配方。"""
    core = _core(name, tail=True) or _core(name)
    return _lcs_ratio(core, _core(requirement)) >= 0.75



def _stages(case):
    return [case['expected']] + [t['expected'] for t in case['turns']]


def _predicates(tree):
    if not tree:
        return []
    if tree['kind'] == 'GROUP':
        return [p for c in tree['children'] for p in _predicates(c)]
    if tree['kind'] == 'PREDICATE':
        return [tree]
    return []


def _tag_exprs(tree):
    found = []
    def scan(node):
        if isinstance(node, dict):
            if node.get('kind') == 'TAG':
                found.append(node)
            for value in node.values():
                scan(value)
        elif isinstance(node, list):
            for item in node:
                scan(item)
    scan(tree)
    return found


def _mentions(value, requirement):
    """数值在自然语言里的常见书写形式：原值、万元、百分比、千分位。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    forms = {value, str(int(number)) if number == int(number) else str(number)}
    for scale, suffix in ((10000.0, '万'), (100000000.0, '亿')):
        scaled = number / scale
        forms.add((f'{scaled:g}') + suffix)
        if scaled == int(scaled):
            forms.add(str(int(scaled)) + suffix)
    if 0 < number < 1:
        forms.add(f'{number * 100:g}%')
    return any(form in requirement for form in forms if form)


def mechanical(p0_facts, cases):
    """逐题确定性证据；只报事实，不宣布题意正确。"""
    findings = []
    seen_requirements = Counter(c['requirement'] for c in cases)
    for case in cases:
        flags = []
        targets = set(case['target_tag_ids'])
        eligible = set(case['eligible_tag_ids'])

        def utterance(stage):
            """本题在第 stage 轮时用户可见的全部话术（首轮 + 之前轮次）。"""
            parts = [case['requirement']] + [t['user_message'] for t in case['turns'][:stage]]
            return ''.join(parts).replace(' ', '')

        for stage_index, expected in enumerate(_stages(case)):
            tree = expected.get('tree')
            ready = 'READY' in expected['outcomes']
            said = utterance(stage_index)
            refs = references(tree)
            if tree is not None and not refs <= eligible:
                flags.append({'code': 'ELIGIBILITY_LEAK', 'stage': stage_index,
                              'detail': sorted(refs - eligible)})
            if ready and refs & set(case['forbidden_tag_ids']):
                flags.append({'code': 'FORBIDDEN_IN_TREE', 'stage': stage_index,
                              'detail': sorted(refs & set(case['forbidden_tag_ids']))})
            for expr in _tag_exprs(tree):
                fact = p0_facts.get(expr['tag_id'])
                if not fact:
                    continue
                if expr['field_name'] != fact['field_name']:
                    flags.append({'code': 'FIELD_BINDING', 'stage': stage_index,
                                  'detail': {'tag': fact['tag_id'], 'expr': expr['field_name'],
                                             'fact': fact['field_name']}})
                if expr.get('unit') != fact['published_semantics']['unit']:
                    flags.append({'code': 'UNIT_BINDING', 'stage': stage_index,
                                  'detail': {'tag': fact['tag_id'], 'expr': expr.get('unit'),
                                             'fact': fact['published_semantics']['unit']}})
                if not _name_rebound(fact['name'], said):
                    flags.append({'code': 'NAME_NOT_REBOUND', 'stage': stage_index,
                                  'detail': {'tag': fact['tag_id'], 'name': fact['name'],
                                             'bound_from': fact['source_evidence']['original_matches']}})
            for node in _predicates(tree):
                expr = node['expression']
                if expr['kind'] != 'TAG':
                    continue
                fact = p0_facts.get(expr['tag_id'])
                if not fact:
                    continue
                semantics = fact['published_semantics']
                if ready and node['operator'] not in semantics['allowed_operators']:
                    flags.append({'code': 'UNSUPPORTED_OPERATOR', 'stage': stage_index,
                                  'detail': {'tag': fact['tag_id'], 'operator': node['operator']}})
                if fact['codes'] and node['operator'] not in {'is_null', 'is_not_null'}:
                    codes = {c['code'] for c in fact['codes']}
                    if not set(node['values']) <= codes:
                        flags.append({'code': 'CODE_NOT_IN_MAP', 'stage': stage_index,
                                      'detail': {'tag': fact['tag_id'],
                                                 'values': [v for v in node['values'] if v not in codes]}})
                if ready:
                    expect_caliber = {k: v for k, v in semantics['caliber_struct'].items() if v is not None}
                    if node['caliber'] != expect_caliber:
                        flags.append({'code': 'CALIBER_MISMATCH', 'stage': stage_index,
                                      'detail': {'tag': fact['tag_id']}})
                if ready and node['data_kind'] == 'NUMBER':
                    hit_any = any(_mentions(v, said) for v in node['values'])
                    if not hit_any:
                        flags.append({'code': 'THRESHOLD_NOT_IN_UTTERANCE', 'stage': stage_index,
                                      'detail': {'tag': fact['tag_id'], 'values': node['values']}})
                if ready and fact['codes'] and node['operator'] in {'=', 'in'} \
                        and fact['tag_type'] != '布尔型':
                    definitions = {c['code']: c['definition'] for c in fact['codes']}
                    labels = [v for code in node['values']
                              for v in (code, definitions.get(code, code))]
                    if not any(str(label) in said for label in labels):
                        flags.append({'code': 'CODE_LABEL_NOT_IN_UTTERANCE', 'stage': stage_index,
                                      'detail': {'tag': fact['tag_id'], 'labels': labels}})
                if ready:
                    window = semantics['caliber_struct'].get('time_window_value')
                    if window is not None:
                        unit_word = {'DAY': '天', 'MONTH': '个月', 'YEAR': '年'}.get(
                            semantics['caliber_struct'].get('time_window_unit'), '')
                        if f'近{window}{unit_word}' not in said:
                            flags.append({'code': 'WINDOW_NOT_IN_UTTERANCE', 'stage': stage_index,
                                          'detail': {'tag': fact['tag_id'], 'window': window, 'unit': unit_word}})
            if ready:
                for tag in refs:
                    if p0_facts[tag]['fact_status'] == 'UNRESOLVED':
                        flags.append({'code': 'READY_ON_UNRESOLVED', 'stage': stage_index,
                                      'detail': tag})
        if 'SIM_' in case['requirement']:
            flags.append({'code': 'FIXTURE_LITERAL_IN_UTTERANCE', 'stage': None,
                          'detail': '自然语言中出现模拟数据字面量 SIM_'})
        if seen_requirements[case['requirement']] > 1:
            flags.append({'code': 'REQUIREMENT_TEXT_REUSED', 'stage': None,
                          'detail': seen_requirements[case['requirement']]})
        findings.append({'case_id': case['case_id'], 'category': case['category'],
                         'target_tags': sorted(targets), 'flags': flags})
    return findings


def build_packet(p0, calibration):
    """给独立复核人的紧凑证据包：每题一行关键事实，不替代人工判断。"""
    facts = {r['tag_id']: r for r in read_jsonl(Path(p0) / 'facts.jsonl')}
    cases = read_jsonl(Path(calibration) / 'cases.jsonl')
    findings = {f['case_id']: f for f in mechanical(facts, cases)}
    packet = []
    for case in cases:
        evidence = []
        for tag in sorted(set(case['target_tag_ids']) | set(case['forbidden_tag_ids'])):
            fact = facts.get(tag)
            if not fact:
                continue
            semantics = fact['published_semantics']
            evidence.append({'tag_id': tag, 'field': fact['field_name'], 'name': fact['name'],
                             'type': fact['tag_type'], 'unit': semantics['unit'],
                             'scale': semantics['unit_scale'], 'status': fact['fact_status'],
                             'concept': semantics['concept_name'],
                             'caliber': {k: v for k, v in semantics['caliber_struct'].items() if v is not None},
                             'codes': [c['code'] for c in fact['codes']][:12],
                             'source_line': fact['source_evidence']['original_matches']})
        packet.append({'case_id': case['case_id'], 'category': case['category'],
                       'requirement': case['requirement'], 'domains': case['domains'],
                       'outcomes': case['expected']['outcomes'],
                       'target_tags': case['target_tag_ids'],
                       'forbidden_tags': case['forbidden_tag_ids'],
                       'tree': case['expected'].get('tree'),
                       'required_slots': case['expected'].get('required_slots'),
                       'gap_codes': case['expected'].get('gap_codes'),
                       'turns': [t['user_message'] for t in case['turns']],
                       'truth_basis': case['truth_basis'],
                       'evidence': evidence, 'mechanical_flags': findings[case['case_id']]['flags']})
    return packet


def summarize(packet):
    codes = Counter(flag['code'] for row in packet for flag in row['mechanical_flags'])
    return {'cases': len(packet), 'flagged_cases': sum(1 for r in packet if r['mechanical_flags']),
            'flag_codes': dict(codes)}


def load_reviews(path):
    reviews = {}
    for row in read_jsonl(path):
        if row['verdict'] not in VERDICTS:
            raise ValueError('未知复核结论: ' + str(row['verdict']))
        if not row.get('reviewer') or not row.get('reviewed_at') or not row.get('reason'):
            raise ValueError('复核记录缺少 reviewer/reviewed_at/reason: ' + row['case_id'])
        if row['verdict'] == 'REVISE' and not row.get('patch'):
            raise ValueError('REVISE 必须给出显式 patch: ' + row['case_id'])
        reviews[row['case_id']] = row
    return reviews


def apply_reviews(p0, calibration, reviews_path, output):
    """按复核结论产出 calibration-v2：ACCEPT 保留，REVISE 改话术，QUARANTINE 移出。

    只允许改「表达层」字段（requirement/persona/scenario/truth_basis）；任何触及标准树、
    多轮脚本、目标/资格/事实引用的修改都必须回到配方重新物化，不能在复核环节静默改真值。
    """
    p0, calibration, output = Path(p0), Path(calibration), Path(output)
    reviews = load_reviews(reviews_path)
    cases = read_jsonl(calibration / 'cases.jsonl')
    if {c['case_id'] for c in cases} != set(reviews):
        missing = sorted({c['case_id'] for c in cases} - set(reviews))
        raise ValueError(f'复核未覆盖全部母案例，缺少 {len(missing)} 题: {missing[:5]}')
    cosmetic = {'requirement', 'persona', 'scenario', 'truth_basis'}
    kept, quarantined, revised = [], [], []
    for case in cases:
        review = reviews[case['case_id']]
        if review['verdict'] == 'QUARANTINE':
            quarantined.append({**case, 'quarantine_reason': review['reason']})
            continue
        candidate = dict(case)
        if review['verdict'] == 'REVISE':
            illegal = set(review['patch']) - cosmetic
            if illegal:
                raise ValueError(f'REVISE 只能改表达层字段，收到 {sorted(illegal)}: {case["case_id"]}')
            for key, value in review['patch'].items():
                candidate[key] = value
            revised.append(case['case_id'])
        kept.append(candidate)
    if quarantined:
        raise ValueError('隔离题会破坏 200 题配额；需先重写配方再重新物化，不能静默补数')
    # 重新绑定到新的 P0 包：p0-v2 的 facts 与 p0-v1 逐字节相同，仅新增处置标注，
    # 因此标准树仍然成立；该重绑定在 manifest 中显式记录。
    p0_hash = file_hash(Path(p0) / 'manifest.json')
    for case in kept:
        case['source_manifest_sha256'] = p0_hash
    validated = [EvalCase.model_validate(c).model_dump(exclude_none=True) for c in kept]
    if len(validated) != 200:
        raise ValueError('复核后母案例数不为 200')
    fresh_directory(output)
    write_jsonl(output / 'cases.jsonl', validated)
    write_jsonl(output / 'inputs.jsonl', [{'input_id': c['case_id'], 'requirement': c['requirement'],
                                           'reference_date': c['reference_date'],
                                           'timezone': c['timezone']} for c in validated])
    write_jsonl(output / 'reviews.jsonl', [reviews[c['case_id']] for c in validated])
    # 标准树未变，模拟真值可原样沿用；manifest 记录其来源版本以保可追溯。
    oracle = (calibration / 'oracle-results.jsonl').read_bytes()
    (output / 'oracle-results.jsonl').write_bytes(oracle)
    old = json.loads((calibration / 'manifest.json').read_text())
    manifest = {**old, 'schema_version': 'calibration.v2', 'phase': 'P1', 'status': 'REVIEWED',
                'mother_cases': len(validated),
                'supersedes': {'schema_version': old['schema_version'],
                               'manifest_sha256': file_hash(calibration / 'manifest.json')},
                'p0_manifest_sha256': p0_hash,
                'source_rebind': {'from_manifest_sha256': old['p0_manifest_sha256'],
                                  'to_manifest_sha256': p0_hash,
                                  'reason': 'p0-v2 仅新增冲突处置标注，facts 与 p0-v1 逐字节相同'},
                'independent_model_review': 'COMPLETED',
                'human_review': 'PENDING',
                'review_verdicts': dict(Counter(r['verdict'] for r in reviews.values())),
                'revised_cases': revised,
                'files': {p.name: file_hash(p) for p in output.iterdir() if p.is_file()}}
    write_json(output / 'manifest.json', manifest)
    return {'kept': len(validated), 'revised': revised, 'quarantined': len(quarantined),
            'review_verdicts': manifest['review_verdicts']}
