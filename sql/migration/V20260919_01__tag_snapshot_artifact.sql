-- 前向幂等迁移：文件字节哈希独立于规范化内容哈希；老快照须重发。
SET @ddl = IF((SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'ts_catalog_snapshot' AND column_name = 'file_sha256') = 0,
 'ALTER TABLE ts_catalog_snapshot ADD COLUMN file_sha256 char(64) NULL COMMENT ''快照文件字节 SHA256'' AFTER content_hash', 'SELECT 1');
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 新增唯一键仅约束本版本后的记录，不更改既有反馈。
SET @ddl = IF((SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'ts_retrieval_feedback' AND column_name = 'decision_key') = 0,
 'ALTER TABLE ts_retrieval_feedback ADD COLUMN decision_key varchar(100) NULL, ADD UNIQUE KEY uk_ts_feedback_decision (decision_key)', 'SELECT 1');
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
