from tag_semantic.bootstrap.completeness import gold_ready, score_tag
from tag_semantic.bootstrap.confusable import build_source_pairs, build_time_facet_pairs
from tag_semantic.bootstrap.rule_aliases import build_aliases, normalize
from tag_semantic.bootstrap.terms import SEED_TERMS, seed_terms


def test_normalize_alias():
    assert normalize(" 女 性 ") == "女性"


def test_code_value_aliases_for_gender():
    aliases = build_aliases(
        [{"tag_id": 526, "name": "性别", "semantic_type": "ENUM_NOMINAL", "concept_code": "GENDER"}],
        [{"tag_id": 526, "code": "F", "definition": "女"}],
        [{"concept_code": "GENDER", "concept_name": "性别"}],
    )
    texts = {a["alias_text"] for a in aliases if a["target_type"] == "CODE_VALUE"}
    assert "女" in texts and "女性" in texts


def test_time_facet_pairs_for_same_family():
    tags = [
        {
            "tag_id": 708,
            "name": "近7天异名跨行转入标志",
            "family_key": "FUND_INFLOW_INTERBANK|FLAG|ALL|NONE|NONE|BASE",
            "caliber_struct": {"time_anchor_label": "近7天"},
        },
        {
            "tag_id": 709,
            "name": "近30天异名跨行转入标志",
            "family_key": "FUND_INFLOW_INTERBANK|FLAG|ALL|NONE|NONE|BASE",
            "caliber_struct": {"time_anchor_label": "近30天"},
        },
    ]
    pairs = build_time_facet_pairs(tags)
    assert len(pairs) == 1
    assert pairs[0]["confusion_type"] == "TIME_FACET"
    assert pairs[0]["tag_id_a"] == 708


def test_source_pairs_for_outside_asset():
    tags = [
        {"tag_id": 534, "name": "行外资产", "concept_code": "OUTSIDE_ASSET", "caliber_struct": {"source_system": None}},
        {
            "tag_id": 535,
            "name": "行外资产（运营KYC）",
            "concept_code": "OUTSIDE_ASSET",
            "caliber_struct": {"source_system": "OPS_KYC"},
        },
    ]
    pairs = build_source_pairs(tags)
    assert pairs and pairs[0]["confusion_type"] == "SOURCE"


def test_completeness_gold_threshold():
    tag = {
        "tag_id": 721,
        "semantic_type": "NUM_AMOUNT",
        "allowed_operators": [">"],
        "caliber_struct": {"statistic": "EOP", "scope": "ALL"},
        "definition_long": "当前时点资产管理规模",
        "review_status": "REVIEWED",
        "concept_code": "AUM",
    }
    concept = {"review_status": "REVIEWED", "status": "0"}
    aliases = [
        {"review_status": "REVIEWED", "alias_type": "FORMAL", "target_type": "TAG"},
        {"review_status": "REVIEWED", "alias_type": "COLLOQUIAL", "target_type": "TAG"},
        {"review_status": "REVIEWED", "alias_type": "COLLOQUIAL", "target_type": "CONCEPT"},
    ]
    examples = [{"review_status": "REVIEWED", "example_type": "POS"}]
    score = score_tag(tag, aliases=aliases, concept=concept, examples=examples)
    assert score >= 90
    assert gold_ready(score, True)


def test_seed_terms_cover_boundary_and_ask():
    terms = seed_terms()
    assert len(terms) >= 40
    assert len(SEED_TERMS) >= 40
    by_term = {t["term"]: t for t in terms}
    assert by_term["超过"]["default_policy"] == "RESOLVE"
    assert by_term["大额"]["default_policy"] == "ASK"
    assert by_term["以上"]["options"] == [">="]
    assert all(t["review_status"] == "REVIEWED" for t in terms)
