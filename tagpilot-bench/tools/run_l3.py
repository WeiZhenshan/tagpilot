"""跑 L3 执行层（对 READY 案例比对完整 ID 集；有 Java 令牌则走权威链）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tagpilot_bench import l3  # noqa: E402
from tagpilot_bench.java import JavaClient  # noqa: E402


def main(run_dir: str):
    run = Path(run_dir)
    if not run.is_absolute():
        run = ROOT / run
    cases = {}
    for suite in ['core', 'guard', 'smoke']:
        p = ROOT / f'cases/{suite}/cases.jsonl'
        if p.exists():
            cases.update({json.loads(l)['case_id']: json.loads(l) for l in p.read_text().splitlines() if l.strip()})
    java = JavaClient()
    if not java.available:
        try:
            java.login()
            print('[L3] 已用本机账号登录 Java（验证码须为关闭状态）')
        except Exception as exc:  # noqa: BLE001
            print(f'[L3] Java 登录不可用，回退本地 oracle：{exc}')
    summary = l3.run_l3(cases, run, java_client=java)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main(sys.argv[1])
