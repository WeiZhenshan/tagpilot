-- ============================================================================
-- 98_rollback_L_INDVCST_LABEL.sql
-- 用途      : 回退 —— 删除本任务创建的两张表，使 indiv_cust 库恢复到建表前状态
-- 目标库    : indiv_cust
-- 删除对象  : L_INDVCST_LABEL            （个人客户经营标签大宽表，970 列）
--             L_INDVCST_LABEL_CODE_MAP   （客户标签码值映射表，1723 条码值）
-- 危险等级  : 高 —— DROP TABLE 会永久删除表结构及其全部数据，不可恢复
-- 幂等性    : 使用 IF EXISTS，可重复执行，不报错
-- 执行方式  : 手工执行。本脚本位于 sql/indiv_cust/，不属于自动部署流程
--             （bin/db-migrate.sh 只扫描 sql/migration/）
-- 安全性    : 已确认应用代码（Java / MyBatis XML / 前端）对这两张表零引用，
--             删除不会影响任何运行时功能
-- ============================================================================
--
-- 执行前请先备份（强烈建议）：
--   mysqldump -h<host> -P3306 -uroot -p indiv_cust \
--       L_INDVCST_LABEL L_INDVCST_LABEL_CODE_MAP > backup_indiv_cust_label.sql
--
-- ============================================================================

-- 1) 先删码值映射表（业务上依赖宽表；虽无外键，仍按依赖顺序删除）
DROP TABLE IF EXISTS `indiv_cust`.`L_INDVCST_LABEL_CODE_MAP`;

-- 2) 再删标签大宽表
DROP TABLE IF EXISTS `indiv_cust`.`L_INDVCST_LABEL`;

-- 3) 回退后核对：期望返回 0，表示两张表已全部删除
SELECT COUNT(*) AS remaining_tables
  FROM information_schema.TABLES
 WHERE TABLE_SCHEMA = 'indiv_cust'
   AND TABLE_NAME IN ('L_INDVCST_LABEL', 'L_INDVCST_LABEL_CODE_MAP');

-- 4) 可选：仅清空码值、保留表结构（不删表，可重复导入码值）
--    TRUNCATE TABLE `indiv_cust`.`L_INDVCST_LABEL_CODE_MAP`;
--    TRUNCATE TABLE `indiv_cust`.`L_INDVCST_LABEL`;   -- 会清空全部客户标签数据，慎用
--
-- ============================================================================
-- 回退顺序说明
--   建表导入顺序：01_create → 02_create → 03_insert → 04_insert → 05_insert → 99_validate
--   回退只需执行本脚本；如需重建，重新按上述顺序执行即可。
-- ============================================================================
