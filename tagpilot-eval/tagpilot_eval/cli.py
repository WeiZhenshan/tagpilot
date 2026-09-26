"""只提供本轮授权范围；P2/P3命令在产生任何输出或网络调用前拒绝。"""
import argparse
import json
from pathlib import Path
from .contracts import CONTRACTS
from .inventory import inventory
from .io import fresh_directory, write_json
from .seeds import seed_cases
from .validation import validate_package
from .report import report
from .journal import initialize


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ['inventory','seed','validate','report','schemas','journal']:
        cmd=sub.add_parser(name)
        if name in {'inventory','seed'}:cmd.add_argument('--root',type=Path,required=True)
        if name in {'seed','validate','report'}:cmd.add_argument('--p0',type=Path,required=True)
        if name in {'validate','report','journal'}:cmd.add_argument('--calibration',type=Path,required=True)
        if name!='validate':cmd.add_argument('--output',type=Path,required=True)
        if name=='inventory':cmd.add_argument('--observation',type=Path,required=True)
        if name=='seed':cmd.add_argument('--count',type=int,default=200)
    for name in ['generate','split','run','diagnose','propose','compare','apply']:
        sub.add_parser(name,help='本轮未授权/未实现，立即拒绝')
    args=parser.parse_args(argv)
    if args.command in {'generate','split','run','diagnose','propose','compare','apply'}:
        parser.error('SCOPE_BLOCKED：仅授权P0与P1骨架和200个母案例；P2正式生成及后续动作禁止')
    try:
        if args.command=='inventory':result=inventory(args.root,args.output,args.observation)
        elif args.command=='seed':result={'mother_cases':len(seed_cases(args.p0,args.root,args.output,args.count)),'formal_cases':0}
        elif args.command=='validate':
            result=validate_package(args.p0,args.calibration)
            print(json.dumps(result,ensure_ascii=False));return 0 if result['passed'] else 1
        elif args.command=='report':result=report(args.p0,args.calibration,args.output)
        elif args.command=='journal':result=initialize(args.calibration,args.output)
        else:
            out=fresh_directory(args.output)
            for name,model in CONTRACTS.items():write_json(out/(name+'.schema.json'),model.model_json_schema())
            result={'contracts':list(CONTRACTS)}
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except (ValueError,FileNotFoundError) as exc:
        parser.error(str(exc))


if __name__=='__main__':
    raise SystemExit(main())
