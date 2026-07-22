import { watch, type WatchStopHandle } from 'vue'
import type { Store } from 'pinia'
import type { PageAgentCore } from './core/PageAgentCore'
import type { useTicketStore } from '../stores/ticket'
import type { AiProcessResult, TicketDraftResult, TraceStep } from '../types'

type TicketStore = ReturnType<typeof useTicketStore> & Store

type ObservationKind = 'draft' | 'ai_result' | 'trace' | 'processing' | 'paused'

export interface PageAgentBridgeOptions {
  onObservation?: (content: string, kind: ObservationKind) => void
}

function compact(text: string | undefined, max = 180) {
  const value = String(text || '').replace(/\s+/g, ' ').trim()
  return value.length > max ? `${value.slice(0, max)}...` : value
}

function evidenceIds(result: AiProcessResult | null) {
  if (!result) return []
  const fromEnrichment = result.fieldEnrichment?.evidenceIds || []
  const fromText = String(result.toolEvidence || '').match(/EVID-[A-Z0-9-]+/g) || []
  return Array.from(new Set([...fromEnrichment, ...fromText]))
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
  ].join('；')
}

function describeTrace(step: TraceStep) {
  return `后端Agent进度：${step.agent} / ${step.status} / ${step.summary || '执行中'} / ${step.duration || '等待返回'}。`
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

  const publish = (content: string, kind: ObservationKind) => {
    agent.pushObservation(content)
    options.onObservation?.(content, kind)
  }

  stops.push(watch(() => store.ticketDraftResult, result => {
    if (!result) return
    const signature = JSON.stringify(result.ticketDraft)
    if (signature === draftSignature) return
    draftSignature = signature
    publish(describeDraft(result), 'draft')
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
    publish(describeAiResult(result, paused), paused ? 'paused' : 'ai_result')
  }, { immediate: true }))

  return () => stops.forEach(stop => stop())
}
