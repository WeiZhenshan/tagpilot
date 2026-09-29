"""母案例配方原语：与 P1（`seeds.py`）同一套语义，供 P2 复用而不改动 P1 配方。

真值永远由确定性代码从 P0 事实与仓库 fixture 物化；模型只负责表达（见 `p2_variants.py`）。
`seeds.py` 保持不动：它的 `authoring_code_sha256` 已记入已审核的 calibration 版本。
"""
from collections import Counter
from math import sqrt

from .contracts import EvalCase
from .io import digest
from .oracle import references

PERSONA_BY_DOMAIN = {'风险管理': '贷后客户经理', '业务往来': '网点综合客户经理', '渠道管理': '存量客户维护人员'}
DEFAULT_PERSONA = '理财客户经理'
_LINEAGE_OMIT = {'values', 'value', 'user_message', 'answer_slots', 'caliber'}


def lineage_signature(value):
    """去掉数值、词面与口径后的结构签名；同签名视为同谱系（仅换数字不算新母案例）。"""
    if isinstance(value, dict):
        return {k: lineage_signature(v) for k, v in value.items() if k not in _LINEAGE_OMIT}
    if isinstance(value, list):
        return [lineage_signature(v) for v in value]
    return value


def raw_identity(case):
    """不做剥离的任务标识，用于「标准任务不得重复」的硬门。"""
    return digest({'expected': case['expected'], 'turns': case['turns'], 'targets': case['target_tag_ids']})


def good_fact(fact):
    """可自动生成可执行金标的事实：来源可对应且单位倍率为 1。"""
    return (fact['fact_status'] == 'VERIFIED_SOURCE'
            and str(fact['published_semantics']['unit_scale']) in {'1', '1.0', '1.0000'})


def domain_targets(buckets, quota):
    """「50% 域间均衡 + 50% 域内 √标签数 权重」的配额分配，再补足到 quota。"""
    domains = sorted(buckets)
    sizes = {d: len(buckets[d]) for d in domains}
    total_sqrt = sum(sqrt(n) for n in sizes.values()) or 1.0
    weight = {d: 0.5 / len(domains) + 0.5 * sqrt(sizes[d]) / total_sqrt for d in domains}
    targets = {d: min(int(quota * weight[d]), sizes[d]) for d in domains}
    # 先按权重分，再把差额轮转补足（受各域容量限制）
    order = sorted(domains, key=lambda d: (-weight[d], d))
    while sum(targets.values()) < quota:
        progressed = False
        for d in order:
            if sum(targets.values()) >= quota:
                break
            if targets[d] < sizes[d]:
                targets[d] += 1
                progressed = True
        if not progressed:
            raise ValueError(f'候选不足：需要 {quota} 个，仅 {sum(sizes.values())} 个可用')
    return targets


def rotate(buckets, targets):
    """按域轮转取出，避免同域标签连续堆叠。"""
    picked = []
    for domain in sorted(buckets):
        picked.extend(buckets[domain][:targets[domain]])
    return picked


class Recipe:
    """按 P0 事实物化母案例；不执行任何模型或付费调用。"""

    def __init__(self, facts, rows, source_manifest_sha256, first_index=1001, eligible_tag_ids=None):
        self.facts = facts
        self.rows = rows
        self.source_hash = source_manifest_sha256
        self.first_index = first_index
        self.eligible = sorted(eligible_tag_ids if eligible_tag_ids is not None else facts)
        self.cases = []

    @property
    def count(self):
        return len(self.cases)

    def ids(self, index):
        return f'CAL-{self.first_index + index - 1:04d}', f'M-{self.first_index + index - 1:04d}'

    def expr(self, tag_id):
        fact = self.facts[tag_id]
        return {'kind': 'TAG', 'tag_id': tag_id, 'field_name': fact['field_name'],
                'unit': fact['published_semantics']['unit']}

    def data_kind(self, tag_id):
        fact = self.facts[tag_id]
        if fact['codes'] or fact['tag_type'] == '文本型':
            return 'STRING'
        return 'DATE' if fact['tag_type'] == '日期型' else 'NUMBER'

    def caliber(self, tag_id):
        return {k: v for k, v in self.facts[tag_id]['published_semantics']['caliber_struct'].items() if v is not None}

    def pred(self, tag_id, operator, values):
        return {'kind': 'PREDICATE', 'expression': self.expr(tag_id), 'operator': operator,
                'values': [str(v) for v in values], 'data_kind': self.data_kind(tag_id),
                'caliber': self.caliber(tag_id)}

    def derived(self, expression, operator, values, data_kind='NUMBER', caliber=None, tag_id=None):
        """派生条件（比值/计数）。传 tag_id 时口径取自该标签的已发布口径。"""
        return {'kind': 'PREDICATE', 'expression': expression, 'operator': operator,
                'values': [str(v) for v in values], 'data_kind': data_kind,
                'caliber': self.caliber(tag_id) if tag_id is not None else (caliber or {})}

    @staticmethod
    def group(*children, logic='AND'):
        return {'kind': 'GROUP', 'logic': logic, 'children': list(children)}

    @staticmethod
    def ready(tree):
        return {'outcomes': ['READY'], 'tree': tree}

    @staticmethod
    def clarify(required_slots):
        return {'outcomes': ['NEEDS_USER_INPUT'], 'required_slots': list(required_slots)}

    @staticmethod
    def gap(gap_codes, tree=None, subjects=None):
        expectation = {'outcomes': ['CAPABILITY_GAP'], 'gap_codes': list(gap_codes)}
        if tree is not None:
            expectation['tree'] = tree
        if subjects:
            expectation['gap_subjects'] = list(subjects)
        return expectation

    def add(self, category, scenario, requirement, expected, targets=None, turns=None,
            forbidden=None, excluded=None, basis=None, variant_index=0):
        index = self.count + 1
        refs = references(expected.get('tree'))
        for turn in turns or []:
            refs |= references(turn['expected'].get('tree'))
        target_ids = sorted(set(targets or []) | refs)
        unresolved = [f'TAG:{t}' for t in target_ids if self.facts[t]['fact_status'] == 'UNRESOLVED']
        if 'READY' in expected['outcomes'] and unresolved:
            raise ValueError('未解决事实不得生成 READY 金标')
        final = (turns or [{'expected': expected}])[-1]['expected']
        domains = sorted({self.facts[t]['domain'] for t in target_ids}) or ['能力边界']
        case_id, mother_id = self.ids(index)
        case = {
            'schema_version': 'eval-case.v2',
            'case_id': case_id, 'mother_id': mother_id,
            'lineage_group': 'LIN-' + digest({'expected': lineage_signature(expected),
                                              'turns': lineage_signature(turns or []),
                                              'targets': target_ids})[:16],
            'phase': 'P2', 'split': 'UNPARTITIONED', 'status': 'DRAFT',
            'category': category, 'persona': PERSONA_BY_DOMAIN.get(domains[0], DEFAULT_PERSONA),
            'scenario': scenario, 'domains': domains, 'requirement': requirement,
            'fact_ids': [f'TAG:{t}' for t in target_ids], 'target_tag_ids': target_ids,
            'forbidden_tag_ids': list(forbidden or []),
            'eligible_tag_ids': [t for t in self.eligible if t not in (excluded or [])],
            'source_manifest_sha256': self.source_hash, 'expected': expected, 'turns': list(turns or []),
            'truth_basis': list(basis or ['P0来源事实与已发布字段契约；阈值为本题用户显式条件，不是通用业务默认值']),
            'unresolved_fact_ids': unresolved,
            'l3_status': 'FIXTURE_ORACLE_AVAILABLE' if final['outcomes'] == ['READY'] else 'NOT_APPLICABLE',
            'variant_index': variant_index, 'variant_mode': 'TEMPLATE',
        }
        self.cases.append(EvalCase.model_validate(case).model_dump(exclude_none=True))
        return self.cases[-1]

    def assert_no_duplicate_tasks(self):
        identities = Counter(raw_identity(c) for c in self.cases)
        collisions = [key for key, n in identities.items() if n > 1]
        if collisions:
            groups = {}
            for case in self.cases:
                if raw_identity(case) in collisions:
                    groups.setdefault(raw_identity(case), []).append(case['case_id'])
            raise ValueError('标准任务重复，不能充当新的母案例: ' + repr(list(groups.values())))
