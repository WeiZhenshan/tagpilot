#!/usr/bin/env python3
"""把 skills/ 下的技能包源码编译为 ts_agent_skill 种子 SQL（幂等，可重复执行）。

用法：
    python3 bin/build-agent-skill-seed.py            # 生成 sql/seed/agent-meta-skills.sql
    python3 bin/build-agent-skill-seed.py --check    # 只校验技能包，不写文件

字段规则与 TsAgentSkillService.validate 保持一致；运行前请先阅读 skills/README.md。
"""
import json
import re
import sys
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
SHARED_DIR = SKILLS_DIR / "shared"
OUTPUT = ROOT / "sql" / "seed" / "agent-meta-skills.sql"

RESERVED = {'synced','clear','compact','init','login','logout','config','settings','help','cost','context','exit','quit','model','permissions','add-dir','resume','rewind','mcp','plugin','plugins','agents','skills','memory','status','theme','doctor','feedback','bug','terminal-setup','hooks','output-style','plan'}
CATEGORIES = {'fact', 'diagnosis', 'decision', 'chart', 'general'}
RUNTIME_FIELDS = ('name', 'description', 'argument_hint', 'user_invocable', 'disable_model_invocation', 'allowed_tools')
PLATFORM_FIELDS = ('display_name', 'category', 'version')
MAX_INSTRUCTIONS = 60000
MAX_RESOURCE_CONTENT = 60000
MAX_RESOURCES_TOTAL = 200000
MAX_RESOURCES = 30
PREPROCESS = re.compile(r'!`[^`]+`')
UNSAFE_XML = re.compile(r'<[^>]+>')


class PackError(Exception):
    pass


def parse_skill_md(path):
    text = path.read_text(encoding='utf-8')
    if not text.startswith('---\n'):
        raise PackError(f'{path}: 缺少 frontmatter')
    end = text.index('\n---\n', 3)
    fields = {}
    for line in text[4:end].split('\n'):
        if not line.strip():
            continue
        key, _, raw = line.partition(': ')
        fields[key.strip().replace('-', '_')] = json.loads(raw)
    body = text[end + 5:].strip('\n')
    return fields, body


def load_pack(directory, shared=False):
    fields, instructions = parse_skill_md(directory / 'SKILL.md')
    for key in RUNTIME_FIELDS + PLATFORM_FIELDS:
        if key not in fields:
            raise PackError(f'{directory}: frontmatter 缺少 {key}')
    pack = {
        'name': fields['name'],
        'display_name': fields['display_name'],
        'description': fields['description'],
        'instructions': instructions,
        'argument_hint': fields['argument_hint'],
        'version': fields['version'],
        'category': fields['category'],
        'user_invocable': fields['user_invocable'],
        'disable_model_invocation': fields['disable_model_invocation'],
        'allowed_tools': fields['allowed_tools'],
    }
    resources = []
    for sub in ('references', 'scripts', 'assets'):
        base = directory / sub
        if not base.is_dir():
            continue
        for file in sorted(base.rglob('*')):
            if file.is_file():
                resources.append({'path': file.relative_to(directory).as_posix(),
                                  'content': file.read_text(encoding='utf-8')})
    # shared/ 下的文件分发给分析技能包（运行时技能各自独立物化，不能跨包读文件）。
    if shared and SHARED_DIR.is_dir():
        known = {r['path'] for r in resources}
        for file in sorted(SHARED_DIR.rglob('*')):
            if file.is_file():
                path = f'references/{file.name}'
                if path not in known:
                    resources.append({'path': path, 'content': file.read_text(encoding='utf-8')})
    pack['resources'] = resources
    return pack


def validate_pack(pack, where):
    name = pack['name']
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name) or len(name) > 64:
        raise PackError(f'{where}: 技能名称非法 {name!r}')
    if name in RESERVED or 'anthropic' in name or 'claude' in name:
        raise PackError(f'{where}: 技能名称与平台保留名冲突 {name!r}')
    if not pack['display_name'] or len(pack['display_name']) > 100:
        raise PackError(f'{where}: display-name 缺失或过长')
    if not pack['description'] or len(pack['description']) > 1024:
        raise PackError(f'{where}: description 缺失或过长')
    if UNSAFE_XML.search(pack['description']):
        raise PackError(f'{where}: description 不能包含 XML 标签')
    if len(pack['argument_hint']) > 200:
        raise PackError(f'{where}: argument-hint 过长')
    if not pack['instructions'] or len(pack['instructions']) > MAX_INSTRUCTIONS:
        raise PackError(f'{where}: 指令缺失或超过 {MAX_INSTRUCTIONS} 字')
    if not re.fullmatch(r'\d+\.\d+\.\d+', pack['version']):
        raise PackError(f'{where}: 版本号须为三段数字')
    if pack['category'] not in CATEGORIES:
        raise PackError(f'{where}: 分类非法 {pack["category"]!r}')
    tools = pack['allowed_tools']
    if not isinstance(tools, list) or not tools or not set(tools) <= {'Read', 'Skill'} or len(set(tools)) != len(tools):
        raise PackError(f'{where}: allowed-tools 只允许 Read/Skill')
    if not pack['user_invocable'] and pack['disable_model_invocation']:
        raise PackError(f'{where}: 至少开启一种技能调用方式')
    if PREPROCESS.search(pack['instructions']) or PREPROCESS.search(pack['description']) or PREPROCESS.search(pack['argument_hint']):
        raise PackError(f'{where}: 不支持命令预处理')
    paths = set()
    size = 0
    for resource in pack['resources']:
        path, content = resource['path'], resource['content']
        if not re.fullmatch(r'(references|scripts|assets)/[A-Za-z0-9_./-]+', path) or '..' in path or '//' in path or path.endswith('/') or path in paths:
            raise PackError(f'{where}: 资源路径非法 {path!r}')
        if not content or len(content) > MAX_RESOURCE_CONTENT:
            raise PackError(f'{where}: 资源 {path} 为空或超过 {MAX_RESOURCE_CONTENT} 字')
        paths.add(path)
        size += len(content)
    if len(paths) > MAX_RESOURCES:
        raise PackError(f'{where}: 资源超过 {MAX_RESOURCES} 项')
    if size > MAX_RESOURCES_TOTAL:
        raise PackError(f'{where}: 资源总量超过 {MAX_RESOURCES_TOTAL} 字')


def runtime_frontmatter(pack):
    lines = []
    for key in RUNTIME_FIELDS:
        lines.append(f'{key.replace("_", "-")}: {json.dumps(pack[key], ensure_ascii=False)}')
    return '---\n' + '\n'.join(lines) + '\n---\n\n' + pack['instructions'] + '\n'


def to_skill_md(pack):
    return runtime_frontmatter(pack)


def pack_hash(pack):
    return hashlib.sha256(json.dumps(pack, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def sql_literal(value):
    return "'" + value.replace('\\', '\\\\').replace("'", "''") + "'"


def build_sql(packs):
    header = ('-- 洞察元 Skill 种子：由 bin/build-agent-skill-seed.py 生成，请勿手改。\n'
              '-- 重新生成后重复执行本文件会把技能刷新为源码当前内容（幂等）。\n'
              '-- 前置：已应用 sql/migration/V20260930_01__agent_skill_registry.sql。\n'
              '-- 执行（必须显式 utf8mb4，否则中文会被双重编码）：\n'
              '--   mysql --default-character-set=utf8mb4 -u<user> -p <库名> < sql/seed/agent-meta-skills.sql\n')
    statements = []
    for pack in packs:
        payload = dict(pack)
        payload['skill_md'] = to_skill_md(pack)
        encoded = json.dumps(payload, ensure_ascii=False)
        statements.append(
            'INSERT INTO ts_agent_skill (name, draft_json, published_json, row_version, create_by, update_by, create_time, update_time, publish_time)\n'
            f"VALUES ({sql_literal(pack['name'])}, {sql_literal(encoded)}, {sql_literal(encoded)}, 1, 'seed', 'seed', NOW(), NOW(), NOW())\n"
            "ON DUPLICATE KEY UPDATE draft_json=VALUES(draft_json), published_json=VALUES(published_json),\n"
            "  row_version=row_version+1, update_by='seed', update_time=NOW(), publish_time=NOW();")
    return header + '\n' + '\n\n'.join(statements) + '\n'


def collect():
    packs = []
    for group in ('analysis', 'charts'):
        base = SKILLS_DIR / group
        if not base.is_dir():
            continue
        for directory in sorted(d for d in base.iterdir() if d.is_dir()):
            pack = load_pack(directory, shared=group == 'analysis')
            validate_pack(pack, str(directory.relative_to(ROOT)))
            packs.append(pack)
    names = [pack['name'] for pack in packs]
    if len(set(names)) != len(names):
        raise PackError('技能名称重复')
    if not packs:
        raise PackError('skills/ 下没有找到技能包')
    return packs


def main():
    check = '--check' in sys.argv
    packs = collect()
    for pack in packs:
        print(f"✓ {pack['name']:<22} {pack['display_name']:<14} v{pack['version']} "
              f"{pack['category']:<10} 资源 {len(pack['resources'])} 项 / 指令 {len(pack['instructions'])} 字 "
              f"pack_hash {pack_hash(pack)[:12]}")
    if check:
        print(f'共 {len(packs)} 个技能包校验通过（未写文件）')
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build_sql(packs), encoding='utf-8')
    print(f'已写入 {OUTPUT.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
