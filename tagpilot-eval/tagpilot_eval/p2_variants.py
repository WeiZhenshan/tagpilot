"""P2 表达扩写：确定性真值不变，只换中文表达。

三类校验，各自只证明自己声称的东西：
1. **边界词 lint（确定性，无模型）**：数字/单位/操作符词/码值是否仍然对得上，以及澄清题是否
   泄漏了被扣留的门槛。这是**矛盾检查**，不是「必须出现原标签名」检查——同义改写是合法的。
2. **独立回译（模型，全新上下文，不给母树）**：只给原话与候选标签清单，要求还原条件；
   与母树做 `oracle.normalized` **含口径**比较，再跑边界探针。派生条件（占比/类数）无法这样还原，
   如实标 `BACK_TRANSLATION_NOT_APPLICABLE`，只靠第 1 类校验。
3. **隔离**：最多修 2 次，仍失败则进隔离账本，不无限重试凑数。

表达扩写不改写真值：母案例的标准树、轮次脚本、目标与禁止标签、资格都原样继承。
"""
import json
import re
from collections import Counter, defaultdict
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .contracts import EvalCase
from .io import digest, file_hash, fresh_directory, read_jsonl, write_json, write_jsonl
from .llm import Budget, LlmClient, load_config
from .oracle import boundary_rows, normalized, references
from .p2_partition import similarity
from .validation import verify_package

VARIANTS_PER_MOTHER = 4
BATCH_SIZE = 200
MAX_REPAIRS = 2
# 该端点的 deepseek-flash 是**推理模型**：reasoning_content 也计入 max_tokens，
# 预算给得太小会让可见回答整段为空（内容被推理吃光），表现为大量「空输出」重试。
# 因此上限给足；账本单独记 reasoning_tokens，成本口径不受影响。
GENERATION_MAX_TOKENS = 1500
# 回译保留推理，而推理 token 计入 max_tokens：实测嵌套多条件题的推理可达 2500–4000 token，
# 上限给 1200 会整段为空，给 3000 会在边缘反复失败（同一题不同次调用长度会浮动）。
BACK_TRANSLATION_MAX_TOKENS = 6000
BACK_TRANSLATION_ATTEMPTS = 3
BACK_TRANSLATION_NUDGE = ('\n\n上一次输出不是 JSON。只输出一个 JSON 对象，'
                          '第一个字符必须是 {，不要任何解释或代码块标记。')
# 本端点接受 `reasoning_effort: none`（实测 completion 从 218 降到 12 token）。
# 只对**改写**关掉推理：它是纯表达任务，省下的推理不影响真值；
# 回译是真值保持的**校验**环节，弱校验比多花钱更糟，因此回译保留推理。
GENERATION_EXTRA = {'reasoning_effort': 'none'}
# 只拦「几乎逐字重复」：受约束的短需求（标签名、时间口径、阈值都必须保留）天然共享大量词面，
# 把阈值定低会把合法改写误判成雷同。句式多样性只作诊断统计，不作硬门禁。
SIBLING_SIMILARITY_LIMIT = 0.97
STYLES = (
    ('正式书面语气：用「凡…的客户」「请筛选…」这类完整句式',
     '凡上年12月保险购买金额不低于10万元的客户，请筛选出来。'),
    ('口语提问式：用「有没有…」「我想看看…」这类完整问句',
     '有没有上年12月保险购买金额在10万元以上的客户？'),
    ('业务目标式：一句话说明经营目的，再接筛选条件',
     '我要做一场保险客户回访，需要上年12月保险购买金额在10万元及以上的客户。'),
)

OPERATOR_WORDS = {
    # 形如「达到或超过」「大于或等于」是 >= 的合法中文表达，必须整体遮罩，
    # 否则里面的「超过」「大于」会被当成与 >= 矛盾。
    '>=': {'required': ('达到或超过', '大于或等于', '等于或大于', '达到或高于', '高于或等于',
                        '以上', '至少', '不少于', '不低于', '不小于', '及以上'),
           'forbidden': ('超过', '大于', '高于', '多于', '不足', '小于', '低于', '不超过', '至多', '恰好', '等于')},
    '>': {'required': ('超过', '大于', '高于', '多于'),
          'forbidden': ('至少', '不少于', '不低于', '以上', '不超过', '小于', '不足', '恰好')},
    '<=': {'required': ('不超过', '至多', '不大于', '以下', '不高于', '最多',
                        '小于或等于', '低于或等于'),
           'forbidden': ('超过', '大于', '高于', '至少', '不少于', '小于', '不足', '恰好')},
    '<': {'required': ('小于', '不足', '低于', '少于'),
          'forbidden': ('超过', '大于', '以上', '至少', '不少于', '不低于', '不超过', '恰好')},
    '=': {'required': ('恰好', '等于', '正好'),
          'forbidden': ('超过', '大于', '小于', '不足', '至少', '不超过', '以上', '以下')},
    'between': {'required': ('之间', '区间', '至', '到'), 'forbidden': ('恰好',)},
    'in': {'required': ('属于', '为', '是', '任何一个'), 'forbidden': ()},
    'not_in': {'required': ('不属于', '不是', '排除'), 'forbidden': ()},
    'contains': {'required': (), 'forbidden': ()},
    'is_null': {'required': ('为空', '缺失', '没有值'), 'forbidden': ()},
}

GENERATE_SYSTEM = ('你是银行客户经理圈选需求的复述助手。你只负责中文表达改写，'
                   '绝不改变任何业务条件：不新增条件、不删减条件、不降低精度。只输出改写后的需求句。')
BACK_TRANSLATE_SYSTEM = ('你是圈选需求解析器。只输出 JSON，不要解释。'
                         '值只用数字或码值本身，不要带单位、千分位或货币符号。')

BACK_TRANSLATE_OPERATORS = {'等于': '=', '大于': '>', '大于等于': '>=', '不小于': '>=', '小于': '<',
                            '小于等于': '<=', '不大于': '<=', '区间': 'between', '介于': 'between',
                            '属于': 'in', '不属于': 'not_in', '包含': 'contains', '为空': 'is_null'}


def _leaves(tree, out=None):
    out = [] if out is None else out
    if not tree:
        return out
    if tree['kind'] == 'GROUP':
        for child in tree['children']:
            _leaves(child, out)
    elif tree['kind'] == 'PREDICATE':
        out.append(tree)
    return out


def _number_forms(value, unit=None):
    """一个数值在中文里可被合法写出的形式集合。

    比例字段的树里存的是小数（`0.5`），但人话写的是百分数（`50%`），两种形式都必须接受。
    """
    forms = set()
    try:
        number = Decimal(value)
    except InvalidOperation:
        return forms
    text = format(number.normalize(), 'f')
    forms.add(text)
    if number == number.to_integral_value():
        forms.add(str(int(number)))
    for scale, suffix in ((Decimal(10000), '万'), (Decimal(100000000), '亿')):
        if number != 0 and number % scale == 0:
            quotient = (number / scale).normalize()
            forms.add(format(quotient, 'f') + suffix)
    if unit == 'RATIO':
        percent = format((number * 100).normalize(), 'f')
        forms.add(percent + '%')
        forms.add(percent + '％')
    if number == number.to_integral_value() and 0 <= number <= 99:
        numeral = _chinese_numeral(int(number))
        if numeral:
            forms.add(numeral)
    return forms


_CN_DIGITS = '零一二三四五六七八九'
# 窗口名的等价说法：改写常把「近30天」写成「最近一个月」。
_WINDOW_SPECIAL = {
    '近7天': ('近一周', '最近一周', '过去一周', '近7日', '近一星期'),
    '近30天': ('近一个月', '最近一个月', '过去一个月', '近30日', '近1个月', '近一月'),
    '近3天': ('最近三天', '过去三天', '近3日'),
    '近3个月': ('近三个月', '最近三个月', '近一个季度', '近3月'),
    '近12个月': ('近一年', '最近一年', '过去一年', '近12月', '近十二个月'),
    '上月': ('上个月', '上一个自然月', '上一个月', '前一个月'),
    '本月': ('这个月', '本自然月', '当月'),
    '上年': ('上一年', '去年', '上一年度'),
    '本年': ('今年', '本年度', '当年'),
    '历史': ('历史上', '过往', '曾经', '此前'),
}


def _chinese_numeral(number):
    """0–99 的中文写法，供「近三十天」这类表达使用。"""
    if number < 0 or number > 99:
        return None
    tens, ones = divmod(number, 10)
    if tens == 0:
        return _CN_DIGITS[ones]
    prefix = '十' if tens == 1 else _CN_DIGITS[tens] + '十'
    return prefix if ones == 0 else prefix + _CN_DIGITS[ones]


def window_forms(label):
    """窗口口径的等价说法集合。"""
    forms = {label}
    for prefix, alias in (('近', '最近'), ('近', '过去'), ('上年', '去年'),
                          ('本月', '这个月'), ('上月', '上个月')):
        if label.startswith(prefix):
            forms.add(alias + label[len(prefix):])
    forms |= set(_WINDOW_SPECIAL.get(label, ()))
    return forms


_UNCERTAINTY_MARKERS = ('什么', '多少', '还没', '未定', '待定', '您定', '帮我定', '门槛', '口径',
                        '标准', '确定', '左右', '具体', '怎样', '希望', '请说明', '定一下',
                        '哪段', '多高', '多长', '多久', '未明确', '由您', '给我一个')
# 澄清题必须仍指向**同一个**缺失维度：把「缺门槛」改写成「缺时间口径」就是换了题意。
_SLOT_SIGNALS = {
    'threshold': ('门槛', '标准', '多少', '多高', '多低', '具体', '数值', '水平', '比', '以上',
                  '高于', '低于', '不低于', '金额', '额度', '界定'),
    'time_scope': ('时间', '口径', '什么时候', '哪段', '哪一', '周期', '期间', '近', '最近',
                   '本月', '上月', '年', '月', '天', '季度', '时点', '历史'),
}
# 能力缺口题的改写必须仍让人看出「这里做不到／有冲突」，否则等于把缺口悄悄补平了。
_GAP_SIGNALS = ('冲突', '不一致', '无法', '不能', '不可', '不得', '缺少', '缺失', '不存在', '没有该',
                '需要明细', '请确认', '待确认', '口径', '不可表达', '近似', '不能用', '证据不足',
                '不确定', '不明确', '未明确', '待定', '不清楚', '未知', '无对应', '取不到', '拿不到',
                '没有明细', '凭现有', '怎么算', '如何算', '怎么定义', '如何界定', '怎么对应',
                '说清', '定义', '算不清')
# 用户话术里不应出现评测控制面的内部记号（终态名、操作符名、字段名）。
_INTERNAL_TOKENS = ('CAPABILITY_GAP', 'NEEDS_USER_INPUT', 'PARTIAL', 'SCOPE_ALL', 'COUNT_POSITIVE',
                    'DERIVED_PREDICATE', 'TAG_PREDICATE', 'is_null', 'is_not_null', 'null_policy',
                    'schema_version', 'expected_caliber')


# 「类数」派生条件里「大于零」是计数定义本身（统计余额为正的类目数），不是对计数值的比较。
COUNT_POSITIVE_PHRASES = ('余额大于零', '大于零元', '大于零', '大于0', '不为零', '非零', '为正')
_TIME_PREFIXES = ('当前时点', '当前', '历史', '本月', '上月', '上年', '本年', '近')


def _name_stem(fact):
    """布尔标志的「名称主干」：去掉时间前缀与「标志」二字。

    「当前持有基金标志 = 0」在中文里写作「当前没有持有基金」——没有出现码值也没有出现「否」，
    只有标签主干。此时值由独立回译校验，lint 不该因为找不到码值字面量就判缺失。
    """
    stem = str(fact['name']).replace('标志', '')
    for prefix in _TIME_PREFIXES:
        if stem.startswith(prefix):
            stem = stem[len(prefix):]
            break
    return stem


def _is_boolean_flag(fact):
    return fact['tag_type'] == '布尔型' and sorted(code['code'] for code in fact.get('codes') or []) == ['0', '1']


def _code_forms(value, fact):
    """码值在中文里可被合法写出的形式：码值本身，或它在码表里的中文含义。

    码表里的定义可能自带量词（例如「50万以下」「无经验(1年以下)」），这些词**不是**操作符声明；
    调用方会把它们整体遮罩，避免被当成与操作符矛盾。全角/半角括号两种写法都要给出。
    """
    forms = {value}
    for code in fact.get('codes') or []:
        if code['code'] != value or not code.get('definition'):
            continue
        definition = str(code['definition'])
        forms.add(definition)
        for variant in (definition.replace('（', '(').replace('）', ')'),
                        definition.replace('(', '（').replace(')', '）')):
            forms.add(variant)
        for variant in (definition, definition.replace('（', '(').replace('）', ')')):
            forms |= {part for part in variant.split('(') if part}
            forms |= {part for part in variant.split('（') if part}
    return forms


def boundary_lint(case, utterance, facts):
    """返回矛盾清单；只报「与标准树矛盾」或「必需的量值标记缺失」。

    这是**矛盾检查**而非「必须出现原标签名」检查：同义改写（例如把「当前时点AUM」写成
    「截至目前资产管理规模」）是合法的，标签身份由独立回译验证。
    """
    violations = []
    for token in _INTERNAL_TOKENS:
        if token in utterance:
            violations.append({'code': 'INTERNAL_TOKEN_LEAK', 'token': token})
    leaves = _leaves(case['expected'].get('tree'))
    if case['expected']['outcomes'] == ['CAPABILITY_GAP']:
        # 缺口题的条件里本就有「刻意排除在树外」的项（例如口径冲突的那个标签），
        # 所以逐叶子的量值/码值/操作符检查不适用——题面本来就会提到树里没有的条件。
        # 要守的是**相对**的：母案例带了缺口信号，改写就不能把它说没；母案例本身就是
        # 普通请求（用户并不知道做不到），就不能要求改写去补一个用户没说过的信号。
        if any(signal in case['requirement'] for signal in _GAP_SIGNALS) \
                and not any(signal in utterance for signal in _GAP_SIGNALS):
            violations.append({'code': 'GAP_SIGNAL_LOST'})
        return violations
    window_labels = {leaf.get('caliber', {}).get('time_anchor_label') for leaf in leaves}
    window_labels.discard(None)
    code_vocab = set()
    for leaf in leaves:
        expression = leaf['expression']
        if expression['kind'] != 'TAG':
            continue
        fact = facts[expression['tag_id']]
        for value in leaf['values']:
            if leaf['data_kind'] == 'NUMBER':
                forms = _number_forms(value, expression.get('unit'))
                if forms and not any(form in utterance for form in forms):
                    violations.append({'code': 'THRESHOLD_MISSING',
                                       'tag_id': expression['tag_id'], 'value': value})
            elif leaf['data_kind'] == 'STRING':
                forms = _code_forms(value, fact)
                if _is_boolean_flag(fact):
                    stem = _name_stem(fact)
                    if len(stem) >= 2:
                        forms.add(stem)
                code_vocab |= forms
                if not any(form in utterance for form in forms):
                    violations.append({'code': 'CODE_MISSING',
                                       'tag_id': expression['tag_id'], 'value': value})
    # 取**所有**叶子的操作符，含派生条件：派生条件的操作符词（例如「及以上」对应 >=）
    # 若不计入，就会被当成另一个叶子（例如 AUM>0 的 >）的矛盾。
    # 多个操作符共存时，歧义词自然落进 allowed 而不报矛盾——每个条件的操作符由独立回译分别校验。
    operators = {leaf['operator'] for leaf in leaves}
    allowed = {word for operator in operators for word in OPERATOR_WORDS.get(operator, {}).get('required', ())}
    forbidden = {word for operator in operators for word in OPERATOR_WORDS.get(operator, {}).get('forbidden', ())} - allowed
    # 先把「合法词」与「码值标签」整体遮掉再找「矛盾词」：
    # 否则「不低于」里的「低于」、码值定义「50万以下」里的「以下」都会被误判成矛盾。
    # 派生的「类数」条件会把「大于零」写进句子里，那是它的定义，不是操作符声明。
    derived_vocab = {phrase for leaf in leaves if leaf['expression']['kind'] == 'COUNT_POSITIVE'
                     for phrase in COUNT_POSITIVE_PHRASES}
    masked = utterance
    for word in sorted(allowed | code_vocab | derived_vocab, key=len, reverse=True):
        masked = masked.replace(word, '«量»')
    for word in sorted(forbidden, key=len, reverse=True):
        if word in masked:
            violations.append({'code': 'OPERATOR_CONTRADICTION', 'word': word,
                               'operators': sorted(operators)})
    if len(window_labels) == 1:
        label = next(iter(window_labels))
        if label.startswith('近') or label in {'上月', '本月', '上年', '本年', '历史'}:
            if not any(form in utterance for form in window_forms(label)):
                violations.append({'code': 'WINDOW_MISSING', 'label': label})
    if case['expected']['outcomes'] == ['NEEDS_USER_INPUT']:
        for slot in case['expected'].get('required_slots') or []:
            signals = _SLOT_SIGNALS.get(slot)
            if signals and not any(signal in utterance for signal in signals):
                violations.append({'code': 'SLOT_DIMENSION_LOST', 'slot': slot})
        for leaf in leaves:
            for value in leaf['values']:
                if any(form in utterance for form in _number_forms(value)):
                    violations.append({'code': 'WITHHELD_THRESHOLD_LEAKED', 'value': value})
        if not any(marker in utterance for marker in _UNCERTAINTY_MARKERS):
            violations.append({'code': 'CLARIFICATION_SIGNAL_LOST'})
    return violations


def _render_conditions(case, facts, names):
    """把母树渲染成人可读的条件行，供改写提示使用。"""
    lines = []
    for leaf in _leaves(case['expected'].get('tree')):
        expression = leaf['expression']
        if expression['kind'] == 'TAG':
            name = names.get(expression['tag_id'], f"标签{expression['tag_id']}")
            caliber = leaf.get('caliber') or {}
            window = caliber.get('time_anchor_label')
            lines.append(f"- {name} {leaf['operator']} {'、'.join(leaf['values'])}"
                         + (f"（时间口径 {window}）" if window else ''))
        else:
            lines.append(f"- 派生条件 {expression['kind']} {leaf['operator']} {'、'.join(leaf['values'])}")
    if not lines:
        lines.append(f"- 终态要求：{case['expected']['outcomes'][0]}，不得给出结论性条件")
    return '\n'.join(lines)


def generate_prompt(case, facts, names, variant_index):
    constraints = [
        '所有数字、单位与百分比必须原样保留，不得换算成别的量级。',
        '所有码值必须原样或按其中文含义出现，不得替换成其它档位。',
        '时间口径词必须保留（例如 近7天 不得写成 近30天）。',
        '必须包含所有条件，不得新增或删去任何条件。',
        '不要给出执行结果、人数或建议。',
        '必须是完整通顺的中文句子；不得写「帮找下」「筛下」这类残缺缩略表达。',
        '要与常规写法有明显不同的句式，不能只加一个礼貌前缀。',
        '整句控制在 60 个字以内。',
        '不得出现任何内部记号或英文枚举名（例如 CAPABILITY_GAP、COUNT_POSITIVE、is_null、派生条件）。'
        '这些是系统内部说法，客户经理不会这么说。',
    ]
    if case['expected']['outcomes'] == ['NEEDS_USER_INPUT']:
        constraints.append('用户没有给出具体门槛，改写后仍不得给出任何具体数字门槛。')
    if case['expected']['outcomes'] == ['CAPABILITY_GAP']:
        constraints.append('必须让读者看出该需求存在定义冲突、缺明细或无法精确表达，不得自行选一种解释。')
    style, example = STYLES[(variant_index - 1) % len(STYLES)]
    return (f'原话：{case["requirement"]}\n\n'
            f'必须保持不变的条件：\n{_render_conditions(case, facts, names)}\n\n'
            f'硬性约束：\n' + '\n'.join(f'  {c}' for c in constraints) +
            f'\n\n改写风格：{style}。\n风格示例（仅示范句式，条件以本题为准）：{example}'
            f'\n只输出一句或两句中文需求，不要任何解释、编号或前后缀。')


def back_translate_prompt(case, utterance, candidates):
    listing = '\n'.join(f'  {tag_id}: {name}' for tag_id, name in candidates)
    return (f'候选标签清单：\n{listing}\n\n用户需求：{utterance}\n\n'
            '请还原该需求的条件，输出 JSON：\n'
            '{"logic":"AND 或 OR","conditions":[{"tag_id":整数,"operator":"'
            + '/'.join(sorted(set(BACK_TRANSLATE_OPERATORS))) +
            '","values":[字符串]}],"time_scope":"原文里的时间口径词，没有就空字符串"}\n'
            '只输出 JSON。值只用数字，不要单位。range 条件用两个值。')


def parse_json_object(text):
    start, end = text.find('{'), text.rfind('}')
    if start < 0 or end <= start:
        raise ValueError('回译输出不是 JSON')
    return json.loads(text[start:end + 1])


_NUMERIC_TEXT = re.compile(r'(-?\d+(?:\.\d+)?)\s*(亿|万)?')
_SCALES = {'亿': Decimal(100000000), '万': Decimal(10000)}


def _coerce_value(raw, leaf_data_kind, fact):
    text = str(raw).strip()
    if leaf_data_kind == 'NUMBER':
        # 回译会写成「100万元」「20万」「50%」等，取前导数字与量级词即可，其余单位字忽略。
        match = _NUMERIC_TEXT.search(text)
        if not match:
            raise ValueError(f'回译的数值无法解析：{raw!r}')
        try:
            number = Decimal(match.group(1))
        except InvalidOperation as error:
            raise ValueError(f'回译的数值无法解析：{raw!r}') from error
        scale = _SCALES.get(match.group(2))
        if scale is not None:
            number *= scale
        # 比例字段：树里存小数（0.5），回译常写「50%」或干脆写「50」，都要归一到小数。
        if fact['published_semantics'].get('unit') == 'RATIO':
            percent = ('%' in text) or ('％' in text)
            if percent or (scale is None and number > 1):
                return _plain(number / 100)
        return _plain(number)
    # 字符串：把中文含义映射回码值，否则「为是」会与码值 '1' 比不相等。
    for code in fact.get('codes') or []:
        definition = str(code.get('definition') or '')
        forms = {code['code'], definition}
        forms |= {part for part in definition.replace('（', '(').split('(') if part}
        if text in forms:
            return code['code']
    return text


def _plain(number):
    return str(int(number)) if number == number.to_integral_value() else format(number.normalize(), 'f')


def reconstruct_tree(payload, facts):
    """把回译结果还原成本契约的树；无法还原时抛错。

    模型会自然地给出**嵌套**结构（AND 里套 OR），所以按节点递归还原，不做扁平化假设。
    """
    return _reconstruct_node(payload, facts)


def _reconstruct_node(payload, facts):
    if not isinstance(payload, dict):
        raise ValueError('回译节点不是对象')
    conditions = payload.get('conditions')
    if conditions is not None:
        if not conditions:
            raise ValueError('回译的分组为空')
        children = [_reconstruct_node(item, facts) for item in conditions]
        if len(children) == 1:
            return children[0]
        logic = 'OR' if str(payload.get('logic', 'AND')).upper() == 'OR' else 'AND'
        return {'kind': 'GROUP', 'logic': logic, 'children': children}
    if 'tag_id' not in payload:
        raise ValueError('回译的条件缺少 tag_id')
    tag_id = int(payload['tag_id'])
    if tag_id not in facts:
        raise ValueError(f'回译引用了不存在的标签 {tag_id}')
    operator = BACK_TRANSLATE_OPERATORS.get(str(payload.get('operator')).strip())
    if operator is None:
        raise ValueError(f'回译操作符无法识别：{payload.get("operator")}')
    fact = facts[tag_id]
    data_kind = 'STRING' if fact['codes'] or fact['tag_type'] == '文本型' \
        else 'DATE' if fact['tag_type'] == '日期型' else 'NUMBER'
    values = [_coerce_value(value, data_kind, fact) for value in payload.get('values') or []]
    return {'kind': 'PREDICATE',
            'expression': {'kind': 'TAG', 'tag_id': tag_id, 'field_name': fact['field_name'],
                           'unit': fact['published_semantics']['unit']},
            'operator': operator, 'values': values, 'data_kind': data_kind,
            'caliber': {k: v for k, v in fact['published_semantics']['caliber_struct'].items()
                        if v is not None}}


def back_translation_verdict(mother_tree, payload, facts, rows=None):
    """含口径的规范树比较 + 边界探针。不通过则给出原因。

    澄清题与缺口题**没有标准树**，回译无从比对——这类题由「不泄漏门槛 + 仍带不确定信号」的
    lint 把关，这里如实标 `BACK_TRANSLATION_NOT_APPLICABLE`。
    """
    if mother_tree is None or not _leaves(mother_tree):
        # 没有标准树（澄清题、缺口题）或没有任何叶子（全客群 SCOPE_ALL）：回译无从比对。
        return {'status': 'BACK_TRANSLATION_NOT_APPLICABLE', 'reason': '本题没有可比对的条件叶子'}
    if any(leaf['expression']['kind'] != 'TAG' for leaf in _leaves(mother_tree)):
        return {'status': 'BACK_TRANSLATION_NOT_APPLICABLE',
                'reason': '母树含派生条件，无法用标签/操作符/值还原'}
    try:
        reconstructed = reconstruct_tree(payload, facts)
    except (ValueError, KeyError) as error:
        return {'status': 'FAIL', 'reason': f'回译无法还原：{error}'}
    try:
        if normalized(mother_tree) != normalized(reconstructed):
            return {'status': 'FAIL', 'reason': '规范树不一致（含口径）',
                    'mother_normalized': normalized(mother_tree),
                    'back_normalized': normalized(reconstructed)}
        if rows and boundary_rows(mother_tree) != boundary_rows(reconstructed):
            return {'status': 'FAIL', 'reason': '边界探针不一致'}
    except (ValueError, KeyError) as error:
        # 回译给出的结构本身不合法（例如为空值判定带了值），算校验失败而不是让异常掀掉整批。
        return {'status': 'FAIL', 'reason': f'回译结构无法规范化：{error}'}
    return {'status': 'PASS'}


def candidate_list(case, facts, names, extra=8):
    """候选标签清单：目标与辨析标签 + 同域干扰项，构成真实选择。"""
    chosen = list(dict.fromkeys([*case['target_tag_ids'], *case['forbidden_tag_ids']]))
    domains = {facts[t]['domain'] for t in chosen if t in facts}
    distractors = [tag_id for tag_id, fact in sorted(facts.items())
                   if fact['domain'] in domains and tag_id not in chosen]
    return [(tag_id, names[tag_id]) for tag_id in chosen + distractors[:extra]]


def make_variant(mother, utterance, variant_index, verdict):
    """按母案例派生一条改写；真值、轮次脚本、资格全部继承，只换原话与出处标记。"""
    ordinal = int(mother['case_id'].split('-')[1]) - 1000
    case = deepcopy(mother)
    case.update({'case_id': f'CAL-{3000 + (ordinal - 1) * 3 + variant_index:04d}',
                 'variant_index': variant_index,
                 'variant_mode': 'MODEL_PARAPHRASE',
                 'mother_requirement_sha256': digest(mother['requirement']),
                 'requirement': utterance,
                 'provenance': {**mother.get('provenance', {}),
                                'authoring': 'MODEL_EXPRESSION_FROM_DETERMINISTIC_TRUTH'}})
    return EvalCase.model_validate(case).model_dump(exclude_none=True)


def acceptance_problems(utterance, violations, verdict, peers, limit=SIBLING_SIMILARITY_LIMIT):
    """统一的接受条件：无边界矛盾、有回译结论且非 FAIL、且不与同族雷同。

    回译 FAIL 必须算问题；否则「无 lint 矛盾但回译不通过」会被误收进数据集。
    """
    problems = list(violations)
    if not problems and (verdict is None or verdict['status'] == 'FAIL'):
        problems.append({'code': 'BACK_TRANSLATION_FAILED',
                         'reason': (verdict or {}).get('reason', '缺少回译结论')})
    if not problems and peers and max(similarity(utterance, peer) for peer in peers) >= limit:
        problems.append({'code': 'SIBLING_TOO_SIMILAR'})
    return problems


def slot_key(identifier, variant_index):
    """断点键：把母案例 id（CAL-1001）与母 id（M-1001）都归一到同一数字段。

    曾经这里用 `row['case_id']`（改写自己的编号）做键，而跳过判断用的是母案例编号，
    两者永不相等，于是**每次续跑都会重跑已完成的切片并追加重复行**。统一归一到数字段即可。
    """
    return (str(identifier).split('-')[-1], variant_index)


def sibling_peers(existing_rows):
    """同族比较基准：**只含已接受的改写**，不含母案例原话。

    改写与它要复述的原话本就该相似；把原话放进基准会让忠实改写被判成雷同。
    这里要防的是同一母案例的三条改写互相几乎一样。
    """
    peers = defaultdict(list)
    for row in existing_rows:
        peers[row['mother_id']].append(row['requirement'])
    return peers


def recover_quarantined(p0, cases_dir, variants_dir, root, sdk_cap_usd, authorization=None):
    """用修好的校验器复查隔离记录：表达式没错、只是校验器误判的切片直接恢复。

    只对**纯 lint 误判**的切片恢复，且**不重新生成表达式**——原句本来是对的，
    只是被误判；这里补跑当时被短路掉的回译，把结论补齐。仍不通过的原样留在隔离里。
    """
    p0, cases_dir, variants_dir = Path(p0), Path(cases_dir), Path(variants_dir)
    facts = {r['tag_id']: r for r in read_jsonl(p0 / 'facts.jsonl')}
    names = {tag_id: fact['name'] for tag_id, fact in facts.items()}
    mothers = {case['case_id']: case for case in read_jsonl(cases_dir / 'cases.jsonl')}
    quarantine_path = variants_dir / 'quarantine.jsonl'
    rows = _rows(quarantine_path)
    if not rows:
        return {'recovered': 0, 'still_quarantined': 0, 'checked': 0}
    existing = _rows(variants_dir / 'variants.jsonl')
    accepted = sibling_peers(existing)
    # 已接受的切片不再恢复：否则恢复路径会绕过断点键，把同一 (母案例, 变体号) 追加两次。
    accepted_slots = {slot_key(row['mother_id'], row['variant_index']) for row in existing}
    budget = Budget(variants_dir / 'budget-ledger.jsonl', sdk_cap_usd)
    client = LlmClient(load_config(root), budget)
    (variants_dir / 'quarantine-before-recovery.jsonl').write_text(
        ''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows))

    recovered, still = [], []
    for row in rows:
        mother = mothers.get(row['case_id'])
        utterance = row.get('utterance') or ''
        if mother is None or len(utterance) < 5:
            still.append({**row, 'recovery': 'NO_USABLE_UTTERANCE'})
            continue
        if slot_key(mother['case_id'], row['variant_index']) in accepted_slots:
            still.append({**row, 'recovery': 'ALREADY_ACCEPTED'})
            continue
        problems = boundary_lint(mother, utterance, facts)
        if problems:
            still.append({**row, 'recovery': 'STILL_FAILS_LINT', 'violations': problems})
            continue
        if back_translation_applicable(mother):
            try:
                payload = back_translate(client, mother, utterance, facts, names)
                verdict = back_translation_verdict(mother['expected'].get('tree'), payload, facts)
            except BackTranslationUnavailable as error:
                verdict = {'status': 'BACK_TRANSLATION_UNAVAILABLE', 'reason': str(error)}
            except (ValueError, KeyError) as error:
                verdict = {'status': 'FAIL', 'reason': f'回译不可用：{error}'}
        else:
            verdict = {'status': 'BACK_TRANSLATION_NOT_APPLICABLE',
                       'reason': '本题没有可比对的标准树'}
        problems = acceptance_problems(utterance, [], verdict, accepted[mother['mother_id']])
        if problems:
            still.append({**row, 'recovery': 'STILL_FAILS_CHECKS', 'violations': problems})
            continue
        variant = make_variant(mother, utterance, row['variant_index'], verdict)
        _append(variants_dir / 'variants.jsonl', {**variant, 'back_translation': verdict['status'],
                                                  'recovered_from_quarantine': True})
        accepted[mother['mother_id']].append(utterance)
        accepted_slots.add(slot_key(mother['case_id'], row['variant_index']))
        recovered.append(row['case_id'])
    quarantine_path.write_text(''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n'
                                       for row in still))
    return {'recovered': len(recovered), 'still_quarantined': len(still), 'checked': len(rows),
            'recovered_case_ids': recovered, 'budget': budget.totals(), 'authorization': authorization}


def revalidate_variants(p0, cases_dir, variants_dir, authorization=None):
    """对**已接受**的改写重跑确定性校验（无模型调用，不花钱）。

    用途：校验器后来加强了（例如新增「不得泄漏内部记号」），已产出的改写要按新规则复查，
    不合格的移入 `quarantine-revalidated-v1.jsonl` 留档，不留在数据集里充数。
    """
    p0, cases_dir, variants_dir = Path(p0), Path(cases_dir), Path(variants_dir)
    facts = {r['tag_id']: r for r in read_jsonl(p0 / 'facts.jsonl')}
    mothers = {case['case_id']: case for case in read_jsonl(cases_dir / 'cases.jsonl')}
    variants_path = variants_dir / 'variants.jsonl'
    rows = _rows(variants_path)
    keep, rejected = [], []
    for row in rows:
        case = mothers.get(row['mother_id'].replace('M-', 'CAL-'))
        problems = boundary_lint(case, row['requirement'], facts) if case else \
            [{'code': 'MOTHER_NOT_FOUND'}]
        if problems:
            rejected.append({**case_fields_light(row), 'violations': problems,
                             'reason': '按加强后的校验器复查不合格'})
        else:
            keep.append(row)
    if not rejected:
        return {'checked': len(rows), 'rejected': 0, 'kept': len(rows)}
    (variants_dir / 'variants-before-revalidation.jsonl').write_text(
        ''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows))
    with (variants_dir / 'quarantine-revalidated-v1.jsonl').open('a') as handle:
        for row in rejected:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
    keep.sort(key=lambda row: row['case_id'])
    variants_path.write_text(''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n'
                                     for row in keep))
    return {'checked': len(rows), 'rejected': len(rejected), 'kept': len(keep),
            'authorization': authorization}


def case_fields_light(row):
    return {key: value for key, value in row.items() if key != 'back_translation'}


def dedupe_variants(variants_dir):
    """修复历史续跑造成的重复：每个 (mother_id, variant_index) 只保留第一条。

    重复行不删除，移入 `quarantine-duplicate-slots.jsonl` 留档，原文件另存一份 `.bak`，
    这样「曾经重复过」这件事本身有据可查。
    """
    variants_dir = Path(variants_dir)
    variants_path = variants_dir / 'variants.jsonl'
    rows = _rows(variants_path)
    keep, seen = [], {}
    duplicates = []
    for row in rows:
        key = slot_key(row['mother_id'], row['variant_index'])
        if key in seen:
            duplicates.append(row)
        else:
            seen[key] = row['case_id']
            keep.append(row)
    if not duplicates:
        return {'rows': len(rows), 'kept': len(rows), 'duplicates': 0}
    (variants_dir / 'variants-before-dedupe.jsonl').write_text(
        ''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows))
    with (variants_dir / 'quarantine-duplicate-slots.jsonl').open('a') as handle:
        for row in duplicates:
            handle.write(json.dumps(
                {'case_id': row['case_id'], 'mother_id': row['mother_id'],
                 'variant_index': row['variant_index'], 'utterance': row['requirement'],
                 'violations': [{'code': 'DUPLICATE_SLOT',
                                 'kept': seen[slot_key(row['mother_id'], row['variant_index'])]}],
                 'reason': '续跑键错误导致同一 (母案例, 变体号) 被重复生成；保留首条，本行留档'},
                ensure_ascii=False, sort_keys=True) + '\n')
    keep.sort(key=lambda row: row['case_id'])
    variants_path.write_text(''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n'
                                     for row in keep))
    return {'rows': len(rows), 'kept': len(keep), 'duplicates': len(duplicates)}


def _append(path, row):
    with Path(path).open('a') as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')


def _repair_note(problems, verdict):
    notes = [json.dumps(problem, ensure_ascii=False) for problem in problems]
    if verdict and verdict.get('status') == 'FAIL' and verdict.get('reason'):
        notes.append(f"独立回译不一致：{verdict['reason']}")
    return '；'.join(notes) if notes else '改写在语义上不等价'


class BackTranslationUnavailable(ValueError):
    """回译在预算内没有产出可比对的结构（推理吃满 token），重试也不会更好。

    这类切片**不是**模型答错：它通过了边界词 lint，只是拿不到独立的回译比对。
    交由后续覆盖全部正式案例的独立 AI 复核去判断，并在清单里如实计数。
    """


def back_translation_applicable(case):
    """这道题能不能用回译做结构比对。

    不能的三种：澄清题没有标准树；缺口题的标准树**刻意不完整**（冲突标签被排除在外）；
    全客群题没有任何条件叶子。它们由各自的 lint 把关，不该记成「回译失败」。
    """
    expected = case['expected']
    if expected['outcomes'] == ['CAPABILITY_GAP']:
        return False
    tree = expected.get('tree')
    return tree is not None and bool(_leaves(tree))


def back_translate(client, case, utterance, facts, names):
    """回译：模型没给出可解析 JSON 时重试（那是格式问题，不是语义不符）。

    生成路径与隔离恢复路径都用这一个，避免两处各写一遍、其中一处忘了重试。
    """
    last_error, exhausted = None, False
    for attempt in range(BACK_TRANSLATION_ATTEMPTS):
        prompt = back_translate_prompt(case, utterance, candidate_list(case, facts, names))
        if attempt:
            prompt += BACK_TRANSLATION_NUDGE
        reply = client.complete('back_translation', BACK_TRANSLATE_SYSTEM, prompt,
                                max_tokens=BACK_TRANSLATION_MAX_TOKENS)
        try:
            return parse_json_object(reply['text'])
        except ValueError as error:
            last_error = error
            if reply.get('finish_reason') == 'length' and not reply['text'].strip():
                exhausted = True
                break
    if exhausted:
        raise BackTranslationUnavailable('回译推理吃满 token，未产出可比对结构')
    raise ValueError(f'回译输出不可解析：{last_error}')


def _attempt(client, case, facts, names, variant_index, limit_note='', attempts=3):
    """生成 + 校验；返回 (utterance, violations, verdict, finish_reason)。

    空输出不是「语义违规」而是生成失败，直接重试，不要把它记成隔离。
    """
    prompt = generate_prompt(case, facts, names, variant_index)
    if limit_note:
        prompt += f'\n\n上一次改写的问题：{limit_note}\n请针对性重写，其余保持不变。'
    result = client.complete('paraphrase', GENERATE_SYSTEM, prompt,
                            max_tokens=GENERATION_MAX_TOKENS, extra=GENERATION_EXTRA)
    utterance = result['text'].strip().strip('“”"').strip()
    if len(utterance) < 5 and attempts > 0:
        return _attempt(client, case, facts, names, variant_index, limit_note, attempts - 1)
    violations = boundary_lint(case, utterance, facts)
    if violations:
        return utterance, violations, None, result.get('finish_reason')
    if not back_translation_applicable(case):
        # 澄清题 / 缺口题 / 全客群题：不发起回译调用，也不把「无从比对」记成失败。
        return utterance, violations, {'status': 'BACK_TRANSLATION_NOT_APPLICABLE',
                                       'reason': '本题没有可比对的标准树（澄清题／缺口语义冲突的缺口题／全客群题）'}, \
            result.get('finish_reason')
    try:
        reply = back_translate(client, case, utterance, facts, names)
    except BackTranslationUnavailable as error:
        verdict = {'status': 'BACK_TRANSLATION_UNAVAILABLE', 'reason': str(error)}
        return utterance, violations, verdict, result.get('finish_reason')
    except ValueError as error:
        return utterance, [], {'status': 'FAIL', 'reason': str(error)}, result.get('finish_reason')
    verdict = back_translation_verdict(case['expected'].get('tree'), reply, facts)
    return utterance, violations, verdict, result.get('finish_reason')


def generate_variants(p0, splits, output, authorization, root, sdk_cap_usd,
                      limit=None, token_cap=None, call_cap=None):
    """为分区后的母案例生成模型改写；分批追加、可续跑、预算硬停。"""
    p0, splits, output = Path(p0), Path(splits), Path(output)
    manifest = verify_package(splits)
    facts = {r['tag_id']: r for r in read_jsonl(p0 / 'facts.jsonl')}
    names = {tag_id: fact['name'] for tag_id, fact in facts.items()}
    mothers = read_jsonl(splits / 'cases.jsonl')

    resuming = (output / 'variants.jsonl').exists()
    if resuming:
        variants_path = output / 'variants.jsonl'
    else:
        if output.exists():
            raise ValueError('输出目录已存在')
        output.mkdir(parents=True)
        variants_path = output / 'variants.jsonl'
        variants_path.touch()
    budget = Budget(output / 'budget-ledger.jsonl', sdk_cap_usd, token_cap=token_cap, call_cap=call_cap)
    client = LlmClient(load_config(root), budget)

    existing = _rows(variants_path)
    quarantined_rows = _rows(output / 'quarantine.jsonl')
    done = {slot_key(row['mother_id'], row['variant_index']) for row in existing}
    done |= {slot_key(row['case_id'], row['variant_index']) for row in quarantined_rows}
    accepted = sibling_peers(existing)
    generated, quarantined, stopped = 0, 0, None
    for mother in mothers:
        # 同族集合只装**已接受的改写**：母案例原话不进去。
        # 改写与它要复述的原话本就该相似，拿原话当雷同基准会误杀忠实改写。
        def evaluate(utterance, violations, verdict):
            return acceptance_problems(utterance, violations, verdict, accepted[mother['mother_id']])

        for variant_index in range(1, VARIANTS_PER_MOTHER):
            if limit is not None and generated >= limit:
                stopped = 'LIMIT'
                break
            stopped = budget.stop_reason() or stopped
            if stopped:
                break
            if (slot_key(mother['case_id'], variant_index)) in done:
                continue
            try:
                utterance, violations, verdict, finish = _attempt(client, mother, facts, names,
                                                                 variant_index)
                problems = evaluate(utterance, violations, verdict)
                for _ in range(MAX_REPAIRS):
                    if not problems:
                        break
                    utterance, violations, verdict, finish = _attempt(
                        client, mother, facts, names, variant_index, _repair_note(problems, verdict))
                    problems = evaluate(utterance, violations, verdict)
            except Exception as error:
                # 单题的任何异常都不得掀掉整批：记成隔离并继续，长跑才靠得住。
                quarantined += 1
                _append(output / 'quarantine.jsonl', {
                    'case_id': mother['case_id'], 'mother_id': mother['mother_id'],
                    'variant_index': variant_index, 'split': mother['split'],
                    'category': mother['category'], 'utterance': '',
                    'violations': [{'code': 'GENERATION_ERROR',
                                    'error': f'{type(error).__name__}: {error}'[:200]}],
                    'finish_reason': None, 'back_translation': None,
                    'reason': f'生成或校验过程中抛错：{type(error).__name__}'})
                continue
            if problems:
                quarantined += 1
                _append(output / 'quarantine.jsonl', {
                    'case_id': mother['case_id'], 'mother_id': mother['mother_id'],
                    'variant_index': variant_index,
                    'split': mother['split'], 'category': mother['category'],
                    'utterance': utterance, 'violations': problems, 'finish_reason': finish,
                    'back_translation': verdict, 'reason': _repair_note(problems, verdict)})
                continue
            variant = make_variant(mother, utterance, variant_index, verdict)
            _append(variants_path, {**variant, 'back_translation': verdict['status']})
            accepted[mother['mother_id']].append(utterance)
            generated += 1
        if stopped:
            break
    return {'generated': generated, 'quarantined': quarantined, 'stopped': stopped,
            'budget': budget.totals(), 'splits_manifest_sha256': file_hash(splits / 'manifest.json'),
            'p0_manifest_sha256': manifest['p0_manifest_sha256'], 'authorization': authorization}


def _rows(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
