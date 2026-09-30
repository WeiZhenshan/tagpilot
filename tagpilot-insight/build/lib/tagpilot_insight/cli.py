"""离线验证与共享 schema 导出，不读业务数据库、不调用模型。"""
import argparse
import json
from pathlib import Path

from pydantic import TypeAdapter
from .contracts import InsightReport, Manifest, MetricBinding, MetricQuery
from .fixtures import synthetic_golden_report
from .guards import validate_report
from .registry import SkillRegistry
from .planning import MetricPlan


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="TagPilot 洞察 P0/P1 离线验收")
    parser.add_argument("command", choices=["verify", "schema", "preview"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "schema":
        if args.output is None:
            parser.error("schema 需要 --output 目录")
        for model in (InsightReport, Manifest, MetricBinding, MetricPlan):
            write_json(args.output / (model.__name__ + ".schema.json"), model.model_json_schema())
        write_json(args.output / "MetricQuery.schema.json", TypeAdapter(MetricQuery).json_schema())
        return
    report = synthetic_golden_report()
    validate_report(report)
    if args.command == "preview":
        if args.output is None:
            parser.error("preview 需要 --output JSON 文件")
        write_json(args.output, report.model_dump(mode="json"))
    else:
        registry = SkillRegistry()
        result = {"scope": "P0/P1 聚合 fixtures 与 Guard；不是 Java 业务计算验收", "synthetic": True,
                  "skills": [{"id": skill.skill_id, "version": skill.skill_version, "pack_hash": registry.hash(skill.skill_id),
                              "facts": len(skill.facts), "charts": len(skill.charts), "status": "PASS"} for skill in report.results]}
        if args.output:
            write_json(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
