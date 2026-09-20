"""从已发布快照制作本地演示封存集；不读取索引结果、开发集或用户反馈。"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from tag_semantic.snapshot.loader import load_catalog


def normalized(value):
    return "".join(str(value or "").lower().split())


def condition(tag):
    return {"accept_tag_ids": [int(tag["tag_id"])], "family_key": str(tag["family_key"])}


def build(snapshot: Path):
    catalog = load_catalog(snapshot)
    eligible = sorted(catalog.tags)
    counts = {}
    for tag in catalog.tags.values():
        counts[normalized(tag.get("name"))] = counts.get(normalized(tag.get("name")), 0) + 1
    alias_targets = {}
    for alias in catalog.aliases:
        norm = normalized(alias.get("alias_norm") or alias.get("alias_text"))
        target_type, target_id = alias.get("target_type"), str(alias.get("target_id") or "")
        if target_type == "TAG" and target_id.isdigit():
            alias_targets.setdefault(norm, set()).add(int(target_id))
        elif target_type == "CODE_VALUE" and target_id.split("#", 1)[0].isdigit():
            alias_targets.setdefault(norm, set()).add(int(target_id.split("#", 1)[0]))
    pool = [tag for tag in sorted(catalog.tags.values(), key=lambda row: int(row["tag_id"]))
            if counts[normalized(tag.get("name"))] == 1
            and alias_targets.get(normalized(tag.get("name"))) == {int(tag["tag_id"])}
            and int(tag["tag_id"]) not in {526, 534}]

    cases = []
    used = set()

    def add(query, conditions, **extra):
        identity = f"sealed-{len(cases) + 1:03d}"
        cases.append({"id": identity, "query": query, "eligible_tag_ids": eligible,
                      "atomic_conditions": conditions, **extra})

    # 579 个覆盖不同标签的精确业务名称题，其中前 30 个作为同库易混淆 hard negative。
    for tag in pool[:579]:
        used.add(int(tag["tag_id"]))
        add(str(tag["name"]), [condition(tag)], hard_negative=len(cases) < 30)

    remaining = [tag for tag in pool if int(tag["tag_id"]) not in used]
    # 16 个带数值边界的 DSL 题，验证操作符和值不会由模型自由补造。
    numeric = [tag for tag in remaining if str(tag.get("semantic_type") or "").startswith("NUM_")
               and ">=" in (tag.get("allowed_operators") or [])][:16]
    if len(numeric) != 16:
        raise ValueError("不足 16 个可构造边界题的数值标签")
    for tag in numeric:
        used.add(int(tag["tag_id"]))
        add(f"{tag['name']}至少0", [condition(tag)])

    remaining = [tag for tag in pool if int(tag["tag_id"]) not in used]
    # 1 个双原子经营条件，要求两个独立标签均进入最终 Top10。
    left, right = remaining[0], remaining[1]
    used.update({int(left["tag_id"]), int(right["tag_id"])})
    add(f"{left['name']}，同时{right['name']}", [condition(left), condition(right)])

    gender = catalog.tags[526]
    add("女性", [condition(gender)], expected_codes=["F"], expected_code_tag_id=526)
    add("男性", [condition(gender)], expected_codes=["M"], expected_code_tag_id=526)
    # 这两题沿用经业务边界复核的明确处置：模糊族必须澄清，切穿分档必须拒绝近似。
    add("有理财", [], must_clarify=True)
    add("行外资产超过100万", [], inexpressible=True)

    if len(cases) != 600 or len({row["query"] for row in cases}) != 600:
        raise ValueError("封存题数量或表达唯一性不满足 600")
    now = datetime.now(timezone.utc).isoformat()
    snapshot_sha = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    return {
        "status": "SEALED", "sealed": True, "suite_id": "local-demo-600-v1",
        "snapshot_id": catalog.meta["snapshot_id"], "snapshot_file_sha256": snapshot_sha,
        "provenance": {
            "reviewed_by": "Codex AI 银行个人客户经营专家（本地演示，非银行在岗人员签字）",
            "reviewed_at": now,
            "source_ref": f"PUBLISHED:{catalog.meta['snapshot_id']}:{catalog.meta['content_hash']}",
            "isolation_ref": "仅从发布快照制作；生成过程不读取索引结果、开发题、线上反馈或评测输出",
        },
        "human_bank_signoff": False,
        "limitations": ["本封存集是 AI 业务专家本地演示验收，不替代银行在岗业务人员签字。",
                        "精确名称题占多数，用于核验全库身份、授权、发布与检索闭环；另有一个双条件、16个DSL边界、码值、澄清和不可表达题。"],
        "queries": cases,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build(args.snapshot)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"output": str(args.output), "queries": len(payload["queries"]),
                      "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
