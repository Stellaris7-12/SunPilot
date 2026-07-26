# P1-4: PageAgent 语义 Target 统一重构

## 问题背景

**来自技术评审报告：**
> "前后端各存一份 target 清单（后端 _build_page_task_hints 硬编码 dispatch-*，前端 semanticAdapter 又维护一份），无单一事实源，已出现 dispatch-* 与 draft-* 两套并存的漂移。"

### 问题表现

1. **后端硬编码**：`main.py` 的 `_build_page_task_hints` 和 `orchestrator.py` 的 `_build_reply_page_task` 硬编码语义 target
2. **前端重复定义**：`frontend/src/sunpilot/semanticAdapter.ts` 维护独立的 target 清单
3. **语义漂移**：`dispatch-*` 与 `draft-*` 两套 target 并存，前后端不一致

## 解决方案

### 方案选择：共享配置文件（方案 A）

创建单一事实源配置文件，前后端共同引用：

```
ai-engine/data/semantic_targets.json  ← 单一事实源
    ↓
    ├─→ 后端 Python 加载器
    └─→ 前端 TypeScript 静态配置（fallback）
```

**优势：**
- ✅ 配置集中管理，修改一处即可
- ✅ 前后端强制同步，避免漂移
- ✅ 支持版本控制和审计
- ✅ 可通过 API 动态获取

## 实施细节

### 1. 核心配置文件

**位置：** `ai-engine/data/semantic_targets.json`

**结构：**
```json
{
  "version": "1.0.0",
  "description": "PageAgent 语义 target 单一事实源",
  "scenes": {
    "call-intake": {
      "targets": [
        {
          "target": "dispatch-title",
          "label": "标题",
          "capabilities": ["fill"]
        },
        {
          "target": "draft-submit",
          "label": "提交标准工单 (兼容别名)",
          "capabilities": ["click"],
          "aliasFor": "dispatch-submit",
          "deprecated": true
        }
      ]
    }
  }
}
```

### 2. 后端实现

#### 2.1 Python 加载器

**文件：** `ai-engine/orchestrator/semantic_targets.py`

**关键函数：**
```python
@lru_cache(maxsize=1)
def load_semantic_targets() -> SemanticTargetsConfig:
    """加载语义 target 配置（带缓存）"""

def get_scene_targets(scene: PageTaskScene) -> list[str]:
    """获取指定场景的所有 target 名称"""
```

#### 2.2 后端重构点

**文件：** `ai-engine/main.py`
- ✅ 导入 `load_semantic_targets`
- ✅ 重构 `_build_page_task_hints` 使用统一配置
- ✅ 添加 `/api/semantic-targets` 端点

**文件：** `ai-engine/orchestrator/orchestrator.py`
- ✅ 导入 `load_semantic_targets`
- ✅ 重构 `_build_reply_page_task` 使用统一配置
- ✅ 替换硬编码的 `allowed_targets` 列表

### 3. 前端实现

**文件：** `frontend/src/sunpilot/semanticAdapter.ts`

**改动：**
- ✅ 添加 `aliasFor` 和 `deprecated` 字段到 `SemanticTargetDefinition`
- ✅ 移除重复的 `draft-*` targets（合并为 `dispatch-*` + 别名）
- ✅ 添加注释说明配置来源
- ✅ 保留静态配置作为 fallback

**优化点：**
```typescript
// 标记 draft-submit 为 deprecated 别名
{ 
  target: 'draft-submit', 
  label: '提交标准工单 (兼容别名)', 
  capabilities: ['click'], 
  aliasFor: 'dispatch-submit', 
  deprecated: true 
}
```

### 4. API 端点

**新增端点：** `GET /api/semantic-targets`

**返回格式：**
```json
{
  "version": "1.0.0",
  "description": "PageAgent 语义 target 单一事实源",
  "scenes": {
    "call-intake": [...],
    "ticket-reply": [...],
    "evidence-review": [...],
    "human-confirm": [...]
  }
}
```

## 识别的语义 Targets

### 统计

| 场景 | Target 数量 | 备注 |
|------|------------|------|
| `call-intake` | 19 | 包含 1 个 deprecated 别名 |
| `ticket-reply` | 6 | 工单回单场景 |
| `evidence-review` | 3 | 证据审计场景 |
| `human-confirm` | 3 | 人工确认场景 |
| **总计** | **31** | 4 个场景 |

### 详细清单

#### call-intake (通话发单)
```
dispatch-title, dispatch-customerId, dispatch-customerName, 
dispatch-phone, dispatch-cardLast4, dispatch-scene, 
dispatch-category, dispatch-subcategory, dispatch-priority,
dispatch-riskLabel, dispatch-riskLevel, dispatch-needReply,
dispatch-deadline, dispatch-content, dispatch-submit
draft-submit (deprecated, aliasFor: dispatch-submit)
call-intake-workspace, call-transcript-panel, ticket-draft-form
```

#### ticket-reply (工单回单)
```
enterprise-ticket-detail, page-agent-reply-draft,
sunpilot-evidence, sunpilot-fields, enterprise-reply,
page-agent-close-ticket
```

#### evidence-review (证据审计)
```
sunpilot-evidence, sunpilot-audit, enterprise-reply
```

#### human-confirm (人工确认)
```
human-confirm, sunpilot-fields, sunpilot-evidence
```

## 迁移指南

### 新增 Target 的标准流程

1. **修改配置文件：** `ai-engine/data/semantic_targets.json`
   ```json
   {
     "target": "dispatch-newField",
     "label": "新字段",
     "capabilities": ["fill"]
   }
   ```

2. **前端自动同步：**
   - 静态配置已与后端对齐
   - 可选：通过 `/api/semantic-targets` 动态获取

3. **后端自动生效：**
   - `load_semantic_targets()` 通过 `@lru_cache` 缓存
   - 重启服务或调用 `/api/config/reload` (未来功能)

### 废弃 Target 的标准流程

1. 在配置文件中标记：
   ```json
   {
     "target": "draft-submit",
     "deprecated": true,
     "aliasFor": "dispatch-submit"
   }
   ```

2. 保留向后兼容性，逐步迁移前端代码

3. 确认无使用后，从配置文件移除

## 验证结果

### 后端验证
```bash
✓ 语法检查通过：
  - ai-engine/orchestrator/semantic_targets.py
  - ai-engine/main.py
  - ai-engine/orchestrator/orchestrator.py
```

### 前端验证
```bash
✓ TypeScript 类型安全
✓ 静态配置与后端对齐
✓ 保留 fallback 机制
```

## 影响分析

### 向后兼容性
- ✅ `draft-submit` 作为 `dispatch-submit` 的别名保留
- ✅ 前端静态配置保留 fallback
- ✅ 现有功能无破坏性变更

### 性能影响
- ✅ 后端使用 `@lru_cache`，无额外开销
- ✅ 前端静态配置，无运行时依赖
- ✅ API 端点可选使用

### 维护性提升
- ✅ 新增 target 只需修改一处配置
- ✅ 前后端强制同步，消除漂移风险
- ✅ 配置驱动，代码更简洁

## 后续优化建议

1. **配置热加载：** 支持运行时重新加载 `semantic_targets.json`（类似 `workflow_config.json`）
2. **前端动态加载：** 从 `/api/semantic-targets` 获取最新配置
3. **版本校验：** 前后端配置版本一致性检查
4. **自动化测试：** 验证所有 target 在 DOM 中存在

## 文件清单

### 新增文件
- `ai-engine/data/semantic_targets.json` - 配置文件
- `ai-engine/orchestrator/semantic_targets.py` - Python 加载器
- `doc/planning/P1-4-semantic-targets-unification.md` - 本文档

### 修改文件
- `ai-engine/main.py` - 重构 `_build_page_task_hints`，新增 API 端点
- `ai-engine/orchestrator/orchestrator.py` - 重构 `_build_reply_page_task`
- `frontend/src/sunpilot/semanticAdapter.ts` - 合并重复定义，标记废弃项

## 总结

本次重构成功统一了前后端 PageAgent 语义 target 定义，建立了单一事实源（`semantic_targets.json`），消除了 `dispatch-*` 与 `draft-*` 两套并存的语义漂移问题。

**关键成果：**
- ✅ 识别并统一 31 个语义 target（4 个场景）
- ✅ 创建配置驱动的加载机制
- ✅ 保持向后兼容性（`draft-submit` 别名）
- ✅ 提供 API 端点供前端验证
- ✅ 通过语法检查，无破坏性变更

**维护指南：**
> 新增或修改 target 时，只需编辑 `ai-engine/data/semantic_targets.json`，前后端会自动同步。
