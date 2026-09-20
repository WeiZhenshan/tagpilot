from tag_semantic.bootstrap.expert_review import _semantic_type, _unit, ensure_tag_aliases, split_cross_domain_concepts


def _row(name, field, semantic_type="NUM_AMOUNT", data_type="decimal(9,4)"):
    return {"kind": "tag_semantic", "tag_id": 1, "name": name, "field_name": field,
            "semantic_type": semantic_type, "authority": {"data_type": data_type}}


def test_business_numeric_semantics_and_units():
    ratio = _row("近6个月基金盈利率", "LAST_6M_FUND_PROFIT_RATE")
    assert _semantic_type(ratio, False) == "NUM_RATIO"
    assert _unit(ratio, "NUM_RATIO") == ("RATIO", 1)
    score = _row("当前客户财富综合分", "CUR_CUST_WEALTH_COMPOSITE_SCORE_WEALTH_VALUE_POTENTIAL_MODEL")
    assert _semantic_type(score, False) == "NUM_SCORE"
    amount = _row("当前他行卡最高潜力（万元）", "CUR_OB_CARD_BIN_MAX_POTENTIAL_WAN")
    assert _semantic_type(amount, False) == "NUM_AMOUNT"
    assert _unit(amount, "NUM_AMOUNT") == ("CNY", 10000)


def test_data_dictionary_flag_without_code_table_is_boolean():
    row = _row("当前权益类资产缺配标志", "CUR_EQUITY_ASSET_UNDER_ALLOCATED_FLAG", data_type="int")
    assert _semantic_type(row, False) == "BOOL"


def test_each_business_tag_gets_three_distinct_aliases():
    tags = [{"tag_id": 1, "name": "当前AUM", "semantic_type": "NUM_AMOUNT"}]
    aliases, added = ensure_tag_aliases(tags, [{"target_type": "TAG", "target_id": "1", "alias_text": "当前AUM", "alias_norm": "当前aum", "alias_type": "FORMAL"}])
    assert added == 2
    assert len({a["alias_norm"] for a in aliases}) == 3


def test_cross_domain_concept_is_split_and_family_is_rebound():
    freeze = {"domains": [{"dir_id": 10, "parent_id": 0, "name": "资产"}, {"dir_id": 20, "parent_id": 0, "name": "渠道"}],
              "tags": [{"tag_id": 1, "dir_path": ["资产"]}, {"tag_id": 2, "dir_path": ["渠道"]}]}
    tags = [{"tag_id": 1, "family_key": "AUM|EOP|ALL|NONE|CNY|BASE"}, {"tag_id": 2, "family_key": "AUM|EOP|ALL|NONE|CNY|BASE"}]
    concepts = [{"concept_code": "AUM", "members": [{"tag_id": 1}, {"tag_id": 2}]}]
    aliases = [{"target_type": "CONCEPT", "target_id": "AUM", "alias_text": "AUM"}]
    split, remapped, count = split_cross_domain_concepts(freeze, tags, concepts, aliases)
    assert count == 1 and len(split) == 2 and len(remapped) == 2
    assert tags[0]["concept_code"] != tags[1]["concept_code"]
    assert tags[0]["family_key"].split("|")[0] == tags[0]["concept_code"]
