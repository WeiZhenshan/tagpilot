"""P2 覆盖报告：给出总标签数、事实可确认数、可表达数、具备执行样本数，以及码值覆盖。

方案 §二.2 的覆盖义务（177 个码值字段全覆、"每个业务标签至少在两个母案例中"）按 10,000 条档
写成；本轮 2,000 条档达不到的部分**如实标 NOT_MET 与差额**，不做静默处理。
"""
import json
from collections import Counter
from pathlib import Path

from .io import file_hash, fresh_directory, read_jsonl, write_json, write_jsonl
from .oracle import references
from .validation import verify_package

CODE_FIELD_TARGET = 177
CODE_VALUE_TARGET = 1723
TAGS_PER_MOTHER_TARGET = 2


def code_value_sweep(facts):
    """码值的确定性存在性与类型校验：逐字段逐码值检查，不依赖任何案例。"""
    fields = 0
    values = 0
    problems = []
    for tag_id, fact in sorted(facts.items()):
        codes = fact.get('codes') or []
        if not codes:
            continue
        fields += 1
        seen = set()
        for code in codes:
            values += 1
            raw = code.get('code')
            if not isinstance(raw, str) or not raw:
                problems.append({'tag_id': tag_id, 'code': raw, 'code_problem': 'NOT_A_STRING'})
                continue
            if raw in seen:
                problems.append({'tag_id': tag_id, 'code': raw, 'code_problem': 'DUPLICATE'})
            seen.add(raw)
            if not str(code.get('definition') or '').strip():
                problems.append({'tag_id': tag_id, 'code': raw, 'code_problem': 'MISSING_DEFINITION'})
    return {'code_fields': fields, 'code_values': values, 'problems': problems}


def coverage(p0, cases_dir, output, authorization, cases_filename='cases.jsonl'):
    p0, cases_dir, output = Path(p0), Path(cases_dir), Path(output)
    manifest = verify_package(cases_dir)
    facts = {r['tag_id']: r for r in read_jsonl(p0 / 'facts.jsonl')}
    cases = read_jsonl(cases_dir / cases_filename)

    targets = Counter(tag for case in cases for tag in case['target_tag_ids'])
    with_tree, with_executable = set(), set()
    for case in cases:
        stages = [case['expected']] + [turn['expected'] for turn in case['turns']]
        for expectation in stages:
            tree = expectation.get('tree')
            if not tree:
                continue
            with_tree |= references(tree)
            if case['l3_status'] == 'FIXTURE_ORACLE_AVAILABLE':
                with_executable |= references(tree)
    code_fields = {tag for tag, fact in facts.items() if fact.get('codes')}
    covered_code_fields = code_fields & set(targets)
    sweep = code_value_sweep(facts)

    report = {
        'schema_version': 'p2-coverage.v1',
        'tags': {
            'total': len(facts),
            'source_confirmable': sum(1 for fact in facts.values()
                                      if fact['fact_status'] == 'VERIFIED_SOURCE'),
            'unresolved': sum(1 for fact in facts.values() if fact['fact_status'] == 'UNRESOLVED'),
            'expressible_in_a_standard_tree': len(with_tree),
            'with_execution_sample': len(with_executable),
            'appearing_as_target': len(targets),
        },
        'code_fields': {
            'total': len(code_fields), 'covered_as_target': len(covered_code_fields),
            'target': CODE_FIELD_TARGET,
            'status': 'MET' if len(covered_code_fields) >= CODE_FIELD_TARGET else 'NOT_MET',
            'shortfall': max(0, CODE_FIELD_TARGET - len(covered_code_fields)),
        },
        'code_values': {
            'total': sweep['code_values'], 'target': CODE_VALUE_TARGET,
            'validated': sweep['code_values'] - len({(p['tag_id'], p['code']) for p in sweep['problems']}),
            'problems': sweep['problems'][:50], 'problem_count': len(sweep['problems']),
            'status': 'MET' if sweep['code_values'] >= CODE_VALUE_TARGET and not sweep['problems']
                      else 'NOT_MET',
        },
        'tags_in_at_least_two_mothers': {
            'achieved': sum(1 for count in targets.values() if count >= TAGS_PER_MOTHER_TARGET),
            'required_for_all_tags': len(facts) * TAGS_PER_MOTHER_TARGET,
            'target': f'每个标签至少出现在 {TAGS_PER_MOTHER_TARGET} 个母案例中',
            'status': 'NOT_MET' if len(targets) < len(facts) else 'MET',
            'note': '该义务按 10,000 条档（约 2,500 母案例）写成；2,000 条档的母案例数供不出 '
                    '全部 969 个标签各两次。差额如实列出，不用重复题充数。',
        },
        'by_split': dict(Counter(case['split'] for case in cases)),
        'by_category': dict(Counter(case['category'] for case in cases)),
        'target_tag_domains': dict(Counter(facts[tag]['domain'] for tag in targets if tag in facts)),
        'p0_manifest_sha256': file_hash(p0 / 'manifest.json'),
        'cases_manifest_sha256': file_hash(cases_dir / 'manifest.json'),
        'supersedes': manifest.get('schema_version'),
        'authorization': authorization,
    }
    output = fresh_directory(output)
    write_json(output / 'coverage.json', report)
    write_jsonl(output / 'uncovered-code-fields.jsonl', [
        {'tag_id': tag, 'field_name': facts[tag]['field_name'], 'name': facts[tag]['name'],
         'domain': facts[tag]['domain'], 'codes': len(facts[tag]['codes'])}
        for tag in sorted(code_fields - covered_code_fields)])
    write_json(output / 'manifest.json', {
        'schema_version': 'p2-coverage.v1', 'phase': 'P2', 'status': 'MEASURED',
        'authorization': authorization,
        'files': {p.name: file_hash(p) for p in output.iterdir() if p.is_file()}})
    return report
