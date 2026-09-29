"""P2 案例物化与独立复核。

`assemble_cases`：把分区后的母案例（variant 0）与模型改写合成正式案例集。
  **配额如实**：隔离过的变体不补造；manifest 同时记目标配额与实际配额，差额在报告里展示。
`ai_review`：全新上下文逐条复核**全部**正式案例的业务自然度与语义一致性（方案 §五.2），
  与 `p2_variants` 的边界词 lint、独立回译互补：那两项管结构与量值，这里管表达与业务合理。
`materialize`：按复核结论物化最终集，**容忍隔离**（与 P1 的 `apply_reviews` 不同，后者遇隔离即拒绝）。
"""
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

from .contracts import EvalCase
from .io import digest, file_hash, fresh_directory, read_jsonl, write_json, write_jsonl
from .llm import Budget, LlmClient, load_config
from .oracle import fixture_result
from .p2_mothers import QUOTAS, load_context
from .p2_variants import VARIANTS_PER_MOTHER
from .validation import expected_shape, verify_package

class ReviewUnavailable(RuntimeError):
    """复核在预算内没产出可解析结论（格式问题）。

    这类不算「这一题不合格」，而是要显式记为未复核并计数，不能混进隔离里当作判定。
    """


DIAGNOSTIC_KEYS = ('back_translation', 'recovered_from_quarantine')
REVIEW_VERDICTS = ('ACCEPT', 'REVISE', 'QUARANTINE', 'UNAVAILABLE')
# 复核保留推理（要判断「是否忠实表达且自然」），而推理 token 计入 max_tokens：
# 给 200 会让可见 JSON 整段为空——和改写那边踩过的是同一个坑。
REVIEW_MAX_TOKENS = 1500
REVIEW_ATTEMPTS = 3
REVIEW_NUDGE = ('\n\n上一次输出不是 JSON。只输出一个 JSON 对象，第一个字符必须是 {，'
                '不要任何解释或代码块标记。')

REVIEW_SYSTEM = ('你是银行标签圈选评测集的独立复核员。你只判断给定的需求句是否忠实、自然。'
                 '只输出 JSON，不要解释。')


def case_fields(row):
    """只保留契约字段：中间台账里的诊断键不带进正式数据集。"""
    return {key: value for key, value in row.items() if key not in DIAGNOSTIC_KEYS}


def _render_condition(leaf, names):
    expression = leaf['expression']
    caliber = leaf.get('caliber') or {}
    bits = [f'{k}={v}' for k, v in caliber.items()
            if k in ('time_anchor_label', 'statistic', 'scope', 'period_edge') and v not in (None, 'ALL')]
    suffix = f"（口径：{'、'.join(bits)}）" if bits else ''
    if expression['kind'] == 'TAG':
        name = names.get(expression['tag_id'], expression['tag_id'])
        return f'{name} {leaf["operator"]} {"、".join(leaf["values"])}{suffix}'
    if expression['kind'] == 'COUNT_POSITIVE':
        policy = caliber.get('null_policy') or 'EXCLUDE'
        return (f'【派生】统计「余额大于零的类目数」{leaf["operator"]} {"、".join(leaf["values"])}'
                f'（缺失项处理：{policy}）')
    return f'【派生】{expression["kind"]} {leaf["operator"]} {"、".join(leaf["values"])}{suffix}'


def _render_tree(tree, names):
    """把标准树按其**逻辑结构**渲染出来：AND/OR 与嵌套必须保留。

    原先这里把所有叶子摊平成一个列表，复核员会把「A 且( B 或 C )」读成「A 且 B 且 C」，
    进而误判忠实改写为「放宽了条件」。
    """
    if tree is None:
        return '（无）'
    if tree['kind'] == 'SCOPE_ALL':
        return '全部客户（不加任何条件）'
    if tree['kind'] == 'GROUP':
        joiner = ' 且 ' if tree['logic'] == 'AND' else ' 或 '
        return '（' + joiner.join(_render_tree(child, names) for child in tree['children']) + '）'
    return _render_condition(tree, names)


def review_prompt(case, names):
    expected = case['expected']
    outcome = expected['outcomes'][0]
    structure = _render_tree(expected.get('tree'), names)
    if outcome == 'READY':
        expected_note = '原话应当完整表达该结构，不得新增或删减条件'
    elif outcome == 'NEEDS_USER_INPUT':
        slots = expected.get('required_slots') or []
        missing = {'threshold': '具体门槛', 'time_scope': '时间口径'}.get(
            slots[0] if slots else '', '缺失信息')
        given = '用户已经给出了可执行条件' if expected.get('tree') else '用户没有给出可执行条件'
        expected_note = (f'{given}，但**没有给出{missing}**。原话应当保留已给的条件，'
                         f'并让{missing}保持未定（可询问或说明待确认），不得自行补出一个具体的{missing}')
    else:
        expected_note = ('用户要的东西现有数据/能力做不到。原话**本来就会提到他想筛的条件**，'
                         '这是题目的前提；你要判断的是这句话像不像真实客户经理说的，'
                         '而不是它有没有提到条件')
    return (f'客户经理原话：{case["requirement"]}\n'
            f'该题标准条件的**逻辑结构**：{structure}\n'
            f'该题期望处置：{outcome}（{expected_note}）\n\n'
            '注意：标准里没有的「条件」才算新增；但界定、缺失项处理等已写在口径里的说明不算新增。\n'
            '请判断这句话是否 (a) 与上述期望一致（不得新增标准里没有的可执行条件、'
            '不得删减标准里的条件、不得泄漏评测内部记号），且 (b) 是自然的客户经理表达。\n'
            '输出 JSON：{"verdict":"ACCEPT 或 REVISE 或 QUARANTINE","reason":"一句理由",'
            '"faithful":true/false,"natural":true/false}')


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


def _review_one(client, case, names):
    last_error = None
    for attempt in range(REVIEW_ATTEMPTS):
        prompt = review_prompt(case, names)
        if attempt:
            prompt += REVIEW_NUDGE
        text = client.complete('review', REVIEW_SYSTEM, prompt,
                               max_tokens=REVIEW_MAX_TOKENS)['text']
        try:
            payload = _parse_review(text)
            return payload
        except ValueError as error:
            last_error = error
    # 模型没给出可解析 JSON 是**驱动/格式**问题，不能记成「这一题不合格」。
    raise ReviewUnavailable(f'复核输出不可解析：{last_error}')


def _parse_review(text):
    start, end = text.find('{'), text.rfind('}')
    if start < 0 or end <= start:
        raise ValueError('复核输出不是 JSON')
    payload = json.loads(text[start:end + 1])
    verdict = str(payload.get('verdict', '')).upper()
    if verdict not in REVIEW_VERDICTS:
        raise ValueError(f'复核结论无法识别：{payload.get("verdict")}')
    return {'verdict': verdict, 'reason': str(payload.get('reason', ''))[:300],
            'faithful': bool(payload.get('faithful')), 'natural': bool(payload.get('natural'))}


def assemble_cases(p0, root, splits, variants_dir, output, authorization):
    """合成正式案例集；配额如实记录，不补造被隔离掉的变体。"""
    p0, splits, variants_dir, output = Path(p0), Path(splits), Path(variants_dir), Path(output)
    splits_manifest = verify_package(splits)
    p0_manifest = json.loads((p0 / 'manifest.json').read_text())
    facts = {r['tag_id']: r for r in read_jsonl(p0 / 'facts.jsonl')}
    mothers = read_jsonl(splits / 'cases.jsonl')
    variants_path = variants_dir / 'variants.jsonl'
    raw_variants = read_jsonl(variants_path) if variants_path.exists() else []
    variants = [case_fields(row) for row in raw_variants]
    cases = sorted([*mothers, *variants], key=lambda case: case['case_id'])
    validated = [EvalCase.model_validate(case).model_dump(exclude_none=True) for case in cases]

    achieved = dict(Counter(case['category'] for case in validated))
    # QUOTAS 是**母案例**配额；正式案例集每母案例含 variant 0 与 3 条模型改写，目标要按倍率放大。
    target = {name: count * VARIANTS_PER_MOTHER for name, count in QUOTAS.items()}
    output = fresh_directory(output)
    write_jsonl(output / 'cases.jsonl', validated)
    write_jsonl(output / 'inputs.jsonl', [
        {'input_id': case['case_id'], 'requirement': case['requirement'],
         'reference_date': case['reference_date'], 'timezone': case['timezone']} for case in validated])
    oracle = []
    fixture_sha256 = p0_manifest['sources']['fixture']['sha256']
    rows = load_context(p0, root)['rows']
    for case in validated:
        stages = [case['expected']] + [turn['expected'] for turn in case['turns']]
        for stage, expectation in enumerate(stages):
            if expectation['outcomes'] != ['READY']:
                continue
            result = fixture_result(expectation['tree'], rows)
            oracle.append({'case_id': case['case_id'], 'stage': stage,
                           'dataset_sha256': fixture_sha256,
                           'mode': 'INDEPENDENT_PYTHON_ON_REPOSITORY_SQL_FIXTURE',
                           'java_verified': False, 'live_values_verified': False, **result})
    write_jsonl(output / 'oracle-results.jsonl', oracle)
    write_json(output / 'manifest.json', {
        'schema_version': 'p2-cases.v1', 'phase': 'P2', 'status': 'DRAFT',
        'case_count': len(validated), 'mother_cases': len({c['mother_id'] for c in validated}),
        'formal_cases': len(validated),
        'quotas': target, 'quotas_achieved': achieved, 'quota_shortfall_declared': True,
        'quota_shortfall': {name: target[name] - achieved.get(name, 0)
                            for name in target if target[name] != achieved.get(name, 0)},
        'variants_per_mother': dict(Counter(Counter(c['mother_id'] for c in validated).values())),
        'splits': dict(Counter(case['split'] for case in validated)),
        'lineage_groups': len({case['lineage_group'] for case in validated}),
        'target_tags': len({tag for case in validated for tag in case['target_tag_ids']}),
        'p0_manifest_sha256': splits_manifest['p0_manifest_sha256'],
        'partition_sha256': splits_manifest.get('partition_sha256'),
        'fixture_sha256': fixture_sha256,
        'quarantined_variants': _count_lines(variants_dir / 'quarantine.jsonl'),
        'back_translation_unavailable_variants': sum(
            1 for row in raw_variants if row.get('back_translation') == 'BACK_TRANSLATION_UNAVAILABLE'),
        'verification_note': '通过边界词 lint 且目标标签/操作符/取值可重建的改写才算“已回译核对”；'
                             '回译推理吃满 token 而无法比对的，标 BACK_TRANSLATION_UNAVAILABLE 并计数，'
                             '由覆盖全部正式案例的独立 AI 复核把关，不在此处假装已核对。',
        'independent_model_review': 'PENDING', 'human_review': 'PENDING',
        'authorization': authorization,
        'files': {p.name: file_hash(p) for p in output.iterdir() if p.is_file()}})
    return {'cases': len(validated), 'quotas': achieved, 'target_quotas': target,
            'splits': dict(Counter(case['split'] for case in validated))}


def _count_lines(path):
    path = Path(path)
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text().splitlines() if line.strip())


def ai_review(p0, cases_dir, output, root, sdk_cap_usd, limit=None, token_cap=None, call_cap=None):
    """全新上下文逐条复核全部正式案例；追加式、可续跑、预算硬停。"""
    p0, cases_dir, output = Path(p0), Path(cases_dir), Path(output)
    verify_package(cases_dir)
    facts = {r['tag_id']: r for r in read_jsonl(p0 / 'facts.jsonl')}
    names = {tag_id: fact['name'] for tag_id, fact in facts.items()}
    cases = read_jsonl(cases_dir / 'cases.jsonl')
    output.mkdir(parents=True, exist_ok=True)
    reviews_path = output / 'reviews.jsonl'
    reviews_path.touch()
    budget = Budget(output / 'budget-ledger.jsonl', sdk_cap_usd, token_cap=token_cap, call_cap=call_cap)
    client = LlmClient(load_config(root), budget)
    done = {row['case_id'] for row in _rows(reviews_path)}
    reviewed = 0
    stopped = None
    for case in cases:
        if limit is not None and reviewed >= limit:
            stopped = 'LIMIT'
            break
        stopped = budget.stop_reason() or stopped
        if stopped:
            break
        if case['case_id'] in done:
            continue
        try:
            verdict = _review_one(client, case, names)
        except ReviewUnavailable as error:
            verdict = {'verdict': 'UNAVAILABLE', 'reason': str(error),
                       'faithful': False, 'natural': False}
        except Exception as error:  # 网络/服务异常同样不该按「这一题不合格」记
            verdict = {'verdict': 'UNAVAILABLE',
                       'reason': f'{type(error).__name__}: {error}'[:200],
                       'faithful': False, 'natural': False}
        _append(reviews_path, {'case_id': case['case_id'], 'reviewer': 'independent-model-review-v1',
                              'reviewed_at': None, **verdict})
        reviewed += 1
    return {'reviewed': reviewed, 'stopped': stopped, 'budget': budget.totals(),
            'verdicts': dict(Counter(row['verdict'] for row in _rows(reviews_path)))}


def materialize(cases_dir, reviews_path, output, authorization):
    """按复核结论物化最终集：REVISE 只允许改动表达，QUARANTINE 记录并从正式集剔除。"""
    cases_dir, output = Path(cases_dir), Path(output)
    manifest = verify_package(cases_dir)
    cases = read_jsonl(cases_dir / 'cases.jsonl')
    reviews = {row['case_id']: row for row in read_jsonl(reviews_path)}
    if set(reviews) != {case['case_id'] for case in cases}:
        raise ValueError('复核未覆盖全部案例，不能物化')
    cosmetic = {'requirement', 'persona', 'scenario', 'truth_basis'}
    kept, quarantined, revised, flagged = [], [], [], []
    for case in cases:
        review = reviews[case['case_id']]
        if review['verdict'] == 'QUARANTINE':
            quarantined.append({'case_id': case['case_id'], 'reason': review.get('reason')})
            continue
        if review['verdict'] == 'UNAVAILABLE':
            # 没拿到复核结论 ≠ 不合格：保留但显式计数，不冒充已复核。
            flagged.append({'case_id': case['case_id'], 'reason': review.get('reason')})
            kept.append(case)
            continue
        if review['verdict'] == 'REVISE':
            patch = review.get('patch') or {}
            unexpected = set(patch) - cosmetic
            if unexpected:
                raise ValueError(f'{case["case_id"]} 的改稿超出表达范围：{sorted(unexpected)}')
            if not patch:
                # 复核员要求改但没给具体改法：**不算通过**，如实记为待人工处理的标记项。
                flagged.append({'case_id': case['case_id'], 'reason': review.get('reason')})
                kept.append(case)
                continue
            case = {**case, **patch}
            revised.append(case['case_id'])
        kept.append(case)
    validated = [EvalCase.model_validate(case).model_dump(exclude_none=True) for case in kept]
    output = fresh_directory(output)
    write_jsonl(output / 'cases.jsonl', validated)
    write_jsonl(output / 'inputs.jsonl', [
        {'input_id': case['case_id'], 'requirement': case['requirement'],
         'reference_date': case['reference_date'], 'timezone': case['timezone']} for case in validated])
    (output / 'oracle-results.jsonl').write_bytes((cases_dir / 'oracle-results.jsonl').read_bytes())
    write_json(output / 'manifest.json', {
        **{key: value for key, value in manifest.items() if key not in {'files', 'status'}},
        'schema_version': 'p2-cases.v1', 'status': 'REVIEWED',
        'case_count': len(validated), 'formal_cases': len(validated),
        'quotas': dict(Counter(case['category'] for case in validated)),
        'independent_model_review': 'COMPLETED',
        'review_verdicts': dict(Counter(row['verdict'] for row in reviews.values())),
        'revised_cases': revised, 'quarantined_cases': quarantined,
        'flagged_without_patch': flagged,
        'supersedes': {'schema_version': manifest['schema_version'],
                       'manifest_sha256': file_hash(cases_dir / 'manifest.json')},
        'authorization': authorization,
        'files': {p.name: file_hash(p) for p in output.iterdir() if p.is_file()}})
    return {'cases': len(validated), 'revised': len(revised), 'quarantined': len(quarantined),
            'flagged_without_patch': len(flagged),
            'quotas': dict(Counter(case['category'] for case in validated))}


def _append(path, row):
    with Path(path).open('a') as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')


def _rows(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
