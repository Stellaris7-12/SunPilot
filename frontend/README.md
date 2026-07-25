# TicketAgent 前端工程


## 技术栈

- Vue 3 + TypeScript
- Vite
- Vue Router
- Pinia
- Axios

## 常用命令

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
npm.cmd run build
npm.cmd run smoke:page-agent
```

开发服务器默认监听 `127.0.0.1:5174`，后端 API 默认使用 `VITE_API_BASE_URL || http://localhost:8000/api`。

## 当前目录

```text
src/
  app/          # Vue 入口、根组件、业务路由
  api/          # 后端 API 封装
  domain/       # 工单、发单、回单的业务映射和业务规则
  layouts/      # 企业壳布局边界
  pages/        # 工作台、发单、回单页面路由边界
  components/   # 可复用业务组件和共享组件
  stores/       # Pinia 状态
  sunpilot/     # SunPilot 面板、PageTask、页面桥、受控工具
  types/        # 前后端数据契约
  utils/        # 业务展示辅助函数
  views/        # 当前企业壳主实现，后续可继续拆到 pages/components
```

当前仍采用兼容式迁移：`pages/*` 负责稳定业务 URL，`layouts/EnterpriseLayout.vue` 承接企业壳，主页面实现暂时集中在 `views/EnterpriseTicketShellView.vue`。后续如果继续标准化，优先把该大组件内的工作台、发单、回单区域搬到 `pages/` 和 `components/business/`。

## 业务路由

| 路径 | 作用 |
| --- | --- |
| `/` | 主工作台 |
| `/dispatch` | 发单总页 |
| `/dispatch/:category` | 分类发单页 |
| `/reply` | 回单队列 |
| `/reply/:category` | 分类回单队列 |
| `/reply/tickets/:id` | 回单详情 |
| `/tickets` | 兼容跳转到 `/reply` |
| `/tickets/:id` | 兼容跳转到 `/reply/tickets/:id` |

## 维护入口

- 改页面结构：先看 `src/views/EnterpriseTicketShellView.vue`、`src/layouts/EnterpriseLayout.vue`、`src/pages/*`。
- 改 SunPilot：先看 `src/sunpilot/panel/SunPilotPanel.vue` 和 `src/sunpilot/*`。
- 改业务分类、字段、状态文案：先看 `src/domain/ticket/*` 和 `src/domain/reply/*`。
- 改接口和数据字段：先看 `src/api/index.ts`、`src/stores/ticket.ts`、`src/types/index.ts`。
- 改全局样式：先看 `src/assets/styles.css`。

## 验收

```powershell
npm.cmd run build
npm.cmd run smoke:page-agent
```

页面验收重点：

- `/` 默认进入主工作台。
- 左侧可切换发单、回单及业务分类。
- `/dispatch` 和 `/reply` 独立跳转。
- `/reply/tickets/:id` 能加载详情、处理记录、核验结果、待补充信息和回单工作区。
- SunPilot 固定在右侧，不出界，业务流和折叠卡正常展示。
- 页面可见文案不暴露强技术字段。
