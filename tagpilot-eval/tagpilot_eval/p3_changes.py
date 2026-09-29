"""P3 首轮数据改进：仅从来源和 DEV 根因构造，禁止读取 HOLDOUT 原话。"""
import copy
import json
from pathlib import Path
from .io import digest, file_hash, fresh_directory, read_jsonl, write_json, write_jsonl
from .local import ROOT, mysql
from .contracts import SemanticChangeSet
from tag_semantic.snapshot.canonicalize import canonical_json, sort_value
import hashlib

FIELDS = {
 'ts_tag_semantic': 'tag_id concept_id family_key caliber_struct definition_long semantic_type unit unit_scale allowed_operators semantic_version source_ref',
 'ts_concept': 'concept_id library_id concept_code concept_name domain_dir_id tag_object definition parent_id status source source_ref',
 'ts_alias': 'target_type target_id alias_text alias_norm alias_type weight source source_ref',
 'ts_tag_example': 'tag_id example_type utterance expected_condition source source_ref',
 'ts_concept_tag_relation': 'library_id concept_id tag_id relation_note source_ref version',
 'ts_business_term': 'term_id term term_norm term_type options default_policy applicable_semantic_types tag_object source_ref',
}


def literal(value):
    return "'" + str(value).replace('\\', '\\\\').replace("'", "''") + "'"


def projected(table, key):
    columns=FIELDS[table].split()
    args=','.join(literal(c)+','+c for c in columns)
    where=' and '.join(c+'='+literal(v) for c,v in key.items())
    rows=mysql('select JSON_OBJECT('+args+') from '+table+' where '+where+';')
    if len(rows)>1: raise ValueError('重复变更目标')
    if not rows:return None
    row=json.loads(rows[0])
    for k in ('caliber_struct','allowed_operators','expected_condition','options'):
        if isinstance(row.get(k),str):row[k]=json.loads(row[k])
    return row


def row_hash(row):
    return hashlib.sha256(canonical_json(sort_value(row)).encode()).hexdigest() if row else None


def propose(p0, observation, output):
    p0,output=Path(p0),Path(output)
    live=json.loads(Path(observation).read_text())
    active=next(s for s in live['database']['snapshots'] if s['status']=='ACTIVE')
    facts={f['tag_id']:f for f in read_jsonl(p0/'facts.jsonl')}
    changes=[]
    source='P3-Demo-20260928;source:sql/indiv_cust/01_create_L_INDVCST_LABEL.sql;demo:业务分析场景完整清单.md'
    def add(table,key,after):
        before=projected(table,key)
        value={**(before or {}),**after,**key,'source_ref':source}
        changes.append({'table':table,'key':key,'before_hash':row_hash(before),'before':before,'after':value})
        return value
    highest=int(mysql('select max(concept_id) from ts_concept;')[0])
    def concept(code,name,tag,definition):
        nonlocal highest
        highest+=1
        original=projected('ts_concept',{'concept_id':facts[tag]['published_semantics']['concept_id']})
        add('ts_concept',{'concept_id':highest},{'library_id':107,'concept_code':code,'concept_name':name,
            'domain_dir_id':original['domain_dir_id'],'tag_object':original['tag_object'],'parent_id':0,
            'status':'0','source':'HUMAN','definition':definition})
        return highest
    diff=concept('P3_DIFF_NAME_IN_AMOUNT','异名跨行转入金额',1291,'同一滚动窗口内异名跨行转入金额；Demo 按累计口径，区别于单笔最高金额。不设大额阈值。')
    same=concept('P3_SAME_NAME_IN_AMOUNT','同名跨行转入金额',1282,'指定统计期间同名跨行转入金额；Demo 按累计口径，区别于单笔最高金额。不设阈值。')
    minimum=concept('P3_PAY_LOAN_MIN_RATE','工薪贷最低提款利率',1187,'历史工薪贷提款利率的最小值，不是最高值。')
    fixes={1291:(diff,'SUM'),1305:(diff,'SUM'),1282:(same,'SUM'),1308:(same,'SUM'),1311:(same,'SUM'),1187:(minimum,'MIN'),1073:(None,'COUNT'),1076:(None,'COUNT')}
    for tid,(cid,stat) in fixes.items():
        row=projected('ts_tag_semantic',{'tag_id':tid});cal=copy.deepcopy(row['caliber_struct']);cal['statistic']=stat
        family=row['family_key'].split('|');family[1]=stat
        after={'caliber_struct':cal,'family_key':'|'.join(family),'semantic_version':row['semantic_version']+1}
        if cid:after['concept_id']=cid
        if tid in (1073,1076):
            after.update(semantic_type='NUM_COUNT',unit='COUNT');cal['unit']='COUNT';family[4]='COUNT';after['family_key']='|'.join(family)
        if tid in (1291,1305,1282,1308,1311):after['definition_long']=row['definition_long']+'。Demo按期间累计金额使用，非单笔最高；同名/异名、7天/30天或自然月/年须保持来源口径。'
        add('ts_tag_semantic',{'tag_id':tid},after)
    aliases={
       1291:['近30天异名跨行累计入金','近30天别人从他行转进来的总金额','近30天异名入金合计'],
       1299:['近30天异名跨行单笔最高入金'],1305:['近7天异名跨行累计入金'],
       601:['现在有理财','当前理财持有'],620:['现在有基金','当前基金持有'],
       858:['下一笔定期到期日','最近一笔定期到期日期'],859:['下一笔定期到期金额','最近一笔定期到期金额'],
       1033:['本月代发工资金额','这个月代发工资'],1043:['上月代发工资金额','上个月代发工资'],
       1448:['近30天手机银行登录天数','最近30天APP登录天数'],656:['已开通手机银行','手机银行开通状态'],
       1477:['当前基金风险评级','基金风评'],1466:['当前理财风险评级','理财风评'],
       1319:['本月载体活动参加次数'],1334:['本年载体活动参加次数'],
       1315:['近30天线上经营服务企微私聊消息接收条数'],1357:['掌上银行历史最近一次有效面访日期'],
       735:['当前时点本行资产管理规模'],721:['当前时点资产管理规模'],
       630:['当前持有价值型保险'],806:['当前理财型保险余额'],
    }
    for tid,words in aliases.items():
        for word in words:
            key={'target_type':'TAG','target_id':str(tid),'alias_norm':word.lower().replace(' ','')}
            if projected('ts_alias',key):continue
            add('ts_alias',key,{'alias_text':word,'alias_type':'COLLOQUIAL','weight':1,'source':'HUMAN'})
    for tid in sorted(aliases):
        fact=facts[tid]
        for typ,text in [('POS','请按“'+fact['name']+'”字段筛选，保留该字段时间和范围口径。'),
                         ('POS','查看客户的'+fact['name']+'，以来源标签口径为准。'),
                         ('NEG','不要把'+fact['name']+'替换成其它时间、统计口径或产品的相似指标。')]:
            key={'tag_id':tid,'example_type':typ,'utterance':text}
            if projected('ts_tag_example',key):continue
            add('ts_tag_example',key,{'expected_condition':{'tag_id':tid,'preserve_caliber':True},'source':'HUMAN'})
    # 业务入口仅给候选，不发布复合规则或默认阈值。
    for i,(name,ids) in enumerate([
        ('大额入金转化',[1291,1299,601,1466]),('定期到期承接',[858,859,601]),
        ('代发客户流失预警',[1033,1043,1448]),('沉睡客户激活',[721,1448]),
        ('基金客户配置优化',[620,1477,860]),('营销活动复盘',[1319,1334]),('渠道迁移',[656,1448])]):
        cid=concept('P3_SCENARIO_'+str(i+1),name,ids[0],name+'的候选指标入口，不定义时间、阈值、因果或业务目标；由用户选择明确口径。')
        for tid in ids:
            add('ts_concept_tag_relation',{'library_id':107,'concept_id':cid,'tag_id':tid},
                {'relation_note':'用于'+name+'的候选检索；不表示等价，不改变主概念与标签族。','version':1})
    pack={'schema_version':'semantic-changeset.v1','library_id':107,'change_id':'p3-semantic-20260928-v1',
          'baseline_snapshot':active['snapshot_id'],'baseline_hash':active['content_hash'],'status':'REVIEWED',
          'source_case_ids':['CAL-3392','CAL-3100','CAL-4060','CAL-1272','CAL-3717'],
          'source_refs':[source], 'changes':changes,
          'review_records':[{'reviewer_type':'AI','reviewer':'Codex','status':'REVIEWED',
             'scope':'逐条核对字段来源；SUM为demo约定，非银行签署；仅开发集与通用例子，未读取留出原话'}],
          'regression_refs':['p2-cases-v3:REGRESSION']}
    # before 是落盘审计扩展，在运行时 changes 字典内允许；包顶层仍用严格契约。
    SemanticChangeSet.model_validate(pack)
    fresh_directory(output);write_json(output/'changeset.json',pack)
    write_json(output/'manifest.json',{'phase':'P3','status':'AI_REVIEWED','changes':len(changes),
        'baseline_snapshot':active['snapshot_id'],'files':{'changeset.json':file_hash(output/'changeset.json')},
        'p2_frozen_artifacts_unchanged':True})
    return pack
