from tag_semantic.eval.run import contract_cross_bucket, contract_empty_eligible, contract_partial_eligible, run_dev_eval, snapshot_coverage
from tag_semantic.eval.gold import GOLD_DEV
from tag_semantic.index.builder import build_index
from tag_semantic.index.milvus_store import MilvusStore, MilvusUnavailable
from tag_semantic.profile.aggregator import aggregate_profile
from tag_semantic.retrieve.family import resolve_family
from tag_semantic.retrieve.service import RetrieveService
from tag_semantic.snapshot.canonicalize import content_hash
from tag_semantic.snapshot.loader import load_catalog
from tag_semantic.snapshot.publish import assemble_snapshot, mark_reviewed
from tag_semantic.snapshot.schema import validate_row
from tag_semantic.tests.test_rule_init import freeze_jsonl
from tag_semantic.bootstrap.concept_cluster import PILOT_CONFIRMATIONS, apply_cluster, build_concept_rows
from tag_semantic.bootstrap.confusable import build_time_facet_pairs
from tag_semantic.bootstrap.llm_enrich import enrich_concept, stub_generate, validate_enrichment
from tag_semantic.bootstrap.rule_aliases import build_aliases
from tag_semantic.bootstrap.rule_init import load_freeze, run_rule_init
from tag_semantic.bootstrap.terms import seed_terms
from tag_semantic.docs.templates import tag_views
import json
from pathlib import Path


def _pilot_bundle(tmp_path: Path):
    output = run_rule_init(load_freeze(freeze_jsonl(tmp_path)))
    clustered = apply_cluster(output["result"], confirmations=PILOT_CONFIRMATIONS)
    tags = [r for r in clustered if r.get("kind") == "tag_semantic"]
    codes = [r for r in clustered if r.get("kind") == "code_value_semantic"]
    concepts = build_concept_rows(clustered, 107, 0, "客户")
    aliases = build_aliases(tags, codes, concepts)
    confusable = build_time_facet_pairs(tags)
    tags = mark_reviewed(tags)
    codes = mark_reviewed(codes)
    concepts = mark_reviewed(concepts)
    aliases = mark_reviewed(aliases)
    confusable = mark_reviewed(confusable)
    snapshot = assemble_snapshot(
        library_id=107,
        snapshot_id="L107-TEST-001",
        tags=tags,
        concepts=concepts,
        codes=codes,
        aliases=aliases,
        confusable=confusable,
        examples=[],
        terms=seed_terms(),
        coverage_note="试点 31/969 ≈ 3.2%，不得写成 100%",
    )
    path = tmp_path / "snapshot.jsonl"
    path.write_text(snapshot["jsonl"], encoding="utf-8")
    catalog = load_catalog(path, expected_hash=snapshot["content_hash"])
    built = build_index(catalog, tmp_path / "b1", "b1")
    service = RetrieveService(catalog, built["store"], built["alias_index"])
    return service, catalog, snapshot


def test_hash_stable(tmp_path):
    _, _, snapshot = _pilot_bundle(tmp_path)
    assert snapshot["content_hash"] == content_hash(snapshot["rows"])
    assert snapshot["content_hash"] == content_hash(snapshot["rows"])
    assert all(r.get("review_status") != "DRAFT" for r in snapshot["rows"] if r.get("kind") == "tag")


def test_shared_hash_vector():
    fixture = Path(__file__).resolve().parents[3] / "docs" / "design" / "snapshot_hash_vector.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    assert content_hash(payload["rows"]) == payload["expected_hash"]


def test_female_alias_hits_gender(tmp_path):
    service, _, _ = _pilot_bundle(tmp_path)
    result = service.retrieve("女性", None, k=20)
    tag_ids = [c["doc"].get("tag_id") for c in result["candidates"]]
    assert 526 in tag_ids or any(c["doc"].get("code") == "F" for c in result["candidates"])
    assert result['code_selection'] == {'expressible': True, 'codes': ['F']}
    negated = service.retrieve('不是女性', set(service.catalog.tags), k=20)
    assert negated['code_selection'] is None
    assert negated['decision'] == 'CLARIFY'


def test_interbank_30d(tmp_path):
    service, catalog, _ = _pilot_bundle(tmp_path)
    result = service.retrieve("近30天异名跨行转入", None, k=20)
    assert hit_ids(result)[0] == 709 or 709 in hit_ids(result)
    members = [t for t in catalog.tags.values() if t.get("family_key", "").startswith("FUND_INFLOW_INTERBANK|FLAG")]
    family = resolve_family(members, result["facets"]["time"])
    assert family["status"] == "selected"
    assert family["selected"]["tag_id"] == 709
    shown = {m.get("tag_id") for m in family.get("confusable_shown") or []}
    assert 708 in shown


def test_aum_max_not_same_family_as_eop(tmp_path):
    service, catalog, _ = _pilot_bundle(tmp_path)
    point = catalog.tags[721]
    window = catalog.tags[717]
    assert point["family_key"] != window["family_key"]
    assert point["family_key"].startswith("AUM|EOP")
    assert "MAX" in window["family_key"]
    result = service.retrieve("当前AUM", None, k=20)
    ids = hit_ids(result)
    assert 721 in ids
    assert ids[0] != 717


def test_our_bank_aum(tmp_path):
    service, catalog, _ = _pilot_bundle(tmp_path)
    assert "OUR_BANK" in catalog.tags[735]["family_key"]
    result = service.retrieve("本行AUM", None, k=20)
    assert 735 in hit_ids(result)
    assert hit_ids(result)[0] != 721


def test_gold_dev_twenty(tmp_path):
    service, catalog, snapshot = _pilot_bundle(tmp_path)
    assert len(GOLD_DEV) == 20
    summary = run_dev_eval(service)
    assert not summary["failures"], summary
    assert summary["hit_at_20"] + summary["clarify_ok"] == summary["total"]
    report = snapshot_coverage(len(catalog.tags), reviewed=len(catalog.tags), draft=0)
    assert report["coverage"] == f"{len(catalog.tags)}/969"
    assert report["coverage_pct"] < 100
    contract_empty_eligible(service)
    contract_partial_eligible(service, {534})
    contract_cross_bucket()
    validate_row({"kind": "tag", "tag_id": 1})


def test_clarify_multi_member_without_time():
    members = [
        {"tag_id": 601, "caliber_struct": {"time_anchor_type": "POINT"}},
        {"tag_id": 579, "caliber_struct": {"time_anchor_type": "HIST"}},
    ]
    result = resolve_family(members, {"time_anchor_type": "NONE"})
    assert result["status"] == "clarify_time"


def test_empty_eligible_and_cross_bucket(tmp_path):
    service, _, _ = _pilot_bundle(tmp_path)
    contract_empty_eligible(service)
    contract_cross_bucket()


def test_llm_forbidden_fields_and_draft_not_in_docs():
    try:
        validate_enrichment({"aliases": [], "rank_no": 1})
        assert False, "should reject"
    except ValueError:
        pass
    payload = enrich_concept({"concept_code": "AUM", "concept_name": "AUM", "definition": "规模"}, stub_generate)
    assert payload["review_status"] == "DRAFT"
    assert payload["source"] == "LLM"
    tag = {
        "tag_id": 721,
        "name": "当前时点AUM",
        "aliases": [{"alias_text": "管资规模", "alias_type": "COLLOQUIAL", "review_status": "DRAFT"}],
        "examples": [{"utterance": "当前AUM超过50万", "example_type": "POS", "review_status": "DRAFT"}],
        "confusable": [{"difference_note": "不是最高AUM", "review_status": "DRAFT"}],
        "caliber_struct": {},
    }
    views = tag_views(tag)
    assert "管资规模" not in views["name_text"]
    assert "[示例]" in views["body_text"]
    assert "当前AUM超过50万" not in views["dense_text"]
    assert "[区别于]" not in views["dense_text"]


def test_profile_skips_free_text():
    row = aggregate_profile({"tag_id": 566, "semantic_type": "TEXT_FREE"}, ["iPhone", "华为"], "2026-09-18")
    assert row["top_values"] is None


def test_milvus_unavailable_without_sdk():
    try:
        MilvusStore()
    except MilvusUnavailable:
        return
    try:
        MilvusStore().build([])
        assert False
    except MilvusUnavailable:
        pass


def test_expand_full_keeps_coverage_denominator(tmp_path):
    from tag_semantic.bootstrap.expand_full import expand
    freeze = freeze_jsonl(tmp_path)
    summary = expand(freeze, tmp_path / "full")
    assert "969" in summary["coverage_note"] or "/" in summary["coverage_note"]
    assert "100%" not in summary["coverage_note"].replace("不得写成 100%", "")


def test_importable_draft_joins_concepts_and_clustered_rows(tmp_path):
    from tag_semantic.bootstrap.expand_full import importable_draft
    draft = importable_draft(freeze_jsonl(tmp_path).read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in draft["jsonl"].splitlines() if line.strip()]
    kinds = [row["kind"] for row in rows]
    assert kinds[0] == "concept"
    assert "tag_semantic" in kinds
    assert "code_value_semantic" in kinds
    assert "meta" not in kinds
    business = [row for row in rows if row["kind"] == "tag_semantic" and not row.get("skip_concept")]
    assert business and all(row.get("concept_code") for row in business)


def test_bootstrap_expand_http_requires_token_and_rejects_draft(tmp_path):
    from fastapi.testclient import TestClient
    from tag_semantic.server import create_app
    client = TestClient(create_app(tmp_path, tmp_path, "secret"))
    payload = {"jsonl": freeze_jsonl(tmp_path).read_text(encoding="utf-8")}
    assert client.post("/bootstrap/expand", json=payload).status_code == 401
    ok = client.post("/bootstrap/expand", json=payload, headers={"Authorization": "Bearer secret"})
    assert ok.status_code == 200, ok.text
    assert "tag_semantic" in ok.json()["jsonl"]
    rejected = client.post("/bootstrap/expand", json={"jsonl": '{"kind":"tag_semantic"}\n'}, headers={"Authorization": "Bearer secret"})
    assert rejected.status_code == 422


def test_cli_query_smoke(tmp_path):
    from tag_semantic.cli import main
    _pilot_bundle(tmp_path)
    snap = tmp_path / "snapshot.jsonl"
    artifact = tmp_path / "b1"
    assert main(["query", "--snapshot", str(snap), "--artifact", str(artifact), "--text", "女性"]) == 0
    assert main(["eval", "--snapshot", str(snap), "--artifact", str(artifact)]) == 0


def test_sealed_gold_not_used_for_learning():
    sealed = json.loads((Path(__file__).resolve().parent.parent / "eval" / "gold_retrieval_v1.json").read_text(encoding="utf-8"))
    assert sealed["sealed"] is True
    assert sealed["queries"] == []
    assert sealed["target_size"] == 600


def hit_ids(result: dict) -> list[int]:
    ids = []
    for item in result["candidates"]:
        tag_id = int((item.get("doc") or {}).get("tag_id") or -1)
        if tag_id > 0:
            ids.append(tag_id)
    return ids
