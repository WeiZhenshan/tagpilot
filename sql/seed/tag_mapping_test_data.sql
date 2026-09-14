-- =====================================================================
-- 标签库批量映射同步优化 —— 阶段7测试数据脚本（幂等，可重复执行）
-- 配套计划：docs/plans/标签库批量映射同步优化计划.md 第4节
-- 涉及库：ry（业务库）、indiv_cust（测试数据源库，datasource_id=101）
-- 执行：mysql -uroot -p < sql/seed/tag_mapping_test_data.sql
-- 说明：维表登记与默认码表关联也可通过页面/接口完成（推荐走接口），
--       本脚本以 NOT EXISTS 守卫的 SQL 兜底，保证重复执行不产生脏数据。
-- =====================================================================

-- ---------- 1. 标准码表（indiv_cust 库，六列结构） ----------
-- code 列用 varchar 保留 "0" 与前导零能力
CREATE TABLE IF NOT EXISTS indiv_cust.dim_customer_tag_code (
  tag_name_en      varchar(64)  NOT NULL COMMENT '标签字段别名（= tl_tag.field_name）',
  tag_code         varchar(64)  NOT NULL COMMENT '码值（字符串，保留前导零）',
  tag_name_cn      varchar(64)  DEFAULT NULL COMMENT '标签中文名',
  code_definition  varchar(128) DEFAULT NULL COMMENT '码值中文定义',
  code_sort        int          DEFAULT NULL COMMENT '排序号',
  last_update_time datetime     DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (tag_name_en, tag_code)
) COMMENT '客户标签标准码表（阶段7测试数据）';

-- 幂等回填：按主键逐个补齐缺失映射，不从编码推导额外业务等级含义
INSERT INTO indiv_cust.dim_customer_tag_code
  (tag_name_en, tag_code, tag_name_cn, code_definition, code_sort, last_update_time)
SELECT * FROM (
  SELECT 'gender' AS tag_name_en, 'M' AS tag_code, '性别'     AS tag_name_cn, '男'       AS code_definition, 1 AS code_sort, NOW() AS last_update_time
  UNION ALL SELECT 'gender', 'F', '性别',     '女',       2, NOW()
  UNION ALL SELECT 'level',  'A', '客户等级', 'A级客户',  1, NOW()
  UNION ALL SELECT 'level',  'B', '客户等级', 'B级客户',  2, NOW()
  UNION ALL SELECT 'level',  'C', '客户等级', 'C级客户',  3, NOW()
  UNION ALL SELECT 'is_vip', '1', '是否VIP',  '是',       1, NOW()
  UNION ALL SELECT 'is_vip', '0', '是否VIP',  '否',       2, NOW()
) t
WHERE NOT EXISTS (
  SELECT 1 FROM indiv_cust.dim_customer_tag_code c
  WHERE c.tag_name_en = t.tag_name_en AND c.tag_code = t.tag_code
);

-- ---------- 2. 已确认来源指纹回填（ry 库） ----------
-- 原因：tag_id 365-371 这 7 个标签在历史版本中已完成上线审核，
-- 但 confirmed_fingerprint 是本次改造新增列，历史数据为空。
-- 作为一次性数据整理，将当前观测来源指纹回填为已确认基线，
-- 使后续物理来源变化能被正确识别为 CHANGED（来源变更待确认）。
-- 仅回填历史已上线且尚未确认的标签，不影响新同步生成的记录。
UPDATE ry.tl_tag
SET confirmed_fingerprint = source_fingerprint
WHERE library_id = 105 AND del_flag = '0' AND status = '2'
  AND source_fingerprint IS NOT NULL AND source_fingerprint <> ''
  AND (confirmed_fingerprint IS NULL OR confirmed_fingerprint = '');

-- ---------- 3. 维表登记（ry 库，等价于 POST /databroker/dimension） ----------
-- 前置：数据源 101 已执行元数据同步，dim_customer_tag_code 已进入 dp_meta_table
INSERT INTO ry.dp_dimension_table
  (dimension_name, dimension_code, datasource_id, source_table_id, source_table_name,
   status, del_flag, create_by, create_time, remark)
SELECT '客户标签标准码表', 'dim_customer_tag_code', 101, mt.table_id, 'dim_customer_tag_code',
       '0', '0', 'admin', NOW(), '阶段7测试数据：gender/level/is_vip 码值中文映射'
FROM ry.dp_meta_table mt
WHERE mt.datasource_id = 101 AND mt.object_name = 'dim_customer_tag_code' AND mt.status = '0'
  AND NOT EXISTS (
    SELECT 1 FROM ry.dp_dimension_table d
    WHERE d.dimension_code = 'dim_customer_tag_code' AND d.del_flag = '0'
  );

-- ---------- 4. 默认码表关联标签库 105（等价于 PUT /taglibrary/library/105/dimensions） ----------
INSERT INTO ry.tl_tag_library_dimension (library_id, dimension_id, order_num, create_by, create_time)
SELECT 105, d.dimension_id, 1, 'admin', NOW()
FROM ry.dp_dimension_table d
WHERE d.dimension_code = 'dim_customer_tag_code' AND d.del_flag = '0'
  AND NOT EXISTS (
    SELECT 1 FROM ry.tl_tag_library_dimension r
    WHERE r.library_id = 105 AND r.dimension_id = d.dimension_id
  );
