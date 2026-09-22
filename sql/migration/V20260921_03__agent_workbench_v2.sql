-- 圈选任务归属与加密内容；仅增量创建，不覆盖旧数据。
CREATE TABLE IF NOT EXISTS ts_agent_thread (
  thread_id    varchar(64)  NOT NULL                COMMENT '圈选任务ID',
  user_id      bigint       NOT NULL                COMMENT '归属用户ID',
  library_id   bigint       NOT NULL                COMMENT '所属标签库ID',
  title        varchar(120) NOT NULL DEFAULT '新的圈选' COMMENT '任务标题',
  archived     char(1)      NOT NULL DEFAULT '0'    COMMENT '是否归档（0否 1是）',
  row_version  bigint       NOT NULL DEFAULT 0      COMMENT '乐观锁版本号',
  payload      longtext     NOT NULL                COMMENT 'AES-GCM 加密的消息、方案历史与运行引用',
  create_time  datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time  datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (thread_id),
  KEY idx_agent_owner (user_id, archived, update_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='智能体工作台-圈选任务';

CREATE TABLE IF NOT EXISTS ts_agent_execution (
  execution_id varchar(64) NOT NULL                COMMENT '执行记录ID',
  thread_id    varchar(64) NOT NULL                COMMENT '圈选任务ID',
  user_id      bigint      NOT NULL                COMMENT '归属用户ID',
  revision     bigint      NOT NULL                COMMENT '方案版本号',
  plan_hash    varchar(64) NOT NULL                COMMENT '方案内容哈希',
  group_id     bigint               DEFAULT NULL   COMMENT '创建的客群ID',
  create_time  datetime    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (execution_id),
  UNIQUE KEY uk_agent_group_revision (thread_id, revision),
  KEY idx_agent_execution_owner (user_id, thread_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='智能体工作台-建群执行';
