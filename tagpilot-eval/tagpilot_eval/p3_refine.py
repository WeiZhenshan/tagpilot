"""只由 P3 DEV 失败归因构造第二轮可审计语义补丁，不读取留出原话。"""
import json,copy
from pathlib import Path
from .p3_changes import projected,row_hash
from .local import mysql
from .io import write_json,file_hash

def propose(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    baseline=json.loads(mysql("select JSON_OBJECT('snapshot_id',snapshot_id,'content_hash',content_hash) from ts_catalog_snapshot where library_id=107 and status='ACTIVE';")[0])
    source='P3-DEV-refinement;source:sql/indiv_cust/01_create_L_INDVCST_LABEL.sql;demo:独立产品字段与用户明确时间;AI复核非银行签署'
    changes=[]
    def add(table,key,after):
        before=projected(table,key);value={**(before or {}),**after,**key,'source_ref':source}
        changes.append({'table':table,'key':key,'before_hash':row_hash(before),'before':before,'after':value})
    row=projected('ts_tag_semantic',{'tag_id':1009});cal=copy.deepcopy(row['caliber_struct']);cal['month_of_year']=12;cal['time_anchor_label']='上年12月'
    add('ts_tag_semantic',{'tag_id':1009},{'caliber_struct':cal,'semantic_version':row['semantic_version']+1,
        'definition_long':row['definition_long']+'。上年12月是上一个自然年的12月，不是整个上年；month_of_year=12。'})
    aliases={1291:['异名入金','异名跨行累计转入'],1282:['同名入金'],1299:['异名跨行单笔最高入金'],
        601:['没持有理财','还没买理财','未持理财','当前没理财','现在没有理财'],
        620:['没有基金','未持有基金','基金未持有','没持有基金'],
        721:['当前时点资产','当前时点总资产'],1448:['APP登录','APP低活跃'],
        858:['下一笔定期','最近一笔定期'],859:['到期金额'],
        1466:['理财风评'],1477:['基金风评'],1319:['本月载体活动参与']}
    # 入金是候选集合，不能唯一别名快捷绑定或补造同名/异名/窗口。
    for tid in [1291,1282,1299]:aliases[tid].append('入金')
    for tid,words in aliases.items():
        for word in words:
            key={'target_type':'TAG','target_id':str(tid),'alias_norm':word.lower().replace(' ','')}
            if not projected('ts_alias',key):add('ts_alias',key,{'alias_text':word,'alias_type':'COLLOQUIAL','weight':1,'source':'HUMAN'})
    examples={601:('现在没持有理财', '=', ['0']),620:('当前没有基金','=', ['0']),
        1466:('当前理财风评属于C3、C4','in',['C3','C4']),1477:('当前基金风评属于C3、C4','in',['C3','C4']),
        721:('当前时点AUM至少20万元','>=',['20']),1448:('近30天APP登录最多2天','<=',['2'])}
    for tid,(text,op,values) in examples.items():
        row=projected('ts_tag_semantic',{'tag_id':tid})
        cond={'tag_id':tid,'operator':op,'values':values,'value_unit':row['unit'],'value_scale':10000 if tid==721 else 1,
            'expected_caliber':{k:v for k,v in row['caliber_struct'].items() if k in ['time_anchor_type','time_window_unit','time_window_value','period_edge','calendar_mode'] and v is not None}}
        add('ts_tag_example',{'tag_id':tid,'example_type':'POS','utterance':text},{'expected_condition':cond,'source':'HUMAN'})
        # 更新通用正例，使工具首条例子也提供可执行结构。
        name=mysql('select tag_name from tl_tag where tag_id='+str(tid)+';')[0]
        add('ts_tag_example',{'tag_id':tid,'example_type':'POS','utterance':'请按“'+name+'”字段筛选，保留该字段时间和范围口径。'},
            {'expected_condition':{'tag_id':tid,'expected_caliber':cond['expected_caliber'],'preserve_caliber':True},'source':'HUMAN'})
    term_id=int(mysql('select max(term_id) from ts_business_term;')[0])
    for word in ['持有理财','买理财','未持理财','当前没理财','现在没有理财','理财风评']:
        term_id+=1
        add('ts_business_term',{'term_id':term_id},{'term':word,'term_norm':word,'term_type':'FUZZY_CATEGORY',
            'options':['已明确为独立理财产品字段；未持有对应0，持有对应1；风评使用已发布理财等级；不自动添加基金保险要求'],
            'default_policy':'RESOLVE_BY_FIELD','applicable_semantic_types':'BOOL,ENUM_ORDINAL','tag_object':'客户'})
    term_id+=1
    add('ts_business_term',{'term_id':term_id},{'term':'入金','term_norm':'入金','term_type':'FUZZY_CATEGORY',
        'options':['请明确同名或异名跨行转入','请明确统计窗口和累计或单笔最高','请明确比较阈值'],
        'default_policy':'ASK','applicable_semantic_types':'NUM_AMOUNT','tag_object':'客户'})
    pack={'schema_version':'semantic-changeset.v1','library_id':107,'change_id':'p3-semantic-20260928-v2',
        'baseline_snapshot':baseline['snapshot_id'],'baseline_hash':baseline['content_hash'],'status':'REVIEWED',
        'source_case_ids':['CAL-8001','CAL-8004','CAL-8061'],'source_refs':[source], 'changes':changes,
        'review_records':[{'reviewer':'Codex','reviewer_type':'AI','status':'REVIEWED','scope':'DEV失败归因；词面消歧不设阈值，不导入完整评测问题；非银行签署'}],
        'regression_refs':['p2-cases-v3:REGRESSION']}
    write_json(output/'changeset.json',pack)
    write_json(output/'manifest.json',{'phase':'P3','changes':len(changes),'status':'AI_REVIEWED',
        'files':{'changeset.json':file_hash(output/'changeset.json')},'holdout_inputs_used':False})
    return pack
