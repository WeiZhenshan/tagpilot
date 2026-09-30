#!/usr/bin/env bash
# 从本机 MySQL 导出竞赛彩排库（ry + indiv_cust），供评委一键导入。
set -euo pipefail
ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
OUT_DIR="$ROOT_DIR/sql/seed/competition"
STAMP="${1:-$(date +%Y%m%d)}"
OUT_FILE="$OUT_DIR/tagpilot-competition-${STAMP}.sql.gz"
MANIFEST="$OUT_DIR/tagpilot-competition-${STAMP}.manifest.json"

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-root}"
DB_PASSWORD="${DB_PASSWORD:-}"

if [[ -z "$DB_PASSWORD" ]]; then
  echo "请设置 DB_PASSWORD（或在本机使用：DB_PASSWORD=123456 bash bin/export-competition-db.sh）" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"
export MYSQL_PWD="$DB_PASSWORD"

mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -e "USE ry; USE indiv_cust;" >/dev/null

mysqldump -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" \
  --default-character-set=utf8mb4 \
  --single-transaction --routines --triggers \
  --databases ry indiv_cust \
  | gzip -9 > "$OUT_FILE"

GIT_SHA=$(git -C "$ROOT_DIR" rev-parse HEAD 2>/dev/null || echo unknown)
cat > "$MANIFEST" <<EOF
{
  "exported_at": "$(date -u +%Y-%m-%dT%H:%MZ)",
  "git_commit": "$GIT_SHA",
  "databases": ["ry", "indiv_cust"],
  "artifact": "$(basename "$OUT_FILE")",
  "import": "gunzip -c $(basename "$OUT_FILE") | mysql -h127.0.0.1 -uroot -p --default-character-set=utf8mb4",
  "notes": "含标签库107、已发布元Skill、语义快照ACTIVE、演示对照客群等；导入后勿再执行 ry_init 或 db-migrate（除非空库失败重试）。DataBroker 密码依赖本机 .databroker-crypto-secret，见 README。"
}
EOF

echo "已导出: $OUT_FILE ($(du -h "$OUT_FILE" | cut -f1))"
echo "清单:   $MANIFEST"
