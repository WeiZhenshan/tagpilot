"""不可变目录契约。仅校验快照，不查询实时数据或权限。"""
from collections import Counter

KINDS = ("meta", "domain", "concept", "tag", "code_value", "term", "capability")
SCHEMA_VERSION = "v1"


def validate_row(row: dict) -> None:
    if row.get("kind") not in KINDS:
        raise ValueError(f"未知 kind={row.get('kind')}")
    if row.get("review_status") not in (None, "REVIEWED"):
        raise ValueError("未复核内容不得进入快照")


def validate_catalog(rows: list[dict]) -> None:
    for row in rows:
        validate_row(row)
    metas = [r for r in rows if r['kind'] == 'meta']
    if len(metas) != 1 or metas[0].get('schema_version') != SCHEMA_VERSION:
        raise ValueError('必须存在唯一 v1 meta')
    tags, concepts, codes = {}, {}, {}
    keys = set()
    for row in rows:
        kind = row['kind']
        identity = {'meta': 'meta', 'domain': row.get('dir_id'),
                    'concept': row.get('concept_id') or row.get('concept_code'),
                    'tag': row.get('tag_id'), 'code_value': (row.get('tag_id'), row.get('code')),
                    'term': row.get('term_id') or row.get('term_norm'),
                    'capability': row.get('capability_id')}.get(kind)
        if identity is None or (kind, identity) in keys:
            raise ValueError(f'缺少标识或重复行: {kind}/{identity}')
        keys.add((kind, identity))
        if kind == 'tag':
            if row.get('semantic_type') == 'ID_KEY' or row.get('status', '2') != '2' or row.get('source_status', 'AVAILABLE') != 'AVAILABLE':
                raise ValueError('对象键或不可用标签不得进入快照')
            tags[str(identity)] = row
        elif kind == 'concept':
            concepts[str(identity)] = row
            if row.get('status', '0') != '0':
                raise ValueError('停用概念不得进入快照')
        elif kind == 'code_value':
            if not isinstance(row.get('code'), str):
                raise ValueError('code 必须是字符串，保留前导零')
            codes[f"{row['tag_id']}#{row['code']}"] = row
    for tid, tag in tags.items():
        cid = tag.get('concept_id') or tag.get('concept_code')
        if str(cid) not in concepts:
            raise ValueError(f'标签 {tid} 引用悬空概念 {cid}')
    for row in rows:
        if row['kind'] == 'capability':
            if row.get('review_status') != 'REVIEWED' or not row.get('version') or not row.get('source_ref'):
                raise ValueError('能力必须具有复核、版本及来源')
            if row.get('capability_type') not in {'BUSINESS_DEFINITION', 'DERIVED_METRIC', 'AGGREGATION_TEMPLATE'}:
                raise ValueError('能力类型非法')
            if not set(map(str, row.get('input_tag_ids') or [])) <= set(tags):
                raise ValueError('能力引用未发布标签')
            if not row.get('applicability') or not row.get('definition'):
                raise ValueError('能力缺少适用范围或业务定义')
    for cid, concept in concepts.items():
        seen, cur = set(), concept
        while cur.get('parent_id') not in (None, 0, '0'):
            parent = str(cur['parent_id'])
            if parent in seen or parent == cid or parent not in concepts:
                raise ValueError('概念祖先缺失或成环')
            seen.add(parent)
            cur = concepts[parent]
    for key, code in codes.items():
        if str(code['tag_id']) not in tags:
            raise ValueError(f'码值引用悬空标签: {key}')
        path, seen, cur = [code['code']], {key}, code
        while cur.get('parent_code') is not None:
            parent = f"{cur.get('parent_tag_id') or cur['tag_id']}#{cur['parent_code']}"
            if parent in seen or parent not in codes:
                raise ValueError('码值父节点缺失或成环')
            seen.add(parent)
            cur = codes[parent]
            path.insert(0, cur['code'])
        if 'path' in code and code['path'] != path:
            raise ValueError('码值 path 与父链不一致')
        # 派生只用于加载后的视图，调用方在校验 hash 后运行。
        code['path'] = path
    pairs = {}
    occurrences = Counter()
    for row in rows:
        if row['kind'] == 'capability':
            if not isinstance(row.get('aliases', []), list) or any(not isinstance(v, str) for v in row.get('aliases', [])):
                raise ValueError('能力别名必须是字符串数组')
            continue
        for alias in row.get('aliases') or []:
            if alias.get('review_status') != 'REVIEWED':
                raise ValueError('别名必须 REVIEWED')
            table = {'TAG': tags, 'CONCEPT': concepts, 'CODE_VALUE': codes}.get(alias.get('target_type'))
            if table is None or str(alias.get('target_id')) not in table:
                raise ValueError('别名引用悬空目标')
            owner = str(row.get('tag_id')) if row['kind'] == 'tag' else str(row.get('concept_id') or row.get('concept_code'))
            if row['kind'] == 'code_value':
                owner = f"{row['tag_id']}#{row['code']}"
            if str(alias['target_id']) != owner:
                raise ValueError('嵌入别名与所属目标不一致')
        local_pairs = set()
        for pair in row.get('confusable') or []:
            a, b = str(pair.get('tag_id_a')), str(pair.get('tag_id_b'))
            key = tuple(sorted((a, b)))
            if a == b or a not in tags or b not in tags or str(row.get('tag_id')) not in key:
                raise ValueError('易混淆对引用无效')
            if key in local_pairs or (key in pairs and pairs[key] != pair):
                raise ValueError('易混淆对重复或两端内容不一致')
            local_pairs.add(key)
            pairs[key] = pair
            occurrences[key] += 1
    if any(n != 2 for n in occurrences.values()):
        raise ValueError('易混淆对必须在两端对称出现')
    counts = Counter(r['kind'] for r in rows)
    for kind, count in (metas[0].get('counts') or {}).items():
        if kind in KINDS and counts[kind] != count:
            raise ValueError(f'快照计数不一致: {kind}')
