# TicketAgent PageAgent

This module embeds a local fork of Ali page-agent for the TicketAgent demo.

Source note:

- Upstream source: `C:\Users\heyunhui\OtherProjects\page-agent-main`
- Upstream license: MIT, copyright (c) 2025 Alibaba Group Holding Limited and copyright (c) 2026 SimonLuvRamen.
- Forked runtime pieces live under `core/`, `controller/`, `llm/`, and `tools/`.
- TicketAgent-specific glue lives in `index.ts`, `bridge.ts`, `taskBridge.ts`, `pageTaskExecutor.ts`, `semanticAdapter.ts`, and `panel/AgentPanel.vue`.

MVP boundary:

- Structured `PageTaskEnvelope` is the primary business channel.
- `pageTaskExecutor.ts` maps PageTask actions to deterministic semantic tools before ReAct is used.
- ReAct remains the fallback for missing semantic targets, ambiguous layout, and recovery.
- `execute_javascript` is kept in the forked tools but disabled by default through `experimentalScriptExecutionTool: false`.
- Backend business agents remain the business brain; PageAgent is only the visible page executor.
- Store/SSE results are converted to PageTask plus display observations through `bridge.ts`.
- Save/close style click targets stay blocked by deterministic gates and must remain human-owned.

LLM proxy:

- Browser requests go through `http://localhost:8000/api/llm/proxy/chat/completions`.
- The proxy uses `ALI_API_KEY` and defaults to `qwen3.7-plus`.
- The frontend never receives the provider API key.
