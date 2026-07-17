# 发现与决策

## 需求
- 信用卡工单系统年处理超100万件，人工处理每单1-2分钟
- 目标：多Agent协同将处理时间压缩至5-10秒，人工从"操作者"变为"审核者"
- 聚焦回单侧（Hui Dan），3个高频场景：优惠券补发、地址修改、交易争议
- 8天周期，需"小而精"，有创新亮点，体现工程能力
- 所有Agent结果需人工终审，系统从不自动关闭工单（金融合规）

## 研究发现

### 行业趋势
- Visa 2026年4月发布6款AI争议处理工具，全球争议量超1.06亿笔（+35%）
- AI Agent"代客支付"引发新的争议处理挑战 — 行业亟需AI专项拒付规则
- 2026年多智能体系统（MAS）从"协作网络"走向"自治型智能组织"
- 蚂蚁数科Agentar专家团架构：每个智能体对应完整金融服务岗位角色
- 可控性压倒"聪明程度"：企业关心回滚、解释、审计、责任界定

### 技术选型
- **PageAgent**（阿里巴巴，20k+ Star）：纯前端DOM自动化，适合作为加分项而非主线
- **A2A协议**（Google/Linux Foundation，150+组织）：借鉴Agent Card思想做轻量实现
- **LangGraph**：生产级但学习曲线陡，8天不划算 → 自研编排器更体现设计能力
- **CrewAI**：上手快但太黑盒，看不出工程深度
- **AutoGen**：处于过渡期，不推荐新项目

### 前端框架
- 用户选择：Vue 3 + Vite + TypeScript + Pinia + Vue Router（完整工程化）
- 旧 vue-demo 已移除，全新设计数据契约，无历史约束

## 技术决策
| 决策 | 理由 |
|------|------|
| 纯 FastAPI 后端（无 Spring Boot） | 8天周期，Python AI 生态更适合 Agent 开发 |
| SQLite + JSON 持久化 | 免运维，Schema 设计与 MySQL 一致，可演示迁移路径 |
| 自研编排器（≤500行核心代码） | 体现设计能力，注释说明与 LangGraph/A2A/MCP 的演进关系 |
| 前端 Vite + Vue 3 + TypeScript | 用户要求完整工程化，Component Tree 清晰 |
| A2A-lite Agent Card（非完整协议） | 借鉴核心思想（自描述、自发现），8天内完整接入风险高 |
| SSE 流式 Trace（非 WebSocket） | 单向推送足够，浏览器原生 EventSource，更简单稳定 |
| 三级风险路由 + HITL | 金融合规要素，也是架构亮点 |
| Mock Tool API（非真实外部系统） | Demo 可独立运行，不依赖外部系统，预留 MCP 接口 |
| 零模型微调，纯 Prompt 工程 | 8天周期不现实，zero-shot + JSON mode 足够 |

## 5个工程亮点
1. **A2A-lite Agent Card**：每个Agent自描述能力、输入输出Schema、风险等级、重试策略
2. **显式状态机编排器**：6状态7转移，非简单线性调用，争议类自动升级人工
3. **SSE 流式 Agent Trace**：实时推送每个Agent执行状态，体现可观测性
4. **Tool Registry + MCP预留**：JSON Schema自描述工具，Mock执行器，预留MCP接入点
5. **PageAgent 集成**：CDN一行引入，"一句话处理工单"Demo

## 资源
- [PageAgent GitHub](https://github.com/alibaba/page-agent) — 20k+ Star, v1.12.0
- [A2A Protocol](https://a2aprotocol.org) — Google/Linux Foundation
- [python-a2a PyPI](https://pypi.org/project/python-a2a/) — 社区 A2A 实现
- [CrewAI vs LangGraph vs AutoGen](https://www.datacamp.com/tutorial/crewai-vs-langgraph-vs-autogen) — 框架对比
- [Visa 6款AI争议工具](https://www.mpaypass.com.cn/news/202604/02125031.html)
- [多智能体系统全景 (阿里云)](https://developer.aliyun.com/article/1710744)

## 视觉/浏览器发现
- 无（本阶段未进行视觉操作）

---
*每执行2次查看/浏览器/搜索操作后更新此文件*
*防止视觉信息丢失*
