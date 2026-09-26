"""产生可查看的交付报告与40条人工抽检队列，不设置已审核状态。"""
import html
import json
from pathlib import Path

from .io import digest, read_jsonl, write_json, write_jsonl
from .validation import validate_package


def report(p0,calibration,output):
    p0,calibration,output=Path(p0),Path(calibration),Path(output)
    output.mkdir(parents=True,exist_ok=False)
    summary=json.loads((p0/'summary.json').read_text())
    manifest=json.loads((p0/'manifest.json').read_text())
    cases=read_jsonl(calibration/'cases.jsonl')
    validation=validate_package(p0,calibration)
    write_json(output/'validation.json',validation)
    sample=[]
    for category,n in {'SINGLE':8,'COMPOSITION':8,'CLARIFICATION':8,'BOUNDARY':6,'MULTITURN':5,'GAP':5}.items():
        sample.extend(sorted([c for c in cases if c['category']==category],key=lambda c:digest(c['case_id']))[:n])
    write_jsonl(output/'human-review-queue.jsonl',[{'case_id':c['case_id'],'requirement':c['requirement'],
                                                'expected':c['expected'],'turns':c['turns'],
                                                'review_status':'PENDING','reviewer':None,'comment':None} for c in sample])
    lines=['# P0事实审计与P1校准交付', '',
           '**范围：P0 + P1工程骨架与200个母案例。P2禁止；正式生成条数为0。**','',
           '## 当前发布状态','',
           f'- ACTIVE快照：`{manifest["active_snapshot"]["snapshot_id"]}`；ACTIVE索引：`{manifest["active_build"]["build_id"]}`。',
           f'- 实时只读观测时间：{json.loads((p0/"live-observation.json").read_text())["observed_at"]}。',
           f'- Milvus行集对账：{manifest["index_verified"]}。快照/manifest文件hash与数据库登记值一致。',
           '- 基线检索模型与重排：BGE-M3 / bge-reranker-v2-m3。manifest内NOT_EVALUATED不等于没有历史报告，也不代表本轮评测通过。','',
           '## P0审计','',
           f'- 审计 {summary["business_tags"]} 个业务标签、{summary["code_fields"]} 个码值字段、{summary["code_values"]} 个码值。对象键单列排除。',
           f'- 源事实状态：{summary["fact_status"]}。VERIFIED_SOURCE仅表示当前来源可对应，不是银行业务签署。',
           f'- 问题：{summary["issue_severity"]}；分类：{summary["issue_codes"]}。',
           f'- 仓库SQL实际解析 {summary["fixture_rows_parsed"]} 行，字段数据覆盖：{summary["fixture_coverage"]}。',
           '- 数据库只核对模拟行数；客户逐单元格内容尚未比对。仓库SQL版本与旧字段字典的NULL率差异单列记录，不能按旧文档宣称全部同版。',
           '- 冲突保留在issues.jsonl，未修改标签、语义、客户数据或发布版本。','',
           '## P1工程和数据','',
           f'- 200个母案例，{validation["lineage_groups"]}个谱系组；每个母案例只有一个首轮原话。',
           f'- 类别：{validation["categories"]}；首轮终态：{validation["outcomes"]}。',
           f'- 关联 {validation["target_tags"]} 个标签；这是校准覆盖，不是969标签全覆盖。',
           f'- 契约与事实检查通过：{validation["passed"]}，错误数：{len(validation["errors"])}。',
           '- 已实现独立Decimal/日期/NULL解释器、边界探针、完整模拟ID集hash；尚未做真实Agent或Java执行。',
           '- 案例为Agent编写配方后确定性物化，独立模型复核未执行，40条人工抽检队列待审核。',
           '- P1仅CALIBRATION分区，禁止把现有案例改名充当独立留出集。',
           '- 无付费API调用、无2000条扩写、无语义写回、无索引重建。','',
           '## 200个校准母案例','',
           '| ID | 类别 | 场景 | 原话 | 预期首轮 | 人工抽检 |','|---|---|---|---|---|---|']
    selected={c['case_id'] for c in sample}
    for c in cases:
        lines.append('| '+' | '.join([c['case_id'],c['category'],c['scenario'],c['requirement'].replace('|','\\|'),
                                     '/'.join(c['expected']['outcomes']),'待审核' if c['case_id'] in selected else '未抽中'])+' |')
    lines+=['','## 后续边界','','本次交付完成P0审计和P1骨架/母案例，不宣称P1人工校准、独立模型复核或真实Agent评测已完成。进入P2需要用户另行授权。']
    text='\n'.join(lines)+'\n'
    (output/'REPORT.md').write_text(text)
    blocks=[]
    for c in cases:
        body=html.escape(json.dumps({'expected':c['expected'],'turns':c['turns'],'truth_basis':c['truth_basis']},ensure_ascii=False,indent=2))
        blocks.append(f'<details><summary>{html.escape(c["case_id"]+" · "+c["category"]+" · "+c["requirement"])}</summary><pre>{body}</pre></details>')
    (output/'report.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>P0/P1校准交付</title><style>body{font:16px/1.65 system-ui;max-width:1100px;margin:40px auto;padding:0 24px;color:#223}pre{white-space:pre-wrap;background:#f3f5f7;padding:20px}details{border-bottom:1px solid #ddd;padding:12px}summary{cursor:pointer}h1{font-size:28px}</style><h1>P0/P1校准交付</h1><p>200个母案例 · 正式生成0条 · 独立模型复核未执行 · 人工抽检待审核</p><p>点击案例展开标准答案与后续轮次。仅用于评测控制面，禁止提供给被测Agent。</p>'+''.join(blocks)+'</html>')
    return validation
