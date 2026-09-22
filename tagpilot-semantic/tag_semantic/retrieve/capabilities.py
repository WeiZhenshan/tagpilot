"""发布能力的可见性裁剪和轻量概念检索；不暴露物理实现。"""
from __future__ import annotations
import re

PUBLIC_FIELDS = ('capability_id', 'version', 'capability_type', 'name', 'aliases', 'definition',
                 'applicability', 'parameters', 'input_tag_ids', 'unit', 'grain', 'caliber_struct',
                 'null_policy', 'source_ref', 'plan_template')


def search_capabilities(catalog, query, eligible, ids=()):
    requested = set(ids)
    visible = [c for c in catalog.capabilities.values()
               if c.get('review_status') == 'REVIEWED' and set(c.get('input_tag_ids') or []) <= eligible]
    if requested:
        # 不泄露不存在与不可见之间的差异。
        visible = [c for c in visible if c['capability_id'] in requested]
    else:
        def tokens(text):
            text = re.sub(r'\s+', '', str(text).lower())
            return {text[i:i+2] for i in range(max(0, len(text)-1))}
        wanted = tokens(query)
        def score(cap):
            return len(wanted & tokens(' '.join([cap.get('name', ''), cap.get('definition', ''), *(cap.get('aliases') or [])])))
        visible = sorted((c for c in visible if score(c)), key=lambda c: (-score(c), c['capability_id']))[:12]
    return [{k: c[k] for k in PUBLIC_FIELDS if k in c} for c in visible]
