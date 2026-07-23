import type { PageTaskActionEnvelope, PageTaskEnvelope } from '../types'
import type { PageAgentCore } from './core/PageAgentCore'
import type { PageTaskDirective } from './taskBridge'

interface ToolCall {
  actionKind: PageTaskActionEnvelope['kind']
  tool: string
  input: Record<string, unknown>
  label: string
  target: string
  required: boolean
  isClick: boolean
}

export interface DeterministicPageTaskResult {
  success: boolean
  stopped: boolean
  summary: string
  outputs: string[]
  fallbackInstruction: string
}

export interface PageTaskActionAuditEntry {
  actionKind: string
  toolName: string
  target: string
  input: Record<string, unknown>
  output: Record<string, unknown>
  status: 'executed' | 'error' | 'stopped'
  resultSummary: string
  durationMs: number
  stopReason: string
}

const BLOCKED_CLICK_TARGETS = new Set([
  'page-agent-save-draft',
  'page-agent-close-ticket',
])

export async function executePageTaskDeterministically(
  agent: PageAgentCore,
  task: PageTaskEnvelope,
  directive: PageTaskDirective,
  signal: AbortSignal,
  onActionLog?: (entry: PageTaskActionAuditEntry) => void | Promise<void>,
): Promise<DeterministicPageTaskResult> {
  if (directive.shouldStop) {
    await onActionLog?.({
      actionKind: 'stopForHuman',
      toolName: 'stop_for_human',
      target: 'human-confirm',
      input: { reason: task.stopReason || directive.instruction },
      output: {},
      status: 'stopped',
      resultSummary: task.stopReason || '当前 PageTask 要求停在人工处理节点',
      durationMs: 0,
      stopReason: task.stopReason || '当前 PageTask 要求停在人工处理节点',
    })
    return stopResult(task.stopReason || '当前 PageTask 要求停在人工处理节点', directive.instruction)
  }

  const calls = buildToolCalls(task, directive.allowedTargets)
  const outputs: string[] = []

  for (const call of calls) {
    signal.throwIfAborted()
    if (!directive.allowedTargets.includes(call.target)) {
      const message = `语义目标不在允许列表：${call.target}`
      await onActionLog?.({
        actionKind: call.actionKind,
        toolName: call.tool,
        target: call.target,
        input: call.input,
        output: {},
        status: 'stopped',
        resultSummary: message,
        durationMs: 0,
        stopReason: message,
      })
      if (call.required) throw new Error(message)
      outputs.push(`跳过：${message}`)
      continue
    }
    if (call.isClick && (task.requiresHumanBeforeSubmit || BLOCKED_CLICK_TARGETS.has(call.target))) {
      const reason = `点击动作需要人工确认：${call.label}`
      await onActionLog?.({
        actionKind: call.actionKind,
        toolName: call.tool,
        target: call.target,
        input: call.input,
        output: {},
        status: 'stopped',
        resultSummary: reason,
        durationMs: 0,
        stopReason: reason,
      })
      return stopResult(reason, directive.instruction, outputs)
    }
    const started = performance.now()
    try {
      const output = await agent.runTool(call.tool, call.input, signal)
      const durationMs = Math.round(performance.now() - started)
      outputs.push(output)
      await onActionLog?.({
        actionKind: call.actionKind,
        toolName: call.tool,
        target: call.target,
        input: call.input,
        output: { message: output },
        status: 'executed',
        resultSummary: output,
        durationMs,
        stopReason: '',
      })
    } catch (error) {
      const durationMs = Math.round(performance.now() - started)
      const message = error instanceof Error ? error.message : 'PageTask action failed'
      await onActionLog?.({
        actionKind: call.actionKind,
        toolName: call.tool,
        target: call.target,
        input: call.input,
        output: { message },
        status: 'error',
        resultSummary: message,
        durationMs,
        stopReason: message,
      })
      throw error
    }
  }

  if (!outputs.length) {
    return {
      success: false,
      stopped: false,
      summary: 'PageTask 没有可确定性执行的动作',
      outputs,
      fallbackInstruction: directive.instruction,
    }
  }

  return {
    success: true,
    stopped: false,
    summary: `已按结构化 PageTask 执行 ${outputs.length} 个确定性动作。`,
    outputs,
    fallbackInstruction: directive.instruction,
  }
}

function buildToolCalls(task: PageTaskEnvelope, allowedTargets: string[]) {
  return task.actions
    .map(action => actionToToolCall(action, task, allowedTargets))
    .filter((call): call is ToolCall => Boolean(call))
}

function actionToToolCall(
  action: PageTaskActionEnvelope,
  task: PageTaskEnvelope,
  allowedTargets: string[],
): ToolCall | null {
  const required = Boolean(action.required)
  const label = action.label || action.kind
  const target = action.target
  if (!target && action.kind !== 'stopForHuman') return null

  if (action.kind === 'fillForm') {
    return {
      actionKind: action.kind,
      tool: 'fill_form_by_targets',
      input: {
        fields: [{
          target,
          value: action.value || valueFromPayload(task, action.field),
          label,
        }],
      },
      label,
      target,
      required,
      isClick: false,
    }
  }
  if (action.kind === 'fillTextarea') {
    return {
      actionKind: action.kind,
      tool: 'fill_textarea_by_target',
      input: { target, text: action.value || valueFromPayload(task, action.field) },
      label,
      target,
      required,
      isClick: false,
    }
  }
  if (action.kind === 'selectOption') {
    return {
      actionKind: action.kind,
      tool: 'select_option_by_label',
      input: { target, value: action.value || valueFromPayload(task, action.field) },
      label,
      target,
      required,
      isClick: false,
    }
  }
  if (action.kind === 'clickSemantic' || action.kind === 'openPanel') {
    return {
      actionKind: action.kind,
      tool: 'click_semantic_target',
      input: { target },
      label,
      target,
      required,
      isClick: true,
    }
  }
  if (action.kind === 'locateEvidence') {
    const evidenceIds = action.value
      ? [action.value]
      : arrayFromPayload(task.businessPayload.evidenceIds)
    return {
      actionKind: action.kind,
      tool: 'locate_evidence',
      input: { target, evidence_ids: evidenceIds },
      label,
      target,
      required,
      isClick: false,
    }
  }
  if (action.kind === 'scrollToRegion') {
    return {
      actionKind: action.kind,
      tool: 'scroll_to_region',
      input: { target },
      label,
      target,
      required,
      isClick: false,
    }
  }
  if (action.kind === 'waitForState') {
    return {
      actionKind: action.kind,
      tool: 'wait_for_business_state',
      input: { target: allowedTargets.includes(target) ? target : undefined, state: action.value || label },
      label,
      target,
      required,
      isClick: false,
    }
  }
  if (action.kind === 'stopForHuman') {
    return {
      actionKind: action.kind,
      tool: 'stop_for_human',
      input: { reason: action.value || task.stopReason || label },
      label,
      target: target || 'human-confirm',
      required,
      isClick: false,
    }
  }
  return null
}

function valueFromPayload(task: PageTaskEnvelope, field = '') {
  const draft = task.businessPayload.ticketDraft
  if (field && isRecord(draft) && draft[field] != null) return String(draft[field])
  if (field && task.businessPayload[field] != null) return String(task.businessPayload[field])
  return ''
}

function arrayFromPayload(value: unknown) {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function stopResult(reason: string, fallbackInstruction: string, outputs: string[] = []) {
  return {
    success: false,
    stopped: true,
    summary: reason,
    outputs,
    fallbackInstruction,
  }
}
