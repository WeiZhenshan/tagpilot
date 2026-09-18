"""CLI：cluster / snapshot / build / query / eval。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tag_semantic.bootstrap.concept_cluster import PILOT_CONFIRMATIONS, apply_cluster, build_concept_rows, review_pack
from tag_semantic.bootstrap.confusable import build_source_pairs, build_time_facet_pairs
from tag_semantic.bootstrap.rule_aliases import build_aliases
from tag_semantic.bootstrap.rule_init import load_freeze, run_rule_init, write_jsonl
from tag_semantic.bootstrap.terms import seed_terms
from tag_semantic.eval.run import contract_cross_bucket, contract_empty_eligible, run_dev_eval
from tag_semantic.index.builder import build_index
from tag_semantic.retrieve.service import RetrieveService
from tag_semantic.snapshot.loader import load_catalog
from tag_semantic.snapshot.publish import assemble_snapshot, mark_reviewed


def cmd_pipeline(args: argparse.Namespace) -> int:
    freeze = load_freeze(args.freeze)
    init = run_rule_init(freeze)
    clustered = apply_cluster(init["result"], confirmations=PILOT_CONFIRMATIONS)
    tags = [r for r in clustered if r.get("kind") == "tag_semantic"]
    codes = [r for r in clustered if r.get("kind") == "code_value_semantic"]
    concepts = build_concept_rows(clustered, 107, 0, "客户")
    aliases = build_aliases(tags, codes, concepts)
    confusable = build_time_facet_pairs(tags) + build_source_pairs(tags)
    if args.review:
        tags = mark_reviewed(tags)
        codes = mark_reviewed(codes)
        concepts = mark_reviewed(concepts)
        aliases = mark_reviewed(aliases)
        confusable = mark_reviewed(confusable)
    terms = seed_terms()
    snapshot = assemble_snapshot(
        library_id=107,
        snapshot_id=args.snapshot_id,
        tags=tags,
        concepts=concepts,
        codes=codes,
        aliases=aliases,
        confusable=confusable,
        examples=[],
        terms=terms,
        coverage_note="试点 31/969 ≈ 3.2%，不得写成 100%",
    )
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "snapshot.jsonl").write_text(snapshot["jsonl"], encoding="utf-8")
    write_jsonl(out / "unresolved.jsonl", init["unresolved"])
    (out / "s3_concept_review_pack.md").write_text(review_pack(concepts, clustered, PILOT_CONFIRMATIONS), encoding="utf-8")
    catalog = load_catalog(out / "snapshot.jsonl")
    built = build_index(catalog, out / args.build_id, args.build_id)
    print(json.dumps({"snapshot_hash": snapshot["content_hash"], "manifest": built["manifest"]}, ensure_ascii=False))
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    catalog = load_catalog(Path(args.snapshot))
    built = build_index(catalog, Path(args.artifact), "query")
    service = RetrieveService(catalog, built["store"], built["alias_index"])
    eligible = set(args.eligible) if args.eligible else None
    result = service.retrieve(args.text, eligible)
    print(json.dumps({"facets": result["facets"], "family": _family_brief(result["family"]), "top": [_brief(x) for x in result["candidates"][:10]]}, ensure_ascii=False, indent=2))
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    catalog = load_catalog(Path(args.snapshot))
    built = build_index(catalog, Path(args.artifact), "eval")
    service = RetrieveService(catalog, built["store"], built["alias_index"])
    contract_empty_eligible(service)
    contract_cross_bucket()
    summary = run_dev_eval(service)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not summary["failures"] else 1


def _brief(item: dict) -> dict:
    doc = item.get("doc") or {}
    return {"doc_id": doc.get("doc_id"), "tag_id": doc.get("tag_id"), "rrf": item.get("rrf_score")}


def _family_brief(family: dict | None) -> dict | None:
    if not family:
        return None
    selected = family.get("selected") or {}
    return {"status": family.get("status"), "tag_id": selected.get("tag_id"), "reason": family.get("reason")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tag-semantic")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pipeline")
    p.add_argument("freeze", type=Path)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--snapshot-id", default="L107-PILOT-001")
    p.add_argument("--build-id", default="b1")
    p.add_argument("--review", action="store_true")
    p.set_defaults(func=cmd_pipeline)
    q = sub.add_parser("query")
    q.add_argument("--snapshot", required=True)
    q.add_argument("--artifact", required=True)
    q.add_argument("--text", required=True)
    q.add_argument("--eligible", nargs="*", type=int)
    q.set_defaults(func=cmd_query)
    e = sub.add_parser("eval")
    e.add_argument("--snapshot", required=True)
    e.add_argument("--artifact", required=True)
    e.set_defaults(func=cmd_eval)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
