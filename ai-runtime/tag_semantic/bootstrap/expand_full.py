"""全库 969 扩展流水线：必须走 Java bootstrap/export，禁止离线 03/04/05 冒充运行态。"""

from __future__ import annotations

import argparse
from pathlib import Path

from tag_semantic.bootstrap.concept_cluster import PILOT_CONFIRMATIONS, apply_cluster, build_concept_rows
from tag_semantic.bootstrap.confusable import build_source_pairs, build_time_facet_pairs
from tag_semantic.bootstrap.rule_aliases import build_aliases
from tag_semantic.bootstrap.rule_init import load_freeze, run_rule_init, write_jsonl
from tag_semantic.bootstrap.terms import seed_terms
from tag_semantic.snapshot.publish import assemble_snapshot


def expand(freeze_jsonl: Path, out_dir: Path, review: bool = False) -> dict:
    freeze = load_freeze(freeze_jsonl)
    init = run_rule_init(freeze)
    clustered = apply_cluster(init["result"], confirmations=PILOT_CONFIRMATIONS)
    tags = [r for r in clustered if r.get("kind") == "tag_semantic"]
    codes = [r for r in clustered if r.get("kind") == "code_value_semantic"]
    library_id = int(freeze["meta"].get("library_id") or 107)
    concepts = build_concept_rows(clustered, library_id, 0, freeze["meta"].get("tag_object") or "客户")
    aliases = build_aliases(tags, codes, concepts)
    confusable = build_time_facet_pairs(tags) + build_source_pairs(tags)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_dir / "rule_init_result.jsonl", init["result"])
    write_jsonl(out_dir / "rule_init_unresolved.jsonl", init["unresolved"])
    write_jsonl(out_dir / "s3_clustered.jsonl", clustered)
    write_jsonl(out_dir / "s3_concepts.jsonl", concepts)
    write_jsonl(out_dir / "aliases.jsonl", aliases)
    write_jsonl(out_dir / "confusable.jsonl", confusable)
    write_jsonl(out_dir / "terms.jsonl", seed_terms())
    total = freeze["meta"].get("counts", {}).get("tag") or 969
    coverage = f"{len(tags)}/{total}，分阶段快照必须标注范围，不得写成 100%"
    if review:
        from tag_semantic.snapshot.publish import mark_reviewed
        snapshot = assemble_snapshot(
            library_id=library_id,
            snapshot_id=f"L{library_id}-FULL-DRAFT",
            tags=mark_reviewed(tags),
            concepts=mark_reviewed(concepts),
            codes=mark_reviewed(codes),
            aliases=mark_reviewed(aliases),
            confusable=mark_reviewed(confusable),
            examples=[],
            terms=seed_terms(),
            coverage_note=coverage,
        )
        (out_dir / "snapshot.jsonl").write_text(snapshot["jsonl"], encoding="utf-8")
    return {"tags": len(tags), "unresolved": len(init["unresolved"]), "coverage_note": coverage}


def main() -> int:
    parser = argparse.ArgumentParser(description="从 Java bootstrap/export 的冻结 JSONL 扩展语义草稿")
    parser.add_argument("freeze_jsonl", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--review", action="store_true", help="仅测试用：把草稿标 REVIEWED，生产禁止")
    args = parser.parse_args()
    summary = expand(args.freeze_jsonl, args.out_dir, review=args.review)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
