"""全库 969 扩展流水线：必须走 Java bootstrap/export，禁止离线 03/04/05 冒充运行态。"""

from __future__ import annotations

import argparse
from pathlib import Path

from tag_semantic.bootstrap.concept_cluster import apply_cluster, build_concept_rows, review_pack
from tag_semantic.bootstrap.confusable import build_source_pairs, build_time_facet_pairs
from tag_semantic.bootstrap.rule_aliases import build_aliases
from tag_semantic.bootstrap.rule_init import load_freeze, run_rule_init, write_jsonl
from tag_semantic.bootstrap.terms import seed_terms
from tag_semantic.snapshot.publish import assemble_snapshot


def expand(freeze_jsonl: Path, out_dir: Path, review: bool = False, confirmations: dict | None = None) -> dict:
    if review:
        raise ValueError("全量扩展禁止自动复核；请经 Java 业务复核接口确认")
    freeze = load_freeze(freeze_jsonl)
    init = run_rule_init(freeze)
    clustered = apply_cluster(init["result"], confirmations=confirmations or {})
    tags = [r for r in clustered if r.get("kind") == "tag_semantic"]
    codes = [r for r in clustered if r.get("kind") == "code_value_semantic"]
    library_id = int(freeze["meta"].get("library_id") or 107)
    concepts = build_concept_rows(clustered, library_id, 0, freeze["meta"].get("tag_object") or "客户")
    roots = {d['name']: d['dir_id'] for d in freeze['domains']}
    source_tags = {t['tag_id']: t for t in freeze['tags']}
    for concept in concepts:
        domains = {roots.get((source_tags[m['tag_id']].get('dir_path') or [None])[0]) for m in concept['members']}
        domains.discard(None)
        if not concept.get('domain_dir_id') and len(domains) == 1:
            concept['domain_dir_id'] = next(iter(domains))
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
    total = sum(t.get("is_object_key") != "1" and t.get("business_candidate", True) for t in freeze["tags"])
    (out_dir / "s3_concept_review_pack.md").write_text(review_pack(concepts, clustered, confirmations or {}), encoding="utf-8")
    coverage = f"{sum(t.get('semantic_type') != 'ID_KEY' for t in tags)}/{total}（仅规则草稿生成，非复核发布覆盖）"
    return {"tags": len(tags), "unresolved": len(init["unresolved"]), "coverage_note": coverage}


def main() -> int:
    parser = argparse.ArgumentParser(description="从 Java bootstrap/export 的冻结 JSONL 扩展语义草稿")
    parser.add_argument("freeze_jsonl", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--confirmations", type=Path)
    parser.add_argument("--review", action="store_true", help="已禁用：全量草稿必须经业务复核")
    args = parser.parse_args()
    import json
    confirmations = json.loads(args.confirmations.read_text()) if args.confirmations else {}
    summary = expand(args.freeze_jsonl, args.out_dir, review=args.review, confirmations=confirmations)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
