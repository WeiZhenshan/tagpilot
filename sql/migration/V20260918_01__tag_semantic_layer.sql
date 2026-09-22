-- ----------------------------------------------------------------------------
-- V20260918_01 标签语义层 ts_* 骨架（向前迁移，可重复执行；不得包含 drop table）
-- 内容：
--   1. 11 张 ts_* 表（概念/标签语义/别名/码值语义 + 易混淆/示例/词典/画像/快照/索引构建/反馈）
--   2. 语义维护权限按钮 menu_id 2140-2143（挂在 2102 标签管理下）
-- 说明：不修改 tl_* / dp_* 表结构；码值权威仍为库级绑定的外部标准码表
-- ----------------------------------------------------------------------------

-- 1. 业务概念
create table if not exists ts_concept (
    concept_id      bigint(20)    not null auto_increment comment '概念ID',
    library_id      bigint(20)    not null                comment '所属标签库ID',
    concept_code    varchar(64)   not null                comment '稳定编码，创建后不随中文改名变化',
    concept_name    varchar(64)   not null                comment '概念中文名',
    domain_dir_id   bigint(20)    not null                comment '一级目录 tl_tag_dir.dir_id',
    tag_object      varchar(16)   not null                comment '业务对象',
    definition      varchar(1000)          default null   comment '概念定义',
    parent_id       bigint(20)    not null default 0      comment '父概念ID，0 表示根',
    status          char(1)       not null default '0'    comment '0启用 1停用',
    source          varchar(16)            default null   comment 'RULE/LLM/HUMAN',
    review_status   varchar(16)   not null default 'DRAFT' comment 'DRAFT/REVIEWED',
    review_by       varchar(64)            default ''     comment '复核人',
    review_time     datetime               default null   comment '复核时间',
    source_ref      varchar(500)           default null   comment '复核依据',
    create_by       varchar(64)            default ''     comment '创建者',
    create_time     datetime               default null   comment '创建时间',
    update_by       varchar(64)            default ''     comment '更新者',
    update_time     datetime               default null   comment '更新时间',
    remark          varchar(500)           default null   comment '备注',
    primary key (concept_id),
    unique key uk_ts_concept_lib_code (library_id, concept_code),
    key idx_ts_concept_domain (domain_dir_id),
    key idx_ts_concept_review (review_status)
) engine=innodb auto_increment=1 comment='标签语义层-业务概念';

-- 2. 标签语义（与 tl_tag 1:1，不改 tl_tag）
create table if not exists ts_tag_semantic (
    tag_id              bigint(20)     not null                comment '标签ID，等于 tl_tag.tag_id',
    concept_id          bigint(20)              default null   comment '所属概念，S3 确认前可空',
    family_key          varchar(192)   not null                comment 'concept_code|statistic|scope|source_system|unit|caliber_variant',
    caliber_variant     varchar(32)    not null default 'BASE' comment '非时间口径区分码',
    semantic_type       varchar(24)    not null                comment 'BOOL/ENUM_*/NUM_*/DATE/TEXT_FREE/ID_KEY',
    allowed_operators   varchar(128)   not null                comment '可执行操作符 JSON 数组',
    default_operator    varchar(16)             default null   comment '默认操作符',
    unit                varchar(16)             default null   comment '标准量纲 CNY/RATIO/COUNT/DAY/NONE',
    unit_scale          decimal(18,4)  not null default 1      comment '标准值=物理值×scale',
    caliber_struct      json           not null                comment '结构化口径',
    definition_long     varchar(2000)           default null   comment '面向检索的完整业务定义',
    sensitivity         varchar(16)    not null default 'UNKNOWN' comment '人工确认敏感级',
    completeness_score  tinyint                 default null   comment '完整度 0-100',
    basis_hash          char(64)                default null   comment '复核时权威口径与来源内容哈希',
    source              varchar(16)             default null   comment 'RULE/LLM/HUMAN/FEEDBACK/SYNC',
    review_status       varchar(16)    not null default 'DRAFT' comment 'DRAFT/REVIEWED',
    semantic_version    int(11)        not null default 1      comment '语义层自身版本',
    review_by           varchar(64)             default ''     comment '复核人',
    review_time         datetime                default null   comment '复核时间',
    source_ref          varchar(500)            default null   comment '复核依据',
    create_by           varchar(64)             default ''     comment '创建者',
    create_time         datetime                default null   comment '创建时间',
    update_by           varchar(64)             default ''     comment '更新者',
    update_time         datetime                default null   comment '更新时间',
    remark              varchar(500)            default null   comment '备注（可暂存 concept_candidate）',
    primary key (tag_id),
    key idx_ts_tag_sem_concept (concept_id),
    key idx_ts_tag_sem_family (family_key),
    key idx_ts_tag_sem_review (review_status)
) engine=innodb comment='标签语义层-标签语义';

-- 3. 别名
create table if not exists ts_alias (
    alias_id        bigint(20)    not null auto_increment comment '别名ID',
    target_type     varchar(16)   not null                comment 'TAG/CONCEPT/CODE_VALUE/DOMAIN',
    target_id       varchar(96)   not null                comment 'TAG:tag_id | CONCEPT:concept_id | CODE_VALUE:tag_id#code | DOMAIN:dir_id',
    alias_text      varchar(64)   not null                comment '别名原文',
    alias_norm      varchar(64)   not null                comment '归一化（去空格、全半角、小写）',
    alias_type      varchar(16)   not null                comment 'FORMAL/COLLOQUIAL/ABBR/HISTORICAL/NEGATIVE',
    weight          decimal(4,2)  not null default 1.00   comment '权重',
    source          varchar(16)   not null                comment 'RULE/LLM/HUMAN/FEEDBACK',
    review_status   varchar(16)   not null default 'DRAFT' comment 'DRAFT/REVIEWED',
    hit_count       int(11)       not null default 0      comment '线上命中次数，不参与快照内容哈希',
    review_by       varchar(64)            default ''     comment '复核人',
    review_time     datetime               default null   comment '复核时间',
    source_ref      varchar(500)           default null   comment '复核依据',
    create_by       varchar(64)            default ''     comment '创建者',
    create_time     datetime               default null   comment '创建时间',
    update_by       varchar(64)            default ''     comment '更新者',
    update_time     datetime               default null   comment '更新时间',
    remark          varchar(500)           default null   comment '备注',
    primary key (alias_id),
    unique key uk_ts_alias_target_norm (target_type, target_id, alias_norm),
    key idx_ts_alias_norm (alias_norm),
    key idx_ts_alias_review (review_status)
) engine=innodb auto_increment=1 comment='标签语义层-别名';

-- 4. 码值语义（增补外部码表，不复制可编辑主档）
create table if not exists ts_code_value_semantic (
    tag_id            bigint(20)     not null                comment '标签ID',
    code              varchar(64)    not null                comment '码值，始终按字符串保存',
    rank_no           int(11)                 default null   comment '有序分档序号',
    lower_bound       decimal(20,4)           default null   comment '区间下界',
    upper_bound       decimal(20,4)           default null   comment '区间上界',
    lower_inclusive   tinyint(1)              default null   comment '下界是否包含',
    upper_inclusive   tinyint(1)              default null   comment '上界是否包含',
    bound_unit        varchar(16)             default null   comment '区间量纲',
    parent_tag_id     bigint(20)              default null   comment '父字段标签ID',
    parent_code       varchar(64)             default null   comment '父节点码值',
    level_no          tinyint                 default null   comment '层级号',
    is_unknown_bucket tinyint(1)     not null default 0      comment '是否未知桶，须业务复核',
    basis_hash        char(64)                default null   comment '复核时来源/字段/code/定义哈希',
    source            varchar(16)             default null   comment 'RULE/LLM/HUMAN',
    review_status     varchar(16)    not null default 'DRAFT' comment 'DRAFT/REVIEWED',
    review_by         varchar(64)             default ''     comment '复核人',
    review_time       datetime                default null   comment '复核时间',
    source_ref        varchar(500)            default null   comment '复核依据',
    create_by         varchar(64)             default ''     comment '创建者',
    create_time       datetime                default null   comment '创建时间',
    update_by         varchar(64)             default ''     comment '更新者',
    update_time       datetime                default null   comment '更新时间',
    remark            varchar(500)            default null   comment '备注',
    primary key (tag_id, code),
    key idx_ts_cvs_review (review_status)
) engine=innodb comment='标签语义层-码值语义';

-- 5. 易混淆对
create table if not exists ts_confusable (
    pair_id              bigint(20)    not null auto_increment comment '配对ID',
    tag_id_a             bigint(20)    not null                comment '标签A',
    tag_id_b             bigint(20)    not null                comment '标签B',
    confusion_type       varchar(16)   not null                comment 'TIME_FACET/SOURCE/SIMILAR_NAME/SCOPE',
    difference_note      varchar(500)           default null   comment '差异说明',
    disambiguation_hint  varchar(500)           default null   comment '消歧提示',
    source               varchar(16)            default null   comment 'RULE/LLM/HUMAN',
    review_status        varchar(16)   not null default 'DRAFT' comment 'DRAFT/REVIEWED',
    review_by            varchar(64)            default ''     comment '复核人',
    review_time          datetime               default null   comment '复核时间',
    source_ref           varchar(500)           default null   comment '复核依据',
    create_by            varchar(64)            default ''     comment '创建者',
    create_time          datetime               default null   comment '创建时间',
    update_by            varchar(64)            default ''     comment '更新者',
    update_time          datetime               default null   comment '更新时间',
    remark               varchar(500)           default null   comment '备注',
    primary key (pair_id),
    unique key uk_ts_confusable_pair (tag_id_a, tag_id_b)
) engine=innodb auto_increment=1 comment='标签语义层-易混淆对';

-- 6. 正反例
create table if not exists ts_tag_example (
    example_id          bigint(20)    not null auto_increment comment '示例ID',
    tag_id              bigint(20)    not null                comment '标签ID',
    example_type        char(3)       not null                comment 'POS/NEG',
    utterance           varchar(200)  not null                comment '用户说法',
    expected_condition  json                   default null   comment '期望条件',
    source              varchar(16)            default null   comment 'RULE/LLM/HUMAN',
    review_status       varchar(16)   not null default 'DRAFT' comment 'DRAFT/REVIEWED',
    review_by           varchar(64)            default ''     comment '复核人',
    review_time         datetime               default null   comment '复核时间',
    source_ref          varchar(500)           default null   comment '复核依据',
    create_by           varchar(64)            default ''     comment '创建者',
    create_time         datetime               default null   comment '创建时间',
    update_by           varchar(64)            default ''     comment '更新者',
    update_time         datetime               default null   comment '更新时间',
    remark              varchar(500)           default null   comment '备注',
    primary key (example_id),
    key idx_ts_example_tag (tag_id)
) engine=innodb auto_increment=1 comment='标签语义层-正反例';

-- 7. 业务模糊词典
create table if not exists ts_business_term (
    term_id                    bigint(20)    not null auto_increment comment '词条ID',
    term                       varchar(32)   not null                comment '词面',
    term_norm                  varchar(32)   not null                comment '归一化',
    term_type                  varchar(16)   not null                comment 'FUZZY_TIME/FUZZY_QUANTITY/FUZZY_CATEGORY/ORDINAL_WORD/NEGATION/BOUNDARY',
    options                    json                   default null   comment '可选解释',
    default_policy             varchar(16)            default null   comment 'ASK/RESOLVE_BY_FIELD 等',
    applicable_semantic_types  varchar(128)           default null   comment '适用语义类型',
    tag_object                 varchar(16)            default null   comment '适用对象',
    review_status              varchar(16)   not null default 'DRAFT' comment 'DRAFT/REVIEWED',
    review_by                  varchar(64)            default ''     comment '复核人',
    review_time                datetime               default null   comment '复核时间',
    source_ref                 varchar(500)           default null   comment '复核依据',
    create_by                  varchar(64)            default ''     comment '创建者',
    create_time                datetime               default null   comment '创建时间',
    update_by                  varchar(64)            default ''     comment '更新者',
    update_time                datetime               default null   comment '更新时间',
    remark                     varchar(500)           default null   comment '备注',
    primary key (term_id),
    unique key uk_ts_term_norm (term_norm, term_type, tag_object)
) engine=innodb auto_increment=1 comment='标签语义层-业务模糊词典';

-- 8. 数据画像
create table if not exists ts_tag_profile (
    tag_id             bigint(20)     not null                comment '标签ID',
    profile_date       date           not null                comment '画像日期',
    row_count          bigint(20)              default null   comment '行数',
    null_rate          decimal(6,4)            default null   comment '空值率',
    distinct_count     int(11)                 default null   comment '去重数',
    min_val            decimal(20,4)           default null   comment '最小值',
    max_val            decimal(20,4)           default null   comment '最大值',
    p50                decimal(20,4)           default null   comment '分位 p50',
    p90                decimal(20,4)           default null   comment '分位 p90',
    p99                decimal(20,4)           default null   comment '分位 p99',
    top_values         json                    default null   comment '仅审核枚举码聚合频率，禁止自由文本原值',
    sample_size        bigint(20)              default null   comment '样本量',
    sampled            tinyint(1)     not null default 0      comment '是否抽样',
    source_version_id  bigint(20)              default null   comment '来源数据集版本',
    source_fingerprint char(64)                default null   comment '来源指纹',
    create_by          varchar(64)             default ''     comment '创建者',
    create_time        datetime                default null   comment '创建时间',
    update_by          varchar(64)             default ''     comment '更新者',
    update_time        datetime                default null   comment '更新时间',
    remark             varchar(500)            default null   comment '备注',
    primary key (tag_id, profile_date)
) engine=innodb comment='标签语义层-数据画像';

-- 9. 目录快照
create table if not exists ts_catalog_snapshot (
    snapshot_id      varchar(40)    not null                comment '快照ID，如 L107-20260916-001',
    library_id       bigint(20)     not null                comment '标签库ID',
    snapshot_no      int(11)        not null                comment '库内序号',
    tag_count        int(11)                 default null   comment '标签数',
    concept_count    int(11)                 default null   comment '概念数',
    alias_count      int(11)                 default null   comment '别名数',
    code_value_count int(11)                 default null   comment '码值数',
    content_hash     char(64)       not null                comment '规范化 JSONL 内容 sha256',
    storage_uri      varchar(500)   not null                comment '快照存储位置',
    schema_version   varchar(8)     not null default 'v1'   comment 'Schema 版本',
    status           varchar(16)    not null default 'DRAFT' comment 'DRAFT/PUBLISHED/ACTIVE/RETIRED',
    source_manifest  json                    default null   comment '来源清单',
    quality_report   json                    default null   comment '门禁结果与排除项',
    publish_by       varchar(64)             default ''     comment '发布人',
    publish_time     datetime                default null   comment '发布时间',
    create_by        varchar(64)             default ''     comment '创建者',
    create_time      datetime                default null   comment '创建时间',
    update_by        varchar(64)             default ''     comment '更新者',
    update_time      datetime                default null   comment '更新时间',
    remark           varchar(500)            default null   comment '备注',
    primary key (snapshot_id),
    unique key uk_ts_snapshot_lib_no (library_id, snapshot_no)
) engine=innodb comment='标签语义层-目录快照';

-- 10. 索引构建
create table if not exists ts_index_build (
    build_id              varchar(48)    not null                comment '独立构建ID',
    snapshot_id           varchar(40)    not null                comment '快照ID',
    doc_template_version  varchar(16)    not null                comment '检索文档模板版本',
    analyzer_version      varchar(64)             default null   comment '分析器与词典内容哈希',
    embedding_model       varchar(64)             default null   comment '向量模型',
    embedding_dim         int(11)                 default null   comment '向量维度',
    embedding_model_hash  varchar(64)             default null   comment '向量模型哈希',
    reranker_model        varchar(64)             default null   comment '重排模型',
    reranker_model_hash   varchar(64)             default null   comment '重排模型哈希',
    retrieval_config_hash char(64)                default null   comment '检索配置哈希',
    store_type            varchar(16)    not null                comment 'MILVUS/LOCAL',
    milvus_collection     varchar(96)             default null   comment '实体 Collection 名',
    milvus_alias          varchar(64)             default null   comment '活动别名',
    artifact_uri          varchar(500)   not null                comment '本地产物目录',
    artifact_hash         char(64)                default null   comment '产物校验和',
    doc_count             int(11)                 default null   comment '文档数',
    doc_id_hash           char(64)                default null   comment '全部 doc_id 排序哈希',
    status                varchar(16)    not null default 'BUILDING' comment 'BUILDING/READY/ACTIVE/FAILED/RETIRED',
    eval_summary          json                    default null   comment '评测摘要',
    build_time            datetime                default null   comment '构建时间',
    build_duration_ms     bigint(20)              default null   comment '构建耗时毫秒',
    create_by             varchar(64)             default ''     comment '创建者',
    create_time           datetime                default null   comment '创建时间',
    update_by             varchar(64)             default ''     comment '更新者',
    update_time           datetime                default null   comment '更新时间',
    remark                varchar(500)            default null   comment '备注',
    primary key (build_id),
    key idx_ts_build_snapshot (snapshot_id),
    key idx_ts_build_status (status)
) engine=innodb comment='标签语义层-索引构建';

-- 11. 检索反馈
create table if not exists ts_retrieval_feedback (
    feedback_id         bigint(20)     not null auto_increment comment '反馈ID',
    trace_id            varchar(64)             default null   comment '请求追踪ID',
    snapshot_id         varchar(40)             default null   comment '快照ID',
    build_id            varchar(48)             default null   comment '构建ID',
    user_id             bigint(20)              default null   comment '用户ID，由认证上下文写入',
    query_text          varchar(500)            default null   comment '查询原文（须脱敏）',
    requirement_text    varchar(200)            default null   comment '原子条件片段',
    recommended_tag_id  bigint(20)              default null   comment '推荐标签',
    final_tag_id        bigint(20)              default null   comment '最终标签',
    action              varchar(16)             default null   comment 'ACCEPT/REPLACE/REMOVE/CLARIFY_PICKED/REJECT_ALL',
    clarify_question    varchar(300)            default null   comment '澄清问题',
    clarify_answer      varchar(100)            default null   comment '澄清回答',
    confidence          decimal(4,3)            default null   comment '置信度',
    rank_features       json                    default null   comment '排序特征',
    create_time         datetime                default null   comment '创建时间',
    primary key (feedback_id),
    key idx_ts_fb_snapshot (snapshot_id),
    key idx_ts_fb_final_tag (final_tag_id),
    key idx_ts_fb_action (action)
) engine=innodb auto_increment=1 comment='标签语义层-检索反馈';

-- ----------------------------
-- 语义维护权限按钮（menu_id 2140-2143）挂在 2102 标签管理下
-- ----------------------------
insert into sys_menu select '2140', '语义查询', '2102', '16', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:semantic:list', '#', 'admin', sysdate(), '', null, '' from dual where not exists (select 1 from sys_menu where menu_id = '2140');
insert into sys_menu select '2141', '语义编辑', '2102', '17', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:semantic:edit', '#', 'admin', sysdate(), '', null, '' from dual where not exists (select 1 from sys_menu where menu_id = '2141');
insert into sys_menu select '2142', '语义复核', '2102', '18', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:semantic:review', '#', 'admin', sysdate(), '', null, '' from dual where not exists (select 1 from sys_menu where menu_id = '2142');
insert into sys_menu select '2143', '语义冻结导入', '2102', '19', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:semantic:bootstrap', '#', 'admin', sysdate(), '', null, '' from dual where not exists (select 1 from sys_menu where menu_id = '2143');

-- 将语义查询/编辑/冻结导入授予已有「批量映射查询(2132)」的角色；复核权限不自动授予，与 edit 分离
insert into sys_role_menu (role_id, menu_id)
select rm.role_id, '2140'
  from sys_role_menu rm
 where rm.menu_id = '2132'
   and not exists (select 1 from sys_role_menu x where x.role_id = rm.role_id and x.menu_id = '2140');

insert into sys_role_menu (role_id, menu_id)
select rm.role_id, '2141'
  from sys_role_menu rm
 where rm.menu_id = '2132'
   and not exists (select 1 from sys_role_menu x where x.role_id = rm.role_id and x.menu_id = '2141');

insert into sys_role_menu (role_id, menu_id)
select rm.role_id, '2143'
  from sys_role_menu rm
 where rm.menu_id = '2132'
   and not exists (select 1 from sys_role_menu x where x.role_id = rm.role_id and x.menu_id = '2143');
