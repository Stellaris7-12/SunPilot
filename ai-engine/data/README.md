# data — 配置与数据资源目录

存放驱动多 Agent 工单流程的**配置数据、种子数据、样本数据与本地演示数据**。其中 `workflow_config.json` 是整个业务流程的单一事实来源（single source of truth），代码不应再硬编码与之竞争的字段映射。

## 文件说明

| 文件 | 主要功能 |
| --- | --- |
| `workflow_config.json` | **核心配置**。定义各业务场景（scenario）、工作流名称、编号前缀、SLA、必填字段映射、场景检测与风险门控规则。由 `load_workflow_config()` 加载并经 `WorkflowConfig` 校验。 |
| `agent_cards.json` | 五个业务 Agent 的 AgentCard 定义（能力、技能、描述、版本），供 `agent_registry` 构建 Agent。 |
| `tools.json` | Mock 工具的定义清单（名称、显示名、类别、参数 schema），供工具注册表加载与校验。 |
| `mock_domain_seed.json` | Mock 业务域种子数据（客户、优惠券、权限、申请单等），用于初始化演示/测试数据库。 |
| `call_transcripts.json` | 合成的电话通话记录样本，用于「通话记录 → 工单草稿」生成演示。 |
| `tickets.json` | 演示用工单样本数据。 |
| `evaluation_samples.json` | 评测/冒烟测试用的标注样本集。 |
| `tickets.db` | 本地 SQLite 演示数据库文件（历史遗留 / 本地沙盒用）。 |

## 子目录

| 子目录 | 说明 |
| --- | --- |
| `external/` | 外部公开数据集（如 banking77、cfpb_complaints），用于意图分类的参考与评测。 |
| `generated/` | 由脚本从外部数据集生成的中间产物（如 `banking77_intents.json`）。 |
| `traces/` | 运行时产生的 Agent 执行轨迹（trace）落盘文件。 |

## 注意

- 所有文本文件均为 **UTF-8 无 BOM**。
- 修改 `workflow_config.json`、种子数据前需与用户确认（见根 `CLAUDE.md` 边界约束）。
