import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(dirname(fileURLToPath(import.meta.url)))

function read(path) {
  return readFileSync(join(root, path), 'utf8')
}

function assertIncludes(source, needle, label) {
  if (!source.includes(needle)) throw new Error(`${label} is missing: ${needle}`)
}

function assertNotIncludes(source, needle, label) {
  if (source.includes(needle)) throw new Error(`${label} must not include: ${needle}`)
}

const typeSource = read('src/types/index.ts')
const appRouterSource = read('src/app/router.ts')
const bridgeSource = read('src/sunpilot/taskBridge.ts')
const adapterSource = read('src/sunpilot/semanticAdapter.ts')
const toolsSource = read('src/sunpilot/tools/index.ts')
const executorSource = read('src/sunpilot/pageTaskExecutor.ts')
const sunPilotSource = read('src/sunpilot/panel/SunPilotPanel.vue')
const enterpriseShellSource = read('src/views/EnterpriseTicketShellView.vue')
const catalogSource = read('src/domain/ticket/catalog.ts')
const missingInfoSource = read('src/domain/reply/missingInfo.ts')
const apiSource = read('src/api/index.ts')
const storeSource = read('src/stores/ticket.ts')

for (const path of [
  "'/'",
  "'/dispatch'",
  "'/dispatch/:category'",
  "'/reply'",
  "'/reply/:category'",
  "'/reply/tickets/:id'",
]) {
  assertIncludes(appRouterSource, path, `business route ${path}`)
}

for (const mode of ['auto', 'suggest', 'display', 'stop']) {
  assertIncludes(typeSource, `'${mode}'`, `PageTaskMode ${mode}`)
}

for (const scene of ['call-intake', 'ticket-reply', 'evidence-review', 'human-confirm']) {
  assertIncludes(typeSource, `'${scene}'`, `PageTaskScene ${scene}`)
  assertIncludes(adapterSource, `'${scene}'`, `semantic adapter scene ${scene}`)
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

assertIncludes(bridgeSource, '<page_task_json>', 'structured PageTask directive payload')
assertIncludes(executorSource, 'executePageTaskDeterministically', 'deterministic PageTask executor')
assertIncludes(executorSource, 'BLOCKED_CLICK_TARGETS', 'dangerous click target gate')
assertIncludes(sunPilotSource, 'maybeRunPageTask', 'SunPilot deterministic PageTask path')
assertIncludes(sunPilotSource, 'recordDeterministicActionLog', 'SunPilot PageActionLog persistence hook')
assertIncludes(storeSource, 'recordPageActionLog', 'store PageActionLog persistence')
assertIncludes(apiSource, '/page-action-logs', 'PageActionLog API endpoint')

for (const componentName of [
  'SunPilotSuggestionCard',
  'SunPilotQuickActions',
  'SunPilotBusinessFlow',
  'SunPilotFoldCard',
  'SunPilotComposer',
]) {
  assertIncludes(sunPilotSource, componentName, `SunPilot component ${componentName}`)
}

assertIncludes(enterpriseShellSource, '../sunpilot/panel/SunPilotPanel.vue', 'enterprise shell uses SunPilot module')
assertIncludes(enterpriseShellSource, '../components/business/BusinessFlow.vue', 'enterprise shell uses BusinessFlow component')
assertIncludes(enterpriseShellSource, '../domain/ticket/catalog', 'enterprise shell uses domain catalog')
assertIncludes(catalogSource, "couponType: '券种'", 'business field mapping couponType')
assertIncludes(catalogSource, "reason: '补发原因'", 'business field mapping reason')
assertIncludes(missingInfoSource, 'buildSupplementQuestion', 'reply missing-info question builder')

for (const label of [
  '结构化 PageTask',
  '后端 observation',
  '启动 AI 处理',
  '重新 AI 处理',
  'AI处理中',
]) {
  assertNotIncludes(enterpriseShellSource, label, `enterprise visible technical label ${label}`)
  assertNotIncludes(sunPilotSource, label, `SunPilot visible technical label ${label}`)
}

console.log('page-agent smoke passed')
