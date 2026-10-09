"""tagpilot-bench 命令行入口。

  python -m tagpilot_bench.cli build-cases     # 物化 cases/core（需先有 trees/*.json）
  python -m tagpilot_bench.cli report <run_dir> [cases.jsonl]
  python -m tagpilot_bench.cli compare <suite_dir>
  python -m tagpilot_bench.cli selftest        # 判定器验收套件
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(script: str, *args):
    return subprocess.call([sys.executable, str(ROOT / 'tools' / script), *args])


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'help'
    if cmd == 'build-cases':
        _run('build_cases_61.py')
        _run('build_demo_cases.py')
        _run('merge_cases.py')
        _run('build_guard_cases.py')
        _run('build_smoke.py')
    elif cmd == 'report':
        from . import report
        report.main(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == 'compare':
        from . import compare
        compare.main(sys.argv[2])
    elif cmd == 'selftest':
        from .grade import acceptance_suite
        bad = [c for c in acceptance_suite() if c['verdict'] != c['want']]
        for c in acceptance_suite():
            print(f"{'OK ' if c['verdict'] == c['want'] else 'FAIL'} {c['name']}: {c['verdict']} (want {c['want']})")
        raise SystemExit(1 if bad else 0)
    elif cmd == 'l1':
        _run('run_l1.py', *sys.argv[2:])
    elif cmd == 'l3':
        _run('run_l3.py', *sys.argv[2:])
    elif cmd == 'regrade':
        _run('regrade.py', *sys.argv[2:])
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
