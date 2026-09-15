-- ============================================================================
-- L_INDVCST_LABEL_CODE_MAP  客户标签码值映射表
-- 目标库    : indiv_cust
-- 建模参照  : indiv_cust.dim_customer_tag_code（既有标签标准码表）
-- 关联机制  : tag_name_en = L_INDVCST_LABEL 的列名（与既有系统一致，非 tag_id / 非 code_group）
-- 主键      : (tag_name_en, tag_code) 复合主键 —— 码值按标签字段隔离维护
-- 覆盖范围  : L_INDVCST_LABEL 中全部 177 个选项型/布尔型字段
-- 字段类型  : 完全沿用 dim_customer_tag_code（varchar(64)/varchar(64)/varchar(64)/varchar(128)/int/datetime）
-- 字段决策  : 与 dim_customer_tag_code 完全一致 —— 不新增 status(启停状态)、不新增 del_flag、不新增审计字段、不新增二级索引
-- 本文件仅生成，未在数据库中执行。
-- ============================================================================

CREATE TABLE IF NOT EXISTS `indiv_cust`.`L_INDVCST_LABEL_CODE_MAP` (
  `tag_name_en`      varchar(64)  NOT NULL                COMMENT '标签字段别名（对应 L_INDVCST_LABEL 列名）',
  `tag_code`         varchar(64)  NOT NULL                COMMENT '码值（字符串，保留前导零）',
  `tag_name_cn`      varchar(64)  DEFAULT NULL            COMMENT '标签中文名',
  `code_definition`  varchar(128) DEFAULT NULL            COMMENT '码值中文定义',
  `code_sort`        int          DEFAULT NULL            COMMENT '排序号',
  `last_update_time` datetime     DEFAULT NULL            COMMENT '更新时间',
  PRIMARY KEY (`tag_name_en`,`tag_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC
  COMMENT='客户标签码值映射表（与 L_INDVCST_LABEL 选项型/布尔型字段关联）';
