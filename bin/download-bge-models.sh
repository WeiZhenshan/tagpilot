#!/usr/bin/env bash
# 下载竞赛演示所需的 BGE-M3 与 bge-reranker-v2-m3 到 tagpilot-semantic/out/models/（约 4.3GB）。
# 需要：Python 3.10+、网络；推荐先安装 huggingface_hub：pip install -U "huggingface_hub[cli]"
set -euo pipefail
ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
MODEL_ROOT="$ROOT_DIR/tagpilot-semantic/out/models"
EMBED_DIR="$MODEL_ROOT/bge-m3"
RERANK_DIR="$MODEL_ROOT/bge-reranker-v2-m3"

download_one() {
  local repo="$1" dest="$2"
  if [[ -d "$dest" ]] && find "$dest" -name '*.safetensors' -o -name 'pytorch_model.bin' 2>/dev/null | grep -q .; then
    echo "已存在，跳过: $dest"
    return 0
  fi
  mkdir -p "$dest"
  if command -v huggingface-cli >/dev/null 2>&1; then
    huggingface-cli download "$repo" --local-dir "$dest" --local-dir-use-symlinks False
  elif python3 -c "import huggingface_hub" 2>/dev/null; then
    python3 - <<PY
from huggingface_hub import snapshot_download
snapshot_download(repo_id="${repo}", local_dir="${dest}")
PY
  else
    echo "请先安装: pip install -U huggingface_hub" >&2
    exit 1
  fi
}

echo "Embedding → $EMBED_DIR"
download_one "BAAI/bge-m3" "$EMBED_DIR"
echo "Reranker → $RERANK_DIR"
download_one "BAAI/bge-reranker-v2-m3" "$RERANK_DIR"

cat > "$MODEL_ROOT/sources.json" <<EOF
{"embedding":"BAAI/bge-m3","reranker":"BAAI/bge-reranker-v2-m3","downloaded_at":"$(date -u +%Y-%m-%dT%H:%MZ)"}
EOF
echo "完成。启动前请 export:"
echo "  export TAG_EMBEDDING_PATH=\"$EMBED_DIR\""
echo "  export TAG_RERANKER_PATH=\"$RERANK_DIR\""
