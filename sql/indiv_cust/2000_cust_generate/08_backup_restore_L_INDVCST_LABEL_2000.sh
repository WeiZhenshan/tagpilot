#!/usr/bin/env bash
# ============================================================================
# 08_backup_restore_L_INDVCST_LABEL_2000.sh
# 用途      : 对 indiv_cust.L_INDVCST_LABEL 做 mysqldump 备份 / 还原，
#             用于回退「06_insert_L_INDVCST_LABEL_2000.sql」全量插入的 2000 行模拟数据
# 目标库表  : indiv_cust.L_INDVCST_LABEL
# 危险等级  : restore 会 DROP+重建该表（仅此表，不影响 CODE_MAP）
# 备份目录  : 默认 <本脚本目录>/.backups/（已 gitignore，勿提交仓库）
# 用法      :
#   ./08_backup_restore_L_INDVCST_LABEL_2000.sh backup
#   ./08_backup_restore_L_INDVCST_LABEL_2000.sh restore <backup.sql[.gz]>
#   ./08_backup_restore_L_INDVCST_LABEL_2000.sh list
#   ./08_backup_restore_L_INDVCST_LABEL_2000.sh rollback-sim   # 仅删 SIM20260918* 行（快回退）
#
# 连接参数可通过环境变量覆盖（默认对齐本地 application-druid.yml）：
#   MYSQL_HOST MYSQL_PORT MYSQL_USER MYSQL_PWD MYSQL_CHARSET
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-${SCRIPT_DIR}/.backups}"
MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_USER="${MYSQL_USER:-root}"
MYSQL_PWD="${MYSQL_PWD:-123456}"
MYSQL_CHARSET="${MYSQL_CHARSET:-utf8mb4}"
DB_NAME="indiv_cust"
TABLE_NAME="L_INDVCST_LABEL"
SIM_PREFIX="SIM20260918"

mysql_base=(
  mysql
  --default-character-set="${MYSQL_CHARSET}"
  -h"${MYSQL_HOST}"
  -P"${MYSQL_PORT}"
  -u"${MYSQL_USER}"
  -p"${MYSQL_PWD}"
)

mysqldump_base=(
  mysqldump
  --default-character-set="${MYSQL_CHARSET}"
  -h"${MYSQL_HOST}"
  -P"${MYSQL_PORT}"
  -u"${MYSQL_USER}"
  -p"${MYSQL_PWD}"
  --single-transaction
  --routines=false
  --triggers=false
  --set-gtid-purged=OFF
  --hex-blob
  --max-allowed-packet=512M
)

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
  exit 1
}

require_mysql() {
  command -v mysql >/dev/null 2>&1 || { echo "ERROR: mysql client not found" >&2; exit 1; }
  command -v mysqldump >/dev/null 2>&1 || { echo "ERROR: mysqldump not found" >&2; exit 1; }
}

row_count() {
  "${mysql_base[@]}" -N -e "SELECT COUNT(*) FROM \`${DB_NAME}\`.\`${TABLE_NAME}\`;" 2>/dev/null \
    | grep -E '^[0-9]+$' || echo "?"
}

cmd_backup() {
  require_mysql
  mkdir -p "${BACKUP_DIR}"
  local ts label outfile
  ts="$(date +%Y%m%d_%H%M%S)"
  label="${1:-pre_or_manual}"
  outfile="${BACKUP_DIR}/L_INDVCST_LABEL_${label}_${ts}.sql.gz"

  local cnt
  cnt="$(row_count)"
  echo "==> backup ${DB_NAME}.${TABLE_NAME} (rows=${cnt}) -> ${outfile}"

  "${mysqldump_base[@]}" \
    --databases "${DB_NAME}" \
    --tables "${TABLE_NAME}" \
    | gzip -c > "${outfile}"

  # 写入 sidecar 元数据，方便还原前核对
  {
    echo "table=${DB_NAME}.${TABLE_NAME}"
    echo "label=${label}"
    echo "timestamp=${ts}"
    echo "row_count=${cnt}"
    echo "host=${MYSQL_HOST}:${MYSQL_PORT}"
    echo "file=$(basename "${outfile}")"
  } > "${outfile%.sql.gz}.meta"

  ls -lh "${outfile}"
  echo "OK backup done. Use: $0 restore $(basename "${outfile}")"
}

cmd_list() {
  mkdir -p "${BACKUP_DIR}"
  echo "==> backups in ${BACKUP_DIR}"
  if compgen -G "${BACKUP_DIR}/L_INDVCST_LABEL_*.sql.gz" >/dev/null; then
    ls -lht "${BACKUP_DIR}"/L_INDVCST_LABEL_*.sql.gz
  else
    echo "(none)"
  fi
}

resolve_backup_file() {
  local arg="${1:-}"
  [[ -n "${arg}" ]] || { echo "ERROR: restore requires a backup file" >&2; usage; }
  if [[ -f "${arg}" ]]; then
    echo "${arg}"
    return
  fi
  if [[ -f "${BACKUP_DIR}/${arg}" ]]; then
    echo "${BACKUP_DIR}/${arg}"
    return
  fi
  echo "ERROR: backup file not found: ${arg}" >&2
  exit 1
}

cmd_restore() {
  require_mysql
  local file
  file="$(resolve_backup_file "${1:-}")"
  local before after
  before="$(row_count)"
  echo "==> restore ${file}"
  echo "    current rows=${before}  (will DROP+recreate ${DB_NAME}.${TABLE_NAME})"
  echo "    CONFIRM in 3s... (Ctrl-C to abort)"
  sleep 3

  if [[ "${file}" == *.gz ]]; then
    gunzip -c "${file}" | "${mysql_base[@]}" --max-allowed-packet=512M
  else
    "${mysql_base[@]}" --max-allowed-packet=512M < "${file}"
  fi

  after="$(row_count)"
  echo "OK restore done. rows: ${before} -> ${after}"
}

# 快回退：只删除本次模拟批次 CUST_ID（SIM20260918%），保留表结构与其它数据
cmd_rollback_sim() {
  require_mysql
  local before after deleted
  before="$(row_count)"
  echo "==> DELETE FROM ${DB_NAME}.${TABLE_NAME} WHERE CUST_ID LIKE '${SIM_PREFIX}%'"
  echo "    current rows=${before}"
  echo "    CONFIRM in 3s... (Ctrl-C to abort)"
  sleep 3

  deleted="$("${mysql_base[@]}" -N -e "
    SELECT COUNT(*) FROM \`${DB_NAME}\`.\`${TABLE_NAME}\`
     WHERE CUST_ID LIKE '${SIM_PREFIX}%';
  ")"
  "${mysql_base[@]}" -e "
    DELETE FROM \`${DB_NAME}\`.\`${TABLE_NAME}\`
     WHERE CUST_ID LIKE '${SIM_PREFIX}%';
  "
  after="$(row_count)"
  echo "OK rollback-sim done. matched=${deleted}; rows: ${before} -> ${after}"
}

main() {
  local action="${1:-}"
  case "${action}" in
    backup)        shift; cmd_backup "${1:-manual}" ;;
    restore)       shift; cmd_restore "${1:-}" ;;
    list)          cmd_list ;;
    rollback-sim)  cmd_rollback_sim ;;
    -h|--help|help|"") usage ;;
    *) echo "ERROR: unknown action: ${action}" >&2; usage ;;
  esac
}

main "$@"
