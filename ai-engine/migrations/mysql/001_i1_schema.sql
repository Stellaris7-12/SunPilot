CREATE DATABASE IF NOT EXISTS ticket_agent
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE ticket_agent;

CREATE TABLE IF NOT EXISTS tickets (
  id VARCHAR(64) PRIMARY KEY,
  no VARCHAR(32) NOT NULL UNIQUE,
  title VARCHAR(255) NOT NULL,
  customer_id VARCHAR(32) NOT NULL,
  customer_name VARCHAR(64) NOT NULL,
  phone VARCHAR(32) NOT NULL,
  card_last4 CHAR(4) NOT NULL,
  scene VARCHAR(64) NOT NULL,
  category VARCHAR(64) NOT NULL DEFAULT '',
  subcategory VARCHAR(64) NOT NULL DEFAULT '',
  priority ENUM('low', 'normal', 'urgent', 'critical') NOT NULL DEFAULT 'normal',
  channel VARCHAR(64) NOT NULL DEFAULT '',
  assignee VARCHAR(64) NOT NULL DEFAULT '',
  department VARCHAR(64) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL,
  due_at DATETIME NULL,
  updated_at DATETIME NULL,
  risk_label VARCHAR(32) NOT NULL,
  risk_level ENUM('low', 'medium', 'high') NOT NULL,
  status ENUM(
    'open',
    'in_progress',
    'pending_info',
    'pending_human_confirm',
    'pending_human_review',
    'escalated',
    'failed',
    'closed'
  ) NOT NULL DEFAULT 'open',
  content TEXT NOT NULL,
  closed_at DATETIME NULL,
  final_reply TEXT NULL,
  cancel_reason VARCHAR(255) NOT NULL DEFAULT '',
  INDEX idx_tickets_customer_id (customer_id),
  INDEX idx_tickets_category (category, subcategory),
  INDEX idx_tickets_assignee (assignee),
  INDEX idx_tickets_status_due_at (status, due_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS ai_results (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  ticket_id VARCHAR(64) NOT NULL,
  run_id VARCHAR(64) NULL,
  status VARCHAR(64) NULL,
  result_json JSON NOT NULL,
  workflow_name VARCHAR(128) NULL,
  intent_type VARCHAR(128) NULL,
  intent_label VARCHAR(128) NULL,
  intent_confidence DOUBLE NULL,
  extracted_fields_json JSON NULL,
  tool_name VARCHAR(128) NULL,
  tool_request_json JSON NULL,
  tool_response_json JSON NULL,
  evidence_id VARCHAR(128) NULL,
  reply_draft TEXT NULL,
  notification_json JSON NULL,
  requires_human_review TINYINT NOT NULL DEFAULT 1,
  duration_ms INT NOT NULL DEFAULT 0,
  failure_reason TEXT NULL,
  final_reply TEXT NULL,
  closed_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_ai_results_ticket FOREIGN KEY (ticket_id) REFERENCES tickets(id),
  INDEX idx_ai_results_ticket_created (ticket_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS trace_steps (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  ticket_id VARCHAR(64) NOT NULL,
  run_id VARCHAR(64) NOT NULL,
  agent VARCHAR(128) NOT NULL,
  agent_id VARCHAR(128) NOT NULL,
  summary TEXT NOT NULL,
  duration VARCHAR(32) NOT NULL,
  status ENUM('RUNNING', 'SUCCESS', 'FAILED', 'SKIPPED') NOT NULL,
  step_order INT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_trace_steps_ticket FOREIGN KEY (ticket_id) REFERENCES tickets(id),
  INDEX idx_trace_steps_ticket_created (ticket_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS tool_call_log (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  ticket_id VARCHAR(64) NOT NULL,
  tool_name VARCHAR(128) NOT NULL,
  request_json JSON NOT NULL,
  response_json JSON NOT NULL,
  evidence_id VARCHAR(128) NULL,
  success TINYINT NOT NULL DEFAULT 0,
  duration_ms INT NOT NULL,
  failure_reason TEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_tool_call_log_ticket FOREIGN KEY (ticket_id) REFERENCES tickets(id),
  INDEX idx_tool_call_log_ticket_created (ticket_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS evaluations (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  sample_id VARCHAR(64) NOT NULL,
  scenario VARCHAR(128) NOT NULL,
  intent_correct TINYINT NOT NULL DEFAULT 0,
  field_complete_count INT NOT NULL DEFAULT 0,
  field_total_count INT NOT NULL DEFAULT 0,
  tool_correct TINYINT NOT NULL DEFAULT 0,
  time_saved_ms INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS ticket_operation_log (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  ticket_id VARCHAR(64) NOT NULL,
  operation VARCHAR(128) NOT NULL,
  operator VARCHAR(64) NOT NULL DEFAULT 'system',
  from_status VARCHAR(64) NOT NULL DEFAULT '',
  to_status VARCHAR(64) NOT NULL DEFAULT '',
  detail_json JSON NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_ticket_operation_log_ticket FOREIGN KEY (ticket_id) REFERENCES tickets(id),
  INDEX idx_ticket_operation_log_ticket_created (ticket_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS mock_customers (
  customer_id VARCHAR(32) PRIMARY KEY,
  customer_name VARCHAR(64) NOT NULL,
  phone VARCHAR(32) NOT NULL,
  segment VARCHAR(64) NOT NULL DEFAULT '',
  risk_level ENUM('low', 'medium', 'high') NOT NULL DEFAULT 'low',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS mock_cards (
  card_id VARCHAR(64) PRIMARY KEY,
  customer_id VARCHAR(32) NOT NULL,
  card_last4 CHAR(4) NOT NULL,
  product_name VARCHAR(128) NOT NULL DEFAULT '',
  card_status VARCHAR(32) NOT NULL DEFAULT 'active',
  credit_limit INT NOT NULL DEFAULT 0,
  CONSTRAINT fk_mock_cards_customer FOREIGN KEY (customer_id) REFERENCES mock_customers(customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS mock_transactions (
  transaction_id VARCHAR(64) PRIMARY KEY,
  customer_id VARCHAR(32) NOT NULL,
  card_last4 CHAR(4) NOT NULL,
  amount DECIMAL(12, 2) NOT NULL DEFAULT 0,
  merchant VARCHAR(128) NOT NULL DEFAULT '',
  transaction_time DATETIME NULL,
  status VARCHAR(32) NOT NULL DEFAULT '',
  CONSTRAINT fk_mock_transactions_customer FOREIGN KEY (customer_id) REFERENCES mock_customers(customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS mock_benefits (
  benefit_id VARCHAR(64) PRIMARY KEY,
  customer_id VARCHAR(32) NOT NULL,
  benefit_code VARCHAR(64) NOT NULL,
  benefit_name VARCHAR(128) NOT NULL DEFAULT '',
  remaining_count INT NOT NULL DEFAULT 0,
  expire_at DATE NULL,
  CONSTRAINT fk_mock_benefits_customer FOREIGN KEY (customer_id) REFERENCES mock_customers(customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS mock_applications (
  application_no VARCHAR(64) PRIMARY KEY,
  customer_id VARCHAR(32) NOT NULL,
  product_name VARCHAR(128) NOT NULL DEFAULT '',
  current_node VARCHAR(128) NOT NULL DEFAULT '',
  expected_finish_at DATETIME NULL,
  CONSTRAINT fk_mock_applications_customer FOREIGN KEY (customer_id) REFERENCES mock_customers(customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
