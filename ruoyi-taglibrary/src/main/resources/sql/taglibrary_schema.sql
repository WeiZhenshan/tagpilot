-- ----------------------------
-- 标签库管理模块表结构
-- ----------------------------
drop table if exists tl_tag_library;
create table tl_tag_library (
  library_id   bigint(20)   not null auto_increment comment '标签库ID',
  library_name varchar(64)  not null                comment '标签库名称',
  library_code varchar(64)  not null                comment '标签库编码',
  category     varchar(32)  default ''              comment '分类（字典 tag_library_category）',
  tag_object   varchar(16)  default ''              comment '标签对象（字典 tag_object）',
  dataset_id   bigint(20)   default null            comment '关联数据集ID',
  owner_name   varchar(30)  default ''              comment '负责人',
  status       char(1)      default '0'             comment '状态（0草稿 1待审批 2已上线 3已下线）',
  del_flag     char(1)      default '0'             comment '删除标志（0存在 2删除）',
  create_by    varchar(64)  default ''              comment '创建者',
  create_time  datetime                               comment '创建时间',
  update_by    varchar(64)  default ''              comment '更新者',
  update_time  datetime                               comment '更新时间',
  remark       varchar(500) default null            comment '备注',
  primary key (library_id),
  unique key uk_tl_library_code (library_code, del_flag)
) engine=innodb auto_increment=100 comment='标签库表';

drop table if exists tl_tag_dir;
create table tl_tag_dir (
  dir_id      bigint(20)   not null auto_increment comment '目录ID',
  library_id  bigint(20)   not null                comment '所属标签库ID',
  parent_id   bigint(20)   default 0               comment '父目录ID',
  dir_name    varchar(64)  not null                comment '目录名称',
  order_num   int(4)       default 0               comment '显示顺序',
  del_flag    char(1)      default '0'             comment '删除标志（0存在 2删除）',
  create_by   varchar(64)  default ''              comment '创建者',
  create_time datetime                               comment '创建时间',
  update_by   varchar(64)  default ''              comment '更新者',
  update_time datetime                               comment '更新时间',
  remark      varchar(500) default null            comment '备注',
  primary key (dir_id),
  key idx_tl_dir_library (library_id)
) engine=innodb auto_increment=100 comment='标签目录表';

drop table if exists tl_tag;
create table tl_tag (
  tag_id           bigint(20)   not null auto_increment comment '标签ID',
  library_id       bigint(20)   not null                comment '所属标签库ID',
  dir_id           bigint(20)   not null                comment '所属目录ID',
  field_name       varchar(64)  not null                comment '源字段名',
  tag_name         varchar(128) not null                comment '标签中文名',
  data_type        varchar(32)  default ''              comment '源字段数据类型',
  tag_type         varchar(16)  default ''              comment '标签类型（字典 tag_type）',
  is_object_key    char(1)      default '0'             comment '是否对象键（0否 1是）',
  business_caliber varchar(500) default ''              comment '业务口径',
  tech_caliber     varchar(500) default ''              comment '技术口径',
  valid_period     varchar(32)  default '永久有效'       comment '有效日期',
  update_cycle     varchar(8)   default '日'            comment '更新周期（字典 tag_update_cycle）',
  create_way       varchar(8)   default '同步'           comment '创建方式（同步/自建）',
  status           char(1)      default '0'             comment '状态（0草稿 1待审批 2已上线 3已下线）',
  version          int(8)       default 1               comment '版本号',
  del_flag         char(1)      default '0'             comment '删除标志（0存在 2删除）',
  create_by        varchar(64)  default ''              comment '创建者',
  create_time      datetime                               comment '创建时间',
  update_by        varchar(64)  default ''              comment '更新者',
  update_time      datetime                               comment '更新时间',
  remark           varchar(500) default null            comment '备注',
  primary key (tag_id),
  key idx_tl_tag_library_status (library_id, status),
  key idx_tl_tag_dir (dir_id),
  unique key uk_tl_tag_field (library_id, field_name, del_flag)
) engine=innodb auto_increment=100 comment='标签表（字段快照）';

drop table if exists tl_audit_log;
create table tl_audit_log (
  log_id        bigint(20)   not null auto_increment comment '日志ID',
  biz_type      varchar(16)  not null                comment '业务类型（library/tag）',
  biz_id        bigint(20)   not null                comment '业务对象ID',
  action        varchar(16)  not null                comment '动作（提交/通过/驳回/上线/下线）',
  from_status   varchar(16)  default ''              comment '变更前状态（library/tag为0-3，tagMeta为DRAFT/PENDING/APPROVED/REJECTED）',
  to_status     varchar(16)  default ''              comment '变更后状态（library/tag为0-3，tagMeta为DRAFT/PENDING/APPROVED/REJECTED）',
  apply_by      varchar(64)  default ''              comment '申请人',
  audit_by      varchar(64)  default ''              comment '审批人',
  audit_time    datetime                               comment '审批时间',
  audit_comment varchar(500) default ''              comment '审批意见',
  create_by     varchar(64)  default ''              comment '创建者',
  create_time   datetime                               comment '创建时间',
  primary key (log_id),
  key idx_tl_audit_biz (biz_type, biz_id)
) engine=innodb auto_increment=100 comment='标签审批日志表';
