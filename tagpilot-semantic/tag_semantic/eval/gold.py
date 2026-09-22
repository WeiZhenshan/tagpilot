"""试点开发金样与契约用例。封存集不得用于别名学习。"""

from __future__ import annotations

GOLD_DEV = [
    {"id": "g1", "query": "女性", "accept_tag_ids": [526], "accept_code": "F", "must_clarify": False},
    {"id": "g2", "query": "近30天异名跨行转入", "accept_tag_ids": [709], "family_key_prefix": "FUND_INFLOW_INTERBANK|FLAG", "must_clarify": False},
    {"id": "g3", "query": "当前AUM", "accept_tag_ids": [721], "must_clarify": False},
    {"id": "g4", "query": "本行AUM", "accept_tag_ids": [735], "must_clarify": False},
    {"id": "g5", "query": "有理财", "accept_tag_ids": [601, 579], "must_clarify": True},
    {"id": "g6", "query": "近60天异名跨行转入", "accept_tag_ids": [708, 709], "must_clarify": True},
    {"id": "g7", "query": "行外资产超过100万", "accept_tag_ids": [534], "must_clarify": True, "inexpressible_approx": True},
    {"id": "g8", "query": "男性", "accept_tag_ids": [526], "accept_code": "M", "must_clarify": False},
    {"id": "g9", "query": "近7天异名跨行转入", "accept_tag_ids": [708], "must_clarify": False},
    {"id": "g10", "query": "近12个月最高AUM", "accept_tag_ids": [717], "must_clarify": False},
    {"id": "g11", "query": "历史最高时点AUM", "accept_tag_ids": [727], "must_clarify": False},
    {"id": "g12", "query": "当前持有理财", "accept_tag_ids": [601], "must_clarify": False},
    {"id": "g13", "query": "历史持有理财", "accept_tag_ids": [579], "must_clarify": False},
    {"id": "g14", "query": "勿扰客户", "accept_tag_ids": [536], "must_clarify": False},
    {"id": "g15", "query": "最高学历", "accept_tag_ids": [567], "must_clarify": False},
    {"id": "g16", "query": "理财风评", "accept_tag_ids": [1466], "must_clarify": False},
    {"id": "g17", "query": "固收类AUM占比", "accept_tag_ids": [719], "must_clarify": False},
    {"id": "g18", "query": "行外资产运营KYC", "accept_tag_ids": [535], "must_clarify": False},
    {"id": "g19", "query": "近7天异名跨行转入次数", "accept_tag_ids": [1268], "must_clarify": False},
    {"id": "g20", "query": "证件类型", "accept_tag_ids": [530], "must_clarify": False},
]


def hit_at_k(results: list[dict], accept_tag_ids: list[int], k: int) -> bool:
    accepted = set(accept_tag_ids)
    for item in results[:k]:
        doc = item.get("doc") or item
        if int(doc.get("tag_id") or -1) in accepted:
            return True
    return False
