# scripts — 运维与演示脚本目录

存放**独立运行的辅助脚本**，用于本地演示与演示数据重置。脚本会将 `ENGINE_DIR` 插入 `sys.path` 后再导入引擎内部模块。

## 文件说明

| 文件 | 主要功能 |
| --- | --- |
| `reset_demo_data.py` | 受控地重置**本地演示数据库**：清空工单、AI 结果、轨迹、工具调用日志及 Mock 业务域表，并重新灌入种子数据。仅作用于本地 demo 库，不触碰评测样本或任何外部业务系统。 |
| `demo_intake_modes.py` | 答辩演示脚本：对同一批工单分别走「规则快车道（deterministic）」与「LLM 增强兜底（llm_augmented）」两条路径，直观对比 IntakeAgent 的两种抽取模式。只读运行，LLM 不可用时仍展示规则侧结果。 |

## 运行

```bash
cd ai-engine
python scripts/demo_intake_modes.py
python scripts/reset_demo_data.py
```
