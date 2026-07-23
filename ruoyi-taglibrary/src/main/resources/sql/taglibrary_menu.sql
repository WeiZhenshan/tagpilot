-- ----------------------------
-- 标签库管理模块菜单 SQL（menu_id 2100 起，2000 段已被数据代理占用）
-- sys_menu 共 20 列（含 route_name），每条 insert 20 个值，格式与 databroker_menu.sql 一致。
-- ----------------------------
insert into sys_menu values('2100', '标签库管理', '0', '6', 'taglibrary', null, '', '', 1, 0, 'M', '0', '0', '', 'tag', 'admin', sysdate(), '', null, '标签库管理目录');
insert into sys_menu values('2101', '标签库管理', '2100', '1', 'list', 'taglibrary/list/index', '', '', 1, 0, 'C', '0', '0', 'taglibrary:library:list', 'list', 'admin', sysdate(), '', null, '标签库管理菜单');
insert into sys_menu values('2102', '标签管理', '2100', '2', 'tags', 'taglibrary/tags/index', '', '', 1, 0, 'C', '0', '0', 'taglibrary:tag:list', 'tag', 'admin', sysdate(), '', null, '标签管理菜单');

-- 标签库按钮
insert into sys_menu values('2110', '标签库查询', '2101', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:library:query', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2111', '标签库新增', '2101', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:library:add', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2112', '标签库修改', '2101', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:library:edit', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2113', '标签库删除', '2101', '4', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:library:remove', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2114', '同步字段', '2101', '5', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:library:sync', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2115', '提交审批', '2101', '6', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:library:submit', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2116', '审批', '2101', '7', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:library:audit', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2117', '库下线', '2101', '8', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:library:offline', '#', 'admin', sysdate(), '', null, '');

-- 标签按钮
insert into sys_menu values('2120', '标签查询', '2102', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:tag:query', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2121', '标签修改', '2102', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:tag:edit', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2122', '移动目录', '2102', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:tag:move', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2123', '标签提交审批', '2102', '4', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:tag:submit', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2124', '标签审批', '2102', '5', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:tag:audit', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2125', '标签下线', '2102', '6', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:tag:offline', '#', 'admin', sysdate(), '', null, '');

-- 目录按钮
insert into sys_menu values('2126', '目录查询', '2102', '7', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:dir:list', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2127', '目录新增', '2102', '8', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:dir:add', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2128', '目录修改', '2102', '9', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:dir:edit', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2129', '目录删除', '2102', '10', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:dir:remove', '#', 'admin', sysdate(), '', null, '');

-- 字典：标签对象 / 标签库分类 / 标签类型 / 更新周期
insert into sys_dict_type (dict_name, dict_type, status, create_by, create_time, remark) values
('标签对象', 'tag_object', '0', 'admin', sysdate(), '标签对象字典'),
('标签库分类', 'tag_library_category', '0', 'admin', sysdate(), '标签库分类字典'),
('标签类型', 'tag_type', '0', 'admin', sysdate(), '标签类型字典'),
('更新周期', 'tag_update_cycle', '0', 'admin', sysdate(), '标签更新周期字典');

insert into sys_dict_data (dict_sort, dict_label, dict_value, dict_type, css_class, list_class, is_default, status, create_by, create_time, remark) values
(1, '客户', '客户', 'tag_object', '', 'default', 'Y', '0', 'admin', sysdate(), ''),
(2, '企业', '企业', 'tag_object', '', 'default', 'N', '0', 'admin', sysdate(), ''),
(3, '机构', '机构', 'tag_object', '', 'default', 'N', '0', 'admin', sysdate(), ''),
(4, '商户', '商户', 'tag_object', '', 'default', 'N', '0', 'admin', sysdate(), ''),
(1, '客户维度', '客户维度', 'tag_library_category', '', 'default', 'Y', '0', 'admin', sysdate(), ''),
(2, '产品维度', '产品维度', 'tag_library_category', '', 'default', 'N', '0', 'admin', sysdate(), ''),
(3, '员工维度', '员工维度', 'tag_library_category', '', 'default', 'N', '0', 'admin', sysdate(), ''),
(4, '交易维度', '交易维度', 'tag_library_category', '', 'default', 'N', '0', 'admin', sysdate(), ''),
(5, '营销维度', '营销维度', 'tag_library_category', '', 'default', 'N', '0', 'admin', sysdate(), ''),
(1, '选项型', '选项型', 'tag_type', '', 'default', 'N', '0', 'admin', sysdate(), ''),
(2, '布尔型', '布尔型', 'tag_type', '', 'success', 'N', '0', 'admin', sysdate(), ''),
(3, '数值型', '数值型', 'tag_type', '', 'primary', 'N', '0', 'admin', sysdate(), ''),
(4, '文本型', '文本型', 'tag_type', '', 'info', 'N', '0', 'admin', sysdate(), ''),
(5, '日期型', '日期型', 'tag_type', '', 'warning', 'N', '0', 'admin', sysdate(), ''),
(1, '日', '日', 'tag_update_cycle', '', 'default', 'Y', '0', 'admin', sysdate(), ''),
(2, '周', '周', 'tag_update_cycle', '', 'default', 'N', '0', 'admin', sysdate(), ''),
(3, '月', '月', 'tag_update_cycle', '', 'default', 'N', '0', 'admin', sysdate(), '');
