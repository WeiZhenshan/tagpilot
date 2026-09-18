-- S7 词典种子 + 发布权限。幂等，只向前。
insert into sys_menu select '2144', '语义发布', '2102', '20', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:semantic:publish', '#', 'admin', sysdate(), '', null, '' from dual where not exists (select 1 from sys_menu where menu_id = '2144');

insert into sys_role_menu (role_id, menu_id)
select rm.role_id, '2144'
from sys_role_menu rm
where rm.menu_id = '2141'
  and not exists (select 1 from sys_role_menu x where x.role_id = rm.role_id and x.menu_id = '2144');

insert into ts_business_term (term, term_norm, term_type, options, default_policy, applicable_semantic_types, tag_object, review_status, source_ref, create_by, create_time)
select v.term, v.term_norm, v.term_type, v.options, v.default_policy, v.applicable_semantic_types, '客户', 'REVIEWED', 's7_seed_v1', 'admin', sysdate()
from (
    select '最近' term, '最近' term_norm, 'FUZZY_TIME' term_type, '["7天","30天","90天"]' options, 'ASK' default_policy, 'NUM_AMOUNT,NUM_COUNT,BOOL,DATE' applicable_semantic_types
    union all select '近期', '近期', 'FUZZY_TIME', '["7天","30天","90天"]', 'ASK', 'NUM_AMOUNT,NUM_COUNT,BOOL,DATE'
    union all select '大额', '大额', 'FUZZY_QUANTITY', '["20万","50万","100万"]', 'ASK', 'NUM_AMOUNT,ENUM_ORDINAL'
    union all select '以上', '以上', 'BOUNDARY', '[">="]', 'RESOLVE', 'NUM_AMOUNT,NUM_COUNT,NUM_RATIO,ENUM_ORDINAL'
    union all select '至少', '至少', 'BOUNDARY', '[">="]', 'RESOLVE', 'NUM_AMOUNT,NUM_COUNT'
    union all select '超过', '超过', 'BOUNDARY', '[">"]', 'RESOLVE', 'NUM_AMOUNT,NUM_COUNT,NUM_RATIO'
    union all select '以下', '以下', 'BOUNDARY', '["<="]', 'RESOLVE', 'NUM_AMOUNT,ENUM_ORDINAL'
    union all select '不到', '不到', 'BOUNDARY', '["<"]', 'RESOLVE', 'NUM_AMOUNT,NUM_COUNT'
    union all select '未', '未', 'NEGATION', null, 'NEGATE', null
    union all select '没有', '没有', 'NEGATION', null, 'NEGATE', null
    union all select '排除', '排除', 'NEGATION', null, 'NEGATE', null
    union all select '中等及以上', '中等及以上', 'ORDINAL_WORD', '["C3+"]', 'RESOLVE_BY_FIELD', 'ENUM_ORDINAL'
    union all select '最近一段时间', '最近一段时间', 'FUZZY_TIME', '["7天","30天","90天"]', 'ASK', 'BOOL,NUM_COUNT'
    union all select '高净值', '高净值', 'FUZZY_QUANTITY', '["600万","1000万"]', 'ASK', 'NUM_AMOUNT,ENUM_ORDINAL'
    union all select '小额', '小额', 'FUZZY_QUANTITY', '["1万","5万","10万"]', 'ASK', 'NUM_AMOUNT'
    union all select '理财', '理财', 'FUZZY_CATEGORY', '["仅理财产品","含基金","含保险"]', 'ASK', 'BOOL,NUM_AMOUNT'
    union all select '及以上', '及以上', 'BOUNDARY', '[">="]', 'RESOLVE', 'NUM_AMOUNT,ENUM_ORDINAL'
    union all select '高于', '高于', 'BOUNDARY', '[">"]', 'RESOLVE', 'NUM_AMOUNT,NUM_RATIO'
    union all select '及以下', '及以下', 'BOUNDARY', '["<="]', 'RESOLVE', 'ENUM_ORDINAL,NUM_AMOUNT'
    union all select '不足', '不足', 'BOUNDARY', '["<"]', 'RESOLVE', 'NUM_AMOUNT,NUM_COUNT'
    union all select '不', '不', 'NEGATION', null, 'NEGATE', null
    union all select '无', '无', 'NEGATION', null, 'NEGATE', null
    union all select '非', '非', 'NEGATION', null, 'NEGATE', null
    union all select '不是', '不是', 'NEGATION', null, 'NEGATE', null
    union all select '高', '高', 'ORDINAL_WORD', null, 'RESOLVE_BY_FIELD', 'ENUM_ORDINAL,NUM_SCORE'
    union all select '低', '低', 'ORDINAL_WORD', null, 'RESOLVE_BY_FIELD', 'ENUM_ORDINAL,NUM_SCORE'
    union all select '中等', '中等', 'ORDINAL_WORD', null, 'RESOLVE_BY_FIELD', 'ENUM_ORDINAL'
    union all select '近一周', '近一周', 'FUZZY_TIME', '["7天"]', 'RESOLVE', 'BOOL,NUM_COUNT,NUM_AMOUNT'
    union all select '近一个月', '近一个月', 'FUZZY_TIME', '["1个月"]', 'RESOLVE', 'BOOL,NUM_COUNT,NUM_AMOUNT'
    union all select '上个月', '上个月', 'FUZZY_TIME', '["上月"]', 'RESOLVE', 'BOOL,NUM_AMOUNT,DATE'
    union all select '上月末', '上月末', 'FUZZY_TIME', '["上月末"]', 'RESOLVE', 'NUM_AMOUNT,BOOL'
    union all select '当前', '当前', 'FUZZY_TIME', '["当前时点"]', 'RESOLVE', 'NUM_AMOUNT,BOOL,ENUM_ORDINAL'
    union all select '现在', '现在', 'FUZZY_TIME', '["当前时点"]', 'RESOLVE', 'BOOL,NUM_AMOUNT'
    union all select '历史', '历史', 'FUZZY_TIME', '["历史"]', 'RESOLVE', 'BOOL,NUM_AMOUNT,DATE'
    union all select '未来', '未来', 'FUZZY_TIME', '["未来"]', 'ASK', 'DATE'
    union all select '本行', '本行', 'FUZZY_CATEGORY', '["OUR_BANK"]', 'RESOLVE', 'NUM_AMOUNT'
    union all select '全渠道', '全渠道', 'FUZZY_CATEGORY', '["ALL"]', 'RESOLVE', 'NUM_AMOUNT'
    union all select '私银', '私银', 'FUZZY_CATEGORY', '["PB_KYC"]', 'ASK', 'ENUM_ORDINAL,NUM_COUNT'
    union all select '企微', '企微', 'FUZZY_CATEGORY', '["WECOM"]', 'RESOLVE', 'BOOL'
    union all select '女性', '女性', 'FUZZY_CATEGORY', '["GENDER=F"]', 'RESOLVE', 'ENUM_NOMINAL'
) v
where not exists (
    select 1 from ts_business_term t
    where t.term_norm = v.term_norm and t.term_type = v.term_type and t.tag_object = '客户'
);
