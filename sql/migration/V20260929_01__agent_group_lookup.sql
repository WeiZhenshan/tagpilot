-- 智能体客群回跳反查；仅新增索引，可重复执行。
SET @agent_group_index_sql = IF(
  EXISTS(SELECT 1 FROM information_schema.statistics WHERE table_schema = DATABASE()
    AND table_name = 'ts_agent_execution' AND index_name = 'idx_agent_execution_group'),
  'SELECT 1',
  'ALTER TABLE ts_agent_execution ADD INDEX idx_agent_execution_group (group_id, user_id, create_time)'
);
PREPARE agent_group_index_stmt FROM @agent_group_index_sql;
EXECUTE agent_group_index_stmt;
DEALLOCATE PREPARE agent_group_index_stmt;
