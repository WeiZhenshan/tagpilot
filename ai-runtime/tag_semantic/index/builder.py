"""构建 docs / 词典 / graph / manifest。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from tag_semantic.docs.templates import TEMPLATE_VERSION, render_documents
from tag_semantic.index.alias_index import AliasIndex
from tag_semantic.index.embedder import HashEmbedder
from tag_semantic.index.local_store import LocalStore
from tag_semantic.snapshot.loader import Catalog, write_graph_sqlite


def build_index(catalog: Catalog, out_dir: Path, build_id: str, store_type: str = "LOCAL") -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    docs = render_documents(list(catalog.tags.values()), list(catalog.concepts.values()), catalog.code_values)
    embedder = HashEmbedder()
    dense = embedder.encode(d["dense_text"] for d in docs)
    for doc, vec in zip(docs, dense):
        doc["dense"] = vec
    docs_path = out_dir / "docs.jsonl"
    with docs_path.open("w", encoding="utf-8") as fh:
        for doc in docs:
            slim = {k: v for k, v in doc.items() if k != "dense"}
            fh.write(json.dumps(slim, ensure_ascii=False, separators=(",", ":")) + "\n")
    write_graph_sqlite(catalog, out_dir.parent / "graph.sqlite")
    alias_index = AliasIndex()
    alias_index.build(catalog.aliases)
    store = LocalStore()
    stats = store.build(docs)
    doc_ids = sorted(d["doc_id"] for d in docs)
    doc_id_hash = hashlib.sha256("\n".join(doc_ids).encode("utf-8")).hexdigest()
    manifest = {
        "build_id": build_id,
        "snapshot_id": catalog.meta.get("snapshot_id"),
        "doc_template_version": TEMPLATE_VERSION,
        "embedding_model": embedder.model,
        "embedding_dim": embedder.dim,
        "store_type": store_type,
        "doc_count": len(docs),
        "doc_id_hash": doc_id_hash,
        "status": "READY",
        **stats,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"manifest": manifest, "docs": docs, "store": store, "alias_index": alias_index}
