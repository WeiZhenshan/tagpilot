-- ----------------------------------------------------------------------------
-- V20260924_01 洞察 Skill 管理（向前迁移，可重复执行；不得包含 drop table）
-- 内容：
--   1. 运行记录表 tl_skill_run（Java 侧留存，用于权限化查询运行历史）
--   2. 管理动作审计表 tl_skill_audit（发布/下线/废弃/转草稿）
--   3. 菜单 2147 洞察技能 + 按钮 2148 技能查询 / 2149 技能发布下线 / 2150 技能试运行
-- 说明：Skill 定义与执行权威在 tagpilot-agent（Python），本库只保存治理侧留痕
-- ----------------------------------------------------------------------------

-- 1. 运行记录
create table if not exists tl_skill_run (
    run_id          varchar(64)    not null                comment '运行ID（Python 侧生成，全局唯一）',
    skill_id        varchar(64)    not null                comment '技能ID',
    skill_version   varchar(32)             default null   comment '技能版本',
    audience_id     varchar(64)             default null   comment '客群ID（兼容 bigint，统一字符串）',
    audience_name   varchar(128)            default null   comment '客群名称快照',
    customer_count  int(11)        not null default 0       comment '客群成员数',
    status          varchar(16)    not null default 'unknown' comment 'succeeded/blocked/failed',
    blocked_reason  varchar(500)            default null   comment '被阻断原因（中文）',
    duration_ms     bigint(20)              default null   comment '执行耗时（毫秒）',
    operator_id     varchar(64)             default null   comment '操作人ID',
    operator_name   varchar(64)             default null   comment '操作人名称',
    trace_id        varchar(64)             default null   comment '链路追踪ID',
    create_time     datetime                default null   comment '创建时间',
    primary key (run_id),
    key idx_tl_skill_run_skill (skill_id, create_time),
    key idx_tl_skill_run_audience (audience_id, create_time),
    key idx_tl_skill_run_operator (operator_id, create_time)
) engine=innodb comment='洞察Skill-运行记录';

-- 2. 管理动作审计
create table if not exists tl_skill_audit (
    audit_id        bigint(20)     not null auto_increment comment '审计ID',
    skill_id        varchar(64)    not null                comment '技能ID',
    version         varchar(32)             default null   comment '技能版本',
    action          varchar(32)    not null                comment '动作：publish/offline/deprecate/draft',
    operator_id     varchar(64)             default null   comment '操作人ID',
    operator_name   varchar(64)             default null   comment '操作人名称',
    reason          varchar(500)            default null   comment '操作原因',
    result          varchar(500)            default null   comment '执行结果（状态或失败原因）',
    create_time     datetime                default null   comment '创建时间',
    primary key (audit_id),
    key idx_tl_skill_audit_skill (skill_id, create_time)
) engine=innodb auto_increment=1 comment='洞察Skill-管理动作审计';

-- 3. 菜单：洞察技能（挂在 2100 标签库下，order_num 顺延 2146 之后）
INSERT INTO sys_menu (menu_id, menu_name, parent_id, order_num, path, component, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time)
SELECT 2147, '洞察技能', 2100, 8, 'skill', 'taglibrary/skill/index', 1, 0, 'C', '0', '0', 'taglibrary:skill:list', 'chart', 'admin', sysdate()
FROM dual WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE menu_id = 2147);

INSERT INTO sys_menu (menu_id, menu_name, parent_id, order_num, path, component, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time)
SELECT 2148, '技能查询', 2147, 1, '#', '', 1, 0, 'F', '0', '0', 'taglibrary:skill:query', '#', 'admin', sysdate()
FROM dual WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE menu_id = 2148);

INSERT INTO sys_menu (menu_id, menu_name, parent_id, order_num, path, component, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time)
SELECT 2149, '技能发布下线', 2147, 2, '#', '', 1, 0, 'F', '0', '0', 'taglibrary:skill:publish', '#', 'admin', sysdate()
FROM dual WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE menu_id = 2149);

INSERT INTO sys_menu (menu_id, menu_name, parent_id, order_num, path, component, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time)
SELECT 2150, '技能试运行', 2147, 3, '#', '', 1, 0, 'F', '0', '0', 'taglibrary:skill:run', '#', 'admin', sysdate()
FROM dual WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE menu_id = 2150);

-- 4. 角色授权：沿用既有约定，给拥有语义查询按钮(2140)的角色补授新菜单
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT r.role_id, m.menu_id FROM sys_role_menu r JOIN sys_menu m ON m.menu_id IN (2147, 2148, 2149, 2150)
WHERE r.menu_id = 2140 AND NOT EXISTS (SELECT 1 FROM sys_role_menu x WHERE x.role_id = r.role_id AND x.menu_id = m.menu_id);
