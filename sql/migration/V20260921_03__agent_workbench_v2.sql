-- 圈选任务归属与加密内容；仅增量创建，不覆盖旧数据。
CREATE TABLE IF NOT EXISTS ts_agent_thread (
  thread_id varchar(64) NOT NULL,
  user_id bigint NOT NULL,
  library_id bigint NOT NULL,
  title varchar(120) NOT NULL DEFAULT '新的圈选',
  archived char(1) NOT NULL DEFAULT '0',
  row_version bigint NOT NULL DEFAULT 0,
  payload longtext NOT NULL COMMENT 'AES-GCM 加密的消息、方案历史与运行引用',
  create_time datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(thread_id), KEY idx_agent_owner(user_id,archived,update_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS ts_agent_execution (
  execution_id varchar(64) NOT NULL,
  thread_id varchar(64) NOT NULL,
  user_id bigint NOT NULL,
  revision bigint NOT NULL,
  plan_hash varchar(64) NOT NULL,
  group_id bigint DEFAULT NULL,
  create_time datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(execution_id), UNIQUE KEY uk_agent_group_revision(thread_id,revision),
  KEY idx_agent_execution_owner(user_id,thread_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
