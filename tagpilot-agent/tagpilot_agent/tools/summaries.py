"""展示摘要只使用授权证据和业务文案，不传出诊断代码。"""
import re


def display_target(text):
    # 检索词可能混入聚合术语；仅清理展示，不改变实际检索参数。
    text = re.sub(r'\b(?:SUM|COUNT|AVG|MAX|MIN)\b', '', str(text), flags=re.I)
    if re.search(r'[{}]|\bR\d+\b|\b(?:SQL|SELECT|FROM|WHERE|JOIN)\b|[a-zA-Z]+_\w+', text, re.I):
        return '圈选条件'
    return re.sub(r'\s+', ' ', text).strip()[:80] or '圈选条件'


def leaves(tree):
    if not isinstance(tree, dict) or not tree:
        return []
    if "children" in tree:
        return [n for child in tree["children"] for n in leaves(child)]
    return [tree]

UNITS = {'CNY': '元', 'COUNT': '次', 'RATIO': '比例', 'PERSON': '人', 'DAY': '天', 'MONTH': '月'}


def started_fields(ctx, name, args):
    targets, refs, queries = [], [], []
    if name == 'find_tags':
        for q in args.get('queries', [])[:8]:
            if not isinstance(q, dict):
                continue
            text = display_target(q.get('text', ''))
            rid = q.get('requirement_id')
            targets.append(text)
            queries.append({'text': text, 'requirement_id': rid})
            if rid:
                refs.append(rid)
    elif name == 'get_tag_details':
        ids = args.get('tag_ids', [])
        targets = [ctx.tags[tid]['name'] for tid in ids if tid in ctx.eligible and tid in ctx.tags and ctx.tags[tid].get('name')]
        refs = [rid for tid in ids for rid in sorted(ctx.tag_requirements.get(tid, set()))]
        for node in leaves((ctx.best_plan or {}).get('tree', {})):
            if node.get('tag_id') in ids:
                refs.extend(node.get('requirement_ids', []))
    elif name == 'find_capabilities':
        targets = [display_target(args['query'])] if args.get('query') else []
        refs = args.get('requirement_ids', [])
    else:
        refs = [rid for node in leaves(args.get('plan', {}).get('tree', {})) for rid in node.get('requirement_ids', [])]
    fields = {'targets': targets[:10], 'requirement_ids': list(dict.fromkeys(refs))[:30]}
    if name == 'find_tags':
        fields.update(queries=queries, depth=args.get('depth', 'quick'))
    return fields


def completed_fields(ctx, name, result):
    ok = result.get('ok') is not False
    data = {'ok': ok, 'items': []}
    if result.get('code') in {'TOOL_BUDGET', 'BUDGET_CONVERGE'}:
        return {**data, 'summary': '正在整理已确认的条件'}
    if name == 'check_plan' and 'clauses' in result:
        pending = len(result.get('diagnostics', []))
        found = sum(c.get('status_hint') == 'BOUND' for c in result['clauses'])
        return {**data, 'summary': f'{found} 项条件已核验' + (f'；还有 {pending} 项待处理' if pending else ''),
                'counts': {'found': found, 'pending': pending}}
    if not ok:
        return {**data, 'summary': '本次处理暂未完成，已保留当前进度'}
    ids = []
    if name == 'find_tags':
        ids = [c['tag_id'] for row in result.get('results', []) for c in row.get('cards', []) if 'tag_id' in c]
    elif name == 'get_tag_details':
        ids = [t['tag_id'] for t in result.get('tags', [])]
    names = [ctx.tags[tid]['name'] for tid in dict.fromkeys(ids) if tid in ctx.eligible and tid in ctx.tags and ctx.tags[tid].get('name')]
    data['items'] = [{'name': n} for n in names[:5]]
    if name == 'find_tags':
        data.update(summary=f'找到 {len(names)} 个相关标签' if names else '暂未命中，换个说法再试', counts={'found': len(names)})
    elif name == 'get_tag_details':
        details = result.get('tags', [])
        bits = []
        for t in details[:1]:
            caliber = t.get('caliber_struct') or {}
            if caliber.get('time_window_value') and caliber.get('time_window_unit') in {'DAY', 'MONTH', 'YEAR'}:
                unit = {'DAY': '天', 'MONTH': '个月', 'YEAR': '年'}[caliber['time_window_unit']]
                bits.append(f"近{caliber['time_window_value']}{unit}")
            if t.get('unit') in UNITS or t.get('unit') in UNITS.values():
                bits.append('单位：' + UNITS.get(t['unit'], t['unit']))
            if t.get('code_count'):
                bits.append(f"{t['code_count']} 个取值")
        data['summary'] = '口径：' + ' · '.join(bits) if bits else (f'已核对 {len(details)} 项标签口径' if details else '暂未取得可核验的口径')
    elif name == 'find_capabilities':
        count = len(result.get('capabilities', []))
        data.update(summary=f'找到 {count} 项已发布业务定义' if count else '暂无相关已发布业务定义', counts={'found': count})
    elif name == 'submit_result':
        data['summary'] = '方案已整理'
    return data
