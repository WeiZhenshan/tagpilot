"""P3 Demo 固定 100 个客户经理案例；独立真值、预设多轮，不扩量到 P4。"""
import copy
import json
import shutil
from pathlib import Path
from collections import Counter
from .contracts import EvalCase
from .io import read_jsonl,write_jsonl,write_json,file_hash,fresh_directory
from .l2 import _fixture_rows
from .oracle import fixture_result
from .recipe import Recipe


def facts_after(p0, changeset, output):
    """保留 P0 原件。新事实版本逐条指向来源与变更包，不反推 Agent 输出。"""
    p0,output=Path(p0),Path(output);fresh_directory(output)
    pack=json.loads(Path(changeset).read_text());facts=read_jsonl(p0/'facts.jsonl')
    updates={c['after']['tag_id']:c['after'] for c in pack['changes'] if c['table']=='ts_tag_semantic'}
    concepts={c['after']['concept_id']:c['after'] for c in pack['changes'] if c['table']=='ts_concept'}
    for fact in facts:
        if fact['tag_id'] not in updates:continue
        after=updates[fact['tag_id']];fact['published_semantics'].update({k:after[k] for k in fact['published_semantics'] if k in after})
        if after['concept_id'] in concepts:fact['published_semantics']['concept_name']=concepts[after['concept_id']]['concept_name']
        fact['fact_status']='DEMO_CONVENTION' if after['caliber_struct']['statistic']=='SUM' else 'VERIFIED_SOURCE'
        fact['p3_resolution']={'changeset_sha256':file_hash(changeset),'source_ref':after['source_ref'],
             'official_bank_verified':False,'basis':'来源的金额/张数/最低等字段含义；累计金额仅为模拟数据约定'}
    write_jsonl(output/'facts.jsonl',facts)
    manifest=json.loads((p0/'manifest.json').read_text())
    # 派生事实包携带 manifest 已声明的冻结来源；不改来源字节与旧 manifest。
    for source in manifest.get('sources',{}).values():
        frozen=source.get('frozen_copy')
        if frozen:
            relative=Path(frozen)
            if relative.parts!=('sources',relative.name):
                raise ValueError('冻结来源路径非法')
            (output/relative).parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(p0/relative,output/relative)
    manifest.update(schema_version='p3-facts.v1',phase='P3',supersedes=str(p0),
         files={'facts.jsonl':file_hash(output/'facts.jsonl')},changeset_sha256=file_hash(changeset))
    write_json(output/'manifest.json',manifest)
    return facts


def build_demo(p0,output):
    p0,output=Path(p0),Path(output)
    facts={f['tag_id']:f for f in read_jsonl(p0/'facts.jsonl')}
    rows=_fixture_rows(json.loads((p0/'manifest.json').read_text()))
    r=Recipe(facts,rows,file_hash(p0/'manifest.json'),first_index=8001)
    styles=['标准','口语','省略','模糊澄清','指代追加']
    scenario_counts=[('大额入金转化',15),('定期到期承接',15),('代发客户流失预警',14),('沉睡客户激活',14),
                     ('基金客户配置优化',14),('营销活动复盘',14),('渠道迁移',14)]
    for scenario,count in scenario_counts:
        for i in range(count):
            style=styles[i%5];threshold=[10,20,30,50,80][i%5]+(i//5)*5
            p=r.pred;g=r.group
            if scenario=='大额入金转化':
                amount=[20,30,50,60,80][i%5]+(i//5)*10
                tree=g(p(1291,'>=',[str(amount*10000)]),p(601,'=',['0']),p(1466,'in',['C3','C4','C5']))
                text=f'帮我找近30天异名跨行累计转入至少{amount}万，现在没持有理财，理财风评C3到C5的客户。'
                collo=f'最近30天别人从别的银行转进来，合起来有{amount}万或更多，还没买理财、理财风评是C3、C4或C5的，帮我圈一下。'
                brief=f'近30天异名跨行累计入金≥{amount}万；当前理财未持有；理财风评C3/C4/C5。圈客户。'
                fuzzy='帮我找入金比较多、还没理财的客户，看看能不能转化。'
            elif scenario=='定期到期承接':
                end=['2026-09-25','2026-09-30','2026-10-10','2026-10-18','2026-10-31'][i%5]
                tree=g(p(858,'between',['2026-09-19',end]),p(859,'>=',[str(threshold*10000)]),p(601,'=',['0']))
                text=f'最近一笔定期在2026年9月19日到{end}到期，两个日期都算，到期金额至少{threshold}万，当前没理财的圈出来。'
                collo=f'盯一下下一笔定期，9月19号到{end}到期的，两头都含，金额不低于{threshold}万，而且现在没有理财。'
                brief=f'最近一笔定期到期日[2026-09-19,{end}]；到期金额≥{threshold}万；当前未持理财。'
                fuzzy='最近定期快到期、金额比较大的客户，找一批承接。'
            elif scenario=='代发客户流失预警':
                upper=[0,1000,3000,5000,8000][i%5]
                tree=g(p(1043,'>=',[str(threshold*1000)]),p(1033,'<=',[str(upper)]))
                text=f'上月代发至少{threshold*1000}元、本月代发不超过{upper}元的客户，列入本次代发流失预警观察名单。'
                collo=f'上个月工资是咱们这代发的，至少{threshold*1000}块，这个月最多{upper}块，帮我看看这批人。'
                brief=f'上月代发≥{threshold*1000}元，本月代发≤{upper}元。圈出预警观察客群。'
                fuzzy='工资代发掉得比较厉害的客户，找出来跟进一下。'
            elif scenario=='沉睡客户激活':
                days=[0,1,2,3,4][i%5]
                tree=g(p(721,'>=',[str(threshold*10000)]),p(1448,'<=',[str(days)]))
                text=f'这轮沉睡激活仅按APP低活跃定义：当前时点AUM至少{threshold}万，近30天APP登录不超过{days}天。'
                collo=f'账上还有{threshold}万或更多、最近30天APP最多登录{days}天的找我一下，这次只看APP低活跃。'
                brief=f'本次低活跃激活：当前时点AUM≥{threshold}万，近30天APP登录≤{days}天。'
                fuzzy='找点还有资产但很久没用APP的客户，做低活跃激活。'
            elif scenario=='基金客户配置优化':
                level=[['C3','C4','C5'],['C2','C3'],['C4','C5'],['C3'],['C2','C3','C4','C5']][i%5]
                tree=g(p(620,'=',['0']),p(1477,'in',level),p(721,'>=',[str(threshold*10000)]))
                text=f'当前没有基金、基金风评属于{"、".join(level)}、当前时点AUM至少{threshold}万的客户，找基金配置空白名单。'
                collo=f'现在还没持有基金的，基金风评是{"或".join(level)}，总资产当前时点有{threshold}万或更多，圈出来。'
                brief=f'当前基金未持有；基金风评{"/".join(level)}；当前时点AUM≥{threshold}万。'
                fuzzy='找一批资产还可以、基金配置有空白的客户。'
            elif scenario=='营销活动复盘':
                n=[1,2,3,4,5][i%5]
                tree=g(p(1319,'>=',[str(n)]),p(721,'>=',[str(threshold*10000)]))
                text=f'复盘本月载体活动：参与次数至少{n}次，且当前时点AUM至少{threshold}万元的客户圈出来，只看这两个字段。'
                collo=f'这个月载体活动参加了{n}次或更多的，现在时点资产也有{threshold}万以上（含{threshold}万），找给我看看。'
                brief=f'本月载体活动参与≥{n}次 AND 当前时点AUM≥{threshold}万。用于客群复盘。'
                fuzzy='本月载体活动参与比较积极、资产也比较多的客户，帮我做客群复盘。'
            else:
                days=[0,1,2,3,4][i%5]
                tree=g(p(656,'=',['1']),p(1448,'<=',[str(days)]),p(721,'>=',[str(threshold*10000)]))
                text=f'当前已开通手机银行，近30天APP登录最多{days}天，当前时点AUM至少{threshold}万的客户，作为线上渠道激活名单。'
                collo=f'手机银行已经开了，但最近30天APP最多登过{days}天，当前时点资产不低于{threshold}万，这些人圈一下。'
                brief=f'手机银行已开通；近30天APP登录≤{days}天；当前时点AUM≥{threshold}万。渠道激活。'
                fuzzy='手机银行开了又不怎么用、资产还不错的客户，找出来引导线上使用。'
            turns=[];category='COMPOSITION';expected=r.ready(tree)
            requirement={'标准':text,'口语':collo,'省略':brief,'模糊澄清':fuzzy+['这周准备跟进。','做一份本次观察名单。','准备筛选目标客群。'][i//5],'指代追加':text}[style]
            if style=='模糊澄清':
                category='MULTITURN';expected=r.clarify(['threshold'])
                turns=[{'user_message':'这次口径具体是：'+text,'answer_slots':{'threshold':'用户明确补齐全部时间与阈值'},'expected':r.ready(tree)}]
            elif style=='指代追加':
                category='MULTITURN'
                extra=p(568,'=',['1']) if i<10 else p(662,'=',['0'])
                turn='就在刚才这批里，再加上当前手机号正常这个条件，其他条件都保留。' if i<10 else '那批人还要当前营销黑名单为否，刚才的条件都保留。'
                turns=[{'user_message':turn,'answer_slots':{},'expected':r.ready(g(*tree['children'],extra))}]
            # 第二/第三组不是只换问法：加入明确的产品/可达条件，改变标准树。
            if i>=5 and style not in ('指代追加','模糊澄清'):
                extra=p(568,'=',['1']) if i<10 else p(662,'=',['0'])
                requirement+=' 另外，'+('当前手机号必须正常。' if i<10 else '当前营销黑名单必须为否。')
                expected=r.ready(g(*tree['children'],extra))
            if scenario=='沉睡客户激活' and style=='口语':
                # “账上还有”不能独立确定是存款还是总资产；预先给定真实用户澄清，
                # 保持目标树与完整 ID oracle 不变，不把模糊词硬写成 AUM 等价别名。
                final=copy.deepcopy(expected);expected=r.clarify(['business_scope']);category='MULTITURN'
                clarified=text+(' 当前手机号必须正常。' if i>=5 and i<10 else ' 当前营销黑名单必须为否。' if i>=10 else '')
                turns=[{'user_message':'我说的账上资产是当前时点AUM，不是仅存款余额。这次条件明确为：'+clarified,
                    'answer_slots':{'business_scope':'当前时点AUM，不是仅存款余额'},'expected':final}]
            c=r.add(category,scenario,requirement,expected,turns=turns,
                basis=['冻结来源事实；用户明确条件；累计入金为Demo约定；不使用Agent答案构造真值'])
            c.update(phase='P3',split='DEV');c['variant_mode']='TEMPLATE'
            c['truth_basis'].append('表达方式：'+style+'；AI编写并逐条结构核对，未经银行签署')
            EvalCase.model_validate(c)
    assert len(r.cases)==100 and len({c['requirement'] for c in r.cases})==100
    fresh_directory(output);write_jsonl(output/'cases.jsonl',r.cases)
    write_jsonl(output/'inputs.jsonl',[{k:c[k] for k in ['case_id','requirement','reference_date','timezone']} for c in r.cases])
    results=[]
    for c in r.cases:
        final=(c['turns'] or [{'expected':c['expected']}])[-1]['expected']
        result=fixture_result(final['tree'],rows)
        results.append({'case_id':c['case_id'],**result})
    write_jsonl(output/'oracle-results.jsonl',results)
    write_json(output/'manifest.json',{'schema_version':'p3-demo.v1','phase':'P3','cases':100,'scope':'独立Demo开发验证，不扩充P2/P4',
        'status':'AI_AUTHORED_AND_REVIEWED','scenarios':dict(Counter(c['scenario'] for c in r.cases)),
        'reference_date':'2026-09-18','language_styles':styles,'source_manifest_sha256':file_hash(p0/'manifest.json'),
        'multiturn_cases':sum(bool(c['turns']) for c in r.cases),
        'all_have_fixture_oracle':True,'oracle_nonempty':sum(r['count']>0 for r in results),
        'files':{p.name:file_hash(p) for p in output.iterdir() if p.is_file()}})
    return r.cases
