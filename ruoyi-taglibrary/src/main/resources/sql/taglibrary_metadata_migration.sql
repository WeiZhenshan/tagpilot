-- ----------------------------
-- 标签库维表关系 + 标签元数据变更迁移 SQL（向前迁移，可重复执行；不得包含 drop table）
-- 内容：
--   1. tl_tag_library_dimension 标签库默认码表关系表
--   2. tl_tag_metadata_change 标签元数据变更表
--   3. tl_audit_log 增加 request_id / detail_json 列
--   4. 默认码表与批量映射权限按钮（menu_id 2130-2137）
-- ----------------------------

-- 标签库默认码表关系表（全部记录共同构成标签库的默认码表集合）
create table if not exists tl_tag_library_dimension (
    relation_id  bigint(20) not null auto_increment comment '关系ID',
    library_id   bigint(20) not null                comment '标签库ID',
    dimension_id bigint(20) not null                comment '维表ID（dp_dimension_table.dimension_id）',
    order_num    int(4)     not null default 0      comment '显示顺序',
    create_by    varchar(64)         default ''     comment '创建者',
    create_time  datetime            default null   comment '创建时间',
    primary key (relation_id),
    unique key uk_tl_lib_dim (library_id, dimension_id)
) engine=innodb auto_increment=1 comment='标签库默认码表关系表';

-- 标签元数据变更表（草稿/审核，审核通过后才更新 tl_tag）
create table if not exists tl_tag_metadata_change (
    change_id     bigint(20)   not null auto_increment    comment '变更ID',
    library_id    bigint(20)   not null                   comment '标签库ID',
    tag_id        bigint(20)   not null                   comment '标签ID',
    base_version  int(11)      not null default 0         comment '创建草稿时的 tl_tag.version',
    change_type   varchar(16)  not null default 'METADATA' comment '变更类型（FIRST首次建档 METADATA元数据修改 SOURCE来源变更确认）',
    before_json   varchar(2000)         default null      comment '变更前快照（JSON，仅五个可改字段）',
    after_json    varchar(2000)         default null      comment '变更后快照（JSON，仅五个可改字段）',
    source_before varchar(1000)         default null      comment '变更前来源快照JSON',
    source_after  varchar(1000)         default null      comment '变更后来源快照JSON',
    status        varchar(16)  not null default 'DRAFT'   comment '状态（DRAFT草稿 PENDING待审核 APPROVED已通过 REJECTED已驳回）',
    revision      int(11)      not null default 1         comment '草稿修订号（保存草稿递增，提交/审核校验）',
    apply_by      varchar(64)           default ''        comment '申请人',
    submit_time   datetime              default null      comment '提交时间',
    audit_by      varchar(64)           default ''        comment '审核人',
    audit_time    datetime              default null      comment '审核时间',
    audit_comment varchar(500)          default null      comment '审核意见',
    create_by     varchar(64)           default ''        comment '创建者',
    create_time   datetime              default null      comment '创建时间',
    update_by     varchar(64)           default ''        comment '更新者',
    update_time   datetime              default null      comment '更新时间',
    primary key (change_id),
    key idx_tl_meta_change_tag (tag_id, status),
    key idx_tl_meta_change_lib (library_id, status),
    key idx_tl_meta_change_status (status, submit_time)
) engine=innodb auto_increment=1 comment='标签元数据变更表';

-- tl_audit_log 扩展列（information_schema 守卫，可重复执行）
set @has_request_id := (select count(*) from information_schema.columns
    where table_schema = database() and table_name = 'tl_audit_log' and column_name = 'request_id');
set @ddl := if(@has_request_id = 0,
    'alter table tl_audit_log add column request_id varchar(64) default null comment ''关联请求ID（如元数据变更ID）'' after audit_comment',
    'select 1');
prepare stmt from @ddl;
execute stmt;
deallocate prepare stmt;

set @has_detail_json := (select count(*) from information_schema.columns
    where table_schema = database() and table_name = 'tl_audit_log' and column_name = 'detail_json');
set @ddl := if(@has_detail_json = 0,
    'alter table tl_audit_log add column detail_json text null comment ''变更明细快照（JSON）''',
    'select 1');
prepare stmt from @ddl;
execute stmt;
deallocate prepare stmt;

-- from_status/to_status 拓宽为 varchar(16)：tagMeta 日志写入 DRAFT/PENDING/APPROVED/REJECTED，原 char(1) 会截断报错
alter table tl_audit_log
    modify column from_status varchar(16) default '' comment '变更前状态（library/tag为0-3，tagMeta为DRAFT/PENDING/APPROVED/REJECTED）',
    modify column to_status   varchar(16) default '' comment '变更后状态（library/tag为0-3，tagMeta为DRAFT/PENDING/APPROVED/REJECTED）';

-- ----------------------------
-- 默认码表 / 批量映射权限按钮（menu_id 2130-2135）
-- 2130-2131 挂在 2101 标签库管理菜单下；2132-2134 挂在 2102 标签管理菜单下；2135 挂在 2103 审批管理菜单下
-- sys_menu 共 20 列（含 route_name），格式与 taglibrary_menu.sql 一致
-- ----------------------------
insert into sys_menu values('2130', '默认码表查询', '2101', '9',  '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:library:dimension:list', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2131', '默认码表设置', '2101', '10', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:library:dimension:set', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2132', '批量映射查询', '2102', '11', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:tag:mapping:list', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2133', '映射草稿保存', '2102', '12', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:tag:mapping:save', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2134', '映射提交审核', '2102', '13', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:tag:mapping:submit', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2135', '元数据变更审批', '2103', '1',  '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:tag:mapping:audit', '#', 'admin', sysdate(), '', null, '');

-- 批量映射新增权限按钮（守卫可重复执行；存量库授权见 sql/archive/tag_mapping_sync_upgrade_migration.sql）
insert into sys_menu
select '2136', '映射重新同步', '2102', '14', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:tag:mapping:sync', '#', 'admin', sysdate(), '', null, ''
from dual where not exists (select 1 from sys_menu where menu_id = '2136');
insert into sys_menu
select '2137', '映射撤回申请', '2102', '15', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:tag:mapping:withdraw', '#', 'admin', sysdate(), '', null, ''
from dual where not exists (select 1 from sys_menu where menu_id = '2137');
