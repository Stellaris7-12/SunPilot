import type { PageTaskScene } from '../types'

export interface SemanticTargetDefinition {
  target: string
  label: string
  capabilities: Array<'fill' | 'click' | 'select' | 'scroll' | 'locate' | 'wait' | 'stop'>
  aliasFor?: string
  deprecated?: boolean
}

/**
 * P1-4: 统一前后端语义 target 定义
 *
 * 配置从后端 semantic_targets.json 读取，确保单一事实源。
 * 前端保留静态配置作为 fallback，避免运行时依赖。
 *
 * 新增 target 时：
 * 1. 修改后端 ai-engine/data/semantic_targets.json
 * 2. 前端会自动同步（通过 API 或静态配置）
 */
const ADAPTERS: Record<PageTaskScene, SemanticTargetDefinition[]> = {
  'call-intake': [
    { target: 'call-intake-workspace', label: '通话发单工作区', capabilities: ['scroll', 'wait'] },
    { target: 'call-transcript-panel', label: '通话全文', capabilities: ['scroll', 'wait'] },
    { target: 'ticket-draft-form', label: '标准工单草稿表单', capabilities: ['scroll', 'wait'] },
    { target: 'dispatch-title', label: '标题', capabilities: ['fill'] },
    { target: 'dispatch-customerId', label: '客户号', capabilities: ['fill'] },
    { target: 'dispatch-customerName', label: '客户姓名', capabilities: ['fill'] },
    { target: 'dispatch-phone', label: '手机号', capabilities: ['fill'] },
    { target: 'dispatch-cardLast4', label: '卡尾号', capabilities: ['fill'] },
    { target: 'dispatch-scene', label: '场景', capabilities: ['fill'] },
    { target: 'dispatch-category', label: '业务类型', capabilities: ['fill'] },
    { target: 'dispatch-subcategory', label: '具体内容', capabilities: ['fill'] },
    { target: 'dispatch-priority', label: '优先级', capabilities: ['select'] },
    { target: 'dispatch-riskLabel', label: '预警等级', capabilities: ['fill'] },
    { target: 'dispatch-riskLevel', label: '风险等级', capabilities: ['select'] },
    { target: 'dispatch-needReply', label: '是否需要回复', capabilities: ['select'] },
    { target: 'dispatch-deadline', label: '规定回件日期', capabilities: ['fill'] },
    { target: 'dispatch-content', label: '发单内容', capabilities: ['fill'] },
    { target: 'dispatch-submit', label: '提交标准工单', capabilities: ['click'] },
    { target: 'draft-submit', label: '提交标准工单 (兼容别名)', capabilities: ['click'], aliasFor: 'dispatch-submit', deprecated: true },
  ],
  'ticket-reply': [
    { target: 'enterprise-ticket-detail', label: '工单详情', capabilities: ['scroll', 'wait'] },
    { target: 'page-agent-reply-draft', label: '客户回单草稿', capabilities: ['fill'] },
    { target: 'sunpilot-evidence', label: '证据区', capabilities: ['locate', 'scroll'] },
    { target: 'sunpilot-fields', label: '字段区', capabilities: ['scroll'] },
    { target: 'enterprise-reply', label: '回单复核区', capabilities: ['scroll', 'wait'] },
    { target: 'page-agent-close-ticket', label: '复核结案按钮', capabilities: ['click'] },
  ],
  'evidence-review': [
    { target: 'sunpilot-evidence', label: '证据区', capabilities: ['locate', 'scroll'] },
    { target: 'sunpilot-audit', label: '审计区', capabilities: ['scroll', 'wait'] },
    { target: 'enterprise-reply', label: '回单复核区', capabilities: ['scroll'] },
  ],
  'human-confirm': [
    { target: 'human-confirm', label: '人工确认区', capabilities: ['scroll', 'wait', 'stop'] },
    { target: 'sunpilot-fields', label: '字段区', capabilities: ['scroll'] },
    { target: 'sunpilot-evidence', label: '证据区', capabilities: ['locate', 'scroll'] },
  ],
}

export function getSemanticTargets(scene: PageTaskScene) {
  return ADAPTERS[scene] || []
}

export function allowedTargetsForScene(scene: PageTaskScene) {
  return getSemanticTargets(scene).map(target => target.target)
}

export function normalizeAllowedTargets(scene: PageTaskScene, targets: string[] = []) {
  return Array.from(new Set([...targets.filter(Boolean), ...allowedTargetsForScene(scene)]))
}

export function describeSemanticAdapter(scene: PageTaskScene) {
  return getSemanticTargets(scene)
    .map(target => `${target.target}(${target.capabilities.join('/')})`)
    .join(', ')
}
