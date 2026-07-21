import type { AiProcessResult, EvaluationMetrics, Ticket, TicketOperationLog, TicketStatus, ToolCallLog, TraceStep } from '../types';

export type Tone = 'green' | 'blue' | 'amber' | 'red' | 'neutral';

export interface UiMeta {
  label: string;
  tone: Tone;
  description: string;
}

export interface ScenarioFamily {
  id: string;
  label: string;
  tone: Tone;
  deskFocus: string;
}

export interface WorkBucket {
  id: string;
  label: string;
  hint: string;
  count: number;
}

export interface BusinessStep {
  id: string;
  label: string;
  description: string;
  status: 'done' | 'running' | 'blocked' | 'waiting';
}

export interface EnterpriseMenuGroup {
  id: string;
  label: string;
  items: Array<{
    id: string;
    label: string;
    count: number;
    active?: boolean;
    sub?: boolean;
  }>;
}

export interface EvidenceItem {
  id: string;
  source: string;
  summary: string;
}

export interface OperationLog {
  id: string;
  time: string;
  operator: string;
  actionType: string;
  content: string;
  evidenceId: string;
  nextOwner: string;
  transition?: string;
}

export interface FieldVerificationItem {
  id: string;
  label: string;
  value: string;
  source: string;
  evidenceId: string;
  status: 'verified' | 'enriched' | 'missing' | 'conflict' | 'review';
  note: string;
}

export interface ReplyWorkspaceSection {
  id: 'customer' | 'internal' | 'review' | 'question' | 'followUp' | 'evidence';
  title: string;
  status: string;
  body: string;
  evidenceIds: string[];
}

export interface CopilotSuggestion {
  title: string;
  summary: string;
  tone: Tone;
  actions: Array<{
    id: 'process' | 'fill_reply' | 'locate_evidence' | 'locate_missing' | 'open_audit' | 'prepare_review' | 'prepare_confirm';
    label: string;
    disabled: boolean;
    reason?: string;
  }>;
}

const statusMap: Record<string, UiMeta> = {
  open: { label: '待处理', tone: 'blue', description: '等待坐席启动智能处理或人工处理。' },
  in_progress: { label: '处理中', tone: 'blue', description: '系统正在生成业务建议。' },
  pending_info: { label: '待补充', tone: 'amber', description: '缺少客户或业务关键字段，需要先追问补齐。' },
  pending_human_confirm: { label: '待确认', tone: 'amber', description: '涉及敏感动作，必须由坐席确认后继续。' },
  pending_human_review: { label: '待复核', tone: 'green', description: '已有处理建议，等待坐席复核回单和结案。' },
  escalated: { label: '已升级', tone: 'red', description: '需要人工团队接管，不允许包装为自动完成。' },
  failed: { label: '处理失败', tone: 'red', description: '自动流程失败，需要人工排查失败原因。' },
  closed: { label: '已结案', tone: 'neutral', description: '工单已完成归档。' },
};

const agentStepMap: Record<string, string> = {
  intake_agent: 'intake',
  classifier_agent: 'classify',
  escalation_agent: 'guard',
  resolution_agent: 'execute',
  notification_agent: 'reply',
};

const businessAgentLabel: Record<string, string> = {
  intake_agent: '接单提取',
  classifier_agent: '业务分诊',
  escalation_agent: '风险拦截',
  resolution_agent: '执行处理',
  notification_agent: '回单生成',
};

export function statusMeta(status?: string): UiMeta {
  return statusMap[status || ''] || { label: status || '未知', tone: 'neutral', description: '等待业务确认状态。' };
}

export function riskMeta(riskLevel?: string, riskLabel?: string): UiMeta {
  if (riskLevel === 'high') return { label: riskLabel || '高风险', tone: 'red', description: '禁止自动结论，优先人工接管。' };
  if (riskLevel === 'medium') return { label: riskLabel || '中风险', tone: 'amber', description: '需要人工确认关键动作。' };
  return { label: riskLabel || '低风险', tone: 'green', description: '可按标准流程处理。' };
}

export function scenarioFamily(ticket: Ticket, result?: AiProcessResult | null): ScenarioFamily {
  const text = [
    ticket.scene,
    ticket.title,
    result?.intent?.label,
    result?.workflowName,
    result?.toolName,
  ].filter(Boolean).join(' ');

  if (/优惠|券|coupon|权益补发|DINING/i.test(text)) {
    return { id: 'benefit-reissue', label: '权益/优惠券', tone: 'green', deskFocus: '核对达标原因、补发结果和证据编号。' };
  }
  if (/申请|进度|progress|application/i.test(text)) {
    return { id: 'application', label: '申请进度', tone: 'blue', deskFocus: '同步当前节点、预计完成时间和后续提醒。' };
  }
  if (/资料|地址|手机|联系人|address|profile/i.test(text)) {
    return { id: 'profile', label: '客户资料', tone: 'amber', deskFocus: '核验身份、确认敏感字段和人工授权。' };
  }
  if (/交易|争议|盗刷|境外|拒付|调单|transaction|dispute|fraud/i.test(text)) {
    return { id: 'transaction', label: '交易与风险', tone: 'red', deskFocus: '核查流水、识别风险并保留人工复核路径。' };
  }
  if (/投诉|催办|征信|跨部门|年费|积分|额度|还款|停卡|挂失|complaint/i.test(text)) {
    return { id: 'manual', label: '人工协办', tone: 'red', deskFocus: '生成协办摘要、说明升级原因和接管建议。' };
  }
  return { id: 'general', label: ticket.scene || '通用工单', tone: 'neutral', deskFocus: '先识别诉求，再确认是否可自动处理。' };
}

export function nextOwner(result?: AiProcessResult | null, status?: TicketStatus | string): string {
  const owner = result?.notification?.standardReply?.nextOwner || result?.notification?.internalNotice?.nextOwner;
  if (owner === 'customer') return '客户补充';
  if (owner === 'agent' || owner === 'system') return '系统继续处理';
  if (owner === 'human') return '坐席/复核岗';
  if (status === 'pending_info') return '客户补充';
  if (status === 'pending_human_confirm' || status === 'pending_human_review') return '坐席/复核岗';
  if (status === 'escalated' || status === 'failed') return '人工团队';
  if (status === 'closed') return '已完成';
  return '坐席';
}

export function evidenceIds(result?: AiProcessResult | null): string[] {
  if (!result) return [];
  const ids = new Set<string>();
  const responseEvidence = result.toolResponse?.evidenceId || result.toolResponse?.evidence_id;
  if (typeof responseEvidence === 'string' && responseEvidence) ids.add(responseEvidence);
  result.notification?.standardReply?.evidenceIds?.forEach(id => ids.add(id));
  result.notification?.internalNotice?.evidenceIds?.forEach(id => ids.add(id));
  result.notification?.reviewSummary?.toolEvidenceIds?.forEach(id => ids.add(id));
  const matches = result.toolEvidence?.match(/[A-Z]{2,}-[A-Z0-9-]+|\bEVIDENCE[-_][A-Z0-9-]+\b/gi) || [];
  matches.forEach(id => ids.add(id));
  return Array.from(ids);
}

export function evidenceItems(result?: AiProcessResult | null, toolCalls: ToolCallLog[] = []): EvidenceItem[] {
  const items = new Map<string, EvidenceItem>();
  evidenceIds(result).forEach(id => items.set(id, {
    id,
    source: result?.toolName || 'Agent',
    summary: typeof result?.toolResponse?.businessResult === 'string'
      ? result.toolResponse.businessResult
      : '已生成业务证据。',
  }));
  toolCalls.forEach(call => {
    if (!call.evidenceId) return;
    const response = call.response;
    items.set(call.evidenceId, {
      id: call.evidenceId,
      source: call.toolName,
      summary: call.success ? response?.businessResult || '工具调用成功。' : call.failureReason || '工具调用失败。',
    });
  });
  return Array.from(items.values());
}

function stringifyValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-';
  if (Array.isArray(value)) return value.join('、');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function fieldVerificationItems(result?: AiProcessResult | null): FieldVerificationItem[] {
  if (!result) return [];

  const items = new Map<string, FieldVerificationItem>();
  const enrichment = result.fieldEnrichment;
  const sourceTools = enrichment?.sourceTools?.length ? enrichment.sourceTools.join('、') : '工单文本';
  const enrichmentEvidence = enrichment?.evidenceIds?.join(' / ') || '-';

  result.fields?.forEach(field => {
    items.set(field.name, {
      id: field.name,
      label: field.label || field.name,
      value: stringifyValue(field.value),
      source: '接单提取',
      evidenceId: '-',
      status: 'verified',
      note: '来自原始工单文本，已进入业务处理上下文。',
    });
  });

  Object.entries(enrichment?.filledFields || {}).forEach(([key, value]) => {
    items.set(key, {
      id: key,
      label: key,
      value: stringifyValue(value),
      source: sourceTools,
      evidenceId: enrichmentEvidence,
      status: 'enriched',
      note: '已从客户、卡片、交易或权益系统自动核验补齐。',
    });
  });

  result.missingFields?.forEach(field => {
    items.set(field, {
      id: field,
      label: field,
      value: '-',
      source: '补全兜底',
      evidenceId: '-',
      status: 'missing',
      note: '受控工具仍无法安全补齐，需要客户或人工补充。',
    });
  });

  enrichment?.conflicts?.forEach((conflict, index) => {
    items.set(`conflict-${index}`, {
      id: `conflict-${index}`,
      label: '补全冲突',
      value: conflict,
      source: sourceTools,
      evidenceId: enrichmentEvidence,
      status: 'conflict',
      note: '存在多源结果不一致，不能直接自动结论。',
    });
  });

  result.verifyChecks?.forEach((check, index) => {
    items.set(`verify-${index}`, {
      id: `verify-${index}`,
      label: check.label,
      value: check.status,
      source: '风险规则',
      evidenceId: evidenceIds(result)[0] || '-',
      status: /待|需|拦截|失败/.test(check.status) ? 'review' : 'verified',
      note: '用于解释当前处理是否允许自动继续。',
    });
  });

  return Array.from(items.values());
}

export function replyWorkspaceSections(result?: AiProcessResult | null, ticket?: Ticket | null): ReplyWorkspaceSection[] {
  const notification = result?.notification;
  const evidence = evidenceIds(result);
  const standardReply = notification?.standardReply?.body || result?.replyDraft || '';
  const review = notification?.reviewSummary;
  const family = ticket ? scenarioFamily(ticket, result) : null;
  const question = result?.missingFields?.length
    ? `请客户补充 ${result.missingFields.join('、')} 后继续处理。`
    : '暂无必须追问客户的信息。';
  const followUp = notification?.followUp?.enabled
    ? notification.followUp.template
    : '结案后按客户满意度回访规则预留跟进。';

  return [
    {
      id: 'customer',
      title: notification?.standardReply?.title || '客户回单',
      status: standardReply ? '待坐席复核' : '未生成',
      body: standardReply,
      evidenceIds: notification?.standardReply?.evidenceIds || evidence,
    },
    {
      id: 'internal',
      title: notification?.internalNotice?.title || '内部处理意见',
      status: notification?.internalNotice ? '已生成' : '待生成',
      body: notification?.internalNotice?.body || family?.deskFocus || '',
      evidenceIds: notification?.internalNotice?.evidenceIds || evidence,
    },
    {
      id: 'review',
      title: '复核摘要',
      status: review ? '待复核岗确认' : '待生成',
      body: review?.suggestedAction || review?.reason || result?.riskDecision || '',
      evidenceIds: review?.toolEvidenceIds || evidence,
    },
    {
      id: 'question',
      title: '客户追问',
      status: result?.missingFields?.length ? '需要补充' : '无需追问',
      body: question,
      evidenceIds: [],
    },
    {
      id: 'followUp',
      title: '跟进计划',
      status: notification?.followUp?.enabled ? '已预留' : '默认规则',
      body: followUp,
      evidenceIds: [],
    },
    {
      id: 'evidence',
      title: '证据附件',
      status: evidence.length ? '可插入回单' : '暂无证据',
      body: evidence.length ? evidence.join(' / ') : '启动处理后展示证据编号。',
      evidenceIds: evidence,
    },
  ];
}

export function caseConclusion(ticket: Ticket, result?: AiProcessResult | null): string {
  if (!result) return '尚未生成处理建议，坐席可启动 SunPilot 辅助处理。';
  if (result.failureReason) return result.failureReason;
  const businessResult = result.toolResponse?.businessResult;
  if (typeof businessResult === 'string' && businessResult) return businessResult;
  if (result.notification?.closureSuggestion?.reason) return result.notification.closureSuggestion.reason;
  if (result.notification?.standardReply?.body) return result.notification.standardReply.body;
  if (result.missingFields?.length) return `还缺少 ${result.missingFields.join('、')}，需要先补齐后继续处理。`;
  return `${scenarioFamily(ticket, result).label}已完成业务分诊，等待坐席复核。`;
}

export function suggestedAction(ticket: Ticket, result?: AiProcessResult | null, processing = false): string {
  if (processing) return '等待系统返回';
  if (!result) return '启动智能处理';
  if (ticket.status === 'pending_info' || result.missingFields?.length) return '请求客户补充';
  if (ticket.status === 'pending_human_confirm') return '人工确认执行';
  if (ticket.status === 'pending_human_review') return '复核回单';
  if (ticket.status === 'escalated') return '人工团队接管';
  if (ticket.status === 'failed') return '查看失败原因';
  if (ticket.status === 'closed') return '查看归档';
  if (result.notification?.closureSuggestion?.canClose) return '复核后结案';
  return '继续人工处理';
}

export function workBuckets(tickets: Ticket[]): WorkBucket[] {
  const count = (predicate: (ticket: Ticket) => boolean) => tickets.filter(predicate).length;
  return [
    { id: 'all', label: '全部', hint: '全部工单', count: tickets.length },
    { id: 'todo', label: '待处理', hint: '需要坐席启动或跟进', count: count(t => ['open', 'in_progress'].includes(t.status)) },
    { id: 'info', label: '待补充', hint: '缺客户或业务字段', count: count(t => t.status === 'pending_info') },
    { id: 'confirm', label: '待确认', hint: '敏感操作待确认', count: count(t => t.status === 'pending_human_confirm') },
    { id: 'review', label: '待复核', hint: '回单和结案建议', count: count(t => t.status === 'pending_human_review') },
    { id: 'escalated', label: '已升级', hint: '人工团队接管', count: count(t => ['escalated', 'failed'].includes(t.status)) },
    { id: 'closed', label: '已结案', hint: '已完成归档', count: count(t => t.status === 'closed') },
  ];
}

export function bucketMatches(bucket: string, ticket: Ticket): boolean {
  if (bucket === 'all') return true;
  if (bucket === 'todo') return ['open', 'in_progress'].includes(ticket.status);
  if (bucket === 'info') return ticket.status === 'pending_info';
  if (bucket === 'confirm') return ticket.status === 'pending_human_confirm';
  if (bucket === 'review') return ticket.status === 'pending_human_review';
  if (bucket === 'escalated') return ['escalated', 'failed'].includes(ticket.status);
  if (bucket === 'closed') return ticket.status === 'closed';
  return true;
}

export function enterpriseMenuGroups(tickets: Ticket[], activeFamily = 'all'): EnterpriseMenuGroup[] {
  const byStatus = (statuses: string[]) => tickets.filter(ticket => statuses.includes(ticket.status)).length;
  const byFamily = (familyId: string) => tickets.filter(ticket => scenarioFamily(ticket).id === familyId).length;
  const countByText = (pattern: RegExp) => tickets.filter(ticket => pattern.test(`${ticket.title} ${ticket.scene} ${ticket.content}`)).length;
  return [
    {
      id: 'queue',
      label: '受理队列',
      items: [
        { id: 'all', label: '待处理工单', count: tickets.length, active: activeFamily === 'all' },
        { id: 'info', label: '待补充信息', count: byStatus(['pending_info']), sub: true },
        { id: 'confirm', label: '待人工确认', count: byStatus(['pending_human_confirm']), sub: true },
        { id: 'review', label: '待回单复核', count: byStatus(['pending_human_review']), sub: true },
        { id: 'escalated', label: '已升级待接管', count: byStatus(['escalated', 'failed']), sub: true },
      ],
    },
    {
      id: 'benefit',
      label: '权益与活动',
      items: [
        { id: 'benefit-reissue', label: '优惠券补发', count: byFamily('benefit-reissue'), active: activeFamily === 'benefit-reissue' },
        { id: 'dining', label: '餐饮券/满减券', count: countByText(/餐饮|满减|DINING/i), sub: true },
        { id: 'airport', label: '机场贵宾厅权益', count: countByText(/机场|贵宾厅/i), sub: true },
        { id: 'points', label: '积分到账/兑换', count: countByText(/积分|兑换/i), sub: true },
      ],
    },
    {
      id: 'customer',
      label: '客户资料',
      items: [
        { id: 'profile', label: '地址变更', count: byFamily('profile'), active: activeFamily === 'profile' },
        { id: 'phone', label: '手机号变更', count: countByText(/手机|手机号/i), sub: true },
        { id: 'contact', label: '联系人变更', count: countByText(/联系人/i), sub: true },
        { id: 'company', label: '商务卡公司资料', count: countByText(/商务卡|公司资料/i), sub: true },
      ],
    },
    {
      id: 'risk',
      label: '交易与风险',
      items: [
        { id: 'transaction', label: '交易查询', count: byFamily('transaction'), active: activeFamily === 'transaction' },
        { id: 'fraud', label: '非本人交易', count: countByText(/非本人|盗刷/i), sub: true },
        { id: 'chargeback', label: '调单/拒付', count: countByText(/调单|拒付/i), sub: true },
        { id: 'oversea', label: '境外交易核查', count: countByText(/境外/i), sub: true },
      ],
    },
    {
      id: 'accounting',
      label: '申请与账务',
      items: [
        { id: 'application', label: '申请进度查询', count: byFamily('application'), active: activeFamily === 'application' },
        { id: 'limit', label: '额度咨询', count: countByText(/额度/i), sub: true },
        { id: 'annual-fee', label: '年费调整', count: countByText(/年费/i), sub: true },
        { id: 'repayment', label: '还款协商', count: countByText(/还款|延期/i), sub: true },
      ],
    },
    {
      id: 'manual',
      label: '人工协办',
      items: [
        { id: 'manual', label: '投诉升级', count: byFamily('manual'), active: activeFamily === 'manual' },
        { id: 'credit', label: '征信异议', count: countByText(/征信/i), sub: true },
        { id: 'cross-team', label: '跨部门协办', count: countByText(/跨部门|协办/i), sub: true },
        { id: 'retry', label: '失败重试工单', count: byStatus(['failed']), sub: true },
      ],
    },
  ];
}

export function businessSteps(traceSteps: TraceStep[], result?: AiProcessResult | null, processing = false): BusinessStep[] {
  const stepStatus = (id: string): BusinessStep['status'] => {
    const related = traceSteps.filter(step => agentStepMap[step.agentId] === id);
    if (related.some(step => step.status === 'FAILED')) return 'blocked';
    if (related.some(step => step.status === 'RUNNING')) return 'running';
    if (related.some(step => step.status === 'SUCCESS')) return 'done';
    if (result && ['intake', 'classify', 'guard', 'execute', 'reply'].includes(id)) return 'done';
    return processing ? 'waiting' : 'waiting';
  };

  return [
    { id: 'intake', label: '接单提取', description: '识别客户、诉求和关键字段', status: stepStatus('intake') },
    { id: 'classify', label: '业务分诊', description: '判断场景、优先级和处理路径', status: stepStatus('classify') },
    { id: 'guard', label: '风险拦截', description: '检查缺失字段、敏感操作和升级条件', status: stepStatus('guard') },
    { id: 'execute', label: '执行处理', description: '调用工具或生成人工协办建议', status: stepStatus('execute') },
    { id: 'reply', label: '回单生成', description: '生成客户回单和内部复核摘要', status: stepStatus('reply') },
  ];
}

export function operationLogs(
  ticket: Ticket | null,
  result: AiProcessResult | null,
  traceSteps: TraceStep[],
  toolCalls: ToolCallLog[] = [],
  ticketOperations: TicketOperationLog[] = [],
): OperationLog[] {
  if (!ticket) return [];
  const rows: OperationLog[] = [{
    id: `${ticket.id}-created`,
    time: formatShortTime(ticket.createdAt),
    operator: '客服坐席',
    actionType: '创建工单',
    content: '人工客服转办后录入客户诉求。',
    evidenceId: '-',
    nextOwner: result ? nextOwner(result, ticket.status) : '坐席',
  }];

  ticketOperations.forEach(operation => {
    rows.push({
      id: `${ticket.id}-operation-${operation.id}`,
      time: formatShortTime(operation.createdAt),
      operator: operation.operator || '坐席',
      actionType: operation.operation,
      content: stringifyValue(operation.detail),
      evidenceId: '-',
      nextOwner: result ? nextOwner(result, ticket.status) : '坐席',
      transition: `${statusMeta(operation.fromStatus).label} -> ${statusMeta(operation.toStatus).label}`,
    });
  });

  traceSteps.forEach((step, index) => {
    rows.push({
      id: `${ticket.id}-trace-${index}`,
      time: result ? 'AI处理' : '待处理',
      operator: 'Agent',
      actionType: businessAgentLabel[step.agentId] || step.agent,
      content: step.summary || `${businessAgentLabel[step.agentId] || step.agent}已执行。`,
      evidenceId: '-',
      nextOwner: result ? nextOwner(result, ticket.status) : '坐席',
    });
  });

  toolCalls.forEach(call => {
    const response = call.response;
    rows.push({
      id: `${ticket.id}-tool-${call.id}`,
      time: formatShortTime(call.createdAt),
      operator: 'Agent',
      actionType: '工具调用',
      content: `${call.toolName}：${call.success ? response?.businessResult || '执行成功' : call.failureReason || '执行失败'}`,
      evidenceId: call.evidenceId || '-',
      nextOwner: response?.requiresHuman ? '人工团队' : nextOwner(result, ticket.status),
    });
  });

  if (result?.notification?.standardReply?.body) {
    rows.push({
      id: `${ticket.id}-reply`,
      time: 'AI处理',
      operator: 'Agent',
      actionType: '生成回单',
      content: result.notification.closureSuggestion?.canClose ? '已生成标准回单和结案建议。' : '已生成回单草稿，等待人工复核。',
      evidenceId: evidenceIds(result)[0] || '-',
      nextOwner: nextOwner(result, ticket.status),
    });
  }

  if (ticket.status === 'closed') {
    rows.push({
      id: `${ticket.id}-closed`,
      time: '已归档',
      operator: '坐席',
      actionType: '复核结案',
      content: '坐席通过主系统结案按钮提交最终回单。',
      evidenceId: evidenceIds(result)[0] || '-',
      nextOwner: '已完成',
    });
  }

  return rows;
}

export function copilotSuggestion(ticket: Ticket | null, result: AiProcessResult | null, processing = false): CopilotSuggestion {
  if (!ticket) {
    return {
      title: '请选择工单',
      summary: '选择左侧队列中的工单后，SunPilot 会读取当前上下文并生成辅助动作。',
      tone: 'neutral',
      actions: [],
    };
  }

  const status = statusMeta(ticket.status);
  const canFillReply = Boolean(result?.notification?.standardReply?.body || result?.replyDraft);
  const canLocateEvidence = evidenceIds(result).length > 0;
  const hasMissing = Boolean(result?.missingFields?.length);
  const canReview = Boolean(result);
  const needsConfirm = ticket.status === 'pending_human_confirm';
  const title = result
    ? suggestedAction(ticket, result, processing)
    : '等待启动 SunPilot';
  const summary = result
    ? caseConclusion(ticket, result)
    : 'SunPilot 只读取当前工单上下文，生成分诊、字段、风险、证据和回单建议；业务状态仍由主系统按钮控制。';

  return {
    title,
    summary,
    tone: status.tone,
    actions: [
      { id: 'process', label: result ? '生成处理建议' : '生成处理建议', disabled: processing, reason: processing ? '正在处理当前工单' : undefined },
      { id: 'prepare_confirm', label: '进入人工确认', disabled: !needsConfirm, reason: needsConfirm ? undefined : '当前工单不处于待人工确认状态' },
      { id: 'fill_reply', label: '填入回单', disabled: !canFillReply, reason: canFillReply ? undefined : '暂无可填入的回单草稿' },
      { id: 'locate_evidence', label: '定位证据', disabled: !canLocateEvidence, reason: canLocateEvidence ? undefined : '暂无证据编号' },
      { id: 'locate_missing', label: '请求补充', disabled: !hasMissing, reason: hasMissing ? undefined : '当前未识别到缺失字段' },
      { id: 'open_audit', label: '打开系统审计', disabled: !canReview, reason: canReview ? undefined : '尚未生成 AI 处理结果' },
      { id: 'prepare_review', label: '进入回单复核', disabled: !canReview, reason: canReview ? undefined : '尚未生成回单建议' },
    ],
  };
}

export function formatPercent(value?: number): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '暂无';
  return `${(value * 100).toFixed(1)}%`;
}

export function formatMs(value?: number): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '暂无';
  if (value >= 1000) return `${(value / 1000).toFixed(1)} 秒`;
  return `${value.toFixed(0)} ms`;
}

export function metricCards(metrics?: EvaluationMetrics | null) {
  return [
    { label: '状态匹配率', value: formatPercent(metrics?.closedLoopSuccessRate), hint: '状态/预期结果匹配，不等同真实客户结案率。' },
    { label: '业务能力匹配率', value: formatPercent(metrics?.toolCorrectness), hint: '处理能力选择与参数结果。' },
    { label: '字段完整率', value: formatPercent(metrics?.fieldCompleteness), hint: 'Intake 关键字段抽取。' },
    { label: '平均耗时', value: formatMs(metrics?.avgProcessingMs), hint: '40 条真实链路平均处理耗时。' },
  ];
}

export function formatShortTime(value?: string): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const pad = (num: number) => String(num).padStart(2, '0');
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
