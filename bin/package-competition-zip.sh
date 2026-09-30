#!/usr/bin/env bash
# 生成评委代码包 zip（含 Git 跟踪文件 + 本地语义索引 out/full-* + 彩排机密两件，
# 不含模型权重与 node_modules/.venv/target）。
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

# 竞赛彩排机密：随包交付，评委解压后即可直接启动。
#   .databroker-crypto-secret —— 与快照内 dp_datasource 密码密文配对，缺失需在「数据源管理」重录密码
#   .tag-runtime-token        —— Java/Python 服务间令牌；随包固定后本机不必再生成
# 仅限本地演示：对外分发或生产使用前请替换/轮换这两个值。
for secret in .databroker-crypto-secret .tag-runtime-token; do
  if [[ -f "$ROOT_DIR/$secret" ]]; then
    cp "$ROOT_DIR/$secret" "$STAGE/$secret"
    chmod 600 "$STAGE/$secret"
    echo "已纳入: $secret"
  elif [[ "$secret" == ".databroker-crypto-secret" ]]; then
    echo "警告: 缺少 $secret —— 快照内的数据源密码将无法解密，评委须在「数据源管理」重新录入密码" >&2
  else
    echo "提示: 未找到 $secret —— 评委首次启动时 dev.sh 会自动生成" >&2
  fi
done

(
  cd "$STAGE"
  zip -rq "$OUT_ZIP" . \
    -x '*/node_modules/*' -x '*/.venv/*' -x '*/.venv-models/*' \
    -x '*/target/*' -x '*/logs/*' -x '*/tagpilot-agent/out/*' \
    -x '*/tagpilot-semantic/out/models/*' -x '*/.git/*'
)
echo "已生成: $OUT_ZIP ($(du -h "$OUT_ZIP" | cut -f1))"
