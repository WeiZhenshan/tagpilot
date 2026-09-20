"""初版业务模糊词典 ~40 条。"""

from __future__ import annotations

from tag_semantic.bootstrap.rule_aliases import normalize

SEED_TERMS = [
    ("最近", "FUZZY_TIME", ["7天", "30天", "90天"], "ASK", "NUM_AMOUNT,NUM_COUNT,BOOL,DATE"),
    ("近期", "FUZZY_TIME", ["7天", "30天", "90天"], "ASK", "NUM_AMOUNT,NUM_COUNT,BOOL,DATE"),
    ("最近一段时间", "FUZZY_TIME", ["7天", "30天", "90天"], "ASK", "BOOL,NUM_COUNT"),
    ("大额", "FUZZY_QUANTITY", ["20万", "50万", "100万"], "ASK", "NUM_AMOUNT,ENUM_ORDINAL"),
    ("高净值", "FUZZY_QUANTITY", ["600万", "1000万"], "ASK", "NUM_AMOUNT,ENUM_ORDINAL"),
    ("小额", "FUZZY_QUANTITY", ["1万", "5万", "10万"], "ASK", "NUM_AMOUNT"),
    ("理财", "FUZZY_CATEGORY", ["仅理财产品", "含基金", "含保险"], "ASK", "BOOL,NUM_AMOUNT"),
    ("以上", "BOUNDARY", [">="], "RESOLVE", "NUM_AMOUNT,NUM_COUNT,NUM_RATIO,ENUM_ORDINAL"),
    ("及以上", "BOUNDARY", [">="], "RESOLVE", "NUM_AMOUNT,ENUM_ORDINAL"),
    ("至少", "BOUNDARY", [">="], "RESOLVE", "NUM_AMOUNT,NUM_COUNT"),
    ("超过", "BOUNDARY", [">"], "RESOLVE", "NUM_AMOUNT,NUM_COUNT,NUM_RATIO"),
    ("高于", "BOUNDARY", [">"], "RESOLVE", "NUM_AMOUNT,NUM_RATIO"),
    ("以下", "BOUNDARY", ["<="], "RESOLVE", "NUM_AMOUNT,ENUM_ORDINAL"),
    ("及以下", "BOUNDARY", ["<="], "RESOLVE", "ENUM_ORDINAL,NUM_AMOUNT"),
    ("不到", "BOUNDARY", ["<"], "RESOLVE", "NUM_AMOUNT,NUM_COUNT"),
    ("不足", "BOUNDARY", ["<"], "RESOLVE", "NUM_AMOUNT,NUM_COUNT"),
    ("未", "NEGATION", None, "NEGATE", None),
    ("没有", "NEGATION", None, "NEGATE", None),
    ("不", "NEGATION", None, "NEGATE", None),
    ("无", "NEGATION", None, "NEGATE", None),
    ("排除", "NEGATION", None, "NEGATE", None),
    ("非", "NEGATION", None, "NEGATE", None),
    ("不是", "NEGATION", None, "NEGATE", None),
    ("中等及以上", "ORDINAL_WORD", ["C3+"], "RESOLVE_BY_FIELD", "ENUM_ORDINAL"),
    ("高", "ORDINAL_WORD", None, "RESOLVE_BY_FIELD", "ENUM_ORDINAL,NUM_SCORE"),
    ("低", "ORDINAL_WORD", None, "RESOLVE_BY_FIELD", "ENUM_ORDINAL,NUM_SCORE"),
    ("中等", "ORDINAL_WORD", None, "RESOLVE_BY_FIELD", "ENUM_ORDINAL"),
    ("近一周", "FUZZY_TIME", ["7天"], "RESOLVE", "BOOL,NUM_COUNT,NUM_AMOUNT"),
    ("近一个月", "FUZZY_TIME", ["1个月"], "RESOLVE", "BOOL,NUM_COUNT,NUM_AMOUNT"),
    ("上个月", "FUZZY_TIME", ["上月"], "RESOLVE", "BOOL,NUM_AMOUNT,DATE"),
    ("上月末", "FUZZY_TIME", ["上月末"], "RESOLVE", "NUM_AMOUNT,BOOL"),
    ("当前", "FUZZY_TIME", ["当前时点"], "RESOLVE", "NUM_AMOUNT,BOOL,ENUM_ORDINAL"),
    ("现在", "FUZZY_TIME", ["当前时点"], "RESOLVE", "BOOL,NUM_AMOUNT"),
    ("历史", "FUZZY_TIME", ["历史"], "RESOLVE", "BOOL,NUM_AMOUNT,DATE"),
    ("未来", "FUZZY_TIME", ["未来"], "ASK", "DATE"),
    ("本行", "FUZZY_CATEGORY", ["OUR_BANK"], "RESOLVE", "NUM_AMOUNT"),
    ("全渠道", "FUZZY_CATEGORY", ["ALL"], "RESOLVE", "NUM_AMOUNT"),
    ("私银", "FUZZY_CATEGORY", ["PB_KYC"], "ASK", "ENUM_ORDINAL,NUM_COUNT"),
    ("企微", "FUZZY_CATEGORY", ["WECOM"], "RESOLVE", "BOOL"),
    ("女性", "FUZZY_CATEGORY", ["GENDER=F"], "RESOLVE", "ENUM_NOMINAL"),
]


def seed_terms(tag_object: str = "客户") -> list[dict]:
    rows = []
    for term, term_type, options, policy, types in SEED_TERMS:
        rows.append(
            {
                "kind": "term",
                "term": term,
                "term_norm": normalize(term),
                "term_type": term_type,
                "options": options,
                "default_policy": policy,
                "applicable_semantic_types": types,
                "tag_object": tag_object,
                "source": "HUMAN",
                "review_status": "REVIEWED",
                "source_ref": "s7_seed_v1",
            }
        )
    return rows
