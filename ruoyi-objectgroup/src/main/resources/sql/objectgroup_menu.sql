-- ----------------------------
-- 对象群管理模块菜单 SQL（menu_id 2200 起，格式与 taglibrary_menu.sql 一致）
-- ----------------------------
insert into sys_menu values('2200', '对象群', '0', '7', 'objectgroup', null, '', '', 1, 0, 'M', '0', '0', '', 'user', 'admin', sysdate(), '', null, '对象群目录');
insert into sys_menu values('2201', '对象群管理', '2200', '1', 'group', 'objectgroup/list/index', '', '', 1, 0, 'C', '0', '0', 'objectgroup:group:list', 'list', 'admin', sysdate(), '', null, '对象群管理菜单');

-- 对象群按钮
insert into sys_menu values('2202', '对象群查询', '2201', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'objectgroup:group:query', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2203', '对象群新增', '2201', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'objectgroup:group:add', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2204', '对象群修改', '2201', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'objectgroup:group:edit', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2205', '对象群删除', '2201', '4', '#', '', '', '', 1, 0, 'F', '0', '0', 'objectgroup:group:remove', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2206', '运行刷新', '2201', '5', '#', '', '', '', 1, 0, 'F', '0', '0', 'objectgroup:group:run', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2207', '样例预览', '2201', '6', '#', '', '', '', 1, 0, 'F', '0', '0', 'objectgroup:group:preview', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2208', '文件导入', '2201', '7', '#', '', '', '', 1, 0, 'F', '0', '0', 'objectgroup:group:import', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2209', '码值同步', '2201', '8', '#', '', '', '', 1, 0, 'F', '0', '0', 'objectgroup:codevalue:sync', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2210', '码值维护', '2201', '9', '#', '', '', '', 1, 0, 'F', '0', '0', 'objectgroup:codevalue:edit', '#', 'admin', sysdate(), '', null, '');
