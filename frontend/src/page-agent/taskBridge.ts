import type { PageTaskActionEnvelope, PageTaskEnvelope } from '../types'
import { describeSemanticAdapter, normalizeAllowedTargets } from './semanticAdapter'

export interface PageTaskDirective {
  mode: PageTaskEnvelope['mode']
  summary: string
  instruction: string
  shouldAutoRun: boolean
  shouldStop: boolean
  allowedTargets: string[]
}

export function buildPageTaskDirective(task: PageTaskEnvelope): PageTaskDirective {
  const allowedTargets = normalizeAllowedTargets(task.scene, [
    ...task.allowedTargets,
    ...task.actions.map(action => action.target),
  ])
  const shouldStop = task.mode === 'stop'
  const shouldAutoRun = task.mode === 'auto' && !task.requiresHumanBeforeSubmit && !shouldStop
  const actionLines = task.actions.map(describeAction).join('\n')
  const summary = [
    `${task.scene} / ${task.mode} / ${task.actions.length} 个动作`,
    task.stopReason ? `停止原因：${task.stopReason}` : '',
  ].filter(Boolean).join('；')
  const instruction = [
    '按结构化 PageTask 执行当前页面任务。',
    '优先使用语义 custom tools；只有语义目标缺失或失败时才退回 DOM index 工具。',
    `执行模式：${task.mode}`,
    `允许目标：${allowedTargets.join(', ') || '无'}`,
    `页面适配器：${describeSemanticAdapter(task.scene) || '无'}`,
    actionLines ? `动作序列：\n${actionLines}` : '动作序列：无',
    task.stopReason ? `停止/接管原因：${task.stopReason}` : '',
    `<page_task_json>\n${JSON.stringify({ ...task, allowedTargets }, null, 2)}\n</page_task_json>`,
  ].filter(Boolean).join('\n')

  return {
    mode: task.mode,
    summary,
    instruction,
    shouldAutoRun,
    shouldStop,
    allowedTargets,
  }
}

function describeAction(action: PageTaskActionEnvelope, index: number) {
  const prefix = `${index + 1}. ${action.label || action.kind}`
  const field = action.field ? ` field=${action.field}` : ''
  const value = action.value ? ` value=${compact(action.value)}` : ''
  return `${prefix}: kind=${action.kind} target=${action.target}${field}${value}`
}

function compact(value: string, max = 120) {
  const normalized = value.replace(/\s+/g, ' ').trim()
  return normalized.length > max ? `${normalized.slice(0, max)}...` : normalized
}
