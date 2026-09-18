"""规则别名：正式名、口语、码值中文。source=RULE。"""

from __future__ import annotations

import re
from typing import Any, Iterable

from tag_semantic.bootstrap.time_lexicon import parse_source_system, parse_time_anchor


def normalize(text: str) -> str:
    value = (text or "").strip().lower()
    value = value.replace(" ", "").replace("　", "")
    trans = str.maketrans("（）【】，。；：", "()[],.;:")
    return value.translate(trans)


def _without_time_and_source(name: str) -> str:
    text = name
    span = parse_time_anchor(text).get("matched_span")
    if span:
        text = text.replace(span, "", 1)
    _, source_span = parse_source_system(name)
    if source_span:
        text = text.replace(source_span, "", 1)
    return re.sub(r"[（()）]", "", text).strip(" -_/") or name


COLLOQUIAL = {
    "GENDER": ["性别", "男女"],
    "AUM": ["aum", "资产管理规模", "管资"],
    "WMP_HOLDING": ["有理财", "持有理财", "买了理财"],
    "FUND_INFLOW_INTERBANK": ["异名跨行转入", "他行转入", "跨行入金"],
    "OUTSIDE_ASSET": ["行外资产", "体外资产"],
    "WMP_RISK": ["理财风评", "风险等级"],
    "DND_WECOM": ["勿扰", "不要打扰", "勿扰客户"],
    "EDUCATION": ["学历", "最高学历"],
    "ID_TYPE": ["证件类型", "证件"],
    "AUM_FI_RATIO": ["固收占比", "固收类AUM占比"],
}

TAG_COLLOQUIAL = {
    "CUR_POINT_AUM": ["当前AUM", "时点AUM"],
    "CUR_POINT_AUM_OUR_BANK": ["本行AUM", "本行时点AUM"],
    "LAST_12_MONTHS_MAX_AUM": ["近12个月最高AUM", "十二个月最高AUM"],
    "HIST_MAX_POINT_AUM": ["历史最高AUM", "历史最高时点AUM"],
    "CUR_HOLDING_WMP_FLAG": ["当前持有理财", "现在有理财"],
    "HIST_HOLDING_WMP_FLAG": ["历史持有理财", "曾经有理财"],
    "LAST_7_DAYS_DIFF_NAME_INTERBANK_TRANSFER_IN_FLAG": ["近7天异名跨行转入"],
    "LAST_30_DAYS_DIFF_NAME_INTERBANK_TRANSFER_IN_FLAG": ["近30天异名跨行转入"],
    "LAST_7_DAYS_DIFF_NAME_INTERBANK_TRANSFER_IN_COUNT": ["近7天异名跨行转入次数"],
    "OUTSIDE_ASSET_OPS_KYC": ["行外资产运营KYC", "运营KYC行外资产"],
    "HIGHEST_EDUCATION": ["最高学历"],
    "DO_NOT_DISTURB_CUST_WECOM_TAG_FLAG": ["勿扰客户"],
    "CUR_FIXED_INCOME_AUM_RATIO": ["固收类AUM占比"],
    "ID_TYPE": ["证件类型"],
}


def build_aliases(
    tags: Iterable[dict[str, Any]],
    codes: Iterable[dict[str, Any]],
    concepts: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def add(target_type: str, target_id: str, text: str, alias_type: str) -> None:
        norm = normalize(text)
        if not norm:
            return
        key = (target_type, str(target_id), norm)
        if key in seen:
            return
        seen.add(key)
        rows.append(
            {
                "kind": "alias",
                "target_type": target_type,
                "target_id": str(target_id),
                "alias_text": text.strip()[:64],
                "alias_norm": norm[:64],
                "alias_type": alias_type,
                "weight": 1.0,
                "source": "RULE",
                "review_status": "DRAFT",
            }
        )

    for concept in concepts:
        code = concept.get("concept_code")
        if not code:
            continue
        add("CONCEPT", code, concept.get("concept_name") or code, "FORMAL")
        for extra in COLLOQUIAL.get(code, []):
            add("CONCEPT", code, extra, "COLLOQUIAL")
    for tag in tags:
        if tag.get("semantic_type") == "ID_KEY":
            continue
        tag_id = str(tag.get("tag_id"))
        name = str(tag.get("name") or "")
        add("TAG", tag_id, name, "FORMAL")
        stripped = _without_time_and_source(name)
        if stripped and stripped != name:
            add("TAG", tag_id, stripped, "COLLOQUIAL")
        concept_code = tag.get("concept_code")
        for extra in COLLOQUIAL.get(concept_code or "", []):
            add("TAG", tag_id, extra, "COLLOQUIAL")
        for extra in TAG_COLLOQUIAL.get(str(tag.get("field_name") or ""), []):
            add("TAG", tag_id, extra, "COLLOQUIAL")
    extra_code_alias = {"F": ["女", "女性", "女士"], "M": ["男", "男性", "男士"]}
    for code in codes:
        tag_id = code.get("tag_id")
        value = str(code.get("code") or "")
        target = f"{tag_id}#{value}"
        label = str(code.get("definition") or code.get("label") or "")
        if label:
            add("CODE_VALUE", target, label, "FORMAL")
        for extra in extra_code_alias.get(value, []):
            add("CODE_VALUE", target, extra, "COLLOQUIAL")
    return rows
