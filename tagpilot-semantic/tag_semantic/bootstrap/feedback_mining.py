"""纠错仅产生复核候选；不直接写别名、不参与同次 RRF 加分。"""
from collections import defaultdict


def mine_feedback(rows, sealed_query_hashes):
    grouped = defaultdict(list)
    seen = set()
    for row in rows:
        # 原查询摘要无法恢复为别名；候选文本须由业务脱敏确认后提供。
        key = (row.get('trace_id'), row.get('user_id'))
        digest = row.get('query_hash')
        if key in seen or not digest or digest in sealed_query_hashes or row.get('source') == 'SEALED':
            continue
        if row.get('text_review_status') != 'REVIEWED' or not row.get('sanitized_text'):
            continue
        seen.add(key)
        grouped[(digest, row.get('final_tag_id'), row['sanitized_text'])].append(row)
    candidates = []
    for (digest, tag_id, text), group in grouped.items():
        accepted = sum(r.get('action') in {'ACCEPT', 'REPLACE', 'CLARIFY_PICKED'} for r in group)
        if tag_id and len(group) >= 5 and accepted / len(group) >= .9:
            candidates.append({'target_type': 'TAG', 'target_id': str(tag_id), 'alias_text': text,
                               'alias_norm': text.lower().replace(' ', ''), 'alias_type': 'COLLOQUIAL',
                               'review_status': 'DRAFT', 'source': 'FEEDBACK', 'sample_count': len(group),
                               'acceptance_rate': accepted / len(group), 'query_hash': digest})
    return candidates
