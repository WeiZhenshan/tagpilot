#!/usr/bin/env bash
# 固定合成H2 → Java聚合 → Python执行器/独立参考；不会连接业务数据库或模型。
set -euo pipefail
insight_root="$(cd "$(dirname "$0")/.." && pwd)"
insight_python="${TAGPILOT_INSIGHT_PYTHON:-$insight_root/tagpilot-agent/.venv/bin/python}"
insight_temp="$(mktemp -d "${TMPDIR:-/tmp}/tagpilot-insight-verify.XXXXXX")"
trap 'rm -rf "$insight_temp"' EXIT
cd "$insight_root"
PYTHONPATH="$insight_root/tagpilot-agent${PYTHONPATH:+:$PYTHONPATH}" "$insight_python" tagpilot-agent/legacy-insight/scripts/export_sql_test_inputs.py "$insight_temp/plans.json"
mvn test -pl ruoyi-taglibrary -am \
  -Dtest=TsInsightSqlCompilerTest,TsInsightQueryServiceTest,TsInsightRegistryServiceTest,TsInsightRunServiceTest,TsAgentWorkbenchServiceTest,RuleSqlBuilderTest \
  -Dsurefire.failIfNoSpecifiedTests=false \
  -Dinsight.test.plans="$insight_temp/plans.json" -Dinsight.test.output="$insight_temp/aggregates.json" -q
PYTHONPATH="$insight_root/tagpilot-agent:$insight_root/tagpilot-eval${PYTHONPATH:+:$PYTHONPATH}" "$insight_python" -m tagpilot_eval.insight \
  --java-aggregates "$insight_temp/aggregates.json" --output tagpilot-agent/legacy-insight/reports/sql-reference-verification.json
"$insight_python" -m pytest -q tagpilot-agent/tests/legacy_insight
