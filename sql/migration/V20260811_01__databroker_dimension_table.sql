-- ----------------------------------------------------------------------------
-- V20260811_01 维表管理迁移（向前迁移，可重复执行；不得包含 drop table）
-- 来源：ruoyi-databroker/src/main/resources/sql/databroker_dimension_migration.sql
-- 内容：dp_dimension_table 登记表 + 维表管理菜单（menu_id 2040-2046，挂在 2000 数据代理目录下）
-- 说明：菜单插入已统一加 not exists 守卫，保证幂等
-- ----------------------------------------------------------------------------

-- 维表登记表（只登记元数据，不存储码值，码值留在外部物理维表）
create table if not exists dp_dimension_table (
    dimension_id       bigint(20)   not null auto_increment    comment '维表ID',
    dimension_name     varchar(128) not null default ''        comment '维表名称（中文业务名）',
    dimension_code     varchar(64)  not null default ''        comment '维表名（平台唯一英文编码）',
    datasource_id      bigint(20)   not null                   comment '数据连接ID（dp_datasource.datasource_id）',
    source_table_id    bigint(20)   not null                   comment '原始物理表ID（dp_meta_table.table_id）',
    source_table_name  varchar(128) not null default ''        comment '原始表名（登记时物理表名快照）',
    status             char(1)      not null default '0'       comment '状态（0启用 1停用）',
    del_flag           char(1)      not null default '0'       comment '删除标志（0存在 2删除）',
    create_by          varchar(64)           default ''        comment '创建者',
    create_time        datetime              default null      comment '创建时间',
    update_by          varchar(64)           default ''        comment '更新者',
    update_time        datetime              default null      comment '更新时间',
    remark             varchar(500)          default null      comment '备注',
    primary key (dimension_id),
    unique key uk_dp_dimension_code (dimension_code),
    unique key uk_dp_dimension_source (datasource_id, source_table_id)
) engine=innodb auto_increment=1 comment='维表登记表';

-- ----------------------------
-- 维表管理菜单（2040）与按钮（2041-2046）
-- sys_menu 共 20 列（含 route_name），格式与 databroker_menu.sql 一致
-- ----------------------------
insert into sys_menu select '2040', '维表管理', '2000', '3', 'dimension', 'databroker/dimension/index', '', '', 1, 0, 'C', '0', '0', 'databroker:dimension:list', 'table', 'admin', sysdate(), '', null, '维表管理菜单' from dual where not exists (select 1 from sys_menu where menu_id = '2040');
insert into sys_menu select '2041', '维表查询', '2040', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:dimension:query', '#', 'admin', sysdate(), '', null, '' from dual where not exists (select 1 from sys_menu where menu_id = '2041');
insert into sys_menu select '2042', '维表新增', '2040', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:dimension:add', '#', 'admin', sysdate(), '', null, '' from dual where not exists (select 1 from sys_menu where menu_id = '2042');
insert into sys_menu select '2043', '维表修改', '2040', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:dimension:edit', '#', 'admin', sysdate(), '', null, '' from dual where not exists (select 1 from sys_menu where menu_id = '2043');
insert into sys_menu select '2044', '维表删除', '2040', '4', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:dimension:remove', '#', 'admin', sysdate(), '', null, '' from dual where not exists (select 1 from sys_menu where menu_id = '2044');
insert into sys_menu select '2045', '状态切换', '2040', '5', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:dimension:status', '#', 'admin', sysdate(), '', null, '' from dual where not exists (select 1 from sys_menu where menu_id = '2045');
insert into sys_menu select '2046', '码值预览', '2040', '6', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:dimension:preview', '#', 'admin', sysdate(), '', null, '' from dual where not exists (select 1 from sys_menu where menu_id = '2046');
