from tag_semantic.bootstrap.expert_review import _semantic_type, _unit, ensure_tag_aliases, reconcile_payroll_rate_concept, reconcile_transfer_in_concepts, review_tag, split_cross_domain_concepts


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


def test_equity_under_allocation_uses_flag_statistic():
    row = _row("当前权益类资产缺配标志", "CUR_EQUITY_ASSET_UNDER_ALLOCATED_FLAG", data_type="int")
    row.update(caliber_struct={"statistic": "COUNT", "unit": "NONE"},
               family_key="权益类资产缺配|COUNT|ALL|NONE|NONE|BASE")
    reviewed, changed = review_tag(row, False)
    assert changed
    assert reviewed["semantic_type"] == "BOOL"
    assert reviewed["caliber_struct"]["statistic"] == "FLAG"
    assert reviewed["family_key"] == "权益类资产缺配|FLAG|ALL|NONE|NONE|BASE"


def test_coupon_count_not_misread_as_rate():
    for subtype, field in (
        ("折扣利率券", "HIST_PERS_LOAN_IFC_USED_COUPON_COUNT_DISC_RATE_COUPON"),
        ("固定利率券", "HIST_PERS_LOAN_IFC_USED_COUPON_COUNT_FIXED_RATE_COUPON"),
    ):
        row = _row(f"历史个贷免息券使用张数（{subtype}）", field, "NUM_RATIO", "int")
        row.update(caliber_struct={"statistic": "COUNT", "unit": "RATIO"},
                   family_key=f"免息券使用张数|COUNT|ALL|NONE|RATIO|BASE")
        reviewed, changed = review_tag(row, False)
        assert changed
        assert reviewed["semantic_type"] == "NUM_COUNT"
        assert reviewed["unit"] == "COUNT"
        assert reviewed["caliber_struct"]["statistic"] == "COUNT"
        assert reviewed["family_key"] == "免息券使用张数|COUNT|ALL|NONE|COUNT|BASE"


def test_shared_rate_concept_alias_no_longer_routes_max_to_min():
    tags = [
        {"field_name": "HIST_PAY_LOAN_MAX_RATE", "concept_code": "工薪贷提款利率", "family_key": "工薪贷提款利率|MAX|ALL|NONE|RATIO|BASE"},
        {"field_name": "HIST_PAY_LOAN_MIN_RATE", "concept_code": "工薪贷提款利率", "family_key": "工薪贷提款利率|MIN|ALL|NONE|RATIO|BASE"},
    ]
    concepts = [{"concept_code": "工薪贷提款利率", "concept_name": "工薪贷最高提款利率", "definition": "工薪贷最高提款利率"}]
    aliases = [
        {"target_type": "CONCEPT", "target_id": "工薪贷提款利率", "alias_text": "工薪贷最高提款利率"},
        {"target_type": "TAG", "target_id": "1185", "alias_text": "工薪贷最高提款利率"},
        {"target_type": "TAG", "target_id": "1187", "alias_text": "工薪贷最低提款利率"},
    ]
    reconcile_payroll_rate_concept(tags, concepts, aliases)
    assert concepts[0]["concept_name"] == "工薪贷提款利率"
    assert "最高值和最低值" in concepts[0]["definition"]
    assert aliases[0]["alias_text"] == aliases[0]["alias_norm"] == "工薪贷提款利率"
    assert aliases[1]["alias_text"] == "工薪贷最高提款利率"
    assert aliases[2]["alias_text"] == "工薪贷最低提款利率"
    assert tags[0]["family_key"] != tags[1]["family_key"]


def test_period_transfer_sum_and_shared_concept_reconciliation():
    rows = []
    for field, name in (
        ("CUR_YEAR_SAME_NAME_INTERBANK_TRANSFER_IN_AMT", "本年同名跨行转入金额"),
        ("LAST_30_DAYS_DIFF_NAME_INTERBANK_TRANSFER_IN_AMT", "近30天异名跨行转入金额"),
        ("LAST_7_DAYS_DIFF_NAME_INTERBANK_TRANSFER_IN_AMT", "近7天异名跨行转入金额"),
        ("CUR_MONTH_SAME_NAME_INTERBANK_TRANSFER_IN_AMT", "本月同名跨行转入金额"),
        ("LAST_7_DAYS_SAME_NAME_INTERBANK_TRANSFER_IN_AMT", "近7天同名跨行转入金额"),
    ):
        code = "同名跨行转入金额" if "SAME_NAME" in field and "DIFF_NAME" not in field else "异名跨行转入金额"
        row = _row(name, field)
        row.update(concept_code=code, concept_name=code.replace("转入金额", "转入最高金额"),
                   caliber_struct={"statistic": "EOP", "unit": "CNY"},
                   family_key=f"{code}|EOP|ALL|NONE|CNY|BASE")
        reviewed, changed = review_tag(row, False)
        assert changed and reviewed["caliber_struct"]["statistic"] == "SUM"
        assert reviewed["family_key"] == f"{code}|SUM|ALL|NONE|CNY|BASE"
        rows.append(reviewed)
    concepts = [{"concept_code": code, "concept_name": code.replace("转入金额", "转入最高金额"),
                 "definition": code.replace("转入金额", "转入最高金额"),
                 "members": [{"tag_id": row["tag_id"], "family_key": f"{code}|EOP|ALL|NONE|CNY|BASE"}
                             for row in rows if row["concept_code"] == code]}
                for code in ("同名跨行转入金额", "异名跨行转入金额")]
    aliases = [{"target_type": "CONCEPT", "target_id": code,
                "alias_text": code.replace("转入金额", "转入最高金额")}
               for code in ("同名跨行转入金额", "异名跨行转入金额")]
    aliases.append({"target_type": "CONCEPT", "target_id": "同名跨行转入金额", "alias_text": "同名跨行入金"})
    reconcile_transfer_in_concepts(rows, concepts, aliases)
    assert {row["concept_name"] for row in concepts} == {"同名跨行转入金额", "异名跨行转入金额"}
    assert all("最高" not in row["alias_text"] and row["alias_norm"] == row["alias_text"] for row in aliases[:2])
    assert aliases[2]["alias_text"] == "同名跨行入金"
    assert all(row["concept_name"] == row["concept_code"] for row in rows)
    assert all(member["family_key"].split("|")[1] == "SUM"
               for concept in concepts for member in concept["members"])


def test_each_business_tag_gets_three_distinct_aliases():
    tags = [{"tag_id": 1, "name": "当前AUM", "semantic_type": "NUM_AMOUNT"}]
    aliases, added = ensure_tag_aliases(tags, [{"target_type": "TAG", "target_id": "1", "alias_text": "当前AUM", "alias_norm": "当前aum", "alias_type": "FORMAL"}])
    assert added == 2
    assert len({a["alias_norm"] for a in aliases}) == 3


def test_period_transfer_amount_gets_explicit_cumulative_alias():
    tags = [{"tag_id": 1291, "name": "近30天异名跨行转入金额",
             "field_name": "LAST_30_DAYS_DIFF_NAME_INTERBANK_TRANSFER_IN_AMT", "semantic_type": "NUM_AMOUNT"},
            {"tag_id": 1299, "name": "近30天异名跨行转入最高金额",
             "field_name": "LAST_30_DAYS_DIFF_NAME_INTERBANK_TRANSFER_IN_MAX_AMT", "semantic_type": "NUM_AMOUNT"}]
    aliases, _ = ensure_tag_aliases(tags, [])
    assert any(row["target_id"] == "1291" and row["alias_text"] == "近30天异名跨行累计转入金额"
               for row in aliases)
    assert not any(row["target_id"] == "1299" and "累计" in row["alias_text"] for row in aliases)


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
