"""rule_init 无网无库测试：覆盖试点难点类型。"""

from __future__ import annotations

import json
from pathlib import Path

from tag_semantic.bootstrap.rule_init import load_freeze, parse_interval, run_rule_init
from tag_semantic.bootstrap.time_lexicon import parse_statistics, parse_time_anchor


def _tag(**kwargs):
    row = {
        "kind": "tag",
        "library_id": 107,
        "status": "2",
        "source_status": "AVAILABLE",
        "version": 3,
        "business_caliber": "测试口径",
        "tech_caliber": "L_INDVCST_LABEL",
        "is_object_key": 0,
        "business_candidate": True,
        "binding": {"table": "L_INDVCST_LABEL", "column": kwargs.get("field_name")},
    }
    row.update(kwargs)
    return row


def _code(tag_id, code, definition, label=None, sort=1):
    return {
        "kind": "code_value",
        "tag_id": tag_id,
        "code": code,
        "label": label or definition,
        "definition": definition,
        "code_sort": sort,
        "sources": [{"source_table_name": "L_INDVCST_LABEL_CODE_MAP"}],
    }


def freeze_jsonl(tmp_path: Path) -> Path:
    rows = [
        {"kind": "meta", "library_id": 107, "collected_at": "2026-09-18T00:00:00+08:00"},
        {"kind": "domain", "dir_id": 1, "name": "基础属性"},
        _tag(tag_id=526, field_name="GENDER", name="性别", data_type="text", tag_type="选项型"),
        _code(526, "M", "男", sort=1),
        _code(526, "F", "女", sort=2),
        _tag(tag_id=534, field_name="OUTSIDE_ASSET_WAN_KYC", name="行外资产", data_type="text", tag_type="选项型"),
        _code(534, "01", "50万以下", sort=1),
        _code(534, "02", "50万(含)-100万", sort=2),
        _code(534, "03", "100万(含)-300万", sort=3),
        _code(534, "04", "300万(含)-600万", sort=4),
        _code(534, "05", "600万(含)-1000万", sort=5),
        _code(534, "06", "1000万及以上", sort=6),
        _tag(tag_id=721, field_name="CUR_POINT_AUM", name="当前时点AUM", data_type="decimal(13,2)", tag_type="数值型"),
        _tag(tag_id=717, field_name="LAST_12_MONTHS_MAX_AUM", name="近12个月最高AUM", data_type="decimal(13,2)", tag_type="数值型"),
        _tag(tag_id=727, field_name="HIST_MAX_POINT_AUM", name="历史最高时点AUM", data_type="decimal(13,2)", tag_type="数值型"),
        _tag(tag_id=1409, field_name="CUR_CORE_CM_LEVEL1_BRANCH", name="当前核心管户一级机构", data_type="text", tag_type="选项型"),
        _code(1409, "102", "北京", sort=1),
        _tag(tag_id=525, field_name="CUST_ID", name="客户号", data_type="varchar(32)", tag_type="文本型", is_object_key="1", business_candidate=False),
        _tag(tag_id=719, field_name="CUR_FIXED_INCOME_AUM_RATIO", name="当前固收类AUM占比", data_type="decimal(9,6)", tag_type="数值型"),
        _tag(tag_id=1466, field_name="CUR_WMP_RISK_ASSESSMENT_LEVEL", name="当前理财风评等级", data_type="text", tag_type="选项型"),
        _code(1466, "C1", "C1 谨慎型", sort=1),
        _code(1466, "C2", "C2 稳健型", sort=2),
        _code(1466, "C3", "C3 平衡型", sort=3),
        _code(1466, "C4", "C4 成长型", sort=4),
        _code(1466, "C5", "C5 进取型", sort=5),
        _tag(tag_id=708, field_name="LAST_7_DAYS_DIFF_NAME_INTERBANK_TRANSFER_IN_FLAG", name="近7天异名跨行转入标志", data_type="tinyint", tag_type="布尔型"),
        _code(708, "0", "否", sort=1),
        _code(708, "1", "是", sort=2),
        _tag(tag_id=709, field_name="LAST_30_DAYS_DIFF_NAME_INTERBANK_TRANSFER_IN_FLAG", name="近30天异名跨行转入标志", data_type="tinyint", tag_type="布尔型"),
        _code(709, "0", "否", sort=1),
        _code(709, "1", "是", sort=2),
        _tag(tag_id=1268, field_name="LAST_7_DAYS_DIFF_NAME_INTERBANK_TRANSFER_IN_COUNT", name="近7天异名跨行转入次数", data_type="int", tag_type="数值型"),
        _tag(tag_id=735, field_name="CUR_POINT_AUM_OUR_BANK", name="当前时点AUM（本行）", data_type="decimal(13,2)", tag_type="数值型"),
        _tag(tag_id=579, field_name="HIST_HOLDING_WMP_FLAG", name="历史持有理财标志", data_type="tinyint", tag_type="布尔型"),
        _code(579, "0", "否", sort=1),
        _code(579, "1", "是", sort=2),
        _tag(tag_id=601, field_name="CUR_HOLDING_WMP_FLAG", name="当前持有理财标志", data_type="tinyint", tag_type="布尔型"),
        _code(601, "0", "否", sort=1),
        _code(601, "1", "是", sort=2),
        _tag(tag_id=530, field_name="ID_TYPE", name="证件类型", data_type="text", tag_type="选项型"),
        _code(530, "01", "身份证", sort=1),
        _tag(tag_id=535, field_name="OUTSIDE_ASSET_OPS_KYC", name="行外资产（运营KYC）", data_type="text", tag_type="选项型"),
        _code(535, "03", "100万(含)-300万", sort=3),
        _tag(tag_id=536, field_name="DO_NOT_DISTURB_CUST_WECOM_TAG_FLAG", name="勿扰客户（企微标签）", data_type="tinyint", tag_type="布尔型"),
        _code(536, "0", "否", sort=1),
        _code(536, "1", "是", sort=2),
        _tag(tag_id=567, field_name="HIGHEST_EDUCATION", name="最高学历", data_type="text", tag_type="选项型"),
        _code(567, "04", "本科", sort=4),
    ]
    path = tmp_path / "freeze.jsonl"
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return path


def _by_field(result_rows, field):
    return next(r for r in result_rows if r.get("kind") == "tag_semantic" and r.get("field_name") == field)


def _codes(result_rows, field):
    return [r for r in result_rows if r.get("kind") == "code_value_semantic" and r.get("field_name") == field]


def test_gender_is_nominal(tmp_path):
    output = run_rule_init(load_freeze(freeze_jsonl(tmp_path)))
    gender = _by_field(output["result"], "GENDER")
    assert gender["semantic_type"] == "ENUM_NOMINAL"
    assert gender["source"] == "RULE"
    assert gender["review_status"] == "DRAFT"
    assert gender.get("concept_id") is None
    assert gender["allowed_operators"] == ["=", "in", "not_in"]


def test_outside_asset_03_half_open_interval(tmp_path):
    output = run_rule_init(load_freeze(freeze_jsonl(tmp_path)))
    tag = _by_field(output["result"], "OUTSIDE_ASSET_WAN_KYC")
    assert tag["semantic_type"] == "ENUM_ORDINAL"
    code03 = next(c for c in _codes(output["result"], "OUTSIDE_ASSET_WAN_KYC") if c["code"] == "03")
    assert code03["lower_bound"] == 1_000_000
    assert code03["upper_bound"] == 3_000_000
    assert code03["lower_inclusive"] == 1
    assert code03["upper_inclusive"] == 0
    assert code03["review_status"] == "DRAFT"
    assert parse_interval("100万(含)-300万")["lower_inclusive"] == 1


def test_aum_families_split_eop_vs_max(tmp_path):
    output = run_rule_init(load_freeze(freeze_jsonl(tmp_path)))
    point = _by_field(output["result"], "CUR_POINT_AUM")
    window_max = _by_field(output["result"], "LAST_12_MONTHS_MAX_AUM")
    hist_max = _by_field(output["result"], "HIST_MAX_POINT_AUM")
    assert point["caliber_struct"]["statistic"] == "EOP"
    assert window_max["caliber_struct"]["statistic"] == "MAX"
    assert hist_max["caliber_struct"]["statistic"] == "MAX"
    assert hist_max["caliber_struct"]["time_anchor_type"] == "HIST"
    assert point["family_candidate"] != window_max["family_candidate"]
    assert "MAX" in window_max["family_candidate"]
    assert "EOP" in point["family_candidate"]
    # 历史最高必须同时抽出 HIST+MAX，不得并进 EOP 族
    stats = parse_statistics("历史最高时点AUM")
    assert "MAX" in stats
    time = parse_time_anchor("历史最高时点AUM")
    assert time["time_anchor_type"] == "HIST"


def test_institution_skips_hierarchy(tmp_path):
    output = run_rule_init(load_freeze(freeze_jsonl(tmp_path)))
    org = _by_field(output["result"], "CUR_CORE_CM_LEVEL1_BRANCH")
    assert org["semantic_type"] == "ENUM_NOMINAL"
    issues = [u["issue"] for u in output["unresolved"] if u["field_name"] == "CUR_CORE_CM_LEVEL1_BRANCH"]
    assert "HIERARCHY_SKIPPED" in issues
    code = _codes(output["result"], "CUR_CORE_CM_LEVEL1_BRANCH")[0]
    assert code["parent_code"] is None
    assert code["level_no"] is None


def test_unit_unknown_and_ratio_unresolved(tmp_path):
    output = run_rule_init(load_freeze(freeze_jsonl(tmp_path)))
    aum = _by_field(output["result"], "CUR_POINT_AUM")
    assert aum["unit"] == "NONE"
    issues = {u["issue"] for u in output["unresolved"]}
    assert "UNIT_UNKNOWN" in issues
    assert "RATIO_SCALE_UNKNOWN" in issues
    assert output["unresolved"], "无法判断项必须显式输出"


def test_id_key_and_bool_window(tmp_path):
    output = run_rule_init(load_freeze(freeze_jsonl(tmp_path)))
    cust = _by_field(output["result"], "CUST_ID")
    assert cust["semantic_type"] == "ID_KEY"
    assert cust["business_candidate"] is False
    flag = _by_field(output["result"], "LAST_7_DAYS_DIFF_NAME_INTERBANK_TRANSFER_IN_FLAG")
    assert flag["semantic_type"] == "BOOL"
    assert flag["caliber_struct"]["time_anchor_type"] == "WINDOW"
    assert flag["caliber_struct"]["time_window_value"] == 7
    assert flag["caliber_struct"]["time_window_unit"] == "DAY"
    assert flag["caliber_struct"]["statistic"] == "FLAG"


def test_risk_level_ordinal_interval_unparsed(tmp_path):
    output = run_rule_init(load_freeze(freeze_jsonl(tmp_path)))
    risk = _by_field(output["result"], "CUR_WMP_RISK_ASSESSMENT_LEVEL")
    assert risk["semantic_type"] == "ENUM_ORDINAL"
    issues = [
        u for u in output["unresolved"]
        if u["field_name"] == "CUR_WMP_RISK_ASSESSMENT_LEVEL" and u["issue"] == "ORDINAL_INTERVAL_UNPARSED"
    ]
    assert issues
    assert risk["review_status"] == "DRAFT"
