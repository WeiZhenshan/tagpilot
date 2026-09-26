"""仅解析仓库 SQL 的字面量；绝不执行 SQL 文件。"""
import re
from collections import defaultdict
from pathlib import Path

VALUE = re.compile(r"\s*(?:'((?:''|\\.|[^'])*)'|(NULL)|(-?\d+(?:\.\d+)?))\s*(,|$)")


def parse_values(text):
    values, pos = [], 0
    while pos < len(text):
        match = VALUE.match(text, pos)
        if not match:
            raise ValueError('不支持的 SQL 字面量；禁止猜测或执行输入')
        quoted, null, number, separator = match.groups()
        values.append(None if null else quoted.replace("''", "'").replace("\\'", "'").replace('\\\\', '\\') if quoted is not None else number)
        pos = match.end()
        if not separator:
            break
    return values


def load_ddl(path):
    fields = {}
    pattern = re.compile(r"^\s*`([A-Z0-9_]+)`\s+([A-Z]+(?:\([0-9,]+\))?).*COMMENT\s+'((?:''|[^'])*)'")
    for line_no, line in enumerate(Path(path).read_text().splitlines(), 1):
        if match := pattern.match(line):
            field, dtype, name = match.groups()
            if field in fields:
                raise ValueError('DDL 字段重复')
            fields[field] = {'data_type': dtype, 'name': name.replace("''", "'"),
                             'nullable': 'NOT NULL' not in line, 'line': line_no}
    if not fields:
        raise ValueError('DDL 无字段')
    return fields


def load_code_maps(paths):
    codes = defaultdict(list)
    for path in paths:
        context = ''
        for line_no, line in enumerate(Path(path).read_text().splitlines(), 1):
            if line.strip().startswith('--'):
                context = line.strip()[2:].strip()
            if not line.strip().startswith("('"):
                continue
            row = parse_values(line.strip().rstrip(',;')[1:-1])
            if len(row) != 6:
                raise ValueError('码表记录格式错误')
            field, code, name, definition, order, _ = row
            if any(c['code'] == code for c in codes[field]):
                raise ValueError('码表主键重复')
            codes[field].append({'code': code, 'definition': definition, 'ordinal': order,
                                 'source_name': name, 'source_file': Path(path).name, 'source_line': line_no,
                                 'source_note': context,
                                 'status': 'VERIFIED_SOURCE' if '复用既有系统' in context else 'DEMO_CONVENTION'})
    return dict(codes)


def load_fixture(path, fields):
    """SQL 必须含显式列名，每行970值；Decimal 的精度通过原始字符串保留。"""
    rows, columns, in_columns = [], None, False
    for line in Path(path).read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith('INSERT INTO'):
            columns = re.findall(r'`([A-Z0-9_]+)`', stripped.split('(', 1)[1]) if '(' in stripped else None
            in_columns = not columns
        elif in_columns and stripped.startswith(('(', '`')):
            columns = re.findall(r'`([A-Z0-9_]+)`', stripped)
            in_columns = False
        elif stripped.startswith("('SIM"):
            if columns != list(fields):
                raise ValueError('模拟数据列顺序与 DDL 不一致')
            values = parse_values(stripped.rstrip(',;')[1:-1])
            if len(values) != len(columns):
                raise ValueError('模拟数据列数不一致')
            rows.append(dict(zip(columns, values)))
    ids = [r['CUST_ID'] for r in rows]
    if not rows or len(set(ids)) != len(ids) or any(not i.startswith('SIM20260918') for i in ids):
        raise ValueError('模拟数据为空、重复或包含非指定模拟客户')
    return rows


def source_names(path):
    result = defaultdict(list)
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        if match := re.match(r'^- (.+?)\s*\[(选项型|文本型|布尔型|数值型|日期型)\]', line):
            name, typ = match.groups()
            result[normalize_name(name)].append({'line': number, 'name': name, 'tag_type': typ})
    return dict(result)


def normalize_name(value):
    return re.sub(r'[\s*＊]', '', str(value)).replace('（', '(').replace('）', ')')
