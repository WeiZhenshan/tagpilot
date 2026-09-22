-- 补齐智能体工作台一级菜单。V20260921_01 误用 menu_id 2200（对象群已占用），插入被跳过；本脚本改用 2300。
-- 若环境已存在 path=agent 的顶级菜单（例如 2200 当时空闲），则不再插入，只补角色授权。
INSERT INTO sys_menu (menu_id, menu_name, parent_id, order_num, path, component, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time)
SELECT 2300, '智能体工作台', 0, 6, 'agent', 'taglibrary/agent/index', 1, 1, 'C', '0', '0', 'taglibrary:semantic:list', 'message', 'admin', sysdate()
FROM dual
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE menu_id = 2300)
  AND NOT EXISTS (SELECT 1 FROM sys_menu WHERE path = 'agent' AND parent_id = 0);

INSERT INTO sys_role_menu (role_id, menu_id)
SELECT r.role_id, m.menu_id
  FROM sys_role_menu r
  JOIN sys_menu m ON m.path = 'agent' AND m.parent_id = 0 AND m.component = 'taglibrary/agent/index'
 WHERE r.menu_id = 2140
   AND NOT EXISTS (SELECT 1 FROM sys_role_menu x WHERE x.role_id = r.role_id AND x.menu_id = m.menu_id);
