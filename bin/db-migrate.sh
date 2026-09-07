#!/bin/bash
# 增量数据库迁移执行器
#
# 用法:
#   DB_USER=root DB_PASSWORD=xxx bash bin/db-migrate.sh
#
# 环境变量:
#   DB_HOST       数据库主机 (默认 127.0.0.1)
#   DB_PORT       数据库端口 (默认 3306)
#   DB_USER       数据库用户 (必填)
#   DB_PASSWORD   数据库密码 (必填)
#   DB_NAME       目标库名   (默认 ry)
#   MIGRATION_DIR 迁移脚本目录 (默认 <仓库根>/sql/migration)
#
# 机制:
#   1. 在目标库创建 schema_migration 记录表 (不存在才建)
#   2. 按文件名排序遍历 MIGRATION_DIR 下 V*.sql，跳过已记录的版本
#   3. 逐个执行未应用的脚本，成功则写入记录，失败立即停止并以非零码退出
#
# 迁移脚本规范: 命名 V<yyyymmdd>_<序号>__<描述>.sql；幂等、只向前、不得包含 drop table

set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-}"
DB_PASSWORD="${DB_PASSWORD:-}"
DB_NAME="${DB_NAME:-ry}"
MIGRATION_DIR="${MIGRATION_DIR:-$ROOT_DIR/sql/migration}"

red()   { printf '\033[0;31m%s\033[0m\n' "$*"; }
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
blue()  { printf '\033[0;34m%s\033[0m\n' "$*"; }

if [ -z "$DB_USER" ] || [ -z "$DB_PASSWORD" ]; then
    red "错误: 必须通过环境变量提供 DB_USER 和 DB_PASSWORD"
    exit 1
fi

if ! command -v mysql >/dev/null 2>&1; then
    red "错误: 未找到 mysql 客户端，请先安装 MySQL client"
    exit 1
fi

if [ ! -d "$MIGRATION_DIR" ]; then
    red "错误: 迁移目录不存在: $MIGRATION_DIR"
    exit 1
fi

export MYSQL_PWD="$DB_PASSWORD"
MYSQL_CMD="mysql -h$DB_HOST -P$DB_PORT -u$DB_USER --default-character-set=utf8mb4"

blue "目标库: $DB_USER@$DB_HOST:$DB_PORT/$DB_NAME"
blue "迁移目录: $MIGRATION_DIR"

# 确认目标库可连接
if ! $MYSQL_CMD -e "use \`$DB_NAME\`" >/dev/null 2>&1; then
    red "错误: 无法连接或选中数据库 $DB_NAME (请先执行 sql/init/ry_init.sql 完成初始化)"
    exit 1
fi

# 创建迁移记录表
$MYSQL_CMD "$DB_NAME" >/dev/null <<'SQL'
CREATE TABLE IF NOT EXISTS `schema_migration` (
  `version`     varchar(64)  NOT NULL            COMMENT '迁移版本号（文件名去掉 .sql）',
  `description` varchar(255) NOT NULL DEFAULT '' COMMENT '迁移描述',
  `applied_at`  datetime     NOT NULL            COMMENT '应用时间',
  PRIMARY KEY (`version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据库增量迁移记录表';
SQL

APPLIED=$($MYSQL_CMD -N -B "$DB_NAME" -e "select version from schema_migration")

PENDING=0
FAILED=0

shopt -s nullglob
for FILE in "$MIGRATION_DIR"/V*.sql; do
    NAME=$(basename "$FILE" .sql)

    if printf '%s\n' "$APPLIED" | grep -qxF "$NAME"; then
        echo "[跳过] $NAME (已应用)"
        continue
    fi

    PENDING=$((PENDING + 1))
    blue "[执行] $NAME ..."

    if $MYSQL_CMD "$DB_NAME" < "$FILE"; then
        $MYSQL_CMD "$DB_NAME" -e \
            "insert into schema_migration (version, description, applied_at) values ('$NAME', '', now())"
        green "[成功] $NAME"
    else
        red "[失败] $NAME —— 迁移中断，请修复后重新执行本脚本"
        FAILED=1
        break
    fi
done

echo
if [ "$FAILED" -ne 0 ]; then
    exit 1
fi

if [ "$PENDING" -eq 0 ]; then
    green "无待执行迁移，数据库已是最新。"
else
    green "迁移完成，本次共执行 $PENDING 个脚本。"
fi
