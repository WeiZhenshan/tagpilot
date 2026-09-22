-- ============================================================================
-- 08_rollback_L_INDVCST_LABEL_2000.sql
-- 用途      : 回退 06_insert_L_INDVCST_LABEL_2000.sql 插入的 2000 行模拟数据
-- 目标库表  : indiv_cust.L_INDVCST_LABEL
-- 范围      : 仅删除 CUST_ID 以 SIM20260918 开头的行（本批次种子前缀）
-- 危险等级  : 中 —— 不可恢复删除；表结构与其它客户行不受影响
-- 幂等性    : 可重复执行；无匹配行时删除 0 行
-- 执行方式  : 手工执行。更稳妥的「整表还原」请用同目录
--             08_backup_restore_L_INDVCST_LABEL_2000.sh restore <backup.sql.gz>
-- ============================================================================

SET NAMES utf8mb4;

-- 回退前核对
SELECT COUNT(*) AS sim_rows_before
  FROM `indiv_cust`.`L_INDVCST_LABEL`
 WHERE CUST_ID LIKE 'SIM20260918%';

DELETE FROM `indiv_cust`.`L_INDVCST_LABEL`
 WHERE CUST_ID LIKE 'SIM20260918%';

-- 回退后核对：期望 sim_rows_after = 0
SELECT COUNT(*) AS sim_rows_after
  FROM `indiv_cust`.`L_INDVCST_LABEL`
 WHERE CUST_ID LIKE 'SIM20260918%';

SELECT COUNT(*) AS total_rows_after
  FROM `indiv_cust`.`L_INDVCST_LABEL`;
