"""解析 61 案例文档 → 结构化 JSON（供人工/半自动编写条件树时参照）。

只做解析，不生成条件树。条件树由作者依据「口径对齐」编写，再由 build_cases_61 实算校核。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DOC = Path(__file__).resolve().parents[2] / 'sql/indiv_cust/2000_cust_generate/客群圈选Agent自然语言测试案例.md'


def parse(doc: str):
    cases = {}
    # 主表：| ID | 场景 | 难度 | 目标 | 主输入 |
    for line in doc.splitlines():
        m = re.match(r'^\|\s*([A-K]\d\d)\s*\|', line)
        if not m:
            continue
        cells = [c.strip() for c in line.split('|')]
        if len(cells) < 7:
            continue
        cases[m.group(1)] = {
            'case_id': m.group(1), 'scenario': cells[2], 'difficulty': cells[3],
            'target': int(cells[4]) if cells[4].lstrip('-').isdigit() else None,
            'main_input': cells[5], 'prose': None, 'caliber': None,
            'contrast': None, 'expect': None, 'eval': None,
        }
    # 逐案例段
    section = None
    for line in doc.splitlines():
        h = re.match(r'^###\s+([A-K]\d\d)\s', line)
        if h:
            section = h.group(1)
            continue
        if section and line.startswith('- '):
            body = line[2:]
            for label, key in [('口语：', 'prose'), ('口径对齐：', 'caliber'),
                               ('对照：', 'contrast'), ('期望：', 'expect'), ('评测：', 'eval')]:
                if body.startswith(label):
                    cases[section][key] = body[len(label):]
    return cases


def main():
    doc = DOC.read_text()
    cases = parse(doc)
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('cases/_source/scenario_61_parsed.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cases, ensure_ascii=False, indent=1) + '\n')
    print(f'{len(cases)} cases → {out}')


if __name__ == '__main__':
    main()
