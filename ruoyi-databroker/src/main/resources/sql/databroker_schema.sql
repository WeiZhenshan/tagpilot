drop table if exists dp_datasource_catalog;
create table dp_datasource_catalog (
  catalog_id      bigint(20)    not null auto_increment comment '目录ID',
  parent_id       bigint(20)    default 0                comment '父目录ID',
  ancestors       varchar(500)  default ''               comment '祖级列表',
  catalog_name    varchar(100)  not null                 comment '目录名称',
  order_num       int(4)        default 0                comment '显示顺序',
  status          char(1)       default '0'              comment '状态（0正常 1停用）',
  create_by       varchar(64)   default ''               comment '创建者',
  create_time     datetime                              comment '创建时间',
  update_by       varchar(64)   default ''               comment '更新者',
  update_time     datetime                              comment '更新时间',
  remark          varchar(500)  default null             comment '备注',
  primary key (catalog_id)
) engine=innodb auto_increment=100 comment='数据源目录表';

drop table if exists dp_datasource;
create table dp_datasource (
  datasource_id    bigint(20)    not null auto_increment comment '数据源ID',
  catalog_id       bigint(20)    default 0                comment '所属目录ID',
  source_name      varchar(100)  not null                 comment '数据源名称',
  source_type      varchar(30)   default 'MYSQL'          comment '数据源类型',
  host             varchar(255)  not null                 comment '主机地址',
  port             int(6)        not null                 comment '端口',
  database_name    varchar(128)  not null                 comment '数据库名称',
  username         varchar(128)  not null                 comment '用户名',
  password_cipher  varchar(1000) default ''               comment '加密密码',
  db_version       varchar(100)  default ''               comment '数据库版本',
  use_pool         char(1)       default '0'              comment '是否使用连接池（0否 1是）',
  use_ssl          char(1)       default '0'              comment '是否启用SSL（0否 1是）',
  ca_cert          text                                   comment 'CA证书',
  jdbc_params      varchar(1000) default ''               comment 'JDBC扩展参数JSON',
  status           char(1)       default '0'              comment '状态（0正常 1停用）',
  usage_count      bigint(20)    default 0                comment '使用量',
  last_sync_time   datetime                              comment '最近同步时间',
  last_sync_status char(1)       default '0'              comment '最近同步状态（0未同步 1成功 2失败）',
  last_error_msg   varchar(1000) default ''               comment '最近错误信息',
  del_flag         char(1)       default '0'              comment '删除标志（0存在 2删除）',
  create_by        varchar(64)   default ''               comment '创建者',
  create_time      datetime                              comment '创建时间',
  update_by        varchar(64)   default ''               comment '更新者',
  update_time      datetime                              comment '更新时间',
  remark           varchar(500)  default null             comment '备注',
  primary key (datasource_id),
  key idx_dp_datasource_catalog (catalog_id),
  unique key uk_dp_datasource_name (source_name, del_flag)
) engine=innodb auto_increment=100 comment='数据源配置表';

drop table if exists dp_meta_table;
create table dp_meta_table (
  table_id        bigint(20)    not null auto_increment comment '表元数据ID',
  datasource_id   bigint(20)    not null                 comment '数据源ID',
  object_name     varchar(200)  not null                 comment '表或视图名称',
  object_type     varchar(20)   not null                 comment '对象类型（TABLE VIEW）',
  table_comment   varchar(500)  default ''               comment '原始备注',
  cn_name         varchar(100)  default ''               comment '中文名',
  row_count       bigint(20)    default null             comment '行数',
  column_count    int(8)        default 0                comment '字段数',
  usage_count     bigint(20)    default 0                comment '使用量',
  sync_batch_no   varchar(64)   default ''               comment '同步批次号',
  status          char(1)       default '0'              comment '状态（0正常 1失效）',
  create_by       varchar(64)   default ''               comment '创建者',
  create_time     datetime                              comment '创建时间',
  update_by       varchar(64)   default ''               comment '更新者',
  update_time     datetime                              comment '更新时间',
  remark          varchar(500)  default null             comment '备注',
  primary key (table_id),
  unique key uk_dp_meta_table (datasource_id, object_name),
  key idx_dp_meta_table_source (datasource_id)
) engine=innodb auto_increment=100 comment='数据源表视图元数据表';

drop table if exists dp_meta_column;
create table dp_meta_column (
  column_id              bigint(20)    not null auto_increment comment '字段元数据ID',
  table_id               bigint(20)    not null                 comment '表元数据ID',
  datasource_id          bigint(20)    not null                 comment '数据源ID',
  object_name            varchar(200)  not null                 comment '表或视图名称',
  column_name            varchar(200)  not null                 comment '字段名',
  ordinal_position       int(8)        not null                 comment '字段序号',
  column_type            varchar(200)  default ''               comment '完整字段类型',
  data_type              varchar(100)  default ''               comment '基础数据类型',
  is_nullable            char(1)       default '1'              comment '是否可为空（0否 1是）',
  column_default         varchar(500)  default null             comment '默认值',
  column_comment         varchar(500)  default ''               comment '字段备注',
  is_pk                  char(1)       default '0'              comment '是否主键（0否 1是）',
  is_fk                  char(1)       default '0'              comment '是否外键（0否 1是）',
  referenced_table_name  varchar(200)  default ''               comment '引用表名',
  referenced_column_name varchar(200)  default ''               comment '引用字段名',
  sync_batch_no          varchar(64)   default ''               comment '同步批次号',
  create_by              varchar(64)   default ''               comment '创建者',
  create_time            datetime                              comment '创建时间',
  update_by              varchar(64)   default ''               comment '更新者',
  update_time            datetime                              comment '更新时间',
  primary key (column_id),
  unique key uk_dp_meta_column (table_id, column_name),
  key idx_dp_meta_column_source (datasource_id, object_name)
) engine=innodb auto_increment=100 comment='数据源字段元数据表';

drop table if exists dp_datasource_log;
create table dp_datasource_log (
  log_id          bigint(20)    not null auto_increment comment '日志ID',
  datasource_id   bigint(20)    default null             comment '数据源ID',
  log_type        varchar(30)   not null                 comment '日志类型（INSERT UPDATE DELETE TEST SYNC CN_NAME）',
  operator_name   varchar(64)   default ''               comment '操作人',
  result          char(1)       default '1'              comment '结果（1成功 0失败）',
  message         varchar(1000) default ''               comment '日志消息',
  detail_json     text                                   comment '详情JSON',
  oper_time       datetime      not null                 comment '操作时间',
  primary key (log_id),
  key idx_dp_datasource_log_source (datasource_id),
  key idx_dp_datasource_log_time (oper_time)
) engine=innodb auto_increment=100 comment='数据源操作日志表';
