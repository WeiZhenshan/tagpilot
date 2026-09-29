"""P2 失败根因报告：先把超时与无效运行从语义失败里拆出来，再做归因。

方案 §四.1 明确要求：不能把所有失败都解释为语义层不足（旧报告里 37 次硬超时即为此类）。
因此本模块的归因是**分层**的：

1. `RUN_INVALID` → 环境/裁判/鉴权问题，不进语义归因；
2. 超时（`AGENT_TIMEOUT` 或裁判证据显示被时限取消）→ 单列一类，并**不**计入语义分母；
3. 其余才按证据归因到方案表里的方向；
4. 证据不足以归因的进 `UNATTRIBUTED`，不硬凑一个原因。

每簇给出受影响母案例数、严重程度、证据与反例，按「影响母案例数 × 严重程度」排序，最多 20 簇。
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

from .io import file_hash, fresh_directory, read_jsonl, write_json, write_jsonl
from .validation import expected_shape, verify_package

MAX_CLUSTERS = 20
SEVERITY = {'ZERO_TOLERANCE': 3, 'CORRECTNESS': 2, 'BEHAVIOR': 1}

CALL_TO_DEFINITION = {
    'RUN_INVALID': '环境、裁判或鉴权问题；不计入语义归因',
    'TIMEOUT': '运行超过单题时限（预算/收敛问题，不是语义不足）',
    'RETRIEVAL_MISS': '目标标签未进入检索前 K：先看别名与概念关联是否缺失',
    'DISAMBIGUATION': '用了易混淆的其它标签（当前/历史、本行/他行、累计/最高）：补易混淆关系与候选关联',
    'CALIBER': '时间或统计口径不一致',
    'CODE_UNIT_ENDPOINT': '码值、单位或区间端点错误',
    'LOGIC': '条件逻辑错误（漏条件、AND 改 OR）',
    'OUTCOME': '终态判断错误（该澄清却作答、该报缺口却给条件）',
    'CLARIFICATION_BEHAVIOR': '澄清槽位未被问到或问了不该问的',
    'GAP_BEHAVIOR': '能力缺口原因与证据不符',
    'AGENT_GUARD': '标签已正确召回但方案错误：归 Agent/Guard 行为',
    'DATASET': '问题与标准答案不一致：修正数据集并重新版本化',
    'SOURCE_FACT': '来源定义或码表冲突未解决',
    'UNATTRIBUTED': '证据不足以归因',
}


def _leaves(tree, out=None):
    """收集叶子节点。被测 Agent 的计划树不保证每个节点都带 kind，这里按结构容忍地下钻。"""
    out = [] if out is None else out
    if not isinstance(tree, dict):
        return out
    kind = tree.get('kind')
    if kind in (None, 'GROUP'):
        for child in tree.get('children') or []:
            _leaves(child, out)
    elif kind == 'PREDICATE':
        out.append(tree)
    return out


def _operators(tree):
    pairs = set()
    for leaf in _leaves(tree):
        expression = leaf.get('expression') or {}
        if expression.get('kind') == 'TAG':
            pairs.add((expression.get('tag_id'), leaf.get('operator')))
    return pairs


def classify(fact, verdict, run, l1_hits, facts):
    """按证据给单个失败案例定类别；证据不足返回 UNATTRIBUTED。

    `l1_hits` 为 None 表示该题没有 L1 结果，此时**不能**据此判「检索未命中」。
    """
    if run.get('status') == 'RUN_INVALID':
        return 'RUN_INVALID'
    evidence = verdict.get('evidence') or {}
    stats = run.get('stats') or {}
    # 硬超时要单列：Agent 侧 stop_reason=timeout 的运行即使带着草案（因此 run.status 是 COMPLETED），
    # 也**不能**算成语义失败。方案 §四.1 明确要求拆开超时与语义。
    if stats.get('stop_reason') == 'timeout' or run.get('status') == 'AGENT_TIMEOUT' \
            or evidence.get('cancelled_by_harness') or '时限' in str(evidence.get('note') or '') \
            or any(str(f).startswith('AGENT_NOT_TERMINAL') for f in verdict.get('failures') or []):
        return 'TIMEOUT'
    failures = set(verdict.get('failures') or [])
    targets = set(fact['target_tag_ids'])
    unresolved = {item.split(':')[-1] for item in fact['unresolved_fact_ids']}
    if targets and {str(tag) for tag in targets} & unresolved:
        return 'SOURCE_FACT'
    if l1_hits is not None and targets and not (targets & l1_hits):
        return 'RETRIEVAL_MISS'
    if 'SLOTS' in failures or 'NO_INTERRUPT' in failures:
        return 'CLARIFICATION_BEHAVIOR'
    if 'GAP_REASON' in failures:
        return 'GAP_BEHAVIOR'
    if 'OUTCOME' in failures or 'NO_TREE' in failures:
        return 'OUTCOME'
    if 'TREE' in failures:
        expected_tree = (fact['expected'] or {}).get('tree')
        actual_plan = ((run.get('output') or {}).get('plan') or {})
        if not actual_plan:
            return 'AGENT_GUARD'
        expected_pairs = _operators(expected_tree)
        actual_pairs = _operators(actual_plan.get('tree'))
        if {tag for tag, _ in expected_pairs} == {tag for tag, _ in actual_pairs}:
            if {op for _, op in expected_pairs} != {op for _, op in actual_pairs}:
                return 'CALIBER' if _has_caliber(actual_plan.get('tree')) else 'LOGIC'
            return 'CODE_UNIT_ENDPOINT'
        # 用了别的标签：方案 §四.1 归到易混淆关系/概念关联，而不是另立「绑定错误」类。
        return 'DISAMBIGUATION'
    if 'FIRST_TURN' in failures:
        return 'LOGIC'
    if 'CALIBER' in failures:
        return 'CALIBER'
    if 'FULL_ID_SET' in failures:
        return 'AGENT_GUARD'
    return 'UNATTRIBUTED'


def _has_caliber(tree):
    return any(leaf.get('caliber') for leaf in _leaves(tree))


def diagnose(p0, cases_dir, runs_dir, l1_dir, output, authorization):
    p0, cases_dir, runs_dir, output = Path(p0), Path(cases_dir), Path(runs_dir), Path(output)
    verify_package(cases_dir)
    run_manifest = verify_package(runs_dir)
    facts = {r['tag_id']: r for r in read_jsonl(p0 / 'facts.jsonl')}
    expected = expected_shape(json.loads((cases_dir / 'manifest.json').read_text()))
    cases = {case['case_id']: case for case in read_jsonl(cases_dir / 'cases.jsonl')}
    verdicts = read_jsonl(runs_dir / 'verdicts.jsonl')
    runs = {(row['case_id'], row.get('repeat', 0)): row for row in read_jsonl(runs_dir / 'runs.jsonl')}
    l1_hits, l1_available = _l1_hits(l1_dir, cases)

    buckets = defaultdict(list)
    unattributed_ids = []
    for verdict in verdicts:
        if verdict['status'] == 'PASS':
            continue
        key = (verdict['case_id'], verdict.get('repeat', 0))
        run = runs.get(key, {})
        case = cases.get(verdict['case_id'])
        if case is None:
            continue
        category = classify(case, verdict, run, l1_hits.get(verdict['case_id']), facts)
        if category == 'UNATTRIBUTED':
            unattributed_ids.append(verdict['case_id'])
        buckets[category].append({'case_id': verdict['case_id'], 'repeat': verdict.get('repeat', 0),
                                 'split': case['split'], 'category': case['category'],
                                 'failures': verdict.get('failures'),
                                 'domains': case['domains'],
                                 'target_tags': case['target_tag_ids']})

    clusters = []
    for name, rows in buckets.items():
        mothers = {row['case_id'] for row in rows}
        domain_counts = Counter(domain for row in rows for domain in row['domains'])
        clusters.append({
            'cluster': name, 'affected_mothers': len(mothers), 'occurrences': len(rows),
            'severity': SEVERITY.get('ZERO_TOLERANCE' if name in {'DATASET', 'SOURCE_FACT'} else
                                     'CORRECTNESS' if name in {'DISAMBIGUATION', 'LOGIC', 'OUTCOME',
                                                               'CALIBER', 'CODE_UNIT_ENDPOINT',
                                                               'RETRIEVAL_MISS'} else 'BEHAVIOR'),
            'domains': dict(domain_counts.most_common(5)),
            'direction': CALL_TO_DEFINITION[name],
            'evidence_case_ids': sorted(mothers)[:10]})
    clusters.sort(key=lambda cluster: (-cluster['affected_mothers'] * cluster['severity'],
                                       cluster['cluster']))
    clusters = clusters[:MAX_CLUSTERS]

    total = len(verdicts)
    non_semantic = len(buckets.get('RUN_INVALID', [])) + len(buckets.get('TIMEOUT', []))
    report = {
        'schema_version': 'p2-diagnosis.v1',
        'verdicts_total': total,
        'failed_total': sum(1 for verdict in verdicts if verdict['status'] != 'PASS'),
        'run_invalid': len(buckets.get('RUN_INVALID', [])),
        'timeouts': len(buckets.get('TIMEOUT', [])),
        'semantic_denominator': total - non_semantic,
        'note': '超时与无效运行单列，不计入语义归因分母；证据不足以归因的案例不硬凑原因。',
        'severity_weights': SEVERITY,
        'clusters': clusters,
        'unattributed_mothers': sorted(set(unattributed_ids)),
        'l1_used_for_retrieval_attribution': l1_available,
        'cases_manifest_sha256': file_hash(cases_dir / 'manifest.json'),
        'runs_manifest_sha256': file_hash(runs_dir / 'manifest.json'),
        'p0_manifest_sha256': file_hash(p0 / 'manifest.json'),
        'dataset_shape': {'phase': expected['phase'], 'case_count': expected['case_count']},
        'authorization': authorization,
    }
    output = fresh_directory(output)
    write_json(output / 'diagnosis.json', report)
    write_jsonl(output / 'cluster-evidence.jsonl',
                [{'cluster': cluster['cluster'], 'case_ids': cluster['evidence_case_ids']}
                 for cluster in clusters])
    write_json(output / 'manifest.json', {
        'schema_version': 'p2-diagnosis.v1', 'phase': 'P2', 'status': 'DIAGNOSED',
        'authorization': authorization, 'runs_manifest_sha256': report['runs_manifest_sha256'],
        'files': {p.name: file_hash(p) for p in output.iterdir() if p.is_file()}})
    return {'clusters': len(clusters), 'failed_total': report['failed_total'],
            'timeouts': report['timeouts'], 'run_invalid': report['run_invalid'],
            'top_clusters': [(cluster['cluster'], cluster['affected_mothers']) for cluster in clusters[:5]]}


def _l1_hits(l1_dir, cases):
    """L1 命中集合：case_id -> 进入 top-K 的目标标签集合。

    L1 结果按 `_leaves(tree)` 的顺序给出 `recalled`，但行里不含 tag_id，
    因此用同一顺序把案例的标准树叶子与 `recalled` 对齐还原。
    """
    path = Path(l1_dir) / 'l1-results.jsonl'
    if not path.exists():
        return None, False
    hits = {}
    for row in read_jsonl(path):
        case = cases.get(row['case_id'])
        if case is None:
            continue
        leaves = [leaf['expression']['tag_id'] for leaf in _leaves(case['expected'].get('tree'))
                  if leaf['expression']['kind'] == 'TAG']
        recalled = row.get('recalled') or []
        hits[row['case_id']] = {tag_id for tag_id, ok in zip(leaves, recalled) if ok}
    return hits, True
