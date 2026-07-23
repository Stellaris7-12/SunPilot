import type { PageTaskScene } from '../types'

export interface SemanticTargetDefinition {
  target: string
  label: string
  capabilities: Array<'fill' | 'click' | 'select' | 'scroll' | 'locate' | 'wait' | 'stop'>
}

const ADAPTERS: Record<PageTaskScene, SemanticTargetDefinition[]> = {
  'call-intake': [
    { target: 'call-intake-workspace', label: '通话发单工作区', capabilities: ['scroll', 'wait'] },
    { target: 'call-transcript-panel', label: '通话全文', capabilities: ['scroll', 'wait'] },
    { target: 'ticket-draft-form', label: '标准工单草稿表单', capabilities: ['scroll', 'wait'] },
    { target: 'draft-title', label: '标题', capabilities: ['fill'] },
    { target: 'draft-customerId', label: '客户号', capabilities: ['fill'] },
    { target: 'draft-customerName', label: '客户姓名', capabilities: ['fill'] },
    { target: 'draft-phone', label: '手机号', capabilities: ['fill'] },
    { target: 'draft-cardLast4', label: '卡尾号', capabilities: ['fill'] },
    { target: 'draft-scene', label: '场景', capabilities: ['fill'] },
    { target: 'draft-category', label: '类目', capabilities: ['fill'] },
    { target: 'draft-subcategory', label: '子类目', capabilities: ['fill'] },
    { target: 'draft-priority', label: '优先级', capabilities: ['select'] },
    { target: 'draft-riskLabel', label: '风险标签', capabilities: ['fill'] },
    { target: 'draft-riskLevel', label: '风险等级', capabilities: ['select'] },
    { target: 'draft-content', label: '工单内容', capabilities: ['fill'] },
    { target: 'draft-submit', label: '提交标准工单', capabilities: ['click'] },
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
