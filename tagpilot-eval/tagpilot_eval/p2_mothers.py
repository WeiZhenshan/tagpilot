"""P2 母案例配方：500 个确定性母案例（150/125/75/50/50/50）。

与 P1 的关系：复用 `recipe.py` 的同一套语义与不变量，但**不改动 `seeds.py`**——P1 配方的
`authoring_code_sha256` 已记入已审核的 calibration 版本。本模块只产出母案例（variant 0），
表达扩写与真值保持校验在 `p2_variants.py`；分区在 `p2_partition.py`。

不变量（沿用 P1）：未解决事实不得生成 READY 金标；标准任务不得重复；码值与操作符必须在
已发布契约内；单位倍率非 1 的字段不自动生成可执行金标。
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

from .io import digest, file_hash, fresh_directory, read_jsonl, write_json, write_jsonl
from .oracle import fixture_result, references
from .recipe import Recipe, domain_targets, good_fact, raw_identity
from .sources import load_ddl, load_fixture

QUOTAS = {'SINGLE': 150, 'COMPOSITION': 125, 'CLARIFICATION': 75, 'BOUNDARY': 50, 'MULTITURN': 50, 'GAP': 50}
SINGLE_TYPE_QUOTAS = [('数值型', 40), ('布尔型', 30), ('选项型', 40), ('日期型', 25), ('文本型', 15)]
PRODUCTS = [601, 620, 580, 607, 609, 613, 587, 638, 645, 618, 621, 630]
BALANCES = [813, 918, 867, 860, 1006, 994, 804]
AUM = 721

_NUMERIC_LABEL = {'CNY': '10万元', 'RATIO': '50%', 'DAY': '3天', 'MONTH': '3个月',
                  'PERSON': '3个', 'COUNT': '3', 'POINT': '50分', 'SHARE': '3份'}
_NUMERIC_VALUE = {'CNY': '100000', 'RATIO': '0.5', 'POINT': '50'}


def load_context(p0, root):
    """核验 P0 工件与仓库来源 hash，返回母案例生成所需的一切。"""
    p0, root = Path(p0), Path(root)
    manifest = json.loads((p0 / 'manifest.json').read_text())
    for name, sha in manifest['files'].items():
        if file_hash(p0 / name) != sha:
            raise ValueError('P0 工件被修改')
    facts = {r['tag_id']: r for r in read_jsonl(p0 / 'facts.jsonl')}
    ddl_path = root / manifest['sources']['ddl']['path']
    fixture_path = root / manifest['sources']['fixture']['path']
    for key, path in (('ddl', ddl_path), ('fixture', fixture_path)):
        if file_hash(path) != manifest['sources'][key]['sha256']:
            raise ValueError('源数据已变化，必须重新执行 P0')
    rows = load_fixture(fixture_path, load_ddl(ddl_path))
    return {'manifest': manifest, 'facts': facts, 'rows': rows,
            'source_hash': file_hash(p0 / 'manifest.json')}


def _singles(recipe):
    """单标签与码值理解：按类型桶、域均衡轮转选标签，每标签一题。

    布尔标签只取池中未被 COMPOSITION/MULTITURN 使用的那一段，使码值字段覆盖最大化。
    """
    facts = recipe.facts
    excluded = set(_flag_pool(recipe)[0:90])
    need = {'数值型': '>=', '布尔型': '=', '选项型': '=', '日期型': '>', '文本型': 'contains'}
    for tag_type, quota in SINGLE_TYPE_QUOTAS:
        buckets = defaultdict(list)
        for tag_id, fact in sorted(facts.items()):
            if not good_fact(fact) or fact['tag_type'] != tag_type:
                continue
            if tag_type == '布尔型' and tag_id in excluded:
                continue
            if need[tag_type] not in fact['published_semantics']['allowed_operators']:
                continue
            if tag_type == '日期型' and fact['physical_type'] != 'DATE':
                continue
            if tag_type in {'布尔型', '选项型'} and not fact['codes']:
                continue
            if tag_type == '文本型' and 'contains' not in fact['published_semantics']['allowed_operators']:
                continue
            buckets[fact['domain']].append(tag_id)
        targets = domain_targets(buckets, quota)
        selected = []
        for domain in sorted(buckets):
            selected.extend(buckets[domain][:targets[domain]])
        if len(selected) != quota:
            raise ValueError(f'{tag_type} 候选不足')
        for tag_id in selected:
            _add_single(recipe, tag_id, tag_type)


def _add_single(recipe, tag_id, tag_type):
    fact = recipe.facts[tag_id]
    name, unit = fact['name'], fact['published_semantics']['unit']
    if tag_type == '数值型':
        value = _NUMERIC_VALUE.get(unit, '3')
        label = _NUMERIC_LABEL.get(unit, value)
        recipe.add('SINGLE', f'{fact["domain"]}单字段理解', f'帮我找{name}至少{label}的客户。',
                   recipe.ready(recipe.pred(tag_id, '>=', [value])))
    elif tag_type in {'布尔型', '选项型'}:
        code = next((c for c in fact['codes'] if c['code'] == '1'), fact['codes'][0])
        recipe.add('SINGLE', f'{fact["domain"]}单字段理解',
                   f'筛选{name}为“{code["definition"]}”的客户。',
                   recipe.ready(recipe.pred(tag_id, '=', [code['code']])))
    elif tag_type == '日期型':
        recipe.add('SINGLE', f'{fact["domain"]}单字段理解',
                   f'{name}晚于2026年9月1日的客户有哪些？当天不包含。',
                   recipe.ready(recipe.pred(tag_id, '>', ['2026-09-01'])))
    else:
        value = next(r[fact['field_name']] for r in recipe.rows if r[fact['field_name']] is not None)[:30]
        recipe.add('SINGLE', f'{fact["domain"]}单字段理解',
                   f'请找{name}文本中包含“{value}”的客户，按文字包含匹配。',
                   recipe.ready(recipe.pred(tag_id, 'contains', [value])))


_RISK_WORDS = ('C3', 'C4', 'C5')


def _flag_pool(recipe, wanted=None):
    """「为否」类布尔标签池：有 '0' 码值且操作符支持等值；已核数据集里的产品标签优先。

    返回的顺序是确定的，因此各区块按下标切片即可拿到互不重叠的码值字段，扩大覆盖。
    """
    scanned = [tid for tid, f in sorted(recipe.facts.items())
               if f['tag_type'] == '布尔型' and good_fact(f)
               and {'0'} <= {c['code'] for c in f['codes']}
               and '=' in f['published_semantics']['allowed_operators'] and tid not in PRODUCTS]
    pool = [tid for tid in PRODUCTS if tid in recipe.facts] + scanned
    if wanted is None:
        return pool
    if len(pool) < wanted:
        raise ValueError(f'「为否」布尔标签不足：需要 {wanted}，仅 {len(pool)}')
    return pool[:wanted]


def _risk_pool(recipe, wanted):
    """风评等级标签池：码值同时含 C3/C4/C5 的选项型字段。"""
    pool = [tid for tid, f in sorted(recipe.facts.items())
            if f['tag_type'] == '选项型' and good_fact(f)
            and set(_RISK_WORDS) <= {c['code'] for c in f['codes']}]
    if len(pool) < wanted:
        raise ValueError(f'风评标签不足：需要 {wanted}，仅 {len(pool)}')
    return pool[:wanted]


def _ratio_numerators(recipe, wanted):
    """占比分子池：产品持有域的金额型字段（占比为本行明确给出的业务定义）。"""
    pool = [tid for tid, f in sorted(recipe.facts.items())
            if f['domain'] == '产品持有' and f['tag_type'] == '数值型' and good_fact(f)
            and f['published_semantics']['unit'] == 'CNY']
    if len(pool) < wanted:
        raise ValueError(f'占比分子候选不足：需要 {wanted}，仅 {len(pool)}')
    return pool[:wanted]


def _compositions(recipe):
    """多条件与派生表达：显式条件组合、占比与类数；全部条件由用户在题面写明。

    配额：25 + 15 + 12 + 25 + 20 + 7 + 21 = 125。布尔标签池按下标分片，两个区块不重叠。
    """
    pool = _flag_pool(recipe)
    flags = pool[0:25]
    risks = _risk_pool(recipe, 3)
    for tag_id in flags:
        recipe.add('COMPOSITION', '资产门槛与产品空白',
                   f'当前时点AUM至少20万元，并且{recipe.facts[tag_id]["name"]}为否的客户圈出来。',
                   recipe.ready(recipe.group(recipe.pred(AUM, '>=', ['200000']),
                                             recipe.pred(tag_id, '=', ['0']))))
    for product in PRODUCTS[:5]:
        for risk in risks:
            recipe.add('COMPOSITION', '持有状态与指定风评',
                       f'{recipe.facts[product]["name"]}为否，并且{recipe.facts[risk]["name"]}属于C3、C4、C5的客户。',
                       recipe.ready(recipe.group(recipe.pred(product, '=', ['0']),
                                                 recipe.pred(risk, 'in', list(_RISK_WORDS)))))
    for scenario, requirement, tree in _DIRECT_COMPOSITIONS(recipe):
        recipe.add('COMPOSITION', scenario, requirement, recipe.ready(tree))
    thresholds = ['300000', '500000', '800000', '1000000', '1500000']
    for index, tag_id in enumerate(pool[25:50]):
        threshold = thresholds[index % len(thresholds)]
        risk = risks[index % len(risks)]
        recipe.add('COMPOSITION', '资产门槛与产品及指定风评',
                   f'当前时点AUM至少{_wan(threshold)}、{recipe.facts[tag_id]["name"]}为否，'
                   f'并且{_current(recipe.facts[risk]["name"])}为C3或C4。三项同时满足；'
                   '这里只按我给的条件筛选。',
                   recipe.ready(recipe.group(recipe.pred(AUM, '>=', [threshold]),
                                             recipe.pred(tag_id, '=', ['0']),
                                             recipe.pred(risk, 'in', ['C3', 'C4']))))
    numerators = _ratio_numerators(recipe, 20)
    for numerator in numerators:
        recipe.add('COMPOSITION', '显式产品占比',
                   f'当前时点AUM大于0，并且{recipe.facts[numerator]["name"]}除以当前时点AUM达到20%及以上；'
                   '任一数据缺失就排除。',
                   recipe.ready(recipe.group(
                       recipe.pred(AUM, '>', ['0']),
                       recipe.derived({'kind': 'DIV', 'args': [recipe.expr(numerator), recipe.expr(AUM)],
                                       'unit': 'RATIO'}, '>=', ['0.2'], tag_id=AUM))))
    count_conditions = [('=', '1', '恰好1类'), ('>=', '2', '至少2类'), ('>=', '4', '至少4类'),
                        ('<=', '2', '不超过2类'), ('<=', '5', '不超过5类'), ('>=', '1', '至少1类'), ('=', '0', '一类都没有')]
    for operator, value, word in count_conditions:
        recipe.add('COMPOSITION', '显式产品类数',
                   f'当前存款、理财、基金、黄金、国债、信托、价值型保险这七类余额里，余额大于零的有{word}。'
                   '七项有缺失就排除。',
                   recipe.ready(recipe.derived(
                       {'kind': 'COUNT_POSITIVE', 'args': [recipe.expr(t) for t in BALANCES], 'unit': 'COUNT'},
                       operator, [value], caliber={'definition': 'count strictly positive balances',
                                                   'null_policy': 'EXCLUDE'})))
    for scenario, requirement, tree in _NUMERIC_COMPOSITIONS(recipe):
        recipe.add('COMPOSITION', scenario, requirement, recipe.ready(tree))


def _DIRECT_COMPOSITIONS(recipe):
    p = recipe.pred
    g = recipe.group
    return [
        ('理财空白且高价值', '当前没有持有理财，并且当前时点AUM至少100万元。',
         g(p(601, '=', ['0']), p(AUM, '>=', ['1000000']))),
        ('理财或基金持有', '当前持有理财或者当前持有基金，满足一项就保留。',
         g(p(601, '=', ['1']), p(620, '=', ['1']), logic='OR')),
        ('价值与产品任选', '当前时点AUM不少于100万元，并且当前持有理财或基金至少一种。',
         g(p(AUM, '>=', ['1000000']), g(p(601, '=', ['1']), p(620, '=', ['1']), logic='OR'))),
        ('双产品空白', '当前既没有理财也没有基金；两项都要明确为否，不把未知当成否。',
         g(p(601, '=', ['0']), p(620, '=', ['0']))),
        ('指定营销排除', '当前时点AUM至少50万元，排除营销黑名单和勿扰客户；这两项须明确为否。',
         g(p(AUM, '>=', ['500000']), p(662, '=', ['0']), p(536, '=', ['0']))),
        ('渠道任一可达', '手机号正常或已企微认证的客户，任一明确满足即可。',
         g(p(568, '=', ['1']), p(691, '=', ['1']), logic='OR')),
        ('价值与渠道', '当前时点AUM至少20万元，且手机号正常或者已企微认证。AUM条件对两种渠道都生效。',
         g(p(AUM, '>=', ['200000']), g(p(568, '=', ['1']), p(691, '=', ['1']), logic='OR'))),
        ('登录区间', '近30天APP登录至少3天、但不超过10天的客户。',
         g(p(1448, '>=', ['3']), p(1448, '<=', ['10']))),
        ('到期且金额', '以2026年9月18日为基准，最近一笔定期到期日在9月19日至10月18日之间（两端含），'
                   '到期金额至少10万元。',
         g(p(858, 'between', ['2026-09-19', '2026-10-18']), p(859, '>=', ['100000']))),
        ('代发前后', '上月代发金额大于0，本月代发金额不大于0的客户。',
         g(p(1043, '>', ['0']), p(1033, '<=', ['0']))),
        ('两项风险任选', '当前反洗钱黑名单标志为是，或者当前营销黑名单标志为是；这是排查名单。',
         g(p(661, '=', ['1']), p(662, '=', ['1']), logic='OR')),
        ('未持有且低余额', '当前未持有信用卡，且当前时点AUM不足5万元。',
         g(p(580, '=', ['0']), p(AUM, '<', ['50000']))),
    ]


def _NUMERIC_COMPOSITIONS(recipe):
    p = recipe.pred
    g = recipe.group
    c3c4 = ['C3', 'C4']
    return [
        ('历史峰值与产品', '历史最高时点AUM至少100万元，并且当前没有持有理财。',
         g(p(727, '>=', ['1000000']), p(601, '=', ['0']))),
        ('本行口径与产品', '当前时点本行AUM至少50万元，并且当前没有持有基金。',
         g(p(735, '>=', ['500000']), p(620, '=', ['0']))),
        ('活跃与渠道', '近7天APP登录至少3天，并且手机号正常。',
         g(p(1442, '>=', ['3']), p(568, '=', ['1']))),
        ('消费与资产', '上月借记卡消费金额超过1000元，并且当前时点AUM至少30万元。',
         g(p(1175, '>', ['1000']), p(AUM, '>=', ['300000']))),
        ('近7天转入与资产', '近7天异名跨行转入标志为是，并且当前时点AUM至少20万元。',
         g(p(708, '=', ['1']), p(AUM, '>=', ['200000']))),
        ('近30天转入与空白', '近30天异名跨行转入标志为是，并且当前没有持有信用卡。',
         g(p(709, '=', ['1']), p(580, '=', ['0']))),
        ('性别与高价值', '性别为女，并且当前时点AUM至少100万元。',
         g(p(526, '=', ['F']), p(AUM, '>=', ['1000000']))),
        ('行外资产与风评', '行外资产（万元KYC）为第03档，并且当前理财风评为C3、C4或C5。',
         g(p(534, '=', ['03']), p(1466, 'in', list(_RISK_WORDS)))),
        ('代发与基金风评', '本月代发金额大于0，并且当前基金风评为C1或C2。',
         g(p(1033, '>', ['0']), p(1477, 'in', ['C1', 'C2']))),
        ('登录天数与勿扰', '近30天APP登录在3天到10天之间（两端含），并且勿扰客户标志为否。',
         g(p(1448, 'between', ['3', '10']), p(536, '=', ['0']))),
        ('到期区间与金额', '最近一笔定期到期日在2026年9月19日至9月25日之间（两端含），到期金额至少10万元。',
         g(p(858, 'between', ['2026-09-19', '2026-09-25']), p(859, '>=', ['100000']))),
        ('代发与理财空白', '上月代发金额大于0，并且当前没有持有理财。',
         g(p(1043, '>', ['0']), p(601, '=', ['0']))),
        ('反洗钱与资产', '当前反洗钱黑名单标志为是，并且当前时点AUM至少50万元。',
         g(p(661, '=', ['1']), p(AUM, '>=', ['500000']))),
        ('勿扰与认证', '勿扰客户标志为否，并且已企微认证。',
         g(p(536, '=', ['0']), p(691, '=', ['1']))),
        ('黑名单与渠道', '当前营销黑名单标志为否，并且手机号正常。',
         g(p(662, '=', ['0']), p(568, '=', ['1']))),
        ('信用卡与基金空白', '当前持有信用卡，并且当前没有持有基金。',
         g(p(580, '=', ['1']), p(620, '=', ['0']))),
        ('黄金空白与资产', '当前没有持有黄金，并且当前时点AUM至少30万元。',
         g(p(645, '=', ['0']), p(AUM, '>=', ['300000']))),
        ('价值型保险与风评', '当前没有持有价值型保险，并且当前理财风评为C3或C4。',
         g(p(630, '=', ['0']), p(1466, 'in', c3c4))),
        ('基金收益与风评', '当前持仓基金累计收益大于0元，并且当前理财风评为C3或C4。',
         g(p(882, '>', ['0']), p(1466, 'in', c3c4))),
        ('收益率与资产', '当前持仓基金累计收益率至少5%，换算成比例是0.05；并且当前时点AUM至少20万元。',
         g(p(881, '>=', ['0.05']), p(AUM, '>=', ['200000']))),
        ('征信更新与信用卡', '最新征信报告更新日期早于2026年6月1日，并且当前没有持有信用卡。',
         g(p(1484, '<', ['2026-06-01']), p(580, '=', ['0']))),
    ]


def _clarifications(recipe):
    """模糊表达与澄清：缺阈值 25 题 + 未说明时间口径至多 50 题，不足以缺阈值补足到 75。"""
    amounts = [tid for tid, f in sorted(recipe.facts.items())
               if f['tag_type'] == '数值型' and good_fact(f)
               and f['published_semantics']['unit'] in {'CNY', 'COUNT', 'RATIO'}]
    for tag_id in amounts[:25]:
        recipe.add('CLARIFICATION', '未定义比较阈值',
                   f'帮我找{recipe.facts[tag_id]["name"]}比较高的客户，具体门槛还没定。',
                   recipe.clarify(['threshold']), targets=[tag_id])
    pairs = defaultdict(list)
    for tag_id, fact in recipe.facts.items():
        if good_fact(fact) and fact['tag_type'] in {'数值型', '布尔型'}:
            pairs[fact['published_semantics']['concept_id']].append(tag_id)
    ambiguous = []
    for tag_ids in pairs.values():
        if len(tag_ids) < 2:
            continue
        name = recipe.facts[tag_ids[0]]['published_semantics']['concept_name']
        if any(word in name for word in ('当前', '上月', '本月', '上年', '本年', '历史', '最高')):
            continue
        if len({recipe.facts[t]['published_semantics']['caliber_struct'].get('time_anchor_label')
                for t in tag_ids}) < 2:
            continue
        ambiguous.append(sorted(tag_ids))
    for tag_ids in ambiguous[:50]:
        name = recipe.facts[tag_ids[0]]['published_semantics']['concept_name']
        suffix = '为是' if recipe.facts[tag_ids[0]]['tag_type'] == '布尔型' else '超过1000元'
        recipe.add('CLARIFICATION', '未说明时间口径',
                   f'帮我找{name}{suffix}的客户，时间口径还没决定。',
                   recipe.clarify(['time_scope']), targets=tag_ids)
    used = {c['target_tag_ids'][0] for c in recipe.cases}
    filler = [tid for tid in amounts if tid not in used]
    for tag_id in filler:
        if len([c for c in recipe.cases if c['category'] == 'CLARIFICATION']) >= 75:
            break
        recipe.add('CLARIFICATION', '未定义比较阈值',
                   f'找一下{recipe.facts[tag_id]["name"]}偏高的客户，门槛等我确认。',
                   recipe.clarify(['threshold']), targets=[tag_id])
    total = len([c for c in recipe.cases if c['category'] == 'CLARIFICATION'])
    if total != 75:
        raise ValueError(f'澄清题配额未达成：{total}（歧义组 {len(ambiguous)} 个）')


def _multiturns(recipe):
    """多轮维护：追加条件 18 + 改阈值 12 + 删条件 10 + 答澄清 10。"""
    flags = _flag_pool(recipe, None)[50:90]
    for tag_id in flags[:18]:
        first = recipe.pred(AUM, '>=', ['200000'])
        recipe.add('MULTITURN', '追加产品空白', '先找当前时点AUM至少20万元的客户。',
                   recipe.ready(first),
                   turns=[{'user_message': f'在刚才的基础上，再要求{recipe.facts[tag_id]["name"]}为否。',
                           'expected': recipe.ready(recipe.group(first, recipe.pred(tag_id, '=', ['0'])))}])
    for index, tag_id in enumerate(flags[18:30]):
        first = recipe.group(recipe.pred(AUM, '>=', ['200000']), recipe.pred(tag_id, '=', ['0']))
        recipe.add('MULTITURN', '修改阈值保留条件',
                   f'当前时点AUM至少20万元，{recipe.facts[tag_id]["name"]}为否。',
                   recipe.ready(first),
                   turns=[{'user_message': '资产条件改为严格超过50万元，其余保持。',
                           'expected': recipe.ready(recipe.group(recipe.pred(AUM, '>', ['500000']),
                                                               recipe.pred(tag_id, '=', ['0'])))}])
    delete_pool = flags[30:40]
    for tag_id in delete_pool:
        first = recipe.group(recipe.pred(AUM, '>=', ['200000']), recipe.pred(tag_id, '=', ['0']))
        recipe.add('MULTITURN', '删除指定条件',
                   f'当前时点AUM至少20万元，且{recipe.facts[tag_id]["name"]}为否。',
                   recipe.ready(first),
                   turns=[{'user_message': f'去掉{recipe.facts[tag_id]["name"]}这个条件，只保留刚才的资产门槛。',
                           'expected': recipe.ready(recipe.pred(AUM, '>=', ['200000']))}])
    clarify_pool = [AUM, 735, 813, 918, 867, 860, 1006, 994, 804, 1448]
    for tag_id in clarify_pool:
        recipe.add('MULTITURN', '回答阈值澄清',
                   f'找{recipe.facts[tag_id]["name"]}较高的客户，门槛等我确认。',
                   recipe.clarify(['threshold']), targets=[tag_id],
                   turns=[{'user_message': '这里较高明确指大于等于50万元。',
                           'answer_slots': {'threshold': '500000 CNY inclusive'},
                           'expected': recipe.ready(recipe.pred(tag_id, '>=', ['500000']))}])


def _boundaries(recipe):
    """易混淆与边界：阈值上下与相等、端点、NULL/零/负数、枚举未知、单位倍率、口径替换。"""
    p, g, ready = recipe.pred, recipe.group, recipe.ready
    c3c4c5 = ['C3', 'C4', 'C5']
    items = [
        ('严格上界', '当前时点AUM超过50万元，刚好50万元不算。', p(AUM, '>', ['500000']), [735]),
        ('下界严格', '当前时点AUM大于0元，等于0的不算。', p(AUM, '>', ['0']), []),
        ('不足下界', '当前时点AUM不足20万元的客户。', p(AUM, '<', ['200000']), []),
        ('本行范围', '当前时点本行AUM至少50万元，按带“本行”口径的那个指标筛选。', p(735, '>=', ['500000']), [AUM]),
        ('半开区间', '当前时点AUM在20万元至100万元之间，含20万，不含100万。',
         g(p(AUM, '>=', ['200000']), p(AUM, '<', ['1000000'])), []),
        ('历史最高', '历史最高时点AUM至少100万元。', p(727, '>=', ['1000000']), [AUM]),
        ('历史与当前同时满足', '历史持有理财且当前仍持有理财，两个时态都要满足。',
         g(p(579, '=', ['1']), p(601, '=', ['1'])), []),
        ('历史持有当前空白', '历史上持有过理财，但当前没有持有理财；不要拿历史持有当当前持有。',
         g(p(579, '=', ['1']), p(601, '=', ['0'])), []),
        ('近7天标志', '近7天异名跨行转入标志为是。', p(708, '=', ['1']), [709]),
        ('近30天标志', '近30天异名跨行转入标志为是，不要改成近7天。', p(709, '=', ['1']), [708]),
        ('两个期间同时为是', '近7天和近30天异名跨行转入标志都为是。',
         g(p(708, '=', ['1']), p(709, '=', ['1'])), []),
        ('期间标志为否', '近7天异名跨行转入标志为否。', p(708, '=', ['0']), []),
        ('自然月消费', '上月借记卡消费金额超过1000元，用上个自然月的指标。', p(1175, '>', ['1000']), []),
        ('上月代发为负', '上月代发金额小于0元，即发生冲正的客户。', p(1043, '<', ['0']), []),
        ('当前未持有', '当前没有持有理财，未知状态不算没有持有。', p(601, '=', ['0']), [579]),
        ('当前持有且低资产', '当前持有信用卡，且当前时点AUM不足10万元。',
         g(p(580, '=', ['1']), p(AUM, '<', ['100000'])), []),
        ('理财风评', '当前理财风评为C3、C4或C5。', p(1466, 'in', c3c4c5), [1477]),
        ('基金风评', '当前基金风评为C1或C2。', p(1477, 'in', ['C1', 'C2']), [1466]),
        ('双风评交集', '当前理财风评为C1或C2，并且基金风评为C3、C4或C5。',
         g(p(1466, 'in', ['C1', 'C2']), p(1477, 'in', c3c4c5)), []),
        ('否定码值', '当前理财风评不是C1或C2，缺失风评排除。', p(1466, 'not_in', ['C1', 'C2']), []),
        ('基金风评取反', '当前基金风评不属于C1也不属于C2。', p(1477, 'not_in', ['C1', 'C2']), []),
        ('前导零码值', '行外资产（万元KYC）按现有码表第03档筛选，不进行金额近似。', p(534, '=', ['03']), []),
        ('明确枚举集合', '性别是男或女的客户，未知值排除。', p(526, 'in', ['M', 'F']), []),
        ('枚举取反', '性别不是男的客户；等值判断按码值，不做模糊匹配。', p(526, 'not_in', ['M']), []),
        ('日期不含当天', '最新征信报告更新日期早于2026年3月22日，当天不算。', p(1484, '<', ['2026-03-22']), []),
        ('日期端点相等', '最新征信报告更新日期恰好是2026年3月22日的客户。', p(1484, '=', ['2026-03-22']), []),
        ('到期闭区间', '最近一笔定期到期日在2026年9月19日至9月25日之间，两个日期都包含。',
         p(858, 'between', ['2026-09-19', '2026-09-25']), []),
        ('到期端点相等', '最近一笔定期到期日恰好是2026年9月19日的客户。', p(858, '=', ['2026-09-19']), []),
        ('到期单点区间', '最近一笔定期到期日在2026年9月19日这一天；区间两端相同。',
         p(858, 'between', ['2026-09-19', '2026-09-19']), []),
        ('负收益', '当前持仓基金累计收益小于0元。', p(882, '<', ['0']), []),
        ('收益率单位', '当前持仓基金累计收益率至少5%，百分比换成比例是0.05。', p(881, '>=', ['0.05']), []),
        ('收益率上限', '当前持仓基金累计收益率不超过5%，比例口径同样是0.05。', p(881, '<=', ['0.05']), []),
        ('负收益率', '当前持仓基金累计收益率为负，即小于0。', p(881, '<', ['0']), []),
        ('零天与缺失', '近7天APP登录天数不大于0天，不把缺失数据当0天。', p(1442, '<=', ['0']), []),
        ('登录上界为零', '近30天APP登录天数不超过0天。', p(1448, '<=', ['0']), []),
        ('登录区间单点', '近30天APP登录天数恰好等于5天的客户。', p(1448, 'between', ['5', '5']), []),
        ('渠道双否', '手机号不正常，且未企微认证。', g(p(568, '=', ['0']), p(691, '=', ['0'])), []),
        ('营销名单双否', '当前营销黑名单和勿扰客户标志都为否。',
         g(p(662, '=', ['0']), p(536, '=', ['0'])), []),
        ('风险名单任选', '当前反洗钱黑名单标志为是，或者勿扰客户标志为是。',
         g(p(661, '=', ['1']), p(536, '=', ['1']), logic='OR'), []),
        ('活跃或登录上限', '近7天APP登录至少3天，或者近30天APP登录至少5天；任一满足即可。',
         g(p(1442, '>=', ['3']), p(1448, '>=', ['5']), logic='OR'), []),
        ('三条件同时满足', '当前时点AUM至少50万元、当前没有持有基金，并且当前理财风评为C3、C4或C5。',
         g(p(AUM, '>=', ['500000']), p(620, '=', ['0']), p(1466, 'in', c3c4c5)), []),
        ('价值门槛与风评', '当前时点AUM至少100万元，并且当前理财风评为C3。',
         g(p(AUM, '>=', ['1000000']), p(1466, 'in', ['C3'])), []),
        ('消费与认证组合', '上月借记卡消费超过1000元，并且已企微认证。',
         g(p(1175, '>', ['1000']), p(691, '=', ['1'])), []),
        ('到期区间与产品', '最近一笔定期到期日在2026年9月19日至9月25日之间（两端含），'
                     '并且当前没有持有理财。',
         g(p(858, 'between', ['2026-09-19', '2026-09-25']), p(601, '=', ['0'])), []),
        ('精确全集', '圈出这批模拟客户的全部客户，不增加任何经营条件。', {'kind': 'SCOPE_ALL'}, []),
    ]
    for title, requirement, tree, forbidden in items:
        recipe.add('BOUNDARY', title, requirement, ready(tree), forbidden=forbidden)
    for label, requirement, tag_id in _INEXPRESSIBLE_EQUALITY:
        recipe.add('BOUNDARY', '数值精确相等不可表达', requirement,
                   recipe.gap(['CALIBER_UNAVAILABLE'], subjects=[label]), targets=[tag_id])


_INEXPRESSIBLE_EQUALITY = [
    ('当前时点AUM恰好等于50万元', '当前时点AUM恰好等于50万元的客户；必须精确相等，不接受区间近似。', AUM),
    ('上月借记卡消费恰好等于1000元', '上月借记卡消费金额恰好等于1000元的客户；只接受精确相等。', 1175),
    ('本月代发金额恰好为零', '本月代发金额恰好等于0元的客户；只接受精确相等，不接受大于或小于。', 1033),
    ('到期金额恰好为零', '最近一笔定期到期金额恰好等于0元，是有到期记录但金额为零的客户。', 859),
    ('近7天登录天数恰好为零', '近7天APP登录天数恰好等于0天的客户；必须精确相等。', 1442),
]


def _gaps(recipe):
    """能力缺口与资格边界：元数据冲突 9 + 缺明细/缺能力 29 + 不可精确分档 6 + 空值操作符 3 + 资格 3。"""
    facts = recipe.facts
    unresolved = sorted(tid for tid, f in facts.items() if f['fact_status'] == 'UNRESOLVED')
    if len(unresolved) != 9:
        raise ValueError(f'事实冲突数量变化（{len(unresolved)}），必须审查 P2 配方')
    for tag_id in unresolved:
        name = facts[tag_id]['name']
        requirement = (f'请按{name}筛选客户；先核实这个指标的定义是否一致，存在冲突就停止，'
                       '不要自行选一种解释。')
        expectation = recipe.gap(['METADATA_INCOMPLETE'])
        if tag_id == 1291:
            requirement = '帮我圈选近30天异名跨行累计转入至少50万元、当前没有持有理财、理财风评是C3、C4或C5的客户。'
            expectation = recipe.gap(['METADATA_INCOMPLETE'],
                                     tree=recipe.group(recipe.pred(601, '=', ['0']),
                                                       recipe.pred(1466, 'in', ['C3', 'C4', 'C5'])))
        recipe.add('GAP', '元数据口径冲突（B02谱系）' if tag_id == 1291 else '元数据口径冲突',
                   requirement, expectation, targets=[tag_id],
                   basis=['P0审计发现的未解决事实冲突；不能将 REVIEWED 视为事实无冲突'])
    for scenario, requirement in _CAPABILITY_GAPS:
        recipe.add('GAP', scenario, requirement,
                   recipe.gap(['NO_PUBLISHED_CAPABILITY'], subjects=[scenario]),
                   basis=['现有969业务字段与 ACTIVE 能力目录；源文档中出现不等于已发布可查询'])
    for tag_id, label, requirement in [
        (534, '万元KYC严格超过100万元', '行外资产（万元KYC）严格超过100万元，不能把等于100万元的客户算进来，也不接受近似分档。'),
        (535, '运营KYC 55万至90万元', '行外资产（运营KYC）在55万至90万元之间，只接受精确筛选，不能用整个50至100万档替代。'),
        (534, '万元KYC 80万至120万元', '行外资产（万元KYC）在80万至120万元之间，跨了现有两个档位，不能只取其中一档近似。'),
        (535, '运营KYC恰好65万元', '行外资产（运营KYC）恰好等于65万元，只接受精确相等，不接受档位匹配。'),
        (534, '万元KYC严格小于50万元', '行外资产（万元KYC）严格小于50万元，排除等于50万元，也不接受档位近似。'),
        (535, '运营KYC超过150万元', '行外资产（运营KYC）超过150万元，不能用最高档代替精确筛选。'),
    ]:
        recipe.add('GAP', '码值分档无法精确表达', requirement,
                   recipe.gap(['CALIBER_UNAVAILABLE'], subjects=[label]), targets=[tag_id])
    for tag_id, requirement in [
        (1466, '当前理财风评等级为空的客户；不能用不在C1到C5中代替空值判断。'),
        (1477, '当前基金风评等级为空的客户；空值必须显式判断，不能用其它码值组合代替。'),
        (580, '当前是否有信用卡未知（空值）的客户，不能把未知当成持有或未持有。'),
    ]:
        recipe.add('GAP', '缺少空值操作符', requirement,
                   recipe.gap(['NULL_OPERATOR_UNAVAILABLE'],
                              tree=recipe.pred(tag_id, 'is_null', [])), targets=[tag_id])
    for tag_id, requirement in [
        (AUM, '按当前时点AUM至少100万元筛选。若当前没有该指标的可用资格，请说明无法完成，'
              '不要换成另一种资产口径。'),
        (601, '按当前持有理财标志为是筛选。若该标签不在本次可用资格内，请直接说明，'
              '不要改用历史持有标志替代。'),
        (1466, '按当前理财风评为C3或C4筛选。若风评标签不可见，请说明能力不足，'
               '不要用基金风评近似。'),
    ]:
        recipe.add('GAP', '当前资格不包含所需标签', requirement,
                   recipe.gap(['NO_ELIGIBLE_TAG']), targets=[tag_id],
                   forbidden=[tag_id], excluded=[tag_id])


_CAPABILITY_GAPS = [
    ('年龄明细', '找55岁及以上的客户，必须按实际年龄，不使用客户等级代替。'),
    ('基金持仓只数', '找当前只持有一只基金的客户，不能把基金类别数当基金只数。'),
    ('单只基金集中度', '找最大单只基金市值占基金总市值80%以上的客户，需要单只持仓明细。'),
    ('活动转化归因', '找2026年7月指定理财活动已触达但未转化的客户，需要同一活动ID的明细。'),
    ('柜面交易明细', '近30天柜面交易至少3笔的客户，不能拿全渠道交易笔数替代。'),
    ('资金续存明细', '找历史定期到期后实际续存比例至少70%的客户，需要逐笔到期去向。'),
    ('产品风险明细', '找当前持仓基金产品风险高于客户基金风评的客户，需要产品风险等级与持仓明细。'),
    ('持仓成本明细', '找当前持仓基金浮盈超过20%的客户，需要持仓成本与当前市值逐笔明细。'),
    ('交易频次明细', '找近30天理财申赎合计超过5次的客户，需要逐笔申赎流水，不能用持有标志替代。'),
    ('信用卡额度明细', '找当前信用卡额度使用率超过80%的客户，需要授信额度与已用额度明细。'),
    ('贷款还款明细', '找近6个月出现过逾期还款的客户，需要逐期还款状态明细。'),
    ('保险缴费明细', '找近12个月保费拖欠的客户，需要逐期缴费明细，不能用保单状态替代。'),
    ('客户关系明细', '找同一家庭下持有账户数超过3个的客户，需要家庭关系与账户归属明细。'),
    ('渠道偏好明细', '找近90天仅通过柜面办理业务、未使用任何电子渠道的客户，需要分渠道交易明细。'),
    ('产品交叉明细', '找同时持有理财与基金且两支产品到期日相差不超过7天的客户，需要逐支持仓明细。'),
    ('资产峰值时点', '找近12个月内出现过的单日资产峰值超过500万元的客户，需要逐日资产快照。'),
    ('资金流向明细', '找近30天内从他行转入后又全额转出的客户，需要逐笔资金流向明细。'),
    ('代发连续性', '找连续12个月均有代发入账的客户，需要逐月代发明细，不能用上年累计金额替代。'),
    ('消费类别明细', '找近30天餐饮类消费占比超过50%的客户，需要按商户类别拆分的消费明细。'),
    ('积分兑换明细', '找近12个月从未使用过积分的客户，需要积分获取与兑换逐笔明细。'),
    ('理财赎回明细', '找近30天发生部分赎回的客户，需要逐笔赎回明细，不能用当前持有份额变化替代。'),
    ('客户经理轮换', '找近一年内更换过归属客户经理的客户，需要客户经理归属变更明细。'),
    ('产品到期提醒', '找未来30天内理财到期且金额超过100万元的客户，需要逐支持仓与到期日明细。'),
    ('风险事件明细', '找近12个月触发过反欺诈预警的客户，需要预警事件明细与处置结果。'),
    ('渠道活跃明细', '找近30天手机银行登录但未发生任何交易的客户，需要登录与交易两类明细。'),
    ('资产结构明细', '找单一类资产占其总资产超过70%的客户，需要按资产类别拆分的持仓明细。'),
    ('授信审批明细', '找近6个月有一次授信申请被拒记录的客户，需要审批流水明细。'),
    ('产品货架明细', '找当前持有的理财产品均已下架的客户，需要产品状态与持仓明细。'),
    ('客户等级变动', '找近一年内客户等级下调过一级的客户，需要等级评定历史明细。'),
]


# 题面里点名的业务词，必须在目标标签名里能找到（或命中同义映射），否则就是文案与标准树对不上。
# 这条检查的直接动因：配方里把「没有持有黄金」错挂在标签 613（实为个人养老金账户）上。
_BUSINESS_WORDS = {
    '黄金': (), '理财': (), '基金': (), '保险': (), '信用卡': (), '存款': (), '国债': (), '信托': (),
    '手机号': ('手机',), '企微': ('企微', '企业微信'), '代发': (), '征信': (), '反洗钱': (),
    '营销黑名单': ('营销黑名单',), '勿扰': (), '风评': (), '性别': (), '学历': (),
    'AUM': ('AUM', '资产'), '消费': (), '转入': (), '转出': (), '到期': (), '续存': (),
    '积分': (), '额度': (), '逾期': (), '柜面': (), '活动': (), '持仓': (), '明细': (),
}


def audit_requirements(cases, facts):
    """母案例文案与标准树的一致性粗检：题面点名的业务词要能在目标标签里找到。

    这不是硬门禁，而是**发布前的粗筛**：命中就人工看一眼，因为业务词与标签名不可能完全同义。
    """
    findings = []
    for case in cases:
        searchable = []
        for tag in case['target_tag_ids']:
            fact = facts.get(tag)
            if not fact:
                continue
            searchable.append(fact['name'])
            # 业务词也可能出现在码值含义里（例如「本年最高财富收益产品大类 = 基金」），
            # 那是合法的，不算文案与标签对不上。
            searchable += [str(code.get('definition') or '') for code in fact.get('codes') or []]
        joined = ' '.join(searchable)
        for word, synonyms in _BUSINESS_WORDS.items():
            if word not in case['requirement']:
                continue
            accepted = (word, *synonyms)
            if not any(alias in joined for alias in accepted):
                findings.append({'case_id': case['case_id'], 'scenario': case['scenario'],
                                 'word': word, 'target_tags': case['target_tag_ids'],
                                 'target_names': [facts[t]['name'] for t in case['target_tag_ids'] if t in facts]})
                break
    return findings


def _wan(value):
    return f'{int(value) // 10000}万元'


def _current(name):
    """标签名已带时间前缀时不再重复加「当前」，避免出现「当前当前理财风评」。"""
    return name if name.startswith(('当前', '历史', '本月', '上月', '上年', '本年', '近')) else '当前' + name


def _write_package(recipe, output, p0_manifest, authorization, oracle_source):
    if dict(Counter(c['category'] for c in recipe.cases)) != QUOTAS:
        raise ValueError(f'类别配额错误: {dict(Counter(c["category"] for c in recipe.cases))}')
    recipe.assert_no_duplicate_tasks()
    output = fresh_directory(output)
    write_jsonl(output / 'cases.jsonl', recipe.cases)
    write_jsonl(output / 'inputs.jsonl', [
        {'input_id': c['case_id'], 'requirement': c['requirement'],
         'reference_date': c['reference_date'], 'timezone': c['timezone']} for c in recipe.cases])
    gold = []
    for case in recipe.cases:
        stages = [case['expected']] + [t['expected'] for t in case['turns']]
        for stage, expected in enumerate(stages):
            if expected['outcomes'] == ['READY']:
                result = fixture_result(expected['tree'], oracle_source['rows'])
                gold.append({'case_id': case['case_id'], 'stage': stage,
                             'dataset_sha256': p0_manifest['sources']['fixture']['sha256'],
                             'mode': 'INDEPENDENT_PYTHON_ON_REPOSITORY_SQL_FIXTURE',
                             'java_verified': False, 'live_values_verified': False, **result})
    write_jsonl(output / 'oracle-results.jsonl', gold)
    write_json(output / 'manifest.json', {
        'schema_version': 'p2-mothers.v1', 'phase': 'P2', 'status': 'DRAFT',
        'split': 'UNPARTITIONED',
        'mother_cases': len(recipe.cases), 'case_count': len(recipe.cases), 'formal_cases': 0,
        'quotas': QUOTAS,
        'lineage_groups': len({c['lineage_group'] for c in recipe.cases}),
        'p0_manifest_sha256': recipe.source_hash,
        'fixture_sha256': p0_manifest['sources']['fixture']['sha256'],
        'target_tags': len({t for c in recipe.cases for t in c['target_tag_ids']}),
        'authorization': authorization,
        'ai_authoring': 'deterministic recipe over P0 facts + repository fixture',
        'independent_model_review': 'NOT_RUN', 'human_review': 'PENDING',
        'paid_api_calls': 0, 'agent_runs': 0, 'java_execution': False,
        'authoring_code_sha256': {name: file_hash(Path(__file__).parent / name)
                                  for name in ('p2_mothers.py', 'recipe.py', 'contracts.py', 'oracle.py', 'sources.py')},
        'files': {p.name: file_hash(p) for p in output.iterdir() if p.is_file()}})
    return recipe.cases


def build_mothers(p0, root, output, authorization):
    context = load_context(p0, root)
    recipe = Recipe(context['facts'], context['rows'], context['source_hash'])
    _singles(recipe)
    _compositions(recipe)
    _clarifications(recipe)
    _boundaries(recipe)
    _multiturns(recipe)
    _gaps(recipe)
    return _write_package(recipe, output, context['manifest'], authorization, context)
