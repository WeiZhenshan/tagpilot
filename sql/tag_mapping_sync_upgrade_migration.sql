-- ----------------------------------------------------------------------------
-- 标签库批量映射同步优化：结构迁移（向前迁移，幂等，可重复执行；不得包含 drop table）
-- 对应计划：doc/标签库批量映射同步优化计划.md
-- 内容：
--   1. tl_tag_library 增加最近同步版本/时间
--   2. tl_tag 增加来源版本、来源快照、来源指纹、已确认指纹、来源状态；status 新增取值 '4'（待完善）
--   3. tl_tag_metadata_change 增加变更类型、来源前后快照、草稿修订号
--   4. 批量映射新增权限按钮（menu_id 2136-2137），并授予已有"映射草稿保存(2133)"的角色
--   5. 存量数据：无任何审核通过记录的旧同步草稿迁入"待完善"(status='4')
-- 执行时机：在升级应用代码之前执行。
-- ----------------------------------------------------------------------------

-- ===================== 1. tl_tag_library =====================
set @has_col := (select count(*) from information_schema.columns
    where table_schema = database() and table_name = 'tl_tag_library' and column_name = 'last_sync_version_id');
set @ddl := if(@has_col = 0,
    'alter table tl_tag_library add column last_sync_version_id bigint(20) default null comment ''最近同步的数据集版本ID'' after dataset_id',
    'select 1');
prepare stmt from @ddl; execute stmt; deallocate prepare stmt;

set @has_col := (select count(*) from information_schema.columns
    where table_schema = database() and table_name = 'tl_tag_library' and column_name = 'last_sync_time');
set @ddl := if(@has_col = 0,
    'alter table tl_tag_library add column last_sync_time datetime default null comment ''最近同步时间'' after last_sync_version_id',
    'select 1');
prepare stmt from @ddl; execute stmt; deallocate prepare stmt;

-- ===================== 2. tl_tag =====================
set @has_col := (select count(*) from information_schema.columns
    where table_schema = database() and table_name = 'tl_tag' and column_name = 'source_version_id');
set @ddl := if(@has_col = 0,
    'alter table tl_tag add column source_version_id bigint(20) default null comment ''来源数据集版本ID（最近一次同步解析的版本）'' after version',
    'select 1');
prepare stmt from @ddl; execute stmt; deallocate prepare stmt;

set @has_col := (select count(*) from information_schema.columns
    where table_schema = database() and table_name = 'tl_tag' and column_name = 'source_snapshot');
set @ddl := if(@has_col = 0,
    'alter table tl_tag add column source_snapshot varchar(1000) default null comment ''来源字段快照JSON（数据源/物理表/物理列/数据类型/主键标记）'' after source_version_id',
    'select 1');
prepare stmt from @ddl; execute stmt; deallocate prepare stmt;

set @has_col := (select count(*) from information_schema.columns
    where table_schema = database() and table_name = 'tl_tag' and column_name = 'source_fingerprint');
set @ddl := if(@has_col = 0,
    'alter table tl_tag add column source_fingerprint varchar(64) default null comment ''来源指纹（最近同步观察值）'' after source_snapshot',
    'select 1');
prepare stmt from @ddl; execute stmt; deallocate prepare stmt;

set @has_col := (select count(*) from information_schema.columns
    where table_schema = database() and table_name = 'tl_tag' and column_name = 'confirmed_fingerprint');
set @ddl := if(@has_col = 0,
    'alter table tl_tag add column confirmed_fingerprint varchar(64) default null comment ''已确认来源指纹（元数据审核通过时写入）'' after source_fingerprint',
    'select 1');
prepare stmt from @ddl; execute stmt; deallocate prepare stmt;

set @has_col := (select count(*) from information_schema.columns
    where table_schema = database() and table_name = 'tl_tag' and column_name = 'source_status');
set @ddl := if(@has_col = 0,
    'alter table tl_tag add column source_status varchar(16) not null default ''AVAILABLE'' comment ''来源状态（AVAILABLE当前版本可用 MISSING来源缺失 CHANGED来源变更待确认）'' after confirmed_fingerprint',
    'select 1');
prepare stmt from @ddl; execute stmt; deallocate prepare stmt;

-- status 取值扩展：新增 '4' 待完善（尚未通过首次元数据审核的同步字段）
alter table tl_tag
    modify column status char(1) default '0' comment '状态（0草稿 1待审批 2已上线 3已下线 4待完善）';

-- ===================== 3. tl_tag_metadata_change =====================
set @has_col := (select count(*) from information_schema.columns
    where table_schema = database() and table_name = 'tl_tag_metadata_change' and column_name = 'change_type');
set @ddl := if(@has_col = 0,
    'alter table tl_tag_metadata_change add column change_type varchar(16) not null default ''METADATA'' comment ''变更类型（FIRST首次建档 METADATA元数据修改 SOURCE来源变更确认）'' after base_version',
    'select 1');
prepare stmt from @ddl; execute stmt; deallocate prepare stmt;

set @has_col := (select count(*) from information_schema.columns
    where table_schema = database() and table_name = 'tl_tag_metadata_change' and column_name = 'source_before');
set @ddl := if(@has_col = 0,
    'alter table tl_tag_metadata_change add column source_before varchar(1000) default null comment ''变更前来源快照JSON'' after after_json',
    'select 1');
prepare stmt from @ddl; execute stmt; deallocate prepare stmt;

set @has_col := (select count(*) from information_schema.columns
    where table_schema = database() and table_name = 'tl_tag_metadata_change' and column_name = 'source_after');
set @ddl := if(@has_col = 0,
    'alter table tl_tag_metadata_change add column source_after varchar(1000) default null comment ''变更后来源快照JSON'' after source_before',
    'select 1');
prepare stmt from @ddl; execute stmt; deallocate prepare stmt;

set @has_col := (select count(*) from information_schema.columns
    where table_schema = database() and table_name = 'tl_tag_metadata_change' and column_name = 'revision');
set @ddl := if(@has_col = 0,
    'alter table tl_tag_metadata_change add column revision int(11) not null default 1 comment ''草稿修订号（保存草稿递增，提交/审核校验）'' after status',
    'select 1');
prepare stmt from @ddl; execute stmt; deallocate prepare stmt;

-- ===================== 4. 批量映射新增权限按钮（menu_id 2136-2137）=====================
-- 2136 重新同步：守卫"进入页面自动同步/手动重新同步"写操作；仅查询权限用户可查看页面但不触发写入
-- 2137 撤回申请：申请人将待审申请撤回为草稿
insert into sys_menu
select '2136', '映射重新同步', '2102', '14', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:tag:mapping:sync', '#', 'admin', sysdate(), '', null, ''
from dual where not exists (select 1 from sys_menu where menu_id = '2136');

insert into sys_menu
select '2137', '映射撤回申请', '2102', '15', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:tag:mapping:withdraw', '#', 'admin', sysdate(), '', null, ''
from dual where not exists (select 1 from sys_menu where menu_id = '2137');

-- 迁移授权：已有"映射草稿保存(2133)"权限的角色自动获得 2136/2137
insert into sys_role_menu (role_id, menu_id)
select distinct rm.role_id, '2136' from sys_role_menu rm
where rm.menu_id = '2133'
  and not exists (select 1 from sys_role_menu x where x.role_id = rm.role_id and x.menu_id = '2136');

insert into sys_role_menu (role_id, menu_id)
select distinct rm.role_id, '2137' from sys_role_menu rm
where rm.menu_id = '2133'
  and not exists (select 1 from sys_role_menu x where x.role_id = rm.role_id and x.menu_id = '2137');

-- ===================== 5. 存量数据迁移 =====================
-- 历史正式标签保留原状态；无任何审核通过记录的旧同步草稿迁入待完善阶段
update tl_tag t
set t.status = '4'
where t.status = '0'
  and t.create_way = '同步'
  and t.del_flag = '0'
  and not exists (select 1 from tl_audit_log l
                  where l.biz_type in ('tag', 'tagMeta') and l.biz_id = t.tag_id and l.action = '通过')
  and not exists (select 1 from tl_tag_metadata_change c
                  where c.tag_id = t.tag_id and c.status = 'APPROVED');
