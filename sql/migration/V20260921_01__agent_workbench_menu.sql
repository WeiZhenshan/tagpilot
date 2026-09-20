-- 一级菜单：智能体工作台。权限沿用 taglibrary:semantic:list，不扩大编辑、复核、发布。
-- 顶级 C 菜单经 isMenuFrame 注册为 /agent，供侧栏常驻入口与工作台深链共用。
INSERT INTO sys_menu (menu_id, menu_name, parent_id, order_num, path, component, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time)
SELECT 2200, '智能体工作台', 0, 6, 'agent', 'taglibrary/agent/index', 1, 1, 'C', '0', '0', 'taglibrary:semantic:list', 'message', 'admin', sysdate()
FROM dual WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE menu_id = 2200);

INSERT INTO sys_role_menu (role_id, menu_id)
SELECT r.role_id, 2200 FROM sys_role_menu r
WHERE r.menu_id = 2140
  AND NOT EXISTS (SELECT 1 FROM sys_role_menu x WHERE x.role_id = r.role_id AND x.menu_id = 2200);
