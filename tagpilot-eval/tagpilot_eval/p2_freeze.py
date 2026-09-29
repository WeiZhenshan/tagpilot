"""P2 验收冻结：把版本清单、四层结果、覆盖与**未达标项**冻结成一份报告。

与 P1 的 `freeze.py` 分开写：P1 那份的文字与口径是 P1 专属的，参数化它会破坏已交付版本的
可复现性。本模块只做一件事——把已经产出的证据汇总，并**如实标注缺口**，不美化。
"""
import json
from collections import Counter
from pathlib import Path

from .io import file_hash, fresh_directory, read_jsonl, write_json
from .validation import verify_package


def _hash(path):
    path = Path(path)
    return {'file': str(path), 'sha256': file_hash(path)[:16] + '…'} if path.exists() else None


def _variants_summary(variants_dir):
    rows = read_jsonl(Path(variants_dir) / 'variants.jsonl') if (Path(variants_dir) / 'variants.jsonl').exists() else []
    return {'variants': len(rows),
            'back_translation': dict(Counter(row.get('back_translation') for row in rows)),
            'quarantined': _count(Path(variants_dir) / 'quarantine.jsonl')}


def _count(path):
    path = Path(path)
    return sum(1 for line in path.read_text().splitlines() if line.strip()) if path.exists() else 0


def freeze_p2(p0, cases_dir, l1_dir, l2_dir, reviews_path, coverage_dir, variants_dir,
              mothers_dir, split_dir, output, authorization, diagnosis_dir=None):
    p0, cases_dir = Path(p0), Path(cases_dir)
    variants_dir, mothers_dir, split_dir = Path(variants_dir), Path(mothers_dir), Path(split_dir)
    reviews_path = Path(reviews_path)
    verify_package(p0)
    cases_manifest = verify_package(cases_dir)
    cases = read_jsonl(cases_dir / 'cases.jsonl')
    l1 = _load(l1_dir, 'l1-summary.json') or {}
    l2 = _load(l2_dir, 'l2-summary.json') or {}
    coverage = _load(coverage_dir, 'coverage.json') or {}
    diagnosis = _load(diagnosis_dir, 'diagnosis.json') if diagnosis_dir else None
    reviews = read_jsonl(reviews_path) if Path(reviews_path).exists() else []

    versions = {
        '事实包 manifest': _hash(p0 / 'manifest.json'),
        '事实清单 facts.jsonl': _hash(p0 / 'facts.jsonl'),
        '根因报告 diagnosis.json': _hash(Path(diagnosis_dir) / 'diagnosis.json') if diagnosis_dir else None,
        '母案例 cases.jsonl': _hash(mothers_dir / 'cases.jsonl'),
        '分区 manifest': _hash(split_dir / 'manifest.json'),
        '模型改写 variants.jsonl': _hash(variants_dir / 'variants.jsonl'),
        '正式案例 manifest': _hash(cases_dir / 'manifest.json'),
        '正式案例 cases.jsonl': _hash(cases_dir / 'cases.jsonl'),
        '独立复核 reviews.jsonl': _hash(reviews_path),
        'L1 l1-summary.json': _hash(Path(l1_dir) / 'l1-summary.json'),
        'L2 l2-summary.json': _hash(Path(l2_dir) / 'l2-summary.json'),
        '覆盖报告 coverage.json': _hash(Path(coverage_dir) / 'coverage.json'),
    }
    active = json.loads((p0 / 'manifest.json').read_text())
    # 稳定性：计划 100 条×3，实际执行了几次要说清楚（预算受限时只跑了一部分）。
    l2_runs = read_jsonl(Path(l2_dir) / 'runs.jsonl') if (Path(l2_dir) / 'runs.jsonl').exists() else []
    stability_executed = sum(1 for run in l2_runs if run.get('repeat'))
    stability_planned = 100 * 3

    # 未达标与限制：逐项列出，不做隐藏。
    review_kinds = dict(Counter(row['verdict'] for row in reviews))
    limitations = [
        {'item': 'L2 稳定性复跑', 'status': 'NOT_MEASURED',
         'detail': f"计划 100 条×3 = {stability_planned} 次，实际执行 {stability_executed} 次"
                   f"（预算上限 $150 用尽后停止）。方案 §五.3 的「三次运行语义一致率 ≥90%」本轮**无证据**，"
                   f"不作推断、不给近似值。"},
        {'item': '回译独立核对', 'status': 'PARTIAL',
         'detail': f"改写中通过回译核对 {_variants_summary(variants_dir)['back_translation'].get('PASS', 0)} 条；"
                   f"其余为结构上无法比对（澄清/缺口/派生/全客群）或推理吃满 token，已分别计数。"},
        {'item': '码值字段覆盖', 'status': coverage.get('code_fields', {}).get('status', 'UNKNOWN'),
         'detail': f"覆盖 {coverage.get('code_fields', {}).get('covered_as_target', 0)}/"
                   f"{coverage.get('code_fields', {}).get('total', 0)}；差额已列出未覆盖清单。"},
        {'item': '每标签至少出现在 2 个母案例', 'status': 'NOT_MET',
         'detail': '该义务按 10,000 条档写成；2,000 条档的母案例数供不出全部 969 个标签各两次。'},
        {'item': 'AI 复核未产出结论', 'status': f"{review_kinds.get('UNAVAILABLE', 0)} 条",
         'detail': '复核模型未返回可解析 JSON；标记保留、不冒充已复核。'},
        {'item': 'AI 复核要求修改但未给改法', 'status': f"{review_kinds.get('REVISE', 0)} 条",
         'detail': '复核员判定不忠实或语气不自然但未给出具体改法；按设计保留并计数，转 P3 改进。'},
        {'item': 'L1 未全覆盖案例', 'status': f"{len(l1.get('failures') or [])} 例",
         'detail': '未进入 top-K；同一母案例的多条改写同时失败，指向标签消歧而非改写抖动。'},
        {'item': 'L3 Java 执行', 'status': 'NOT_APPLICABLE',
         'detail': '本轮未接入隔离的 Java 编译/执行路径，不计入通过分母。'},
    ]

    report = {
        'schema_version': 'p2-acceptance.v1',
        'phase': 'P2', 'authorization': authorization,
        'dataset_version': cases_dir.name,
        'active_snapshot': active['active_snapshot']['snapshot_id'],
        'active_build': active['active_build']['build_id'],
        'versions': versions,
        'dataset': {'cases': len(cases), 'mothers': len({c['mother_id'] for c in cases}),
                    'quotas': cases_manifest['quotas'],
                    'splits': dict(Counter(c['split'] for c in cases)),
                    'outcomes': dict(Counter(c['expected']['outcomes'][0] for c in cases)),
                    'target_tags': len({t for c in cases for t in c['target_tag_ids']})},
        'variants': _variants_summary(variants_dir),
        'review_verdicts': review_kinds,
        'coverage': coverage,
        'l1': {k: l1.get(k) for k in ('cases', 'conditions', 'atomic_recall_at_k',
                                      'all_conditions_covered_at_k', 'splits', 'holdout_excluded',
                                      'failures')},
        'l2': {**{k: l2.get(k) for k in ('runs', 'sampled_cases', 'stability_cases', 'agent_states',
                                         'sample_verdicts', 'by_category', 'by_split', 'stability',
                                         'cost_usd_estimate')},
               'stopped': l2.get('stopped') or 'PROCESS_STOPPED_AT_BUDGET_CAP',
               'stability_executed': stability_executed, 'stability_planned': stability_planned},
        'limitations': limitations,
        'diagnosis': ({k: diagnosis.get(k) for k in ('failed_total', 'timeouts', 'run_invalid',
                                                     'semantic_denominator', 'clusters',
                                                     'unattributed_mothers')}
                      if diagnosis else None),
    }

    output = fresh_directory(output)
    write_json(output / 'acceptance.json', report)
    (output / 'REPORT.md').write_text(_markdown(report))
    write_json(output / 'manifest.json', {
        'schema_version': 'p2-acceptance.v1', 'phase': 'P2', 'status': 'FROZEN',
        'authorization': authorization,
        'files': {p.name: file_hash(p) for p in output.iterdir() if p.is_file()}})
    return report


def _load(directory, name):
    path = Path(directory) / name
    return json.loads(path.read_text()) if path.exists() else None


def _markdown(report):
    lines = ['# TagPilot 评测 P2 验收（首期评测冻结）', '',
             f"数据集版本 `{report['dataset_version']}`（{report['dataset']['cases']} 条）；"
             f"活动快照 `{report['active_snapshot']}`；索引 `{report['active_build']}`。", '',
             '## 1. 数据集', '',
             f"- 母案例 {report['dataset']['mothers']}，正式案例 {report['dataset']['cases']}"
             f"（每母案例 4 条：1 条配方原话 + 3 条模型改写）",
             f"- 类别配额：{report['dataset']['quotas']}",
             f"- 分区：{report['dataset']['splits']}",
             f"- 终态分布：{report['dataset']['outcomes']}",
             f"- 覆盖标签：{report['dataset']['target_tags']}", '',
             '## 2. 改写核对与复核', '',
             f"- 回译核对：{report['variants']['back_translation']}",
             f"- 隔离改写：{report['variants']['quarantined']} 条",
             f"- 独立复核结论：{report['review_verdicts']}", '',
             '## 3. L1 检索与消歧', '',
             f"- 样本 {report['l1'].get('cases')} 例、{report['l1'].get('conditions')} 个原子条件；"
             f"k=20",
             f"- 原子条件 Recall@20 = **{report['l1'].get('atomic_recall_at_k')}**"
             f"（目标 ≥0.98）；全条件覆盖 "
             f"{report['l1'].get('all_conditions_covered_at_k')}/{report['l1'].get('cases')}",
             f"- 分区：{report['l1'].get('splits')}；HOLDOUT 是否排除：{report['l1'].get('holdout_excluded')}",
             f"- 未全覆盖：{report['l1'].get('failures')}", '',
             '## 4. L2 Agent 基线（真实运行）', '',
             f"- 运行 {report['l2'].get('runs')} 次；抽样 {report['l2'].get('sampled_cases')} 条；"
             f"稳定性复跑计划 100 条×3，实际执行 "
             f"{report['l2'].get('stability_executed')}/{report['l2'].get('stability_planned')} 次",
             f"- 抽样判定：{report['l2'].get('sample_verdicts')}",
             f"- 分层（类别）：{report['l2'].get('by_category')}",
             f"- 分层（分区）：{report['l2'].get('by_split')}",
             f"- 成本（SDK 估值）：{report['l2'].get('cost_usd_estimate')}；停止原因：{report['l2'].get('stopped')}", '',
             '## 5. 覆盖报告', '',
             f"- 标签：{report['coverage'].get('tags')}",
             f"- 码值字段：{report['coverage'].get('code_fields')}",
             f"- 码值校验：{report['coverage'].get('code_values', {}).get('status')}"
             f"（{report['coverage'].get('code_values', {}).get('validated')}/"
             f"{report['coverage'].get('code_values', {}).get('total')}）", '',
             '## 6. 失败根因', '']
    if report.get('diagnosis'):
        diag = report['diagnosis']
        lines += [f"- 未通过 {diag['failed_total']} 例；其中**硬超时 {diag['timeouts']} 例、无效运行 "
                  f"{diag['run_invalid']} 例单列**，不计入语义归因分母（{diag['semantic_denominator']}）",
                  f"- 证据不足以归因：{len(diag.get('unattributed_mothers') or [])} 例（不硬凑原因）", '',
                  '| 根因簇 | 影响母案例 | 严重度 | 处理方向 |', '|---|---:|---:|---|']
        lines += [f"| {c['cluster']} | {c['affected_mothers']} | {c['severity']} | {c['direction']} |"
                  for c in diag['clusters']]
    else:
        lines += ['- 未接入根因报告']
    lines += ['', '## 7. 未达标与限制（如实列出，不做隐藏）', '',
             '| 项 | 状态 | 说明 |', '|---|---|---|']
    lines += [f"| {item['item']} | {item['status']} | {item['detail']} |" for item in report['limitations']]
    lines += ['', '## 8. 版本清单', '', '| 工件 | sha256 |', '|---|---|']
    lines += [f"| {name} | `{(info or {}).get('sha256', '—')}` |" for name, info in report['versions'].items()]
    lines += ['', '> 本报告冻结上述哈希对应的工件；任何后续修订必须新建数据集版本与 manifest。']
    return '\n'.join(lines) + '\n'
