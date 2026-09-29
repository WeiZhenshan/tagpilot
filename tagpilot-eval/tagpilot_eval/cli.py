"""评测控制面：P0–P3；P3 不隐式扩量、发布或激活。"""
import argparse
import json
from datetime import date
from pathlib import Path

from .contracts import CONTRACTS
from .dispositions import build_p0_v2
from .freeze import freeze
from .inventory import inventory
from .human_review import build_page, import_decisions
from .io import fresh_directory, write_json
from .journal import initialize
from .l1 import run_l1
from .l2 import regrade, run_l2
from .p2_basis import verify_basis
from .p2_cases import ai_review, assemble_cases, materialize
from .p2_coverage import coverage
from .p2_diagnose import diagnose
from .p2_freeze import freeze_p2
from .p2_l2 import EVAL_AGENT_URL, run_p2_l2
from .p2_mothers import build_mothers
from .p2_partition import partition
from .p2_variants import generate_variants
from .report import report
from .review import apply_reviews, build_packet, summarize
from .seeds import seed_cases
from .validation import validate_package

BLOCKED = set()
P2_WRITE = {'basis', 'mothers', 'split', 'generate', 'assemble', 'case-review', 'materialize',
            'coverage', 'run', 'diagnose', 'p2-freeze'}


def _authorization(args):
    return {'authorized_by': getattr(args, 'authorized_by', None) or 'USER',
            'authorized_at': date.today().isoformat(),
            'basis': '会话授权：开启P2（承接 P2 前置复核）',
            'budget_usd_cap': getattr(args, 'budget_usd', None)}


def _add_authorization(parser):
    parser.add_argument('--authorized-by', default=None)
    parser.add_argument('--budget-usd', type=float, default=None)


def _build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ['inventory', 'seed', 'validate', 'report', 'schemas', 'journal',
                 'dispose', 'review', 'human-review', 'human-import', 'l1', 'l2', 'judge', 'freeze']:
        cmd = sub.add_parser(name)
        if name in {'inventory', 'seed'}: cmd.add_argument('--root', type=Path, required=True)
        if name in {'seed', 'validate', 'report', 'review', 'human-review', 'l1', 'l2', 'judge', 'freeze'}:
            cmd.add_argument('--p0', type=Path, required=True)
        if name in {'validate', 'report', 'journal', 'review', 'human-review', 'l1', 'l2', 'judge', 'freeze'}:
            cmd.add_argument('--calibration', type=Path, required=True)
        if name != 'validate': cmd.add_argument('--output', type=Path, required=True)
        if name == 'inventory': cmd.add_argument('--observation', type=Path, required=True)
        if name == 'seed': cmd.add_argument('--count', type=int, default=200)
        if name == 'dispose': cmd.add_argument('--p0-v1', type=Path, required=True)
        if name == 'review': cmd.add_argument('--reviews', type=Path, default=None)
        if name == 'human-review': cmd.add_argument('--reviews', type=Path, required=True)
        if name == 'human-import':
            cmd.add_argument('--queue', type=Path, required=True)
            cmd.add_argument('--decisions', type=Path, required=True)
        if name == 'freeze':
            cmd.add_argument('--reviews', type=Path, required=True)
            cmd.add_argument('--runs', type=Path, required=True)
            cmd.add_argument('--human-ledger', type=Path, required=True)
        if name in {'l1', 'l2'}:
            cmd.add_argument('--limit', type=int, default=None)
            cmd.add_argument('--k', type=int, default=20)
        if name == 'l2':
            cmd.add_argument('--max-seconds', type=int, default=150)
            cmd.add_argument('--regrade', action='store_true')
    for name in sorted(P2_WRITE):
        cmd = sub.add_parser(name)
        _add_authorization(cmd)
        if name == 'basis':
            cmd.add_argument('--p0', type=Path, required=True)
            cmd.add_argument('--root', type=Path, required=True)
            cmd.add_argument('--observation', type=Path, default=None)
        elif name == 'mothers':
            cmd.add_argument('--p0', type=Path, required=True)
            cmd.add_argument('--root', type=Path, required=True)
        elif name == 'split':
            cmd.add_argument('--p0', type=Path, required=True)
            cmd.add_argument('--mothers', type=Path, required=True)
        elif name == 'generate':
            cmd.add_argument('--p0', type=Path, required=True)
            cmd.add_argument('--split', type=Path, required=True)
            cmd.add_argument('--root', type=Path, required=True)
            cmd.add_argument('--limit', type=int, default=None)
            cmd.add_argument('--token-cap', type=int, default=None)
            cmd.add_argument('--call-cap', type=int, default=None)
        elif name == 'assemble':
            cmd.add_argument('--p0', type=Path, required=True)
            cmd.add_argument('--root', type=Path, required=True)
            cmd.add_argument('--split', type=Path, required=True)
            cmd.add_argument('--variants', type=Path, required=True)
        elif name == 'case-review':
            cmd.add_argument('--p0', type=Path, required=True)
            cmd.add_argument('--cases', type=Path, required=True)
            cmd.add_argument('--root', type=Path, required=True)
            cmd.add_argument('--limit', type=int, default=None)
            cmd.add_argument('--token-cap', type=int, default=None)
            cmd.add_argument('--call-cap', type=int, default=None)
        elif name == 'materialize':
            cmd.add_argument('--cases', type=Path, required=True)
            cmd.add_argument('--reviews', type=Path, required=True)
        elif name == 'coverage':
            cmd.add_argument('--p0', type=Path, required=True)
            cmd.add_argument('--cases', type=Path, required=True)
        elif name == 'run':
            cmd.add_argument('--p0', type=Path, required=True)
            cmd.add_argument('--cases', type=Path, required=True)
            cmd.add_argument('--sample', type=int, default=500)
            cmd.add_argument('--stability-cases', type=int, default=100)
            cmd.add_argument('--max-seconds', type=int, default=240)
            cmd.add_argument('--agent-url', default=None)
            cmd.add_argument('--limit', type=int, default=None)
        elif name == 'diagnose':
            cmd.add_argument('--p0', type=Path, required=True)
            cmd.add_argument('--cases', type=Path, required=True)
            cmd.add_argument('--runs', type=Path, required=True)
            cmd.add_argument('--l1', type=Path, required=True)
        elif name == 'p2-freeze':
            for flag in ('p0', 'cases', 'l1', 'l2', 'reviews', 'coverage', 'variants', 'mothers', 'split'):
                cmd.add_argument(f'--{flag}', type=Path, required=True)
            cmd.add_argument('--diagnosis', type=Path, default=None)
        if name in {'basis', 'mothers', 'split', 'generate', 'assemble', 'case-review', 'materialize',
                    'coverage', 'run', 'diagnose', 'p2-freeze'}:
            cmd.add_argument('--output', type=Path, required=True)
    for name in sorted(BLOCKED):
        sub.add_parser(name, help='本轮未授权/未实现，立即拒绝')
    cmd=sub.add_parser('propose',help='生成本机P3变更包，不应用、不发布')
    cmd.add_argument('--p0',type=Path,required=True);cmd.add_argument('--observation',type=Path,required=True);cmd.add_argument('--output',type=Path,required=True)
    cmd=sub.add_parser('compare',help='比较固定案例与检索配置的A/B L1证据')
    cmd.add_argument('--baseline',type=Path,required=True);cmd.add_argument('--candidate',type=Path,required=True);cmd.add_argument('--output',type=Path,required=True)
    cmd=sub.add_parser('apply',help='经本机Java受控接口应用已复核变更包，不自动发布/激活')
    cmd.add_argument('--changeset',type=Path,required=True);cmd.add_argument('--captcha-uuid',required=True);cmd.add_argument('--captcha-answer',required=True);cmd.add_argument('--output',type=Path,required=True)
    return parser


def _review(args):
    """无 --reviews 时输出机械证据包；带 --reviews 时按复核结论物化 calibration-v2。"""
    if getattr(args, 'reviews', None):
        return apply_reviews(args.p0, args.calibration, args.reviews, args.output)
    packet = build_packet(args.p0, args.calibration)
    out = fresh_directory(args.output)
    write_json(out / 'packet.json', packet)
    write_json(out / 'summary.json', summarize(packet))
    return summarize(packet)


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command in BLOCKED:
        parser.error('SCOPE_BLOCKED：仅授权 P1 收尾（复核/处置/校准/冻结）；P2 正式生成及后续动作禁止')
    try:
        if args.command == 'inventory':
            result = inventory(args.root, args.output, args.observation)
        elif args.command == 'seed':
            result = {'mother_cases': len(seed_cases(args.p0, args.root, args.output, args.count)),
                      'formal_cases': 0}
        elif args.command == 'validate':
            result = validate_package(args.p0, args.calibration)
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result['passed'] else 1
        elif args.command == 'report':
            result = report(args.p0, args.calibration, args.output)
        elif args.command == 'journal':
            result = initialize(args.calibration, args.output)
        elif args.command == 'dispose':
            result = build_p0_v2(args.p0_v1, args.output)
        elif args.command == 'review':
            result = _review(args)
        elif args.command == 'human-review':
            result = build_page(args.p0, args.calibration, args.reviews, args.output)
        elif args.command == 'human-import':
            result = import_decisions(args.queue, args.decisions, args.output)
        elif args.command == 'l1':
            result = run_l1(args.p0, args.calibration, args.output, k=args.k, limit=args.limit)
        elif args.command == 'l2':
            result = regrade(args.p0, args.calibration, args.output) if args.regrade else run_l2(
                args.p0, args.calibration, args.output, limit=args.limit,
                max_seconds=args.max_seconds)
        elif args.command == 'freeze':
            result = freeze(args.p0, args.calibration, args.reviews, args.runs,
                            args.human_ledger, args.output)
        elif args.command == 'basis':
            result = verify_basis(args.p0, args.root, args.output, observation=args.observation,
                                  authorization=_authorization(args))
        elif args.command == 'mothers':
            result = {'mother_cases': len(build_mothers(args.p0, args.root, args.output,
                                                        _authorization(args)))}
        elif args.command == 'split':
            result = partition(args.p0, args.mothers, args.output, _authorization(args))
        elif args.command == 'generate':
            if args.budget_usd is None:
                parser.error('付费命令必须显式给出 --budget-usd（未设预算只做估价，不发起调用）')
            result = generate_variants(args.p0, args.split, args.output, _authorization(args), args.root,
                                       sdk_cap_usd=args.budget_usd, limit=args.limit,
                                       token_cap=args.token_cap, call_cap=args.call_cap)
        elif args.command == 'assemble':
            result = assemble_cases(args.p0, args.root, args.split, args.variants, args.output,
                                    _authorization(args))
        elif args.command == 'case-review':
            if args.budget_usd is None:
                parser.error('付费命令必须显式给出 --budget-usd（未设预算只做估价，不发起调用）')
            result = ai_review(args.p0, args.cases, args.output, args.root, args.budget_usd,
                               limit=args.limit, token_cap=args.token_cap, call_cap=args.call_cap)
        elif args.command == 'materialize':
            result = materialize(args.cases, args.reviews, args.output, _authorization(args))
        elif args.command == 'coverage':
            result = coverage(args.p0, args.cases, args.output, _authorization(args))
        elif args.command == 'run':
            if args.budget_usd is None:
                parser.error('付费命令必须显式给出 --budget-usd（未设预算只做估价，不发起调用）')
            result = run_p2_l2(args.p0, args.cases, args.output,
                               base=args.agent_url or EVAL_AGENT_URL, max_seconds=args.max_seconds,
                               sample_target=args.sample, stability_cases=args.stability_cases,
                               sdk_cap_usd=args.budget_usd, limit=args.limit,
                               authorization=_authorization(args))
        elif args.command == 'diagnose':
            result = diagnose(args.p0, args.cases, args.runs, args.l1, args.output,
                              _authorization(args))
        elif args.command == 'p2-freeze':
            result = freeze_p2(args.p0, args.cases, args.l1, args.l2, args.reviews, args.coverage,
                               args.variants, args.mothers, args.split, args.output,
                               _authorization(args), diagnosis_dir=args.diagnosis)
        elif args.command == 'propose':
            from .p3_changes import propose
            pack=propose(args.p0,args.observation,args.output)
            result={'phase':'P3','changes':len(pack['changes']),'status':pack['status']}
        elif args.command == 'compare':
            from .p3_compare import compare
            result=compare(args.baseline,args.candidate,args.output)
        elif args.command == 'apply':
            from .local import JavaClient
            pack=json.loads(args.changeset.read_text());client=JavaClient().login(args.captcha_answer,args.captcha_uuid)
            result={'validation':client.call('POST','/taglibrary/semantic/changeset/validate',pack),
                    'application':client.call('POST','/taglibrary/semantic/changeset/apply',pack)}
            write_json(fresh_directory(args.output)/'application.json',result)
        else:
            out = fresh_directory(args.output)
            for name, model in CONTRACTS.items():
                write_json(out / (name + '.schema.json'), model.model_json_schema())
            result = {'contracts': list(CONTRACTS)}
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, FileNotFoundError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    raise SystemExit(main())
