-- 业务计算能力使用不可变版本；复核之后通过现有快照发布流程生效。
CREATE TABLE IF NOT EXISTS ts_agent_capability (
  library_id BIGINT NOT NULL,
  capability_id VARCHAR(96) NOT NULL,
  version INT NOT NULL,
  definition_json LONGTEXT NOT NULL,
  review_status VARCHAR(24) NOT NULL DEFAULT 'DRAFT',
  create_by VARCHAR(64) NOT NULL,
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  review_by VARCHAR(64) DEFAULT NULL,
  review_time DATETIME DEFAULT NULL,
  PRIMARY KEY (library_id, capability_id, version),
  KEY idx_capability_review (library_id, review_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent业务定义与受控计算能力版本';
