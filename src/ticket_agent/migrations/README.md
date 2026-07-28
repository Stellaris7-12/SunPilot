# migrations — 数据库迁移脚本目录

存放 MySQL 数据库的 **schema 定义与增量迁移 SQL**。持久化层使用 SQLAlchemy 2 + asyncmy，数据库连接由 `.env` 中的 `DATABASE_URL` 配置。项目同时集成了 Alembic。

## 子目录 `mysql/`

| 文件 | 主要功能 |
| --- | --- |
| `001_i1_schema.sql` | 初始 schema。创建 `ticket_agent` 库及核心表：`tickets`（工单主表）、`ai_results`、`trace_steps`、`tool_call_log`、`ticket_operation_log`、Mock 业务域表（`mock_*`）等。 |
| `002_dispatch_ext.sql` | 派单/回件扩展迁移。为 `tickets` 表增补 `ext_json`（场景特有字段）、`order_prefix`（编号前缀）、`biz_type`/`biz_sub_type`（业务类型）、`deadline`（SLA 回件日期）、`receive_unit`（接单单位）、`need_reply`（是否需回复）等列。 |

## 注意

- 修改 DB schema 前需与用户确认。
- 测试库为 `ticket_agent_test`，与演示库 `ticket_agent` 相互隔离。
