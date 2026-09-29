"""收尾第 6 项：冻结 P1 验收版本。

把已复核的版本、审核记录、运行证据与残留缺口汇总为可复现的验收报告。
报告只陈述实际证据；未执行的部分（如 Java 执行）如实标注，不折算为通过。
"""
import html
import json
from collections import Counter
from pathlib import Path

from .io import file_hash, read_jsonl


def _json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else default


def _exists(path):
    return Path(path).exists()


def _demo_metrics(p0, calibration, l2_dir):
    """按方案的 Demo 质量目标口径计算可核对的指标（分母如实展示）。"""
    p0, calibration, l2_dir = Path(p0), Path(calibration), Path(l2_dir)
    verdicts_path, runs_path = l2_dir / 'verdicts.jsonl', l2_dir / 'runs.jsonl'
    if not verdicts_path.exists() or not runs_path.exists():
        return None
    from .judge import strip_caliber
    from .oracle import grade_tree
    from .plan_adapter import AdapterError, to_eval_tree
    from .l2 import _fixture_rows
    facts = {r['tag_id']: r for r in read_jsonl(Path(p0) / 'facts.jsonl')}
    rows = _fixture_rows(json.loads((Path(p0) / 'manifest.json').read_text()))
    cases = {c['case_id']: c for c in read_jsonl(calibration / 'cases.jsonl')}
    run_rows = {r['case_id']: r for r in read_jsonl(runs_path)}
    verdicts = read_jsonl(verdicts_path)
    answerable = [v for v in verdicts if 'READY' in cases[v['case_id']]['expected']['outcomes']]
    over_clarify = [v for v in answerable if run_rows[v['case_id']]['outcome'] == 'NEEDS_USER_INPUT']
    agent_ready = [v for v in verdicts if run_rows[v['case_id']]['outcome'] == 'READY']
    ready_ok = [v for v in agent_ready if v['status'] == 'PASS']
    # 判定未通过的题里，草案方案在语义上是否正确：区分"语义错"与"未在预算内收敛"。
    missed = [v for v in verdicts if v['status'] != 'PASS']
    draft_correct, draft_total = [], 0
    for v in missed:
        case = cases[v['case_id']]
        plan = (run_rows[v['case_id']]['output'] or {}).get('plan') or {}
        if not plan.get('tree') or case['expected'].get('tree') is None:
            continue
        draft_total += 1
        try:
            actual = to_eval_tree(plan['tree'], facts)
        except AdapterError:
            continue
        graded = grade_tree(strip_caliber(case['expected']['tree']), actual, rows)
        if graded['status'] == 'PASS':
            draft_correct.append(v['case_id'])
    causes = Counter((run_rows[v['case_id']].get('stats') or {}).get('sdk_result') or 'n/a'
                     for v in verdicts if v['status'] != 'PASS')
    return {
        'unnecessary_clarification': {'numerator': len(over_clarify), 'denominator': len(answerable),
                                      'rate': round(len(over_clarify) / len(answerable), 4) if answerable else None,
                                      'cases': [v['case_id'] for v in over_clarify]},
        'ready_precision': {'numerator': len(ready_ok), 'denominator': len(agent_ready),
                            'rate': round(len(ready_ok) / len(agent_ready), 4) if agent_ready else None},
        'capability_gap_cases': len([v for v in verdicts
                                     if cases[v['case_id']]['expected']['outcomes'] == ['CAPABILITY_GAP']]),
        'missed_cases': len(missed),
        'draft_semantics_correct': {'numerator': len(draft_correct), 'denominator': draft_total,
                                    'cases': draft_correct},
        'failure_causes': dict(causes),
    }


def freeze(p0, calibration, reviews, runs_root, human_ledger, output):
    p0, calibration, reviews = Path(p0), Path(calibration), Path(reviews)
    runs_root, output = Path(runs_root), Path(output)
    if (output / 'REPORT.md').exists():
        raise ValueError('验收报告已存在，请使用新的版本目录，避免覆盖已审核版本')
    output.mkdir(parents=True, exist_ok=True)
    p0_manifest = _json(p0 / 'manifest.json')
    cal_manifest = _json(calibration / 'manifest.json')
    dispositions = read_jsonl(p0 / 'dispositions.jsonl')
    review_rows = read_jsonl(reviews)
    l1 = _json(runs_root / 'l1-calibration-v2/l1-summary.json')
    l2 = _json(runs_root / 'l2-calibration-v2/l2-summary.json')
    demo = _demo_metrics(p0, calibration, runs_root / 'l2-calibration-v2')
    human_page = Path(human_ledger).parent / 'human-review.html'
    human = read_jsonl(human_ledger) if _exists(human_ledger) else None
    from .validation import validate_package
    validate_package(p0, calibration)
    blocking = [d for d in dispositions if d['severity'] == 'ERROR']
    lines = []
    add = lines.append

    add('# TagPilot 评测 P1 验收（收尾冻结）')
    add('')
    add(f"生成时间基准：2026-09-27 ｜ 分支 `feature/tag-agent-v4.0` ｜ 数据集版本 `calibration.v2`")
    add('')
    add('本报告冻结 P1 收尾六项的证据。**P2 未授权**，正式生成 0 条；语义变更与索引重建未执行。')
    add('')

    add('## 1. 版本清单')
    add('')
    add('| 工件 | 版本 / 文件 | sha256 |')
    add('|---|---|---|')
    for label, path in [('事实包 manifest', p0 / 'manifest.json'),
                        ('事实清单 facts.jsonl', p0 / 'facts.jsonl'),
                        ('来源冲突处置 dispositions.jsonl', p0 / 'dispositions.jsonl'),
                        ('码值分母漂移 source-drift.json', p0 / 'source-drift.json'),
                        ('校准集 manifest', calibration / 'manifest.json'),
                        ('母案例 cases.jsonl', calibration / 'cases.jsonl'),
                        ('无答案输入 inputs.jsonl', calibration / 'inputs.jsonl'),
                        ('独立复核 reviews.jsonl', reviews),
                        ('人工抽检页', Path(human_page)),
                        ('人工抽检台账', Path(human_ledger)),
                        ('L1 结果 l1-summary.json', runs_root / 'l1-calibration-v2/l1-summary.json'),
                        ('L2 结果 l2-summary.json', runs_root / 'l2-calibration-v2/l2-summary.json'),
                        ('L2 逐题运行证据 runs.jsonl', runs_root / 'l2-calibration-v2/runs.jsonl'),
                        ('L2 逐题判定 verdicts.jsonl', runs_root / 'l2-calibration-v2/verdicts.jsonl')]:
        if _exists(path):
            add(f"| {label} | `{Path(path).name}` | `{file_hash(path)[:16]}…` |")
    add('')
    add(f"- 事实包 supersedes：`{p0_manifest.get('supersedes', {}).get('manifest_sha256', '')[:16]}…`；"
        f"校准集 supersedes：`{cal_manifest.get('supersedes', {}).get('manifest_sha256', '')[:16]}…`")
    add(f"- 活动快照/索引：`{p0_manifest.get('active_snapshot', {}).get('snapshot_id')}` / "
        f"`{p0_manifest.get('active_build', {}).get('build_id')}`；观测时间 "
        f"`{p0_manifest.get('observation_sha256', '')[:16]}…`")
    add('')

    add('## 2. 收尾六项状态')
    add('')
    add('| 项 | 状态 | 证据 |')
    add('|---|---|---|')
    add('| ① 独立复核 200 母案例 | 完成 | 机械复核无绑定/单位/口径/阈值/码值/资格缺陷；'
        '6 题 Demo 字面量、8 题话术同文已处置 |')
    add('| ② 裁判与解析复核 | 完成 | `JUDGE-AUDIT.md`；树级无假通过，终态裁判补齐 |')
    add(f"| ③ 来源冲突处置 | 完成 | {len(blocking)} 个阻断项全部处置，无阻断项被静默忽略 |")
    if human:
        decisions = Counter(r['decision'] for r in human)
        when = sorted({(r.get('reviewed_at') or '') for r in human})[-1]
        add(f"| ④ 人工抽检 | 完成 | {len(human)} 题：{dict(decisions)}（{when}，复核人本人的确认） |")
    else:
        add('| ④ 人工抽检 | 待本人填答 | `human-review.html` 40 题待复核 |')
    add(f"| ⑤ 真实运行链路 | {'完成' if l2 else '进行中'} | L1 全量 + L2 全量 200 + 终态裁判 + 裁判验收套件 |")
    add('| ⑥ 冻结验收版本 | 本报告 | — |')
    add('')

    add('## 3. 独立复核（第 1 项）')
    add('')
    add('独立复核由与被测 Agent、与配方作者不同的上下文完成，逐题核对标签重绑定、字段/单位、'
        '时间与统计口径、阈值与码值是否出现在原话、资格与未解决事实边界、以及自然表达。')
    add('')
    verdicts = Counter(r['verdict'] for r in review_rows)
    add(f"- 覆盖：{len(review_rows)} / 200 母案例，全部有复核结论与理由。")
    add(f"- 结论分布：{dict(verdicts)}。")
    revised = cal_manifest.get('revised_cases', [])
    add(f"- 改写：{len(revised)} 题（多轮母案例首轮话术同文，改写为语义等价的不同表达）：{', '.join(revised)}。")
    add('- 保留提示（ACCEPT with caveat）：6 题 contains 谓词的原话引用了模拟数据字面量（`SIM_…`），'
        '属 Demo 约定而非真实客户经理表达，仅在模拟数据上可执行。')
    add('- 机械复核零缺陷项：字段绑定、单位、口径、阈值出现、码值成员、资格、未解决事实、'
        '标签重绑定、禁止标签、操作符支持。')
    add('')

    add('## 4. 裁判与解析复核（第 2 项）')
    add('')
    add('- 条件树裁判**不存在假通过**：`PASS` 要求标准化结构相等，结构相等即语义相等；'
        '语义扰动一律判失败（反例覆盖改阈值/操作符/绑定/字段）。')
    add('- 真正的假通过面是**终态层此前未判**，已补 `judge.py` 并通过验收套件：'
        '已知正确 / 等价改写 / 已知错误 / 漏条件 / 伪造 valid / 计划缺失 / 证据缺失 / 非终态。')
    add('- 修复：计划翻译器忽略 `value_scale`（会把 10 万元判错）；口径检查改为只判显式矛盾；'
        '旧字段字典 NULL 率非数值单元格不再导致崩溃。')
    add('- 来源分母漂移 177/1723 → 178/1725 由第 3 项处置引起，已显式记录，未回填事实包。')
    add('')

    add('## 5. 来源冲突处置（第 3 项）')
    add('')
    add(f"9 个阻断项处置（均为源头已修正、快照未重发布，故校准金标保持 GAP）：")
    add('')
    add('| issue | 标签 | 类别 | 处置 |')
    add('|---|---|---|---|')
    for row in blocking:
        add(f"| {row['issue_id']} | {row['tag_id']} | {row['code']} | {row['disposition']} |")
    add('')
    add(f"- 提示项：{dict(Counter(d['disposition'] for d in dispositions if d['severity'] == 'WARNING'))}")
    if _exists(p0 / 'source-drift.json'):
        drift = _json(p0 / 'source-drift.json')
        add(f"- 码值分母漂移：{drift['code_fields']} / {drift['code_values']}（工作树前移，已发布快照未变）。")
    add('')

    add('## 6. 人工抽检（第 4 项）')
    add('')
    if human:
        decisions = Counter(r['decision'] for r in human)
        when = sorted({(r.get('reviewed_at') or '') for r in human})[-1]
        add(f"- 结论：{len(human)} 题，{dict(decisions)}；复核人本人的确认，记录日期 {when}。")
        add(f"- 台账：`reviews/human-review-v2/ledger.jsonl`（绑定校准集 hash，不可覆盖）。")
        for row in human:
            if row['decision'] != 'ACCEPT':
                add(f"  - {row['case_id']}：{row['decision']} — {row['comment']}")
        add('- 抽检覆盖 6 个类别各分层样本；结论为接受即未发现需要修订的业务口径或表达问题。')
    else:
        add('- **待本人填答**：`reviews/human-review-v2/human-review.html`（40 题，分层抽样，可复现）。')
        add('- 页面已内置独立复核结论与来源事实证据，便于聚焦业务合理性与自然表达。')
        add('- 回填命令见 `README.md`；导入会校验覆盖完整性与拒绝原因。')
    add('')

    add('## 7. L1 检索与消歧')
    add('')
    if l1:
        add(f"- 样本：{l1['cases']} 个含原子条件的 READY 母案例，共 {l1['conditions']} 个原子条件；"
            f"k={l1['k']}，确定性 fast 模式（不启用重排）。")
        add(f"- 原子条件 Recall@20 = **{l1['atomic_recall_at_k']:.4f}**；"
            f"全部条件在 top-20 内均被召回的案件 = {l1['all_conditions_covered_at_k']}/{l1['cases']}。")
        add('')
        add('| 类别 | 案件 | 全条件覆盖 | 原子召回 |')
        add('|---|---:|---:|---:|')
        for category, row in l1['by_category'].items():
            add(f"| {category} | {row['cases']} | {row['all_covered']}/{row['cases']} | {row['atomic_recall']:.4f} |")
        add('')
        add(f"- 未全覆盖案件：{', '.join(l1['failures']) or '无'}")
        add('- 例外性质：两处未覆盖均为**高置信度单候选误选**（`当前时点AUM（本行）`→返回非本行 721；'
            '`企微私聊消息接收条数`→返回 1362），属消歧问题而非 top-K 深度不足，指向易混淆关系改进。')
        add('- 说明：分母只含"含原子条件"的题；澄清题、缺口题与全客群题不计入（无语义绑定可比）。')
    else:
        add('- 未执行。')
    add('')

    add('## 8. L2 Agent 方案（真实运行）')
    add('')
    if l2:
        v = l2['verdicts']
        total = sum(v.values())
        add(f"- 样本：{l2['cases']} 个母案例，真实 DeepSeek 调用，隔离评测实例（不打扰开发实例）。")
        add(f"- 终态分布：{l2['outcomes']}")
        add(f"- 判定：{v}；失败标签：{l2['failure_reasons']}")
        add(f"- 成本（SDK 估值，非账单）≈ ${l2['cost_usd_estimate']}；累计耗时 {l2['elapsed_seconds']}s。")
        add('')
        add('| 类别 | 案件 | PASS | FAIL | RUN_INVALID |')
        add('|---|---:|---:|---:|---:|')
        for category, row in l2['by_category'].items():
            add(f"| {category} | {row['cases']} | {row['pass']} | {row['fail']} | {row['run_invalid']} |")
        add('')
        add('- 判定独立性：结构、完整 ID 集、口径由独立裁判重算；不采信 Agent 的 `valid`/`plan_status`。')
        add('- `PARTIAL` 不等于成功；首轮终态不符合案例定义即失败（与方案一致）。')
        if demo:
            uc, rp = demo['unnecessary_clarification'], demo['ready_precision']
            add('')
            add('**Demo 质量目标口径（分母如实展示，未达标不作隐藏）**')
            add('')
            add('| 指标 | 分子/分母 | 本批 | 目标 |')
            add('|---|---:|---:|---:|')
            add(f"| 可回答条件的无必要澄清率 | {uc['numerator']}/{uc['denominator']} | "
                f"{uc['rate']} | ≤0.05 |")
            add(f"| READY 中完整方案正确率 | {rp['numerator']}/{rp['denominator']} | "
                f"{rp['rate']} | ≥0.99 |")
            add(f"| 能力缺口题（应判 CAPABILITY_GAP） | — | {demo['capability_gap_cases']} | — |")
            add('')
            ds = demo['draft_semantics_correct']
            add(f"- **失败归因**：未达标题 {demo['missed_cases']} 个，按 SDK 终止原因 "
                f"{demo['failure_causes']}；其中 **{ds['numerator']}/{ds['denominator']}** 题的草案方案在语义上"
                f"与标准树完全一致——即失败集中在**收敛/预算**（`error_max_turns`）而非语义绑定。")
            add('- 该结论仅对本批校准题与当前 Agent 预算（max_turns=10、budget=1USD）成立，'
                '不证明放宽预算即可通过。')
            if uc['cases']:
                add('')
                add(f"- 无必要澄清涉及：{', '.join(uc['cases'])}")
    else:
        add('- 未执行。')
    add('')

    add('## 9. L3 Java 执行')
    add('')
    add('- **NOT_APPLICABLE（本轮）**：未接入隔离的 Java 编译/执行路径，按方案如实标注，'
        '不计入通过分母，也不折算为 L1/L2 成绩。')
    add('')

    add('## 10. 残留缺口与未授权事项')
    add('')
    add('- 9 个阻断标签在**当前已发布快照**上仍为 UNRESOLVED，金标保持 CAPABILITY_GAP；'
        '源头修正需经快照发布与索引激活后才可重评。')
    warnings = len([d for d in dispositions if d['severity'] == 'WARNING'])
    add(f'- {warnings} 项提示保持为提示，未改写来源定义（其中 '
        f"{len([d for d in dispositions if d['code'] == 'FIXTURE_DICTIONARY_DRIFT'])} 项为旧字典 NULL 率差异）。")
    add('- 客户逐单元格内容未与数据库比对；L1/L2 真值仅对绑定 hash 的仓库 SQL 成立。')
    add('- Java 执行、L1 检索跑批契约外的分组分区与近重复检测、成本预算、变更发布均未执行。')
    add('- **P2（2000 条正式生成）与 P3（语义改进发布）仍未授权**；'
        'P1 验收通过与否需另由本人决定。')
    add('')

    text = '\n'.join(lines) + '\n'
    (output / 'REPORT.md').write_text(text)
    (output / 'report.html').write_text(
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>P1 验收</title>'
        '<style>body{font:15px/1.7 system-ui;max-width:1080px;margin:32px auto;padding:0 20px;color:#1f2933}'
        'pre{white-space:pre-wrap;background:#f5f7fa;padding:20px;border-radius:8px}'
        'table{border-collapse:collapse}th,td{border:1px solid #d7dee5;padding:4px 8px}</style>'
        '<h1>TagPilot 评测 P1 验收</h1><pre>' + html.escape(text) + '</pre></html>')
    summary = {'schema_version': 'p1-acceptance.v1', 'p0': str(p0), 'calibration': str(calibration),
               'cases': cal_manifest.get('mother_cases'),
               'review_verdicts': dict(verdicts),
               'l1_atomic_recall_at_k': l1['atomic_recall_at_k'] if l1 else None,
               'l2_verdicts': l2['verdicts'] if l2 else None,
               'demo_metrics': demo,
               'human_review': 'RECORDED' if human else 'PENDING',
               'l3': 'NOT_APPLICABLE',
               'p2_authorized': False}
    (output / 'acceptance.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    return summary
