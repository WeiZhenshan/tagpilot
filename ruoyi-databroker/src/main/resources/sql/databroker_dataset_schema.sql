drop table if exists dp_dataset_catalog;
create table dp_dataset_catalog (
  catalog_id      bigint(20)    not null auto_increment comment '目录ID',
  parent_id       bigint(20)    default 0                comment '父目录ID',
  ancestors       varchar(500)  default ''               comment '祖级列表',
  catalog_name    varchar(100)  not null                 comment '目录名称',
  order_num       int(4)        default 0                comment '显示顺序',
  status          char(1)       default '0'              comment '状态（0正常 1停用）',
  create_by       varchar(64)   default ''               comment '创建者',
  create_time     datetime                               comment '创建时间',
  update_by       varchar(64)   default ''               comment '更新者',
  update_time     datetime                               comment '更新时间',
  remark          varchar(500)  default null             comment '备注',
  primary key (catalog_id),
  key idx_dp_dataset_catalog_parent (parent_id)
) engine=innodb auto_increment=100 comment='数据集目录表';

drop table if exists dp_dataset;
create table dp_dataset (
  dataset_id         bigint(20)    not null auto_increment comment '数据集ID',
  catalog_id         bigint(20)    default 0                comment '目录ID',
  dataset_code       varchar(64)   not null                 comment '数据集编码',
  dataset_name       varchar(100)  not null                 comment '数据集名称',
  datasource_id      bigint(20)    not null                 comment '数据源ID',
  default_version_id bigint(20)    default null             comment '默认在线版本ID',
  latest_version_no  int(8)        default 0                comment '最新版本号',
  owner_name         varchar(64)   default ''               comment '负责人',
  status             char(1)       default '0'              comment '状态（0正常 1停用）',
  del_flag           char(1)       default '0'              comment '删除标志（0存在 2删除）',
  create_by          varchar(64)   default ''               comment '创建者',
  create_time        datetime                               comment '创建时间',
  update_by          varchar(64)   default ''               comment '更新者',
  update_time        datetime                               comment '更新时间',
  remark             varchar(500)  default null             comment '备注',
  primary key (dataset_id),
  unique key uk_dp_dataset_code (dataset_code, del_flag),
  key idx_dp_dataset_catalog (catalog_id),
  key idx_dp_dataset_source (datasource_id)
) engine=innodb auto_increment=100 comment='数据集主档表';

drop table if exists dp_dataset_version;
create table dp_dataset_version (
  version_id         bigint(20)    not null auto_increment comment '版本ID',
  dataset_id         bigint(20)    not null                 comment '数据集ID',
  version_no         int(8)        not null                 comment '版本号',
  version_name       varchar(100)  default ''               comment '版本名称',
  definition_json    longtext      not null                 comment '结构化定义JSON',
  schema_version     int(4)        default 1                comment '定义结构版本',
  revision           int(8)        default 0                comment '乐观锁版本',
  version_status     varchar(16)   default 'DRAFT'          comment '版本状态（DRAFT ONLINE OFFLINE）',
  health_status      varchar(16)   default 'INVALID'        comment '健康状态（VALID INVALID）',
  validation_message varchar(2000) default ''               comment '校验信息',
  release_note       varchar(500)  default ''               comment '发布说明',
  publish_by         varchar(64)   default ''               comment '发布人',
  publish_time       datetime                               comment '发布时间',
  create_by          varchar(64)   default ''               comment '创建者',
  create_time        datetime                               comment '创建时间',
  update_by          varchar(64)   default ''               comment '更新者',
  update_time        datetime                               comment '更新时间',
  primary key (version_id),
  unique key uk_dp_dataset_version (dataset_id, version_no),
  key idx_dp_dataset_version_status (dataset_id, version_status)
) engine=innodb auto_increment=100 comment='数据集版本表';

drop table if exists dp_dataset_field;
create table dp_dataset_field (
  field_id          bigint(20)    not null auto_increment comment '字段ID',
  version_id        bigint(20)    not null                 comment '版本ID',
  field_alias       varchar(128)  not null                 comment '输出字段别名',
  field_name        varchar(128)  default ''               comment '来源物理字段名',
  source_table_id   bigint(20)    default null             comment '来源表元数据ID',
  source_column_id  bigint(20)    default null             comment '来源字段元数据ID',
  data_type         varchar(32)   not null                 comment '数据类型',
  expression_json   longtext                               comment '表达式JSON（预留）',
  is_object_key     char(1)       default '0'              comment '是否对象键（预留）',
  sensitivity_level varchar(32)   default 'INTERNAL'       comment '敏感级别（预留）',
  mask_rule         varchar(32)   default 'NONE'           comment '脱敏规则（预留）',
  enabled           char(1)       default '1'              comment '是否启用（0否 1是）',
  order_num         int(4)        default 0                comment '显示顺序',
  primary key (field_id),
  unique key uk_dp_dataset_field (version_id, field_alias),
  key idx_dp_dataset_field_source (source_column_id)
) engine=innodb auto_increment=100 comment='数据集输出字段表';

drop table if exists dp_dataset_dependency;
create table dp_dataset_dependency (
  dependency_id   bigint(20)   not null auto_increment comment '依赖ID',
  dataset_id      bigint(20)   not null                 comment '数据集ID',
  version_id      bigint(20)   not null                 comment '版本ID',
  datasource_id   bigint(20)   not null                 comment '数据源ID',
  table_id        bigint(20)   not null                 comment '表元数据ID',
  column_id       bigint(20)   default null             comment '字段元数据ID',
  dependency_type varchar(16)  not null                 comment '依赖类型（TABLE COLUMN）',
  create_time     datetime     not null                 comment '创建时间',
  primary key (dependency_id),
  key idx_dp_dataset_dep_version (version_id),
  key idx_dp_dataset_dep_source (datasource_id),
  key idx_dp_dataset_dep_table (table_id),
  key idx_dp_dataset_dep_column (column_id)
) engine=innodb auto_increment=100 comment='数据集元数据依赖表';

drop table if exists dp_dataset_log;
create table dp_dataset_log (
  log_id        bigint(20)    not null auto_increment comment '日志ID',
  dataset_id    bigint(20)    default null             comment '数据集ID',
  version_id    bigint(20)    default null             comment '版本ID',
  oper_type     varchar(30)   not null                 comment '操作类型（INSERT UPDATE DELETE SAVE COPY PUBLISH OFFLINE PREVIEW）',
  operator_name varchar(64)   default ''               comment '操作人',
  result        char(1)       default '1'              comment '结果（1成功 0失败）',
  message       varchar(1000) default ''               comment '日志消息',
  detail_json   text                                   comment '详情JSON',
  oper_time     datetime      not null                 comment '操作时间',
  primary key (log_id),
  key idx_dp_dataset_log_dataset (dataset_id),
  key idx_dp_dataset_log_time (oper_time)
) engine=innodb auto_increment=100 comment='数据集操作日志表';
