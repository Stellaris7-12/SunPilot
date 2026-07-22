# TicketAgent PageAgent

This module is the TicketAgent-specific GUI execution layer.

Source note:

- It follows the architecture investigated in `C:\Users\heyunhui\OtherProjects\page-agent-main`: execution loop, page controller, visible simulator mask, activity/history, and tool whitelist.
- The upstream project is MIT licensed: copyright (c) 2026 SimonLuvRamen and Alibaba Group Holding Limited.
- This first version does not import the upstream monorepo, Chrome extension, MCP server, website, or generic JavaScript execution tool. It keeps a local, business-scoped implementation for the current TicketAgent Vue page.

Safety policy:

- Natural-language instructions are converted to `PageTaskPlan` before execution.
- The runner accepts only whitelisted page tools: observe, scroll, highlight, input, click, wait, verify, and stop.
- No arbitrary DOM-index click or `execute_javascript` capability is exposed.
- Medium/high-risk flows stop at human confirmation or review nodes.
