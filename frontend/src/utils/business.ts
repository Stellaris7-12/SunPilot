import type { AiProcessResult, EvaluationMetrics, Ticket, TicketStatus, TraceStep } from '../types';

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

const statusMap: Record<string, UiMeta> = {
  open: { label: '待处理', tone: 'blue', description: '等待坐席启动处理' },
  in_progress: { label: '处理中', tone: 'blue', description: '系统正在生成业务建议' },
  pending_info: { label: '待补充', tone: 'amber', description: '需要客户或坐席补齐关键信息' },
  pending_human_confirm: { label: '待确认', tone: 'amber', description: '涉及敏感操作，需人工确认后继续' },
  pending_human_review: { label: '待复核', tone: 'green', description: '已有处理建议，等待坐席复核回单' },
  escalated: { label: '已升级', tone: 'red', description: '需要人工团队接管' },
  failed: { label: '处理失败', tone: 'red', description: '自动流程失败，需要人工排查' },
  closed: { label: '已结案', tone: 'neutral', description: '工单已完成关闭' },
};

const agentStepMap: Record<string, string> = {
  intake_agent: 'intake',
  classifier_agent: 'classify',
  escalation_agent: 'guard',
  resolution_agent: 'execute',
  notification_agent: 'reply',
};

export function statusMeta(status?: string): UiMeta {
  return statusMap[status || ''] || { label: status || '未知', tone: 'neutral', description: '等待业务确认状态' };
}

export function riskMeta(riskLevel?: string, riskLabel?: string): UiMeta {
  if (riskLevel === 'high') return { label: riskLabel || '高风险', tone: 'red', description: '禁止自动结论，优先人工接管' };
  if (riskLevel === 'medium') return { label: riskLabel || '中风险', tone: 'amber', description: '需要人工确认关键动作' };
  return { label: riskLabel || '低风险', tone: 'green', description: '可按标准流程处理' };
}

export function scenarioFamily(ticket: Ticket, result?: AiProcessResult | null): ScenarioFamily {
  const text = [
    ticket.scene,
    ticket.title,
    result?.intent?.label,
    result?.workflowName,
    result?.toolName,
  ].filter(Boolean).join(' ');

  if (/优惠|券|coupon|权益补发/i.test(text)) {
    return { id: 'benefit-reissue', label: '权益/优惠券', tone: 'green', deskFocus: '核对达标原因、补发结果和证据编号' };
  }
  if (/申请|进度|progress/i.test(text)) {
    return { id: 'application', label: '申请进度', tone: 'blue', deskFocus: '同步当前节点、预计完成时间和后续提醒' };
  }
  if (/资料|地址|手机号|联系人|address|profile/i.test(text)) {
    return { id: 'profile', label: '资料变更', tone: 'amber', deskFocus: '核验身份、确认敏感字段和人工授权' };
  }
  if (/交易|争议|盗刷|境外|拒付|transaction|dispute|fraud/i.test(text)) {
    return { id: 'transaction', label: '交易/争议', tone: 'red', deskFocus: '核查流水、识别风险并保留人工复核路径' };
  }
  if (/投诉|催办|征信|跨部门|年费|积分|额度|还款|停卡|挂失|complaint/i.test(text)) {
    return { id: 'manual', label: '人工协办', tone: 'red', deskFocus: '生成协办摘要、说明升级原因和接管建议' };
  }
  return { id: 'general', label: ticket.scene || '通用工单', tone: 'neutral', deskFocus: '先识别诉求，再确认是否可自动处理' };
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
  const responseEvidence = result.toolResponse?.evidenceId;
  if (typeof responseEvidence === 'string' && responseEvidence) ids.add(responseEvidence);
  result.notification?.standardReply?.evidenceIds?.forEach(id => ids.add(id));
  result.notification?.internalNotice?.evidenceIds?.forEach(id => ids.add(id));
  result.notification?.reviewSummary?.toolEvidenceIds?.forEach(id => ids.add(id));
  const matches = result.toolEvidence?.match(/[A-Z]{2,}-[A-Z0-9-]+|\bEVIDENCE[-_][A-Z0-9-]+\b/gi) || [];
  matches.forEach(id => ids.add(id));
  return Array.from(ids);
}

export function caseConclusion(ticket: Ticket, result?: AiProcessResult | null): string {
  if (!result) return '尚未生成处理建议，坐席可启动 AI 辅助处理。';
  if (result.failureReason) return result.failureReason;
  const businessResult = result.toolResponse?.businessResult;
  if (typeof businessResult === 'string' && businessResult) return businessResult;
  if (result.notification?.closureSuggestion?.reason) return result.notification.closureSuggestion.reason;
  if (result.notification?.standardReply?.body) return result.notification.standardReply.body;
  if (result.missingFields?.length) return `还缺少 ${result.missingFields.join('、')}，需先补齐后继续处理。`;
  return `${scenarioFamily(ticket, result).label}已完成业务分诊，等待坐席复核。`;
}

export function suggestedAction(ticket: Ticket, result?: AiProcessResult | null, processing = false): string {
  if (processing) return '等待系统返回';
  if (!result) return '启动 AI 处理';
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

export function businessSteps(traceSteps: TraceStep[], result?: AiProcessResult | null, processing = false): BusinessStep[] {
  const stepStatus = (id: string): BusinessStep['status'] => {
    const related = traceSteps.filter(step => agentStepMap[step.agentId] === id);
    if (related.some(step => step.status === 'FAILED')) return 'blocked';
    if (related.some(step => step.status === 'RUNNING')) return 'running';
    if (related.some(step => step.status === 'SUCCESS')) return 'done';
    if (result && ['intake', 'classify', 'guard', 'execute', 'reply'].includes(id)) return 'done';
    return processing ? 'waiting' : 'waiting';
  };

  const executeStatus = result?.toolName || result?.failureReason || result?.missingFields?.length ? stepStatus('execute') : stepStatus('execute');
  return [
    { id: 'intake', label: '接单提取', description: '识别客户、诉求和关键字段', status: stepStatus('intake') },
    { id: 'classify', label: '业务分诊', description: '判断场景、优先级和处理路径', status: stepStatus('classify') },
    { id: 'guard', label: '风险拦截', description: '检查缺失字段、敏感操作和升级条件', status: stepStatus('guard') },
    { id: 'execute', label: '执行处理', description: '调用工具或生成人工协办建议', status: executeStatus },
    { id: 'reply', label: '回单生成', description: '生成客户回单和内部复核摘要', status: stepStatus('reply') },
  ];
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
    { label: '状态匹配率', value: formatPercent(metrics?.closedLoopSuccessRate), hint: '状态/预期结果匹配，不等同真实结案率' },
    { label: '工具命中率', value: formatPercent(metrics?.toolCorrectness), hint: 'Resolution 工具选择与参数结果' },
    { label: '字段完整率', value: formatPercent(metrics?.fieldCompleteness), hint: 'Intake 关键字段抽取' },
    { label: '平均耗时', value: formatMs(metrics?.avgProcessingMs), hint: '40 条真实链路平均处理耗时' },
  ];
}
