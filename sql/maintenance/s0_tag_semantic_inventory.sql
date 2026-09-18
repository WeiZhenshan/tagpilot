-- ============================================================================
-- S0 标签语义层只读核验（对应《标签语义层与检索索引建设方案》S0）
--
-- 用途：核验 indiv_cust 宽表/码表、标签库、在线数据集版本、库级码表绑定与试点字段可读性。
-- 约束：本脚本仅 SELECT，不得 INSERT/UPDATE/DELETE，不得重跑 sql/indiv_cust/02~05。
-- 产出：将各段结果填入 docs/design/s0_source_inventory.json。
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. 宽表结构：列数与类型分布（预期对照：970 列 / 969 业务字段）
-- ----------------------------------------------------------------------------
SELECT 'wide_table_column_count' AS check_name,
       COUNT(*) AS column_count
  FROM information_schema.columns
 WHERE table_schema = 'indiv_cust'
   AND table_name = 'L_INDVCST_LABEL';

SELECT data_type, COUNT(*) AS cnt
  FROM information_schema.columns
 WHERE table_schema = 'indiv_cust'
   AND table_name = 'L_INDVCST_LABEL'
 GROUP BY data_type
 ORDER BY cnt DESC;

-- ----------------------------------------------------------------------------
-- 2. 标准码表：字段数 / 码值数 / 按字段分布
-- ----------------------------------------------------------------------------
SELECT 'code_map_totals' AS check_name,
       COUNT(*) AS code_count,
       COUNT(DISTINCT tag_name_en) AS field_count
  FROM indiv_cust.L_INDVCST_LABEL_CODE_MAP;

SELECT tag_name_en, COUNT(*) AS code_count
  FROM indiv_cust.L_INDVCST_LABEL_CODE_MAP
 GROUP BY tag_name_en
 ORDER BY code_count DESC, tag_name_en;

-- ----------------------------------------------------------------------------
-- 3. 标签库清单（历史上盘点 library_id=107，以本查询为准）
-- ----------------------------------------------------------------------------
SELECT l.library_id, l.library_name, l.library_code, l.tag_object, l.status,
       l.dataset_id, l.last_sync_version_id, l.del_flag,
       (SELECT COUNT(*) FROM ry.tl_tag t WHERE t.library_id = l.library_id AND t.del_flag = '0') AS tag_count,
       (SELECT COUNT(*) FROM ry.tl_tag t WHERE t.library_id = l.library_id AND t.del_flag = '0' AND t.status = '2') AS online_count,
       (SELECT COUNT(*) FROM ry.tl_tag t
         WHERE t.library_id = l.library_id AND t.del_flag = '0'
           AND t.status = '2' AND t.source_status = 'AVAILABLE') AS available_online_count
  FROM ry.tl_tag_library l
 WHERE l.del_flag = '0'
 ORDER BY l.library_id;

-- ----------------------------------------------------------------------------
-- 4. 在线数据集版本解析（默认 ONLINE 优先，否则最大 version_no）
-- ----------------------------------------------------------------------------
SELECT l.library_id, l.dataset_id, d.dataset_name, d.status AS dataset_status, d.del_flag AS dataset_del_flag,
       d.default_version_id, d.datasource_id,
       v.version_id AS resolved_version_id, v.version_no, v.version_name, v.version_status,
       (v.version_id = d.default_version_id) AS is_default,
       (SELECT COUNT(*) FROM ry.dp_dataset_field f WHERE f.version_id = v.version_id AND f.enabled = '1') AS enabled_field_count
  FROM ry.tl_tag_library l
  JOIN ry.dp_dataset d ON d.dataset_id = l.dataset_id
  LEFT JOIN ry.dp_dataset_version v
         ON v.dataset_id = d.dataset_id AND v.version_status = 'ONLINE'
 WHERE l.del_flag = '0'
 ORDER BY l.library_id,
          (v.version_id = d.default_version_id) DESC,
          v.version_no DESC;

-- ----------------------------------------------------------------------------
-- 5. 库级默认码表绑定
-- ----------------------------------------------------------------------------
SELECT l.library_id, r.relation_id, r.dimension_id, r.order_num,
       dim.dimension_name, dim.dimension_code, dim.source_table_name,
       dim.status AS dim_status, dim.del_flag AS dim_del_flag, dim.datasource_id AS dim_datasource_id,
       d.datasource_id AS library_datasource_id,
       (dim.datasource_id = d.datasource_id) AS same_source
  FROM ry.tl_tag_library l
  LEFT JOIN ry.tl_tag_library_dimension r ON r.library_id = l.library_id
  LEFT JOIN ry.dp_dimension_table dim ON dim.dimension_id = r.dimension_id
  LEFT JOIN ry.dp_dataset d ON d.dataset_id = l.dataset_id AND d.del_flag = '0'
 WHERE l.del_flag = '0'
 ORDER BY l.library_id, r.order_num, r.relation_id;

-- ----------------------------------------------------------------------------
-- 6. 试点字段对照：tl_tag 存在性 / 上线 / 来源 / 在线字段启用 / 码表覆盖
--    码表覆盖仅统计 L_INDVCST_LABEL_CODE_MAP 中 tag_name_en 命中，不替代库级绑定核验。
-- ----------------------------------------------------------------------------
SELECT p.field_name,
       t.tag_id, t.tag_name, t.data_type, t.tag_type, t.is_object_key,
       t.status, t.source_status, t.version, t.library_id,
       CASE WHEN f.field_id IS NULL THEN 0 ELSE 1 END AS enabled_in_resolved_version,
       COALESCE(c.code_count, 0) AS code_count
  FROM (
        SELECT 'CUST_ID' AS field_name UNION ALL
        SELECT 'CUR_HOLDING_WMP_FLAG' UNION ALL
        SELECT 'HIST_HOLDING_WMP_FLAG' UNION ALL
        SELECT 'LAST_7_DAYS_DIFF_NAME_INTERBANK_TRANSFER_IN_FLAG' UNION ALL
        SELECT 'LAST_30_DAYS_DIFF_NAME_INTERBANK_TRANSFER_IN_FLAG' UNION ALL
        SELECT 'GENDER' UNION ALL
        SELECT 'ID_TYPE' UNION ALL
        SELECT 'CUR_APP_DEVICE_TYPE' UNION ALL
        SELECT 'OUTSIDE_ASSET_WAN_KYC' UNION ALL
        SELECT 'OUTSIDE_ASSET_OPS_KYC' UNION ALL
        SELECT 'OUTSIDE_ASSET_PB_KYC' UNION ALL
        SELECT 'CUR_WMP_RISK_ASSESSMENT_LEVEL' UNION ALL
        SELECT 'HIGHEST_EDUCATION' UNION ALL
        SELECT 'HOUSEHOLD_ANNUAL_INCOME_PB_KYC' UNION ALL
        SELECT 'CUR_CORE_CM_LEVEL1_BRANCH' UNION ALL
        SELECT 'CUR_CORE_CM_LEVEL2_BRANCH' UNION ALL
        SELECT 'CUR_CORE_CM_LEVEL3_BRANCH' UNION ALL
        SELECT 'CUR_POINT_AUM' UNION ALL
        SELECT 'T3_MONTH_END_AUM' UNION ALL
        SELECT 'LAST_12_MONTHS_MAX_AUM' UNION ALL
        SELECT 'HIST_MAX_POINT_AUM' UNION ALL
        SELECT 'CUR_POINT_AUM_OUR_BANK' UNION ALL
        SELECT 'CUR_AUM_MONTH_AVG_DAILY_BALANCE' UNION ALL
        SELECT 'CHILD_COUNT_PB_KYC' UNION ALL
        SELECT 'LAST_7_DAYS_DIFF_NAME_INTERBANK_TRANSFER_IN_COUNT' UNION ALL
        SELECT 'CUR_PB_KYC_COMPLETENESS' UNION ALL
        SELECT 'CUR_FIXED_INCOME_AUM_RATIO' UNION ALL
        SELECT 'HIST_MATURED_TIME_DEPOSIT_LATEST_MAT_DATE' UNION ALL
        SELECT 'NEXT_TIME_DEPOSIT_LATEST_MAT_DATE' UNION ALL
        SELECT 'CUR_MOBILE_MODEL' UNION ALL
        SELECT 'DO_NOT_DISTURB_CUST_WECOM_TAG_FLAG'
       ) p
  LEFT JOIN ry.tl_tag t
         ON t.field_name = p.field_name AND t.del_flag = '0'
  LEFT JOIN ry.tl_tag_library l
         ON l.library_id = t.library_id AND l.del_flag = '0'
  LEFT JOIN ry.dp_dataset d
         ON d.dataset_id = l.dataset_id AND d.del_flag = '0' AND d.status = '0'
  LEFT JOIN ry.dp_dataset_version v
         ON v.dataset_id = d.dataset_id AND v.version_status = 'ONLINE'
        AND v.version_id = (
              SELECT v2.version_id
                FROM ry.dp_dataset_version v2
               WHERE v2.dataset_id = d.dataset_id AND v2.version_status = 'ONLINE'
               ORDER BY (v2.version_id = d.default_version_id) DESC, v2.version_no DESC
               LIMIT 1
            )
  LEFT JOIN ry.dp_dataset_field f
         ON f.version_id = v.version_id AND f.enabled = '1'
        AND (f.field_alias = p.field_name OR f.field_name = p.field_name)
  LEFT JOIN (
        SELECT tag_name_en, COUNT(*) AS code_count
          FROM indiv_cust.L_INDVCST_LABEL_CODE_MAP
         GROUP BY tag_name_en
       ) c ON c.tag_name_en = p.field_name
 ORDER BY p.field_name;
