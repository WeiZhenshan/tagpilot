-- 数据集管理菜单（挂在 2000 数据代理 目录下）
insert into sys_menu values('2020', '数据集管理', '2000', '2', 'dataset', 'databroker/dataset/index', '', '', 1, 0, 'C', '0', '0', 'databroker:dataset:list', 'component', 'admin', sysdate(), '', null, '数据集管理菜单');

insert into sys_menu values('2021', '数据集查询', '2020', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:dataset:query', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2022', '数据集新增', '2020', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:dataset:add', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2023', '数据集修改', '2020', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:dataset:edit', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2024', '数据集删除', '2020', '4', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:dataset:remove', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2025', '数据预览', '2020', '5', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:dataset:preview', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2026', '版本发布', '2020', '6', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:dataset:publish', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2027', '版本下线', '2020', '7', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:dataset:offline', '#', 'admin', sysdate(), '', null, '');

-- 数据集目录管理按钮
insert into sys_menu values('2028', '数据集目录列表', '2020', '8', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:dataset:catalog:list', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2029', '数据集目录新增', '2020', '9', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:dataset:catalog:add', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2030', '数据集目录修改', '2020', '10', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:dataset:catalog:edit', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2031', '数据集目录删除', '2020', '11', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:dataset:catalog:remove', '#', 'admin', sysdate(), '', null, '');
