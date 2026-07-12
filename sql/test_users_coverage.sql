-- -----------------------------------------------------------------------------
-- RuoYi-Vue 测试用户数据（可重复导入）
--
-- 基线：sql/ry_20260417.sql。
-- 密码：所有可登录账号均为 admin123。
-- 本脚本会先删除本脚本创建的 qa_* 用户、岗位/角色关联及 qa_scope_* 角色，
-- 再重新插入；不会修改 admin、ry 或其他业务数据。
--
-- 覆盖场景：
--   账号状态：正常、停用、逻辑删除；角色状态：正常、停用、无角色；
--   数据范围：全部、自定义、本部门、本部门及以下、仅本人、多角色并集；
--   组织/属性：不同部门、无部门、男女未知、单岗位与多岗位。
--
-- 说明：角色菜单权限从当前基线的“普通角色”(role_key = common)复制，以保证
-- 每种数据范围均可访问用户列表接口。脚本需在 ry_20260417.sql 导入后执行。
-- -----------------------------------------------------------------------------

START TRANSACTION;

-- 清理旧的测试用户关联。角色条件可处理上次脚本执行后遗留的关联关系。
DELETE ur
FROM sys_user_role ur
LEFT JOIN sys_user u ON u.user_id = ur.user_id
LEFT JOIN sys_role r ON r.role_id = ur.role_id
WHERE u.user_name IN (
    'qa_all_scope', 'qa_custom_scope', 'qa_dept_scope', 'qa_dept_child',
    'qa_self_scope', 'qa_multi_scope', 'qa_no_role', 'qa_role_disabled',
    'qa_user_disabled', 'qa_soft_deleted'
) OR r.role_key IN (
    'qa_scope_all', 'qa_scope_custom', 'qa_scope_dept', 'qa_scope_dept_child',
    'qa_scope_self', 'qa_scope_role_disabled'
);

DELETE up
FROM sys_user_post up
INNER JOIN sys_user u ON u.user_id = up.user_id
WHERE u.user_name IN (
    'qa_all_scope', 'qa_custom_scope', 'qa_dept_scope', 'qa_dept_child',
    'qa_self_scope', 'qa_multi_scope', 'qa_no_role', 'qa_role_disabled',
    'qa_user_disabled', 'qa_soft_deleted'
);

DELETE FROM sys_user
WHERE user_name IN (
    'qa_all_scope', 'qa_custom_scope', 'qa_dept_scope', 'qa_dept_child',
    'qa_self_scope', 'qa_multi_scope', 'qa_no_role', 'qa_role_disabled',
    'qa_user_disabled', 'qa_soft_deleted'
);

DELETE rm
FROM sys_role_menu rm
INNER JOIN sys_role r ON r.role_id = rm.role_id
WHERE r.role_key IN (
    'qa_scope_all', 'qa_scope_custom', 'qa_scope_dept', 'qa_scope_dept_child',
    'qa_scope_self', 'qa_scope_role_disabled'
);

DELETE rd
FROM sys_role_dept rd
INNER JOIN sys_role r ON r.role_id = rd.role_id
WHERE r.role_key IN (
    'qa_scope_all', 'qa_scope_custom', 'qa_scope_dept', 'qa_scope_dept_child',
    'qa_scope_self', 'qa_scope_role_disabled'
);

DELETE FROM sys_role
WHERE role_key IN (
    'qa_scope_all', 'qa_scope_custom', 'qa_scope_dept', 'qa_scope_dept_child',
    'qa_scope_self', 'qa_scope_role_disabled'
);

-- 数据范围角色：1全部、2自定义、3本部门、4本部门及以下、5仅本人。
INSERT INTO sys_role
    (role_name, role_key, role_sort, data_scope, menu_check_strictly, dept_check_strictly,
     status, del_flag, create_by, create_time, remark)
VALUES
    ('QA-全部数据',       'qa_scope_all',           901, '1', 1, 1, '0', '0', 'admin', SYSDATE(), '测试：全部数据范围'),
    ('QA-自定义数据',     'qa_scope_custom',        902, '2', 1, 1, '0', '0', 'admin', SYSDATE(), '测试：自定义数据范围（研发部门、长沙市场部门）'),
    ('QA-本部门数据',     'qa_scope_dept',          903, '3', 1, 1, '0', '0', 'admin', SYSDATE(), '测试：仅本部门数据范围'),
    ('QA-本部门及以下',   'qa_scope_dept_child',    904, '4', 1, 1, '0', '0', 'admin', SYSDATE(), '测试：本部门及下级部门数据范围'),
    ('QA-仅本人数据',     'qa_scope_self',          905, '5', 1, 1, '0', '0', 'admin', SYSDATE(), '测试：仅本人数据范围'),
    ('QA-停用角色',       'qa_scope_role_disabled', 906, '1', 1, 1, '1', '0', 'admin', SYSDATE(), '测试：停用角色；账号可登录但没有菜单和接口权限');

-- 各 QA 角色复用当前 SQL 中普通角色（role_key=common）的全部菜单权限。
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT qa_role.role_id, base_role_menu.menu_id
FROM sys_role qa_role
CROSS JOIN sys_role_menu base_role_menu
INNER JOIN sys_role base_role ON base_role.role_id = base_role_menu.role_id
    AND base_role.role_key = 'common'
WHERE qa_role.role_key IN (
    'qa_scope_all', 'qa_scope_custom', 'qa_scope_dept', 'qa_scope_dept_child',
    'qa_scope_self', 'qa_scope_role_disabled'
);

-- 自定义数据范围：覆盖深圳研发部门(103)与长沙市场部门(108)，用于跨分支数据验证。
INSERT INTO sys_role_dept (role_id, dept_id)
SELECT r.role_id, d.dept_id
FROM sys_role r
INNER JOIN sys_dept d ON d.dept_id IN (103, 108)
WHERE r.role_key = 'qa_scope_custom';

-- BCrypt 哈希与当前初始化账号相同，对应明文密码 admin123。
INSERT INTO sys_user
    (dept_id, user_name, nick_name, user_type, email, phonenumber, sex, avatar, password,
     status, del_flag, login_ip, login_date, pwd_update_date, create_by, create_time, remark)
VALUES
    (103,  'qa_all_scope',     '全量数据测试',   '00', 'qa_all_scope@example.test',     '13900000001', '0', '', '$2a$10$7JB720yubVSZvUI0rEqK/.VqGOZTH.ulu33dHOiBE8ByOhJIrdAu2', '0', '0', '', NULL, SYSDATE(), 'admin', SYSDATE(), '正常账号：全部数据范围、多岗位'),
    (105,  'qa_custom_scope',  '自定义范围测试', '00', 'qa_custom_scope@example.test',  '13900000002', '1', '', '$2a$10$7JB720yubVSZvUI0rEqK/.VqGOZTH.ulu33dHOiBE8ByOhJIrdAu2', '0', '0', '', NULL, SYSDATE(), 'admin', SYSDATE(), '正常账号：自定义范围，部门103和108'),
    (105,  'qa_dept_scope',    '本部门范围测试', '00', 'qa_dept_scope@example.test',    '13900000003', '2', '', '$2a$10$7JB720yubVSZvUI0rEqK/.VqGOZTH.ulu33dHOiBE8ByOhJIrdAu2', '0', '0', '', NULL, SYSDATE(), 'admin', SYSDATE(), '正常账号：仅测试部门(105)数据'),
    (101,  'qa_dept_child',    '部门下级测试',   '00', 'qa_dept_child@example.test',    '13900000004', '0', '', '$2a$10$7JB720yubVSZvUI0rEqK/.VqGOZTH.ulu33dHOiBE8ByOhJIrdAu2', '0', '0', '', NULL, SYSDATE(), 'admin', SYSDATE(), '正常账号：深圳总公司(101)及所有下级部门数据'),
    (104,  'qa_self_scope',    '仅本人范围测试', '00', 'qa_self_scope@example.test',    '13900000005', '1', '', '$2a$10$7JB720yubVSZvUI0rEqK/.VqGOZTH.ulu33dHOiBE8ByOhJIrdAu2', '0', '0', '', NULL, SYSDATE(), 'admin', SYSDATE(), '正常账号：仅本人数据范围'),
    (101,  'qa_multi_scope',   '多角色并集测试', '00', 'qa_multi_scope@example.test',   '13900000006', '2', '', '$2a$10$7JB720yubVSZvUI0rEqK/.VqGOZTH.ulu33dHOiBE8ByOhJIrdAu2', '0', '0', '', NULL, SYSDATE(), 'admin', SYSDATE(), '正常账号：本部门(101)与自定义部门(103、108)范围并集'),
    (NULL, 'qa_no_role',       '无角色测试',     '00', 'qa_no_role@example.test',       '13900000007', '0', '', '$2a$10$7JB720yubVSZvUI0rEqK/.VqGOZTH.ulu33dHOiBE8ByOhJIrdAu2', '0', '0', '', NULL, SYSDATE(), 'admin', SYSDATE(), '正常账号：无部门、无角色；可登录但无菜单/接口权限'),
    (107,  'qa_role_disabled', '停用角色测试',   '00', 'qa_role_disabled@example.test', '13900000008', '1', '', '$2a$10$7JB720yubVSZvUI0rEqK/.VqGOZTH.ulu33dHOiBE8ByOhJIrdAu2', '0', '0', '', NULL, SYSDATE(), 'admin', SYSDATE(), '正常账号：仅关联停用角色；可登录但无菜单/接口权限'),
    (109,  'qa_user_disabled', '停用账号测试',   '00', 'qa_user_disabled@example.test', '13900000009', '2', '', '$2a$10$7JB720yubVSZvUI0rEqK/.VqGOZTH.ulu33dHOiBE8ByOhJIrdAu2', '1', '0', '', NULL, SYSDATE(), 'admin', SYSDATE(), '停用账号：登录应返回账号已停用'),
    (108,  'qa_soft_deleted',  '逻辑删除测试',   '00', 'qa_soft_deleted@example.test',  '13900000010', '0', '', '$2a$10$7JB720yubVSZvUI0rEqK/.VqGOZTH.ulu33dHOiBE8ByOhJIrdAu2', '0', '2', '', NULL, SYSDATE(), 'admin', SYSDATE(), '逻辑删除账号：用户列表与登录查询均不应返回');

-- 用户与角色：qa_multi_scope 同时拥有“本部门”和“自定义”角色，用于验证范围并集。
INSERT INTO sys_user_role (user_id, role_id)
SELECT u.user_id, r.role_id
FROM sys_user u
INNER JOIN sys_role r ON
    (u.user_name = 'qa_all_scope'     AND r.role_key = 'qa_scope_all') OR
    (u.user_name = 'qa_custom_scope'  AND r.role_key = 'qa_scope_custom') OR
    (u.user_name = 'qa_dept_scope'    AND r.role_key = 'qa_scope_dept') OR
    (u.user_name = 'qa_dept_child'    AND r.role_key = 'qa_scope_dept_child') OR
    (u.user_name = 'qa_self_scope'    AND r.role_key = 'qa_scope_self') OR
    (u.user_name = 'qa_multi_scope'   AND r.role_key IN ('qa_scope_dept', 'qa_scope_custom')) OR
    (u.user_name = 'qa_role_disabled' AND r.role_key = 'qa_scope_role_disabled') OR
    (u.user_name = 'qa_user_disabled' AND r.role_key = 'qa_scope_all');

-- 用户与岗位：qa_all_scope 同时关联董事长和项目经理，覆盖多岗位展示。
INSERT INTO sys_user_post (user_id, post_id)
SELECT u.user_id, p.post_id
FROM sys_user u
INNER JOIN sys_post p ON
    (u.user_name = 'qa_all_scope'      AND p.post_code IN ('ceo', 'se')) OR
    (u.user_name = 'qa_custom_scope'   AND p.post_code = 'user') OR
    (u.user_name = 'qa_dept_scope'     AND p.post_code = 'user') OR
    (u.user_name = 'qa_dept_child'     AND p.post_code = 'se') OR
    (u.user_name = 'qa_self_scope'     AND p.post_code = 'hr') OR
    (u.user_name = 'qa_multi_scope'    AND p.post_code IN ('ceo', 'se')) OR
    (u.user_name = 'qa_no_role'        AND p.post_code = 'user') OR
    (u.user_name = 'qa_role_disabled'  AND p.post_code = 'user') OR
    (u.user_name = 'qa_user_disabled'  AND p.post_code = 'hr') OR
    (u.user_name = 'qa_soft_deleted'   AND p.post_code = 'user');

COMMIT;

-- 导入后可用以下语句核对（按需执行）：
-- SELECT u.user_name, u.status, u.del_flag, d.dept_name,
--        GROUP_CONCAT(DISTINCT r.role_key ORDER BY r.role_key) AS roles,
--        GROUP_CONCAT(DISTINCT p.post_name ORDER BY p.post_id) AS posts
-- FROM sys_user u
-- LEFT JOIN sys_dept d ON d.dept_id = u.dept_id
-- LEFT JOIN sys_user_role ur ON ur.user_id = u.user_id
-- LEFT JOIN sys_role r ON r.role_id = ur.role_id
-- LEFT JOIN sys_user_post up ON up.user_id = u.user_id
-- LEFT JOIN sys_post p ON p.post_id = up.post_id
-- WHERE u.user_name IN (
--     'qa_all_scope', 'qa_custom_scope', 'qa_dept_scope', 'qa_dept_child',
--     'qa_self_scope', 'qa_multi_scope', 'qa_no_role', 'qa_role_disabled',
--     'qa_user_disabled', 'qa_soft_deleted'
-- )
-- GROUP BY u.user_id, u.user_name, u.status, u.del_flag, d.dept_name
-- ORDER BY u.user_name;
