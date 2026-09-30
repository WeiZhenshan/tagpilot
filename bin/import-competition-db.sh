#!/usr/bin/env bash
# 导入竞赛全库快照（默认 sql/seed/competition/tagpilot-competition-20260930.sql.gz）。
set -euo pipefail
ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
DUMP="${1:-$ROOT_DIR/sql/seed/competition/tagpilot-competition-20260930.sql.gz}"

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-root}"
DB_PASSWORD="${DB_PASSWORD:-}"

if [[ -z "$DB_PASSWORD" ]]; then
  echo "请设置 DB_PASSWORD" >&2
  exit 1
fi
[[ -f "$DUMP" ]] || { echo "找不到: $DUMP" >&2; exit 1; }

export MYSQL_PWD="$DB_PASSWORD"
echo "导入 $DUMP → $DB_USER@$DB_HOST (ry + indiv_cust) ..."
gunzip -c "$DUMP" | mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" --default-character-set=utf8mb4
echo "完成。请确认 application-druid.yml 账号密码与 DB_PASSWORD 一致，并保留仓库根目录 .databroker-crypto-secret（若从交付包复制）。"
echo "无需再执行 sql/init/ry_init.sql 或 bin/db-migrate.sh（本快照已含 schema_migration 与业务数据）。"
echo "仍须单独准备：BGE 模型、tagpilot-semantic/out 索引目录、.tag-llm-config。"
