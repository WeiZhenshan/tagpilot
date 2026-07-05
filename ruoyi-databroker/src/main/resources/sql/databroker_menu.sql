insert into sys_menu values('2000', '数据代理', '0', '5', 'databroker', null, '', '', 1, 0, 'M', '0', '0', '', 'database', 'admin', sysdate(), '', null, '数据代理目录');
insert into sys_menu values('2001', '数据源管理', '2000', '1', 'datasource', 'databroker/datasource/index', '', '', 1, 0, 'C', '0', '0', 'databroker:datasource:list', 'druid', 'admin', sysdate(), '', null, '数据源管理菜单');

insert into sys_menu values('2002', '数据源查询', '2001', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:datasource:query', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2003', '数据源新增', '2001', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:datasource:add', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2004', '数据源修改', '2001', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:datasource:edit', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2005', '数据源删除', '2001', '4', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:datasource:remove', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2006', '测试连接', '2001', '5', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:datasource:test', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2007', '同步元数据', '2001', '6', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:datasource:sync', '#', 'admin', sysdate(), '', null, '');
