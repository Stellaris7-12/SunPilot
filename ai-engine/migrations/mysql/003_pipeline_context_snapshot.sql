-- P1-8: Pipeline Context Snapshot for re-entrancy support
-- 解决 PENDING_INFO 重入时重复调用 Classifier/Intake 的问题

USE ticket_agent;

CREATE TABLE IF NOT EXISTS pipeline_context_snapshots (
  ticket_id VARCHAR(64) PRIMARY KEY,
  intent_result JSON NOT NULL COMMENT 'ClassifierAgent 输出',
  extract_result JSON NOT NULL COMMENT 'IntakeAgent 输出',
  tool_params JSON NULL COMMENT 'ResolutionAgent 选择的工具参数',
  verify_result JSON NULL COMMENT 'EscalationAgent 校验结果',
  snapshot_at DATETIME NOT NULL COMMENT '快照时间',
  status VARCHAR(32) NOT NULL COMMENT '暂停时的状态',
  FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
  INDEX idx_snapshot_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
