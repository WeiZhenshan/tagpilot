"""从 evaluate_workbench 报告生成指标与门禁对照。

用法：PYTHONPATH=tagpilot-agent tagpilot-agent/.venv/bin/python tagpilot-agent/scripts/eval_metrics.py <报告.json> <输出.json>
"""
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

CASES = 'sql/indiv_cust/2000_cust_generate/客群圈选Agent自然语言测试案例.md'
BASELINE = {'source': 'tagpilot-agent/out/architecture-typical-20260923（LangGraph 11 个典型案例 ×3，迁移前留档）',
            'ready': '23/30 = 76.7%', 'p50_seconds': 63.5, 'p95_seconds': 180}


def percentiles(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return {'n': 0}
    def pick(fraction):
        index = min(len(values) - 1, max(0, round(fraction * (len(values) - 1))))
        return values[index]
    return {'n': len(values), 'p50': pick(.5), 'p95': pick(.95), 'max': values[-1]}


def gold_flags(path):
    flags = {}
    for line in Path(path).read_text().splitlines():
        match = re.match(r'^\| ([A-K]\d\d) \|', line)
        if not match:
            continue
        cells = [cell.strip() for cell in line.split('|')]
        flags[match.group(1)] = cells[3]
    return flags


def first_draft_ms(events):
    started = next((event.get('occurred_at') for event in events if event.get('type') == 'run.started'), None)
    draft = next((event.get('occurred_at') for event in events if event.get('type') in {'plan.observed', 'intent.ready'}), None)
    if started and draft and draft >= started:
        return round((draft - started) * 1000)
    return None


def main():
    report = json.loads(Path(sys.argv[1]).read_text())
    output = Path(sys.argv[2])
    flags = gold_flags(CASES)
    runs = report['results']
    stats_rows = [((row.get('outcome') or {}).get('stats') or {}) for row in runs]
    outcomes = Counter((row.get('outcome') or {}).get('outcome') or 'NONE' for row in runs)
    statuses = Counter(row['status'] for row in runs)
    ready_runs = [row for row in runs if (row.get('outcome') or {}).get('outcome') == 'READY' and (row.get('plan') or {}).get('valid')]
    diagnostics = Counter()
    for row in runs:
        for diagnostic in (row.get('plan') or {}).get('diagnostics') or []:
            diagnostics[diagnostic.get('code')] += 1
    per_flag = {}
    for flag in sorted(set(flags.values())):
        rows = [row for row in runs if flags.get(row['case']) == flag]
        if not rows:
            continue
        per_flag[flag] = {
            'runs': len(rows),
            'ready_rate': round(sum(1 for row in rows if (row.get('outcome') or {}).get('outcome') == 'READY' and (row.get('plan') or {}).get('valid')) / len(rows), 4),
            'seconds': percentiles([row.get('seconds') for row in rows])}
    direct_asks = [row['case'] for row in runs if flags.get(row['case']) == '直达'
                   and (row.get('outcome') or {}).get('outcome') == 'NEEDS_USER_INPUT']
    metrics = {
        'report': str(sys.argv[1]),
        'runs': len(runs),
        'cases': len({row['case'] for row in runs}),
        'ready_and_valid_rate': round(len(ready_runs) / len(runs), 4),
        'plans_valid_rate': round(sum(1 for row in runs if (row.get('plan') or {}).get('valid')) / len(runs), 4),
        'outcome_counts': dict(outcomes),
        'status_counts': dict(statuses),
        'seconds': percentiles([row.get('seconds') for row in runs]),
        'first_draft_ms': percentiles([first_draft_ms(row.get('events') or []) for row in runs]),
        'timeouts': sum(1 for stats in stats_rows if stats.get('stop_reason') == 'timeout'),
        'memory_limit_stops': sum(1 for stats in stats_rows if stats.get('stop_reason') == 'memory_limit'),
        'forced_partial': sum(1 for stats in stats_rows if stats.get('forced_partial')),
        'submit_rejections_total': sum(stats.get('submit_rejections') or 0 for stats in stats_rows),
        'deep_calls_total': sum(stats.get('deep') or 0 for stats in stats_rows),
        'tools_total': sum(stats.get('tools') or 0 for stats in stats_rows),
        'llm_turns': percentiles([stats.get('llm_turns') for stats in stats_rows]),
        'cli_peak_rss_mb': percentiles([stats.get('cli_peak_rss_mb') for stats in stats_rows]),
        'cli_start_ms': percentiles([stats.get('cli_start_ms') for stats in stats_rows]),
        'sdk_cost_estimate_usd_total': round(sum(stats.get('sdk_cost_estimate_usd') or 0 for stats in stats_rows), 4),
        'diagnostic_codes': dict(diagnostics.most_common()),
        'per_gold_flag': per_flag,
        'unnecessary_ask_cases': direct_asks,
        'baseline_reference': BASELINE,
        'case_level': {},
    }
    by_case = {}
    for row in runs:
        by_case.setdefault(row['case'], []).append(row)
    for case, rows in sorted(by_case.items()):
        metrics['case_level'][case] = {
            'flag': flags.get(case),
            'outcomes': [((row.get('outcome') or {}).get('outcome')) for row in rows],
            'seconds': [row.get('seconds') for row in rows],
            'valid': [bool((row.get('plan') or {}).get('valid')) for row in rows],
            'consistent': len({(row.get('outcome') or {}).get('outcome') for row in rows}) == 1}
    stable = [case for case, data in metrics['case_level'].items() if data['consistent']]
    metrics['outcome_stability'] = {'cases': len(by_case), 'stable_cases': len(stable),
                                    'stable_rate': round(len(stable) / len(by_case), 4) if by_case else None}
    output.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: metrics[key] for key in ('runs', 'ready_and_valid_rate', 'plans_valid_rate', 'outcome_counts',
                                                    'seconds', 'first_draft_ms', 'timeouts', 'unnecessary_ask_cases',
                                                    'diagnostic_codes', 'outcome_stability')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
