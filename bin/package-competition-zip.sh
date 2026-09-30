#!/usr/bin/env bash
# 生成评委代码包 zip（含 Git 跟踪文件 + 本地语义索引 out/full-*，不含模型与 node_modules/.venv/target）。
set -euo pipefail
ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"
VERSION="${1:-$(git rev-parse --short HEAD 2>/dev/null || echo local)}"
STAGE=$(mktemp -d "${TMPDIR:-/tmp}/tagpilot-release.XXXXXX")
OUT_ZIP="$ROOT_DIR/tagpilot-release-${VERSION}.zip"
trap 'rm -rf "$STAGE"' EXIT

git archive --format=tar HEAD | tar -x -C "$STAGE"
if [[ -d "$ROOT_DIR/tagpilot-semantic/out" ]]; then
  mkdir -p "$STAGE/tagpilot-semantic/out"
  for set_dir in "$ROOT_DIR"/tagpilot-semantic/out/full-*/; do
    [[ -d "$set_dir/snapshots" && -d "$set_dir/indexes" ]] || continue
    base=$(basename "$set_dir")
    rsync -a --exclude 'drafts' --exclude 'eval' --exclude 'reviewed' \
      "$set_dir" "$STAGE/tagpilot-semantic/out/$base"
  done
fi
(
  cd "$STAGE"
  zip -rq "$OUT_ZIP" . \
    -x '*/node_modules/*' -x '*/.venv/*' -x '*/.venv-models/*' \
    -x '*/target/*' -x '*/logs/*' -x '*/tagpilot-agent/out/*' \
    -x '*/tagpilot-semantic/out/models/*' -x '*/.git/*'
)
echo "已生成: $OUT_ZIP ($(du -h "$OUT_ZIP" | cut -f1))"
