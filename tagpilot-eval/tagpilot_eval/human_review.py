"""收尾第 4 项：人工抽检页与结论导入。

抽检队列按类别分层、以 case_id 摘要排序确定，可复现。页面自包含（无外部依赖），
逐题给出原话、标准树、来源事实证据与独立复核结论，供本人做业务合理性与自然表达复核。
页面导出的 JSON 由 import_decisions 校验后写入复核台账；不覆盖既有审核记录。
"""
import html
import json
from pathlib import Path

from .io import digest, file_hash, read_jsonl, write_json, write_jsonl

SAMPLE = {'SINGLE': 8, 'COMPOSITION': 8, 'CLARIFICATION': 8, 'BOUNDARY': 6, 'MULTITURN': 5, 'GAP': 5}
_OP_WORD = {'>=': '≥', '>': '>', '<=': '≤', '<': '<', '=': '=', '!=': '≠',
            'in': '属于', 'not_in': '不属于', 'between': '介于', 'contains': '包含',
            'is_null': '为空', 'is_not_null': '不为空'}


def stratified_queue(cases, sample=None):
    sample = sample or SAMPLE
    chosen = []
    for category, size in sample.items():
        rows = sorted([c for c in cases if c['category'] == category],
                      key=lambda c: digest(c['case_id']))
        chosen.extend(rows[:size])
    return chosen


def _render_tree(tree, facts, indent=0):
    pad = '&nbsp;' * (indent * 4)
    if tree is None:
        return f'{pad}<i>（本题无标准树）</i>'
    if tree['kind'] == 'SCOPE_ALL':
        return f'{pad}<b>全部客户</b>（不加任何经营条件）'
    if tree['kind'] == 'GROUP':
        lines = [f'{pad}<b>{" 且 " if tree["logic"] == "AND" else " 或 "}</b>']
        lines += [_render_tree(child, facts, indent + 1) for child in tree['children']]
        return '<br>'.join(lines)
    expr = tree['expression']
    if expr['kind'] == 'TAG':
        fact = facts.get(expr['tag_id'], {})
        name = fact.get('name', f"标签{expr['tag_id']}")
        unit = fact.get('published_semantics', {}).get('unit', expr.get('unit', ''))
        values = tree.get('values') or []
        rendered = '、'.join(values)
        word = _OP_WORD.get(tree.get('operator'), tree.get('operator') or '')
        caliber = tree.get('caliber') or {}
        bits = [f'{k}={v}' for k, v in caliber.items()
                if k in ('time_anchor_label', 'statistic', 'scope', 'calendar_mode') and v not in (None, 'ALL')]
        suffix = f' <span class="cal">[{"; ".join(bits)}]</span>' if bits else ''
        return (f'{pad}<b>{html.escape(name)}</b> <code>{expr["tag_id"]}</code> '
                f'{word} {html.escape(rendered)} <span class="unit">{html.escape(str(unit))}</span>{suffix}')
    args = expr.get('args') or []
    rendered = expr['kind']
    if args:
        rendered += '(' + ', '.join(str(a.get('tag_id') or a.get('value')) for a in args) + ')'
    else:
        rendered += f"({expr.get('value')})"
    return f'{pad}<code>{html.escape(rendered)}</code> {_OP_WORD.get(tree.get("operator"), "")} {tree.get("values")}'


def build_page(p0, calibration, reviews_path, output, sample=None):
    p0, calibration, output = Path(p0), Path(calibration), Path(output)
    facts = {r['tag_id']: r for r in read_jsonl(p0 / 'facts.jsonl')}
    cases = read_jsonl(calibration / 'cases.jsonl')
    reviews = {r['case_id']: r for r in read_jsonl(reviews_path)}
    queue = stratified_queue(cases, sample)
    if output.exists():
        raise ValueError('输出目录已存在')
    output.mkdir(parents=True)
    blocks, template = [], []
    for case in queue:
        review = reviews[case['case_id']]
        evidence = []
        for tag in case['target_tag_ids']:
            fact = facts.get(tag, {})
            semantics = fact.get('published_semantics', {})
            caliber = {k: v for k, v in (semantics.get('caliber_struct') or {}).items() if v is not None}
            evidence.append({'tag_id': tag, 'name': fact.get('name'), 'type': fact.get('tag_type'),
                             'unit': semantics.get('unit'), 'scale': semantics.get('unit_scale'),
                             'status': fact.get('fact_status'), 'concept': semantics.get('concept_name'),
                             'caliber': caliber,
                             'codes': [f"{c['code']}={c['definition']}" for c in fact.get('codes', [])][:10],
                             'source': [m.get('name') for m in
                                        (fact.get('source_evidence', {}).get('original_matches') or [])]})
        turns = [t['user_message'] for t in case['turns']]
        flags = review.get('caveats', [])
        template.append({'case_id': case['case_id'], 'decision': None, 'comment': None})
        blocks.append(_block(case, evidence, turns, review, flags, facts))
    page = _page(blocks, template)
    (output / 'human-review.html').write_text(page)
    write_jsonl(output / 'human-review-template.jsonl', template)
    write_json(output / 'queue.json', {'cases': [c['case_id'] for c in queue],
                                       'calibration_sha256': file_hash(calibration / 'cases.jsonl'),
                                       'reviews_sha256': file_hash(reviews_path),
                                       'sample': SAMPLE})
    return {'queued': len(queue), 'page': str(output / 'human-review.html')}


def _block(case, evidence, turns, review, flags, facts):
    rows = ''.join(
        f"<tr><td><code>{e['tag_id']}</code></td><td>{html.escape(str(e['name']))}</td>"
        f"<td>{html.escape(str(e['type']))}</td><td>{html.escape(str(e['unit']))}"
        f"{'' if str(e['scale']) in ('1','1.0','1.0000','None') else ' ×'+html.escape(str(e['scale']))}</td>"
        f"<td>{html.escape(str(e['status']))}</td><td>{html.escape('; '.join(e['codes']))}</td>"
        f"<td>{html.escape(str(e['caliber']))}</td></tr>" for e in evidence)
    turn_html = ''.join(f'<li>{html.escape(t)}</li>' for t in turns) or '<li><i>无后续轮次</i></li>'
    flag_html = ''.join(f'<div class="flag">{html.escape(f)}</div>' for f in flags) or ''
    return f'''
<details class="case" data-case="{case['case_id']}">
 <summary><b>{case['case_id']}</b> · {html.escape(case['category'])} · {html.escape(case['scenario'])}
   <span class="outcome">{'/'.join(case['expected']['outcomes'])}</span></summary>
 <div class="req">原话：{html.escape(case['requirement'])}</div>
 <div class="turn"><b>后续轮次</b><ul>{turn_html}</ul></div>
 <div class="tree"><b>标准语义</b><br>{_render_tree(case['expected'].get('tree'), facts)}</div>
 <table><tr><th>标签</th><th>名称</th><th>类型</th><th>单位</th><th>事实状态</th><th>码值</th><th>口径</th></tr>{rows}</table>
 <div class="ind">独立复核：<b>{review['verdict']}</b> — {html.escape(review['reason'])}</div>
 {flag_html}
 <div class="decide">
  <label><input type="radio" name="{case['case_id']}" value="ACCEPT"> 接受</label>
  <label><input type="radio" name="{case['case_id']}" value="REJECT"> 拒绝</label>
  <label><input type="radio" name="{case['case_id']}" value="ACCEPT_WITH_COMMENT"> 接受但需修订</label>
  <input class="comment" data-case="{case['case_id']}" placeholder="原因/修订建议（拒绝或需修订时必填）">
 </div>
</details>'''


def _page(blocks, template):
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>P1 人工抽检（40 题）</title>
<style>
body{{font:15px/1.7 system-ui;max-width:1180px;margin:32px auto;padding:0 20px;color:#1f2933}}
h1{{font-size:24px}} code{{background:#eef2f6;padding:1px 5px;border-radius:4px}}
table{{border-collapse:collapse;width:100%;margin:8px 0;font-size:13px}}
th,td{{border:1px solid #d7dee5;padding:4px 7px;text-align:left;vertical-align:top}}
th{{background:#f5f7fa}} .case{{border:1px solid #d7dee5;border-radius:8px;margin:12px 0;padding:10px 14px}}
summary{{cursor:pointer}} .req{{font-size:16px;margin:8px 0;color:#111}}
.outcome{{color:#0b6b3a;font-weight:600}} .unit{{color:#6b7280}}
.cal{{color:#8a5a00}} .flag{{background:#fff4e5;border-left:4px solid #d98600;padding:6px 10px;margin:6px 0}}
.ind{{background:#eef6ff;border-left:4px solid #2b6cb0;padding:6px 10px;margin:6px 0}}
.decide{{margin-top:8px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}}
.comment{{flex:1;min-width:260px;padding:5px 8px;border:1px solid #cbd5e1;border-radius:5px}}
button{{font:15px system-ui;padding:8px 16px;border:0;border-radius:6px;background:#1f6feb;color:#fff;cursor:pointer}}
textarea{{width:100%;height:150px;font:12px ui-monospace,monospace}}
.bar{{position:sticky;top:0;background:#fff;padding:10px 0;border-bottom:1px solid #e5e9ef;z-index:5}}
</style>
<div class="bar"><h1>P1 人工抽检 · 40 题</h1>
<p>逐题复核<b>业务合理性</b>与<b>自然表达</b>。标准树与来源事实仅在评测控制面使用，不得进入被测 Agent。完成后点“生成结论”并复制回会话。</p>
<button onclick="collect()">生成结论</button> <span id="done"></span></div>
{''.join(blocks)}
<h2>导出的结论</h2><textarea id="out" placeholder="点击上方“生成结论”"></textarea>
<script>
function collect(){{
 var out=[]; var missing=0;
 document.querySelectorAll('.case').forEach(function(c){{
   var id=c.dataset.case; var sel=c.querySelector('input[type=radio]:checked');
   var comment=c.querySelector('.comment').value.trim();
   if(!sel){{missing++; return;}}
   if(sel.value!=='ACCEPT' && !comment){{missing++; return;}}
   out.push({{case_id:id, decision:sel.value, comment:comment||null}});
 }});
 document.getElementById('out').value=JSON.stringify(out,null,1);
 document.getElementById('done').textContent='已生成 '+out.length+' 条'+(missing?('；'+missing+' 题未完成（需选择，拒绝/需修订须填原因）'):'');
}}
</script></html>'''


def import_decisions(queue_path, decisions_path, output_ledger):
    """校验导出结论并写入复核台账；缺题或缺原因即拒绝。"""
    queue = json.loads(Path(queue_path).read_text())
    decisions = json.loads(Path(decisions_path).read_text())
    expected = set(queue['cases'])
    seen = {}
    for row in decisions:
        if row['case_id'] not in expected:
            raise ValueError('结论包含队列外的题: ' + row['case_id'])
        if row['decision'] not in {'ACCEPT', 'REJECT', 'ACCEPT_WITH_COMMENT'}:
            raise ValueError('未知决策: ' + str(row['decision']))
        if row['decision'] != 'ACCEPT' and not (row.get('comment') or '').strip():
            raise ValueError('拒绝或需修订必须填原因: ' + row['case_id'])
        seen[row['case_id']] = row
    if set(seen) != expected:
        raise ValueError(f"结论未覆盖全部 {len(expected)} 题，缺少 {len(expected - set(seen))} 题")
    rows = [{'case_id': cid, 'decision': seen[cid]['decision'],
             'comment': seen[cid].get('comment'), 'reviewer': 'USER',
             'reviewed_at': queue.get('reviewed_at'), 'calibration_sha256': queue['calibration_sha256']}
            for cid in sorted(expected)]
    Path(output_ledger).parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_ledger, rows)
    from collections import Counter
    return {'imported': len(rows), 'decisions': dict(Counter(r['decision'] for r in rows))}
