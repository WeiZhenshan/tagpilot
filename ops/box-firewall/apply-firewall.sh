#!/usr/bin/env bash
set -euo pipefail
# 所有规则在 iptables-restore 单次 COMMIT 原子提交；不对挂接链执行独立 flush。
python3 /workspace/tagpilot-data/codex-fix-20261006/firewall-rules.py
