"""200 个受控母案例配方：每个只有一个首轮原话，不执行付费生成或P2扩写。"""
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
import json

from .contracts import EvalCase
from .io import digest, file_hash, fresh_directory, read_jsonl, write_json, write_jsonl
from .oracle import references, fixture_result
from .sources import load_ddl, load_fixture

QUOTAS={'SINGLE':60,'COMPOSITION':50,'CLARIFICATION':30,'BOUNDARY':20,'MULTITURN':20,'GAP':20}


def seed_cases(p0, root, output, count=200):
    if count!=200:
        raise ValueError('本轮授权仅为 P1 的200个母案例；P2正式生成禁止执行')
    p0,root,output=Path(p0),Path(root),Path(output)
    facts={r['tag_id']:r for r in read_jsonl(p0/'facts.jsonl')}
    manifest=json.loads((p0/'manifest.json').read_text())
    for name,sha in manifest['files'].items():
        if file_hash(p0/name)!=sha: raise ValueError('P0 工件被修改')
    ddl_path=root/manifest['sources']['ddl']['path']
    fixture_path=root/manifest['sources']['fixture']['path']
    for key,path in [('ddl',ddl_path),('fixture',fixture_path)]:
        if file_hash(path)!=manifest['sources'][key]['sha256']:raise ValueError('源数据已变化，必须重新执行P0')
    rows=load_fixture(fixture_path,load_ddl(ddl_path))
    eligible=sorted(facts)
    cases=[]
    source_hash=file_hash(p0/'manifest.json')

    def expr(tid):
        f=facts[tid]
        return {'kind':'TAG','tag_id':tid,'field_name':f['field_name'],'unit':f['published_semantics']['unit']}

    def pred(tid,op,values):
        f=facts[tid]
        typ='STRING' if f['codes'] or f['tag_type']=='文本型' else 'DATE' if f['tag_type']=='日期型' else 'NUMBER'
        return {'kind':'PREDICATE','expression':expr(tid),'operator':op,'values':[str(v) for v in values],
                'data_kind':typ,'caliber':{k:v for k,v in f['published_semantics']['caliber_struct'].items() if v is not None}}

    def group(*children,logic='AND'):
        return {'kind':'GROUP','logic':logic,'children':list(children)}

    def ready(tree):return {'outcomes':['READY'],'tree':tree}

    def add(category,scenario,query,expected,targets=None,turns=None,forbidden=None,excluded=None,basis=None):
        i=len(cases)+1
        refs=references(expected.get('tree'))
        for t in turns or []:refs|=references(t['expected'].get('tree'))
        targets=sorted(set(targets or [])|refs)
        unresolved=[f'TAG:{tid}' for tid in targets if facts[tid]['fact_status']=='UNRESOLVED']
        if 'READY' in expected['outcomes'] and unresolved:
            raise ValueError('未解决事实不得生成 READY 金标')
        end=(turns or [{'expected':expected}])[-1]['expected']
        capability='FIXTURE_ORACLE_AVAILABLE' if end['outcomes']==['READY'] else 'NOT_APPLICABLE'
        domains=sorted({facts[tid]['domain'] for tid in targets}) or ['能力边界']
        # 去掉数字/词面形成谱系键；不把仅换金额的题算成独立谱系。
        def lineage(value):
            if isinstance(value,dict):return {k:lineage(v) for k,v in value.items() if k not in {'values','value','user_message','answer_slots','caliber'}}
            if isinstance(value,list):return [lineage(v) for v in value]
            return value
        signature={'expected':lineage(expected),'turns':lineage(turns or []),'targets':targets}
        case={'case_id':f'CAL-{i:03d}','mother_id':f'M-{i:03d}',
              'lineage_group':'LIN-'+digest(signature)[:16],'category':category,
              'persona':{'风险管理':'贷后客户经理','业务往来':'网点综合客户经理','渠道管理':'存量客户维护人员'}.get(domains[0],'理财客户经理'),
              'scenario':scenario,'domains':domains,'requirement':query,'fact_ids':[f'TAG:{t}' for t in targets],
              'target_tag_ids':targets,'forbidden_tag_ids':forbidden or [],
              'eligible_tag_ids':[t for t in eligible if t not in (excluded or [])],
              'source_manifest_sha256':source_hash,'expected':expected,'turns':turns or [],
              'truth_basis':basis or ['P0来源事实与已发布字段契约；阈值为本题用户显式条件，不是通用业务默认值'],
              'unresolved_fact_ids':unresolved,'l3_status':capability}
        cases.append(EvalCase.model_validate(case).model_dump(exclude_none=True))

    def good(f):
        return f['fact_status']=='VERIFIED_SOURCE' and str(f['published_semantics']['unit_scale']) in {'1','1.0','1.0000'}

    # 按类型和业务域轮转，避免只挑数值字段或资产领域。
    singles=[]
    for typ,quota in [('数值型',18),('布尔型',12),('选项型',12),('日期型',10),('文本型',8)]:
        buckets=defaultdict(list)
        for tid,f in sorted(facts.items()):
            if not good(f) or f['tag_type']!=typ:continue
            if typ=='日期型' and f['physical_type']!='DATE':continue
            if typ in {'布尔型','选项型'} and not f['codes']:continue
            if typ=='文本型' and 'contains' not in f['published_semantics']['allowed_operators']:continue
            buckets[f['domain']].append(tid)
        selected=[]
        while len(selected)<quota:
            progressed=False
            for domain in sorted(buckets):
                if buckets[domain] and len(selected)<quota:
                    selected.append(buckets[domain].pop(0));progressed=True
            if not progressed:raise ValueError('所需类型不足')
        for tid in selected:
            f=facts[tid];name=f['name'];unit=f['published_semantics']['unit']
            if typ=='数值型':
                value={'CNY':'100000','RATIO':'0.5','POINT':'50'}.get(unit,'3')
                op='>=';label={'CNY':'10万元','RATIO':'50%','DAY':'3天','MONTH':'3个月','PERSON':'3个','COUNT':'3','POINT':'50分','SHARE':'3份'}.get(unit,value)
                query=f'帮我找{name}至少{label}的客户。'
            elif typ in {'布尔型','选项型'}:
                code=next((c for c in f['codes'] if c['code']=='1'),f['codes'][0]);value=code['code'];op='='
                query=f'筛选{name}为“{code["definition"]}”的客户。'
            elif typ=='日期型':
                value='2026-09-01';op='>';query=f'{name}晚于2026年9月1日的客户有哪些？当天不包含。'
            else:
                value=next(r[f['field_name']] for r in rows if r[f['field_name']] is not None)
                value=value[:30];op='contains';query=f'请找{name}文本中包含“{value}”的客户，按文字包含匹配。'
            add('SINGLE',f'{f["domain"]}单字段理解',query,ready(pred(tid,op,[value])))
            singles.append(tid)

    # 30个组合：产品空白、风险适配、排除条件、渠道可达，全部显式条件。
    products=[601,620,580,607,609,613,587,638,645,618,621,630]
    for tid in products:
        name=facts[tid]['name']
        add('COMPOSITION','资产与产品空白',f'当前时点AUM至少20万元，并且{name}为否的客户圈出来。',
            ready(group(pred(721,'>=',['200000']),pred(tid,'=',['0']))))
    for tid,risk in [(601,1466),(620,1477),(618,1480),(621,1480),(630,1480),(587,1480)]:
        add('COMPOSITION','持有状态与指定风评',f'{facts[tid]["name"]}为否，并且{facts[risk]["name"]}属于C3、C4、C5的客户。',
            ready(group(pred(tid,'=',['0']),pred(risk,'in',['C3','C4','C5']))))
    direct=[
        ('历史理财当前空白','历史上持有过理财、现在没有持有理财的客户。',group(pred(579,'=',['1']),pred(601,'=',['0']))),
        ('理财或基金持有','当前持有理财或者当前持有基金，满足一项就保留。',group(pred(601,'=',['1']),pred(620,'=',['1']),logic='OR')),
        ('价值与产品任选','当前时点AUM不少于100万元，并且当前持有理财或基金至少一种。',group(pred(721,'>=',['1000000']),group(pred(601,'=',['1']),pred(620,'=',['1']),logic='OR'))),
        ('双产品空白','当前既没有理财也没有基金；两项都要明确为否，不把未知当成否。',group(pred(601,'=',['0']),pred(620,'=',['0']))),
        ('指定营销排除','当前时点AUM至少50万元，排除营销黑名单和勿扰客户；这两项须明确为否。',group(pred(721,'>=',['500000']),pred(662,'=',['0']),pred(536,'=',['0']))),
        ('渠道任一可达','手机号正常或已企微认证的客户，任一明确满足即可。',group(pred(568,'=',['1']),pred(691,'=',['1']),logic='OR')),
        ('价值与渠道','当前时点AUM至少20万元，且手机号正常或者已企微认证。AUM条件对两种渠道都生效。',group(pred(721,'>=',['200000']),group(pred(568,'=',['1']),pred(691,'=',['1']),logic='OR'))),
        ('登录区间','近30天APP登录至少3天、但不超过10天的客户。',group(pred(1448,'>=',['3']),pred(1448,'<=',['10']))),
        ('到期且金额','以2026年9月18日为基准，最近一笔定期到期日在9月19日至10月18日之间（两端含），到期金额至少10万元。',group(pred(858,'between',['2026-09-19','2026-10-18']),pred(859,'>=',['100000']))),
        ('代发前后','上月代发金额大于0，本月代发金额不大于0的客户。',group(pred(1043,'>',['0']),pred(1033,'<=',['0']))),
        ('两项风险任选','当前反洗钱黑名单标志为是，或者当前营销黑名单标志为是；这是排查名单。',group(pred(661,'=',['1']),pred(662,'=',['1']),logic='OR')),
        ('未持有且低余额','当前未持有信用卡，且当前时点AUM不足5万元。',group(pred(580,'=',['0']),pred(721,'<',['50000']))),
    ]
    for scenario,query,tree in direct:add('COMPOSITION',scenario,query,ready(tree))
    for tid in products[:10]:
        add('COMPOSITION','资产门槛与产品及指定风评',
            f'当前时点AUM至少50万元、{facts[tid]["name"]}为否，并且当前理财风评为C3或C4。三项同时满足；这里只按我给的条件筛选。',
            ready(group(pred(721,'>=',['500000']),pred(tid,'=',['0']),pred(1466,'in',['C3','C4']))))
    # 7个显式比例，3个显式产品类数；定义由用户提供，非平台默许规则。
    balances=[813,918,867,860,1006,994,804]
    for tid in balances:
        tree={'kind':'PREDICATE','expression':{'kind':'DIV','args':[expr(tid),expr(721)],'unit':'RATIO'},
              'operator':'>=','values':['0.2'],'data_kind':'NUMBER','caliber':{'time_alignment':'EXPLICIT_PERIODS','scope':'CURRENT'}}
        add('COMPOSITION','显式产品占比',f'当前时点AUM大于0，并且{facts[tid]["name"]}除以当前时点AUM达到20%及以上；任一数据缺失就排除。',ready(group(pred(721,'>',['0']),tree)))
    for op,value,word in [('=','1','恰好1类'),('>=','4','至少4类'),('<=','2','不超过2类')]:
        tree={'kind':'PREDICATE','expression':{'kind':'COUNT_POSITIVE','args':[expr(t) for t in balances],'unit':'COUNT'},
              'operator':op,'values':[value],'data_kind':'NUMBER','caliber':{'definition':'count strictly positive balances','null_policy':'EXCLUDE'}}
        add('COMPOSITION','显式产品类数',f'当前存款、理财、基金、黄金、国债、信托、价值型保险这七类余额里，余额大于零的有{word}。七项有缺失就排除。',ready(tree))

    # 10个缺阈值、20个缺时间口径。
    for tid in [721,735,813,918,867,860,1006,994,804,1448]:
        add('CLARIFICATION','未定义比较阈值',f'帮我找{facts[tid]["name"]}比较高的客户，具体门槛还没定。',
            {'outcomes':['NEEDS_USER_INPUT'],'required_slots':['threshold']},[tid])
    paired=defaultdict(list)
    for tid,f in facts.items():
        if good(f) and f['tag_type'] in {'数值型','布尔型'}:
            paired[f['published_semantics']['concept_id']].append(tid)
    ambiguous=[]
    for tids in paired.values():
        if len(tids)<2:continue
        name=facts[tids[0]]['published_semantics']['concept_name']
        if any(w in name for w in ['当前','上月','本月','上年','本年','历史','最高']):continue
        if len({facts[t]['published_semantics']['caliber_struct'].get('time_anchor_label') for t in tids})<2:continue
        ambiguous.append(tids)
    for tids in ambiguous[:20]:
        name=facts[tids[0]]['published_semantics']['concept_name']
        suffix='为是' if facts[tids[0]]['tag_type']=='布尔型' else '超过1000元'
        add('CLARIFICATION','未说明时间口径',f'帮我找{name}{suffix}的客户，时间口径还没决定。',
            {'outcomes':['NEEDS_USER_INPUT'],'required_slots':['time_scope']},tids)

    # 边界题使用新的字段、区间或操作符，避免仅换阈值充数。
    boundaries=[
        ('严格上界','当前时点AUM超过50万元，刚好50万元不算。',pred(721,'>',['500000']),[735]),
        ('本行范围','当前时点本行AUM至少50万元，按带“本行”口径的那个指标筛选。',pred(735,'>=',['500000']),[721]),
        ('半开区间','当前时点AUM在20万元至100万元之间，含20万，不含100万。',group(pred(721,'>=',['200000']),pred(721,'<',['1000000'])),[]),
        ('历史最高','历史最高时点AUM至少100万元。',pred(727,'>=',['1000000']),[721]),
        ('近7天标志','近7天异名跨行转入标志为是。',pred(708,'=',['1']),[709]),
        ('近30天标志','近30天异名跨行转入标志为是，不要改成近7天。',pred(709,'=',['1']),[708]),
        ('自然月消费','上月借记卡消费金额超过1000元，用上个自然月的指标。',pred(1175,'>',['1000']),[]),
        ('当前未持有','当前没有持有理财，未知状态不算没有持有。',pred(601,'=',['0']),[579]),
        ('历史与当前同时满足','历史持有理财且当前仍持有理财，两个时态都要满足。',group(pred(579,'=',['1']),pred(601,'=',['1'])),[]),
        ('理财风评','当前理财风评为C3、C4或C5。',pred(1466,'in',['C3','C4','C5']),[1477]),
        ('基金风评','当前基金风评为C1或C2。',pred(1477,'in',['C1','C2']),[1466]),
        ('否定码值','当前理财风评不是C1或C2，缺失风评排除。',pred(1466,'not_in',['C1','C2']),[]),
        ('前导零码值','行外资产（万元KYC）按现有码表第03档筛选，不进行金额近似。',pred(534,'=',['03']),[]),
        ('明确枚举集合','性别是男或女的客户，未知值排除。',pred(526,'in',['M','F']),[]),
        ('日期不含当天','最新征信报告更新日期早于2026年3月22日，当天不算。',pred(1484,'<',['2026-03-22']),[]),
        ('到期闭区间','最近一笔定期到期日在2026年9月19日至9月25日之间，两个日期都包含。',pred(858,'between',['2026-09-19','2026-09-25']),[]),
        ('负收益','当前持仓基金累计收益小于0元。',pred(882,'<',['0']),[]),
        ('收益率单位','当前持仓基金累计收益率至少5%，百分比换成比例是0.05。',pred(881,'>=',['0.05']),[]),
        ('零天与缺失','近7天APP登录天数不大于0天，不把缺失数据当0天。',pred(1442,'<=',['0']),[]),
        ('精确全集','圈出这批模拟客户的全部客户，不增加任何经营条件。',{'kind':'SCOPE_ALL'},[]),
    ]
    for title,query,tree,forbidden in boundaries:add('BOUNDARY',title,query,ready(tree),forbidden=forbidden)

    # 20个独立对话母案例，各自最多一轮后续；先验证状态维护，不运行Agent。
    for tid in products[:8]:
        first=pred(721,'>=',['200000'])
        final=group(first,pred(tid,'=',['0']))
        add('MULTITURN','追加产品空白','先找当前时点AUM至少20万元的客户。',ready(first),
            turns=[{'user_message':f'在刚才的基础上，再要求{facts[tid]["name"]}为否。','expected':ready(final)}])
    for tid in [601,620,580,613]:
        first=group(pred(721,'>=',['200000']),pred(tid,'=',['0']))
        final=group(pred(721,'>',['500000']),pred(tid,'=',['0']))
        add('MULTITURN','修改阈值保留条件',f'当前时点AUM至少20万元，{facts[tid]["name"]}为否。',ready(first),
            turns=[{'user_message':'资产条件改为严格超过50万元，其余保持。','expected':ready(final)}])
    for tid in [601,620,580,613]:
        first=group(pred(721,'>=',['200000']),pred(tid,'=',['0']))
        add('MULTITURN','删除指定条件',f'当前时点AUM至少20万元，且{facts[tid]["name"]}为否。',ready(first),
            turns=[{'user_message':f'去掉{facts[tid]["name"]}这个条件，只保留刚才的资产门槛。','expected':ready(pred(721,'>=',['200000']))}])
    for tid in [721,813,918,867]:
        add('MULTITURN','回答阈值澄清',f'找{facts[tid]["name"]}较高的客户，门槛等我确认。',
            {'outcomes':['NEEDS_USER_INPUT'],'required_slots':['threshold']},[tid],
            turns=[{'user_message':'这里较高明确指大于等于50万元。','answer_slots':{'threshold':'500000 CNY inclusive'},'expected':ready(pred(tid,'>=',['500000']))}])

    # 9个真实元数据冲突 + 7个明细能力 + 2个不可精确分档 + NULL + 资格。
    unresolved=[tid for tid,f in facts.items() if f['fact_status']=='UNRESOLVED']
    if len(unresolved)!=9:raise ValueError('事实冲突数量变化，必须审查校准配方')
    for tid in unresolved:
        f=facts[tid]
        query=f'请按{f["name"]}筛选客户；先核实这个指标的定义是否一致，存在冲突就停止，不要自行选一种解释。'
        if tid==1291:
            query='帮我圈选近30天异名跨行累计转入至少50万元、当前没有持有理财、理财风评是C3、C4或C5的客户。'
        expectation={'outcomes':['CAPABILITY_GAP'],'gap_codes':['METADATA_INCOMPLETE']}
        if tid==1291:expectation['tree']=group(pred(601,'=',['0']),pred(1466,'in',['C3','C4','C5']))
        add('GAP','元数据口径冲突（B02谱系）' if tid==1291 else '元数据口径冲突',query,
            expectation,[tid],basis=['P0审计发现的未解决事实冲突；不能将REVIEWED视为事实无冲突'])
    missing=[
        ('年龄明细','找55岁及以上的客户，必须按实际年龄，不使用客户等级代替。'),
        ('基金持仓只数','找当前只持有一只基金的客户，不能把基金类别数当基金只数。'),
        ('单只基金集中度','找最大单只基金市值占基金总市值80%以上的客户，需要单只持仓明细。'),
        ('活动转化归因','找2026年7月指定理财活动已触达但未转化的客户，需要同一活动ID的明细。'),
        ('柜面交易明细','近30天柜面交易至少3笔的客户，不能拿全渠道交易笔数替代。'),
        ('资金续存明细','找历史定期到期后实际续存比例至少70%的客户，需要逐笔到期去向。'),
        ('产品风险明细','找当前持仓基金产品风险高于客户基金风评的客户，需要产品风险等级与持仓明细。'),
    ]
    for scenario,query in missing:
        add('GAP',scenario,query,{'outcomes':['CAPABILITY_GAP'],'gap_codes':['NO_PUBLISHED_CAPABILITY'],'gap_subjects':[scenario]},basis=['现有969业务字段与ACTIVE能力目录；源文档中出现不等于已发布可查询'])
    for tid,query in [(534,'行外资产（万元KYC）严格超过100万元，不能把等于100万元的客户算进来，也不接受近似分档。'),
                      (535,'行外资产（运营KYC）在55万至90万元之间，只接受精确筛选，不能用整个50至100万档替代。')]:
        add('GAP','码值分档无法精确表达',query,{'outcomes':['CAPABILITY_GAP'],'gap_codes':['CALIBER_UNAVAILABLE']},[tid])
    add('GAP','缺少空值操作符','当前理财风评等级为空的客户；不能用不在C1到C5中代替空值判断。',
        {'outcomes':['CAPABILITY_GAP'],'gap_codes':['NULL_OPERATOR_UNAVAILABLE'],'tree':pred(1466,'is_null',[])},[1466])
    add('GAP','当前资格不包含所需标签','按当前时点AUM至少100万元筛选。若当前没有该指标的可用资格，请说明无法完成，不要换成另一种资产口径。',
        {'outcomes':['CAPABILITY_GAP'],'gap_codes':['NO_ELIGIBLE_TAG']},[721],forbidden=[721],excluded=[721])

    if len(cases)!=200 or dict(Counter(c['category'] for c in cases))!=QUOTAS:
        raise ValueError('母案例数量或类别配额错误')
    identities=[digest({'expected':c['expected'],'turns':c['turns'],'targets':c['target_tag_ids']}) for c in cases]
    if len(set(identities))!=200:
        duplicates=[[cases[i]['case_id'] for i,v in enumerate(identities) if v==key] for key,n in Counter(identities).items() if n>1]
        raise ValueError('标准任务重复，不能充当新的母案例: '+str(duplicates))
    output=fresh_directory(output)
    write_jsonl(output/'cases.jsonl',cases)
    # Agent 可见导出不包含目标标签、标准树、源案例身份、判定或命中人数。
    write_jsonl(output/'inputs.jsonl',[{'input_id':c['case_id'],'requirement':c['requirement'],
                                      'reference_date':c['reference_date'],'timezone':c['timezone']} for c in cases])
    gold=[]
    for case in cases:
        stages=[case['expected']]+[t['expected'] for t in case['turns']]
        for stage,expected in enumerate(stages):
            if expected['outcomes']==['READY']:
                result=fixture_result(expected['tree'],rows)
                gold.append({'case_id':case['case_id'],'stage':stage,'dataset_sha256':manifest['sources']['fixture']['sha256'],
                             'mode':'INDEPENDENT_PYTHON_ON_REPOSITORY_SQL_FIXTURE','java_verified':False,'live_values_verified':False,**result})
    write_jsonl(output/'oracle-results.jsonl',gold)
    write_json(output/'manifest.json',{'schema_version':'calibration.v1','phase':'P1','status':'DRAFT',
                                     'mother_cases':200,'formal_cases':0,'formal_generation_allowed':False,
                                     'quotas':QUOTAS,'lineage_groups':len({c['lineage_group'] for c in cases}),
                                     'p0_manifest_sha256':source_hash,'fixture_sha256':manifest['sources']['fixture']['sha256'],
                                     'ai_authoring':'agent recipes + deterministic materialization',
                                     'independent_model_review':'NOT_RUN','human_review':'PENDING',
                                     'paid_api_calls':0,'agent_runs':0,'java_execution':False,
                                     'authoring_code_sha256':{name:file_hash(Path(__file__).parent/name) for name in ('seeds.py','contracts.py','oracle.py','sources.py')},
                                     'files':{p.name:file_hash(p) for p in output.iterdir() if p.is_file()}})
    return cases
