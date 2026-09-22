-- 新增页面，不提升任何角色的编辑、复核、发布权限。
INSERT INTO sys_menu (menu_id, menu_name, parent_id, order_num, path, component, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time)
SELECT 2145, '标签语义维护', 2100, 6, 'semantic', 'taglibrary/semantic/index', 1, 0, 'C', '0', '0', 'taglibrary:semantic:list', 'education', 'admin', sysdate()
FROM dual WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE menu_id = 2145);
INSERT INTO sys_menu (menu_id, menu_name, parent_id, order_num, path, component, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time)
SELECT 2146, '语义快照与索引', 2100, 7, 'semantic-index', 'taglibrary/semantic-index/index', 1, 0, 'C', '0', '0', 'taglibrary:semantic:list', 'server', 'admin', sysdate()
FROM dual WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE menu_id = 2146);
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT r.role_id, m.menu_id FROM sys_role_menu r JOIN sys_menu m ON m.menu_id IN (2145, 2146)
WHERE r.menu_id = 2140 AND NOT EXISTS (SELECT 1 FROM sys_role_menu x WHERE x.role_id = r.role_id AND x.menu_id = m.menu_id);
