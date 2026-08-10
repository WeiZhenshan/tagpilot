-- ----------------------------
-- 对象群管理模块建表 SQL（menu_id 2200 起）
-- ----------------------------
drop table if exists tl_object_group;
create table tl_object_group (
  group_id    bigint(20)   not null auto_increment comment '对象群ID',
  group_name  varchar(64)  not null                comment '对象群名称',
  group_desc  varchar(500) default ''              comment '对象群描述',
  library_id  bigint(20)   not null                comment '关联标签库ID',
  rule_json   text                                 comment '规则JSON（条件行+逻辑+预览列+导入批次引用）',
  group_sql   text                                 comment '最近生成的查询SQL',
  user_count  bigint(20)   default 0               comment '用户数（运行结果）',
  del_flag    char(1)      default '0'             comment '删除标志（0存在 2删除）',
  create_by   varchar(64)  default ''              comment '创建者',
  create_time datetime                             comment '创建时间',
  update_by   varchar(64)  default ''              comment '更新者',
  update_time datetime                             comment '更新时间',
  remark      varchar(500) default null            comment '备注',
  primary key (group_id),
  key idx_tl_og_library (library_id)
) engine=innodb auto_increment=100 comment='对象群表';

-- 标签码值表（选项型/布尔型选项来源，同步+手工维护）
drop table if exists tl_tag_code_value;
create table tl_tag_code_value (
  value_id        bigint(20)   not null auto_increment comment '码值ID',
  library_id      bigint(20)   not null                comment '所属标签库ID',
  field_name      varchar(64)  not null                comment '标签名称（英文，源字段名）',
  tag_name        varchar(128) default ''              comment '标签名称（中文）',
  code            varchar(500) not null                comment '标签码值（宽表存储值）',
  code_definition varchar(500) default ''              comment '码值定义（显示值，选项展示用）',
  order_num       int(4)       default 0               comment '码值排序',
  create_by       varchar(64)  default ''              comment '创建者',
  create_time     datetime                             comment '创建时间',
  update_by       varchar(64)  default ''              comment '更新者',
  update_time     datetime                             comment '最近一次更新日期',
  remark          varchar(500) default null            comment '备注',
  primary key (value_id),
  unique key uk_tl_cv_field_code (library_id, field_name, code)
) engine=innodb auto_increment=100 comment='标签码值表';

-- 对象群导入值表（批次机制：新建页上传时对象群尚不存在，保存后回填 group_id）
drop table if exists tl_object_group_import;
create table tl_object_group_import (
  import_id    bigint(20)  not null auto_increment comment '导入ID',
  import_batch varchar(64) not null                comment '导入批次号（UUID）',
  group_id     bigint(20)  default null            comment '归属对象群ID（保存后回填）',
  field_name   varchar(64) default ''              comment '客户号字段名',
  value        varchar(64) not null                comment '客户号值',
  create_by    varchar(64) default ''              comment '创建者',
  create_time  datetime                            comment '创建时间',
  primary key (import_id),
  key idx_tl_ogi_batch (import_batch),
  key idx_tl_ogi_group (group_id)
) engine=innodb auto_increment=100 comment='对象群导入值表';
