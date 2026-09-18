"""S3 概念归并：字面归并 + 试点确认，family_key 使用稳定 concept_code。"""

from __future__ import annotations

from tag_semantic.bootstrap.concept_cluster import (
    PILOT_CONFIRMATIONS,
    apply_cluster,
    cluster_tags,
    family_key,
)
from tag_semantic.bootstrap.rule_init import load_freeze, run_rule_init
from tag_semantic.tests.test_rule_init import freeze_jsonl, _by_field


def _clustered(tmp_path):
    output = run_rule_init(load_freeze(freeze_jsonl(tmp_path)))
    return apply_cluster(output["result"], confirmations=PILOT_CONFIRMATIONS)


def test_aum_merges_to_same_concept_code(tmp_path):
    rows = _clustered(tmp_path)
    point = _by_field(rows, "CUR_POINT_AUM")
    window_max = _by_field(rows, "LAST_12_MONTHS_MAX_AUM")
    hist_max = _by_field(rows, "HIST_MAX_POINT_AUM")
    assert point["concept_code"] == "AUM"
    assert window_max["concept_code"] == "AUM"
    assert hist_max["concept_code"] == "AUM"
    assert "最高AUM" not in window_max["family_key"]
    assert window_max["family_key"].startswith("AUM|")


def test_aum_eop_max_and_scope_split_families(tmp_path):
    rows = _clustered(tmp_path)
    point = _by_field(rows, "CUR_POINT_AUM")
    window_max = _by_field(rows, "LAST_12_MONTHS_MAX_AUM")
    assert point["family_key"] != window_max["family_key"]
    assert "|EOP|" in point["family_key"]
    assert "|MAX|" in window_max["family_key"]
    assert point["unit"] == "CNY"
    assert point["unit_scale"] == 1
    assert point["caliber_struct"]["unit"] == "CNY"


def test_interbank_flag_and_count_not_same_family():
    flag = {
        "kind": "tag_semantic",
        "field_name": "LAST_7_DAYS_DIFF_NAME_INTERBANK_TRANSFER_IN_FLAG",
        "name": "近7天异名跨行转入标志",
        "semantic_type": "BOOL",
        "caliber_struct": {
            "statistic": "FLAG",
            "scope": "ALL",
            "source_system": None,
            "unit": "NONE",
        },
        "concept_candidate": "异名跨行转入标志",
        "unit": "NONE",
        "unit_scale": 1,
        "caliber_variant": "BASE",
    }
    count = {
        "kind": "tag_semantic",
        "field_name": "LAST_7_DAYS_DIFF_NAME_INTERBANK_TRANSFER_IN_COUNT",
        "name": "近7天异名跨行转入次数",
        "semantic_type": "NUM_COUNT",
        "caliber_struct": {
            "statistic": "COUNT",
            "scope": "ALL",
            "source_system": None,
            "unit": "COUNT",
        },
        "concept_candidate": "异名跨行转入次数",
        "unit": "COUNT",
        "unit_scale": 1,
        "caliber_variant": "BASE",
    }
    clustered = cluster_tags([flag, count], confirmations=PILOT_CONFIRMATIONS)
    assert clustered[0]["concept_code"] == clustered[1]["concept_code"] == "FUND_INFLOW_INTERBANK"
    assert clustered[0]["family_key"] != clustered[1]["family_key"]
    assert "|FLAG|" in clustered[0]["family_key"]
    assert "|COUNT|" in clustered[1]["family_key"]


def test_our_bank_aum_splits_from_all_channel():
    all_ch = {
        "kind": "tag_semantic",
        "field_name": "CUR_POINT_AUM",
        "name": "当前时点AUM",
        "semantic_type": "NUM_AMOUNT",
        "caliber_struct": {"statistic": "EOP", "scope": "ALL", "source_system": None, "unit": "NONE"},
        "concept_candidate": "时点AUM",
        "unit": "NONE",
        "caliber_variant": "BASE",
    }
    our = {
        "kind": "tag_semantic",
        "field_name": "CUR_POINT_AUM_OUR_BANK",
        "name": "当前时点AUM（本行）",
        "semantic_type": "NUM_AMOUNT",
        "caliber_struct": {"statistic": "EOP", "scope": "OUR_BANK", "source_system": None, "unit": "NONE"},
        "concept_candidate": "时点AUM本行",
        "unit": "NONE",
        "caliber_variant": "BASE",
    }
    clustered = cluster_tags([all_ch, our], confirmations=PILOT_CONFIRMATIONS)
    assert clustered[0]["concept_code"] == clustered[1]["concept_code"] == "AUM"
    assert clustered[0]["family_key"] != clustered[1]["family_key"]
    assert "|OUR_BANK|" in clustered[1]["family_key"]


def test_id_key_has_no_business_concept():
    row = {
        "kind": "tag_semantic",
        "field_name": "CUST_ID",
        "name": "客户号",
        "semantic_type": "ID_KEY",
        "business_candidate": False,
        "caliber_struct": {"statistic": "NONE", "scope": "ALL", "source_system": None, "unit": "NONE"},
        "concept_candidate": "客户号",
        "unit": "NONE",
        "caliber_variant": "BASE",
    }
    clustered = cluster_tags([row], confirmations=PILOT_CONFIRMATIONS)[0]
    assert clustered["concept_code"] is None
    assert clustered.get("skip_concept") is True


def test_family_key_uses_concept_code_not_chinese():
    key = family_key("AUM", "EOP", "ALL", None, "CNY", "BASE")
    assert key == "AUM|EOP|ALL|NONE|CNY|BASE"


def test_ratio_confirmation_sets_unit_scale():
    row = {
        "kind": "tag_semantic",
        "field_name": "CUR_FIXED_INCOME_AUM_RATIO",
        "name": "当前固收类AUM占比",
        "semantic_type": "NUM_RATIO",
        "caliber_struct": {"statistic": "RATIO", "scope": "ALL", "source_system": None, "unit": "NONE"},
        "concept_candidate": "固收类AUM占比",
        "unit": "NONE",
        "caliber_variant": "BASE",
    }
    clustered = cluster_tags([row], confirmations=PILOT_CONFIRMATIONS)[0]
    assert clustered["unit"] == "RATIO"
    assert clustered["unit_scale"] == 1
    assert clustered["concept_code"] == "AUM_FI_RATIO"
