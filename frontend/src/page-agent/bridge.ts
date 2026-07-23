import { watch, type WatchStopHandle } from 'vue'
import type { Store } from 'pinia'
import type { PageAgentCore } from './core/PageAgentCore'
import type { useTicketStore } from '../stores/ticket'
import type { AiProcessResult, PageTaskEnvelope, RiskLevel, TicketDraftResult, TraceStep } from '../types'
import { normalizeAllowedTargets } from './semanticAdapter'

type TicketStore = ReturnType<typeof useTicketStore> & Store

export type ObservationKind = 'draft' | 'ai_result' | 'trace' | 'processing' | 'paused'

export interface PageAgentBridgeOptions {
  onObservation?: (content: string, kind: ObservationKind) => void
  onPageTask?: (task: PageTaskEnvelope, kind: ObservationKind) => void
}

function compact(text: string | undefined, max = 180) {
  const value = String(text || '').replace(/\s+/g, ' ').trim()
  return value.length > max ? `${value.slice(0, max)}...` : value
}

function evidenceIds(result: AiProcessResult | null) {
  if (!result) return []
  const fromEnrichment = result.fieldEnrichment?.evidenceIds || []
  const fromResponse = [
    result.toolResponse?.evidenceId,
    result.toolResponse?.evidence_id,
  ].filter((item): item is string => typeof item === 'string' && Boolean(item))
  const fromText = String(result.toolEvidence || '').match(/[A-Z]{3}[0-9A-Z-]{8,}|EVID-[A-Z0-9-]+/g) || []
  return Array.from(new Set([...fromEnrichment, ...fromResponse, ...fromText]))
}

function jsonBlock(value: unknown) {
  return JSON.stringify(value, null, 2)
}

function describeDraft(result: TicketDraftResult) {
  const draft = result.ticketDraft
  return [
    '发单Agent已生成工单草稿。',
    `客户姓名=${draft.customerName || '未识别'}`,
    `客户号=${draft.customerId || '未识别'}`,
    `手机=${draft.phone || '未识别'}`,
    `卡尾号=${draft.cardLast4 || '未识别'}`,
    `场景=${draft.scene || result.detectedScenario || '未识别'}`,
    `标题=${draft.title || '未识别'}`,
    `风险=${draft.riskLabel || draft.riskLevel || '未识别'}`,
    `发单内容=${compact(draft.content, 220)}`,
    `草稿字段JSON=${jsonBlock(draft)}`,
    `页面任务提示JSON=${jsonBlock(result.pageTaskHints || [])}`,
    '请打开发单表单并填入以上字段，字段完整后点击一键提交工单。',
  ].join('；')
}

function describeAiResult(result: AiProcessResult, paused: boolean) {
  const reply = result.notification?.standardReply?.body || result.replyDraft
  const canClose = result.notification?.closureSuggestion?.canClose ? '是' : '否'
  return [
    '后端多Agent处理完成。',
    `workflow=${result.workflowName || 'unknown'}`,
    `场景=${result.intent?.label || result.intent?.type || '未识别'}`,
    `风险决策=${result.riskDecision || '未识别'}`,
    `缺失字段=${result.missingFields?.length ? result.missingFields.join('、') : '无'}`,
    `证据编号=${evidenceIds(result).join('、') || '无'}`,
    `可结案=${canClose}`,
    paused ? '流程已暂停，需要人工确认。请定位风险/确认区域并停下。' : '请填入回单编辑器，定位证据链，并滚动到复核区等待人工复核。',
    `回单草稿=${compact(reply, 260)}`,
    `AI结果JSON=${jsonBlock({
      workflowName: result.workflowName,
      intent: result.intent,
      missingFields: result.missingFields,
      riskDecision: result.riskDecision,
      evidenceIds: evidenceIds(result),
      replyDraft: reply,
      closureSuggestion: result.notification?.closureSuggestion,
    })}`,
  ].join('；')
}

function describeTrace(step: TraceStep) {
  return `后端Agent进度：${step.agent} / ${step.status} / ${step.summary || '执行中'} / ${step.duration || '等待返回'}。`
}

function riskLevel(value: unknown): RiskLevel {
  return value === 'medium' || value === 'high' ? value : 'low'
}

function pageTaskFromDraft(result: TicketDraftResult): PageTaskEnvelope {
  const actions = (result.pageTaskHints || []).map(hint => ({
    kind: hint.action === 'submit' ? 'clickSemantic' as const : hint.action === 'open' ? 'openPanel' as const : 'fillForm' as const,
    target: hint.target,
    label: hint.label,
    field: hint.field,
    value: hint.value,
    required: hint.required,
  }))
  return {
    id: `draft-${result.sourceCallId || Date.now()}`,
    source: 'call_intake',
    scene: 'call-intake',
    riskLevel: riskLevel(result.ticketDraft.riskLevel),
    mode: result.missingFields.length ? 'suggest' : 'auto',
    businessPayload: {
      ticketDraft: result.ticketDraft,
      keyFields: result.keyFields,
      missingFields: result.missingFields,
    },
    actions,
    allowedTargets: normalizeAllowedTargets('call-intake', actions.map(action => action.target).filter(Boolean)),
    requiresHumanBeforeSubmit: Boolean(result.missingFields.length),
    stopReason: result.missingFields.length ? `字段不足：${result.missingFields.join('、')}` : '',
  }
}

function pageTaskFromAiResult(result: AiProcessResult, paused: boolean): PageTaskEnvelope {
  const ids = evidenceIds(result)
  const reply = result.notification?.standardReply?.body || result.replyDraft
  const scene = paused ? 'human-confirm' : 'ticket-reply'
  return {
    id: `ai-result-${result.workflowName || Date.now()}`,
    source: 'ai_result',
    scene,
    riskLevel: riskLevel(result.verifyChecks?.some(check => /高|拦截|复核/.test(check.status)) ? 'high' : undefined),
    mode: paused ? 'stop' : result.missingFields?.length ? 'suggest' : 'auto',
    businessPayload: {
      workflowName: result.workflowName,
      intent: result.intent,
      missingFields: result.missingFields,
      riskDecision: result.riskDecision,
      evidenceIds: ids,
      replyDraft: reply,
      closureSuggestion: result.notification?.closureSuggestion,
    },
    actions: [
      {
        kind: 'fillTextarea',
        target: 'page-agent-reply-draft',
        label: '填入客户回单',
        value: reply,
        required: Boolean(reply),
      },
      ...ids.map(id => ({
        kind: 'locateEvidence' as const,
        target: 'sunpilot-evidence',
        label: `定位证据 ${id}`,
        value: id,
        required: false,
      })),
      {
        kind: paused ? 'stopForHuman' : 'scrollToRegion',
        target: paused ? 'human-confirm' : 'enterprise-reply',
        label: paused ? '停在人工确认区' : '进入回单复核区',
        required: true,
      },
    ],
    allowedTargets: normalizeAllowedTargets(scene, ['page-agent-reply-draft', 'sunpilot-evidence', 'enterprise-reply', 'human-confirm']),
    requiresHumanBeforeSubmit: true,
    stopReason: paused ? result.failureReason || result.riskDecision || '流程已暂停，需要人工确认' : '',
  }
}

export function bindTicketPageAgentBridge(
  agent: PageAgentCore,
  store: TicketStore,
  options: PageAgentBridgeOptions = {},
) {
  let draftSignature = ''
  let resultSignature = ''
  let traceSignature = ''
  let processingState = store.isProcessing
  const stops: WatchStopHandle[] = []

  const publish = (content: string, kind: ObservationKind, task?: PageTaskEnvelope) => {
    agent.pushObservation(content)
    options.onObservation?.(content, kind)
    if (task) options.onPageTask?.(task, kind)
  }

  stops.push(watch(() => store.ticketDraftResult, result => {
    if (!result) return
    const signature = JSON.stringify(result.ticketDraft)
    if (signature === draftSignature) return
    draftSignature = signature
    const task = result.pageTask || pageTaskFromDraft(result)
    publish(describeDraft(result), 'draft', task)
  }, { immediate: true }))

  stops.push(watch(() => store.traceSteps, steps => {
    const latest = steps.at(-1)
    if (!latest) return
    const signature = `${latest.agentId}:${latest.status}:${latest.summary}:${latest.duration}`
    if (signature === traceSignature) return
    traceSignature = signature
    publish(describeTrace(latest), 'trace')
  }, { deep: true }))

  stops.push(watch(() => store.isProcessing, isProcessing => {
    if (isProcessing === processingState) return
    processingState = isProcessing
    publish(isProcessing ? '后端多Agent开始处理当前工单，请等待处理结果。' : '后端多Agent处理状态已结束，请查看最新结果。', 'processing')
  }))

  stops.push(watch([() => store.aiResult, () => store.workflowPaused], ([result, paused]) => {
    if (!result) return
    const signature = JSON.stringify({
      workflowName: result.workflowName,
      riskDecision: result.riskDecision,
      replyDraft: result.notification?.standardReply?.body || result.replyDraft,
      missingFields: result.missingFields,
      paused,
    })
    if (signature === resultSignature) return
    resultSignature = signature
    const kind = paused ? 'paused' : 'ai_result'
    const task = result.pageTask || pageTaskFromAiResult(result, paused)
    publish(describeAiResult(result, paused), kind, task)
  }, { immediate: true }))

  return () => stops.forEach(stop => stop())
}
