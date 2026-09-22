-- 为智能体工作台会话增加持久置顶状态；仅向前扩展，重复执行安全。
SET @column_exists = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'ts_agent_thread'
    AND column_name = 'pinned'
);
SET @ddl = IF(
  @column_exists = 0,
  'ALTER TABLE ts_agent_thread ADD COLUMN pinned char(1) NOT NULL DEFAULT ''0'' COMMENT ''是否置顶（0否 1是）'' AFTER archived',
  'SELECT 1'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @index_exists = (
  SELECT COUNT(*) FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'ts_agent_thread'
    AND index_name = 'idx_agent_owner_pinned'
);
SET @ddl = IF(
  @index_exists = 0,
  'CREATE INDEX idx_agent_owner_pinned ON ts_agent_thread(user_id, archived, pinned, update_time)',
  'SELECT 1'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
