import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(dirname(fileURLToPath(import.meta.url)))

function read(path) {
  return readFileSync(join(root, path), 'utf8')
}

function assertIncludes(source, needle, label) {
  if (!source.includes(needle)) {
    throw new Error(`${label} is missing: ${needle}`)
  }
}

function assertNotIncludes(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} must not include: ${needle}`)
  }
}

const typeSource = read('src/types/index.ts')
const bridgeSource = read('src/page-agent/taskBridge.ts')
const adapterSource = read('src/page-agent/semanticAdapter.ts')
const toolsSource = read('src/page-agent/tools/index.ts')
const executorSource = read('src/page-agent/pageTaskExecutor.ts')
const agentPanelSource = read('src/page-agent/panel/AgentPanel.vue')
const apiSource = read('src/api/index.ts')
const storeSource = read('src/stores/ticket.ts')
const enterpriseShellSource = read('src/views/EnterpriseTicketShellView.vue')
const appHeaderSource = read('src/components/layout/AppHeader.vue')
const legacyDetailSource = read('src/views/LegacyTicketDetailView.vue')
const legacyAssistantSource = read('src/components/ai/PageAssistantPanel.vue')

for (const mode of ['auto', 'suggest', 'display', 'stop']) {
  assertIncludes(typeSource, `'${mode}'`, `PageTaskMode ${mode}`)
}

for (const scene of ['call-intake', 'ticket-reply', 'evidence-review', 'human-confirm']) {
  assertIncludes(typeSource, `'${scene}'`, `PageTaskScene ${scene}`)
  assertIncludes(adapterSource, `'${scene}'`, `semantic adapter scene ${scene}`)
}

for (const action of [
  'fillForm',
  'fillTextarea',
  'selectOption',
  'clickSemantic',
  'locateEvidence',
  'scrollToRegion',
  'openPanel',
  'waitForState',
  'stopForHuman',
]) {
  assertIncludes(typeSource, `'${action}'`, `PageTask action ${action}`)
}

for (const toolName of [
  'fill_form_by_targets',
  'fill_textarea_by_target',
  'select_option_by_label',
  'click_semantic_target',
  'scroll_to_region',
  'locate_evidence',
  'wait_for_business_state',
  'stop_for_human',
]) {
  assertIncludes(toolsSource, `'${toolName}'`, `custom tool ${toolName}`)
}

assertIncludes(
  bridgeSource,
  "task.mode === 'auto' && !task.requiresHumanBeforeSubmit && !shouldStop",
  'PageTask auto-run human gate',
)
assertIncludes(
  bridgeSource,
  '<page_task_json>',
  'structured PageTask directive payload',
)
assertIncludes(
  adapterSource,
  'normalizeAllowedTargets',
  'semantic target normalization',
)
assertIncludes(
  executorSource,
  'executePageTaskDeterministically',
  'deterministic PageTask executor',
)
assertIncludes(
  executorSource,
  'BLOCKED_CLICK_TARGETS',
  'dangerous click target gate',
)
assertIncludes(
  agentPanelSource,
  'maybeRunPageTask',
  'SunPilot deterministic PageTask path',
)
assertIncludes(
  executorSource,
  'PageTaskActionAuditEntry',
  'deterministic PageTask action audit payload',
)
assertIncludes(
  agentPanelSource,
  'recordDeterministicActionLog',
  'SunPilot PageActionLog persistence hook',
)
assertIncludes(
  storeSource,
  'recordPageActionLog',
  'store PageActionLog persistence',
)
assertIncludes(
  apiSource,
  '/page-action-logs',
  'PageActionLog API endpoint',
)
assertIncludes(
  agentPanelSource,
  '切换 ReAct 兜底',
  'ReAct fallback after deterministic failure',
)
assertIncludes(
  agentPanelSource,
  "const composerMode = ref<ComposerMode>('qa')",
  'SunPilot composer defaults to QA mode',
)
assertIncludes(
  agentPanelSource,
  'answerQuestion(task)',
  'SunPilot QA mode must answer without PageAgent execution',
)
assertIncludes(
  agentPanelSource,
  "composerMode.value = 'task'",
  'SunPilot quick actions switch to task mode',
)
assertIncludes(
  agentPanelSource,
  'class="mode-switch"',
  'SunPilot composer mode switch UI',
)
assertIncludes(
  agentPanelSource,
  'class="model-select"',
  'SunPilot model selector uses native select to avoid clipped menus',
)

if (appHeaderSource.includes('启动 AI') || appHeaderSource.includes('@process')) {
  throw new Error('AI process buttons must stay inside SunPilot AgentPanel, not AppHeader')
}
for (const source of [
  ['EnterpriseTicketShellView', enterpriseShellSource],
  ['AppHeader', appHeaderSource],
  ['LegacyTicketDetailView', legacyDetailSource],
  ['PageAssistantPanel', legacyAssistantSource],
]) {
  for (const label of [
    '启动 AI 处理',
    '重新 AI 处理',
    'AI处理中',
    '生成发单草稿',
    '填入发单表单',
    '填入回单草稿',
    '进入复核区',
  ]) {
    assertNotIncludes(source[1], label, `${source[0]} SunPilot-only AI action`)
  }
}
assertNotIncludes(
  enterpriseShellSource,
  '@click="handleProcess"',
  'EnterpriseTicketShellView AI process direct button',
)
if (legacyDetailSource.includes('PageAssistantPanel')) {
  throw new Error('Legacy detail must mount SunPilot AgentPanel instead of PageAssistantPanel')
}
if (legacyAssistantSource.includes('启动 AI') || legacyAssistantSource.includes('重新生成建议')) {
  throw new Error('PageAssistantPanel compatibility wrapper must not render legacy AI buttons')
}
assertIncludes(
  legacyDetailSource,
  '<AgentPanel',
  'legacy detail SunPilot panel',
)
assertIncludes(
  legacyAssistantSource,
  '<AgentPanel',
  'PageAssistantPanel SunPilot wrapper',
)
assertIncludes(
  enterpriseShellSource,
  '<AgentPanel',
  'enterprise shell SunPilot panel',
)
assertIncludes(
  enterpriseShellSource,
  '@start-ai-process="handleProcess"',
  'enterprise shell delegates AI process through SunPilot',
)
assertIncludes(
  enterpriseShellSource,
  'syncSelectionToFilteredTickets',
  'enterprise shell keeps selected ticket aligned with filters',
)
assertIncludes(
  enterpriseShellSource,
  '@click="selectBucket(bucket.id)"',
  'enterprise bucket buttons must update filtered selection',
)
assertIncludes(
  enterpriseShellSource,
  '@change="handleStatusFilterChange"',
  'enterprise status filter must update filtered selection',
)
assertIncludes(
  enterpriseShellSource,
  'store.clearSelectedTicket()',
  'enterprise shell clears stale detail when filters are empty',
)

console.log('page-agent smoke passed')
