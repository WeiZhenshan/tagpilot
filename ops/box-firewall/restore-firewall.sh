#!/usr/bin/env bash
set -euo pipefail
OUT=/workspace/tagpilot-data/codex-fix-20261006
# 全量回滚到 FIX3 修改前（也撤销 2375 收紧）；仅在 Docker 拓扑未变时使用。
# 日常重启恢复应调用 apply-firewall.sh，包含 2375 规则。
sudo -n iptables-restore --wait 5 < "$OUT/fix3/iptables-before.rules"
sudo -n ip6tables-restore --wait 5 < "$OUT/fix3/ip6tables-before.rules"
echo 'restored firewall to pre-FIX3 backup; reapply to restore 2375 protection'
