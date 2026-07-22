import type { PageAction, PageActionType, PageBusinessContext, PageTaskPlan, RiskLevel } from '../../types';

export type PageAgentIntent =
  | 'call_intake'
  | 'process_ticket'
  | 'auto_reply'
  | 'locate_evidence'
  | 'save_draft'
  | 'close_ticket'
  | 'stop'
  | 'unknown';

export interface PageAgentIntentResult {
  intent: PageAgentIntent;
  label: string;
  reason: string;
}

const allowedTools: PageActionType[] = ['observe', 'scroll', 'highlight', 'input', 'click', 'wait', 'verify', 'stop'];

const writableDraftFields = [
  'title',
  'customerId',
  'customerName',
  'phone',
  'cardLast4',
  'scene',
  'category',
  'subcategory',
  'priority',
  'riskLabel',
  'riskLevel',
  'content',
];

function step(id: string, type: PageActionType, target: string, label: string, value = '', riskLevel: RiskLevel = 'low'): PageAction {
  return { id, type, target, label, value, riskLevel };
}

function contextRisk(context: PageBusinessContext): RiskLevel {
  return context.riskLevel || context.ticketDraft?.riskLevel || 'low';
}

export function resolvePageAgentIntent(instruction: string, context: PageBusinessContext): PageAgentIntentResult {
  const text = instruction.trim();
  if (!text) {
    return { intent: 'unknown', label: '未识别任务', reason: 'empty_instruction' };
  }
  if (/停止|接管|暂停|中止|别动|不要继续/.test(text)) {
    return { intent: 'stop', label: '停止/接管', reason: 'matched_stop' };
  }
  if (/证据|审计|工具|流水|编号|定位/.test(text)) {
    return { intent: 'locate_evidence', label: '定位证据', reason: 'matched_evidence' };
  }
  if (/结案|关闭|提交复核|复核/.test(text)) {
    return { intent: 'close_ticket', label: '复核/结案', reason: 'matched_close' };
  }
  if (/保存草稿|保存回单|存草稿/.test(text)) {
    return { intent: 'save_draft', label: '保存草稿', reason: 'matched_save_draft' };
  }
  if (/自动回单|填好|填写回单|填回单|回复|客户回单|回单/.test(text)) {
    return { intent: 'auto_reply', label: '自动回单', reason: 'matched_reply' };
  }
  if (/处理建议|生成建议|分析|处理当前|启动处理|多 Agent|多Agent|建议/.test(text)) {
    return { intent: 'process_ticket', label: '生成处理建议', reason: 'matched_process' };
  }
  if (context.scene === 'call-intake' || /发单|通话|电话|草稿|提交工单|创建工单|分发/.test(text)) {
    return { intent: 'call_intake', label: '通话发单', reason: 'matched_call_intake' };
  }
  return { intent: 'unknown', label: '未识别任务', reason: 'no_rule_matched' };
}

export function createCallIntakePlan(context: PageBusinessContext): PageTaskPlan {
  const draft = context.ticketDraft;
  const riskLevel = contextRisk(context);
  const steps: PageAction[] = [
    step('observe-call', 'observe', 'call-intake-workspace', '观察通话发单工作区', '', riskLevel),
    step('open-call', 'scroll', 'call-intake-workspace', '移动到通话记录与发单草稿区', '', riskLevel),
    step('highlight-call', 'highlight', 'call-transcript-panel', '定位当前通话全文', '', riskLevel),
    step('highlight-draft', 'highlight', 'ticket-draft-form', '定位标准工单草稿表单', '', riskLevel),
  ];

  if (!draft) {
    steps.push({
      ...step('stop-no-draft', 'stop', 'ticket-draft-form', '未生成发单草稿，等待坐席先生成草稿', '', riskLevel),
      stopReason: 'missing_ticket_draft',
    });
  } else {
    for (const field of writableDraftFields) {
      const value = String(draft[field as keyof typeof draft] || '');
      steps.push(step(`fill-${field}`, 'input', `draft-${field}`, `填写${field}`, value, riskLevel));
    }
    if (context.availableActions.includes('submit_ticket') && riskLevel === 'low') {
      steps.push(step('submit-ticket', 'click', 'draft-submit', '提交标准工单并分发', '', riskLevel));
      steps.push(step('verify-created', 'verify', 'enterprise-reply', '验证已进入工单处理页', '', riskLevel));
    } else {
      steps.push({
        ...step('stop-submit', 'stop', 'draft-submit', '草稿已填好，等待人工确认提交', '', riskLevel),
        stopReason: riskLevel === 'low' ? 'submit_not_available' : 'risk_requires_human_submit',
      });
    }
  }

  return {
    id: `call-intake-${Date.now()}`,
    goal: '根据通话记录生成标准工单并可见填表',
    riskLevel,
    allowDemoAutoSubmit: riskLevel === 'low',
    allowedTools,
    expectedResult: '草稿字段写入页面；低风险样本提交后跳转到工单详情。',
    steps,
  };
}

export function createReplyPlan(context: PageBusinessContext): PageTaskPlan {
  const riskLevel = contextRisk(context);
  const canAutoClose = Boolean(
    context.demoAutoClose &&
    riskLevel === 'low' &&
    context.ticketStatus === 'pending_human_review' &&
    context.availableActions.includes('close_ticket'),
  );
  const steps: PageAction[] = [
    step('observe-ticket', 'observe', 'enterprise-ticket-detail', '观察当前工单页面', '', riskLevel),
  ];

  if (!context.aiResult) {
    steps.push(step('start-process', 'click', 'page-agent-process', '触发多 Agent 生成处理建议', '', riskLevel));
    steps.push(step('wait-process', 'wait', 'sunpilot-flow', '等待后端 Agent Trace 与处理结果', '', riskLevel));
    steps.push({
      ...step('stop-wait-ai', 'stop', 'sunpilot-flow', '已触发多 Agent，等待结果返回后继续回单', '', riskLevel),
      stopReason: 'waiting_for_ai_result',
    });
  } else if (context.aiResult.missingFields?.length) {
    steps.push(step('locate-missing', 'scroll', 'sunpilot-fields', '定位缺失字段与补充提示', '', riskLevel));
    steps.push({
      ...step('stop-missing', 'stop', 'sunpilot-fields', '存在缺失字段，停止在人工补充区', '', riskLevel),
      stopReason: 'missing_fields',
    });
  } else {
    steps.push(step('locate-evidence', 'scroll', 'sunpilot-evidence', '定位工具证据链', '', riskLevel));
    steps.push(step('highlight-evidence', 'highlight', 'sunpilot-evidence', '高亮可插入的证据编号', '', riskLevel));
    steps.push(step('fill-reply', 'input', 'page-agent-reply-draft', '填入客户回单草稿', context.aiResult.notification?.standardReply?.body || context.aiResult.replyDraft, riskLevel));
    steps.push(step('save-draft', 'click', 'page-agent-save-draft', '保存回单草稿', '', riskLevel));
    if (canAutoClose) {
      steps.push(step('close-ticket', 'click', 'page-agent-close-ticket', '低风险高频工单提交复核并结案', '', riskLevel));
      steps.push(step('verify-closed', 'verify', 'enterprise-ticket-detail', '验证结案请求已提交', '', riskLevel));
    } else {
      steps.push({
        ...step('stop-review', 'stop', 'enterprise-reply', '回单已准备，等待人工复核或确认', '', riskLevel),
        stopReason: riskLevel === 'low' ? 'manual_review_required' : 'risk_requires_human_review',
      });
    }
  }

  return {
    id: `reply-${Date.now()}`,
    goal: canAutoClose ? '处理当前工单并自动回单结案' : '处理当前工单并准备人工复核',
    riskLevel,
    allowDemoAutoSubmit: canAutoClose,
    allowedTools,
    expectedResult: canAutoClose ? '回单草稿保存并通过结案接口提交。' : '页面填好处理意见并停在人工复核节点。',
    steps,
  };
}

export function createProcessPlan(context: PageBusinessContext): PageTaskPlan {
  const riskLevel = contextRisk(context);
  const steps: PageAction[] = [
    step('observe-ticket', 'observe', 'enterprise-ticket-detail', '观察当前工单页面', '', riskLevel),
  ];

  if (!context.availableActions.includes('process_ticket')) {
    steps.push({
      ...step('stop-no-process', 'stop', 'page-agent-process', '当前页面不能生成处理建议', '', riskLevel),
      stopReason: 'process_not_available',
    });
  } else {
    steps.push(step('start-process', 'click', 'page-agent-process', '触发多 Agent 生成处理建议', '', riskLevel));
    steps.push(step('wait-process', 'wait', 'sunpilot-flow', '等待后端 Agent Trace 与处理结果', '', riskLevel));
    steps.push({
      ...step('stop-wait-ai', 'stop', 'sunpilot-flow', '处理建议已触发，等待结果返回', '', riskLevel),
      stopReason: 'waiting_for_ai_result',
    });
  }

  return {
    id: `process-${Date.now()}`,
    goal: '生成当前工单处理建议',
    riskLevel,
    allowDemoAutoSubmit: false,
    allowedTools,
    expectedResult: '多 Agent 处理链路已启动，结果返回后在对话流中展示。',
    steps,
  };
}

export function createSaveDraftPlan(context: PageBusinessContext): PageTaskPlan {
  const riskLevel = contextRisk(context);
  const replyDraft = context.replyDraft || context.aiResult?.notification?.standardReply?.body || context.aiResult?.replyDraft || '';
  const steps: PageAction[] = [
    step('observe-ticket', 'observe', 'enterprise-ticket-detail', '观察当前工单页面', '', riskLevel),
  ];

  if (!replyDraft.trim()) {
    steps.push({
      ...step('stop-no-reply', 'stop', 'enterprise-reply', '当前没有可保存的回单草稿', '', riskLevel),
      stopReason: 'missing_reply_draft',
    });
  } else {
    steps.push(step('fill-reply', 'input', 'page-agent-reply-draft', '填入当前回单草稿', replyDraft, riskLevel));
    steps.push(step('save-draft', 'click', 'page-agent-save-draft', '保存回单草稿', '', riskLevel));
    steps.push({
      ...step('stop-review', 'stop', 'enterprise-reply', '草稿已保存，等待人工复核', '', riskLevel),
      stopReason: 'manual_review_required',
    });
  }

  return {
    id: `save-draft-${Date.now()}`,
    goal: '保存当前回单草稿',
    riskLevel,
    allowDemoAutoSubmit: false,
    allowedTools,
    expectedResult: '回单草稿保存后停在人工复核节点。',
    steps,
  };
}

export function createClosePlan(context: PageBusinessContext): PageTaskPlan {
  const riskLevel = contextRisk(context);
  const canClose = context.availableActions.includes('close_ticket');
  const steps: PageAction[] = [
    step('observe-ticket', 'observe', 'enterprise-ticket-detail', '观察复核与结案区', '', riskLevel),
  ];

  if (canClose && riskLevel === 'low' && context.demoAutoClose) {
    steps.push(step('close-ticket', 'click', 'page-agent-close-ticket', '提交复核并结案', '', riskLevel));
    steps.push(step('verify-closed', 'verify', 'enterprise-ticket-detail', '验证结案请求已提交', '', riskLevel));
  } else {
    steps.push({
      ...step('stop-review', 'stop', 'enterprise-reply', '结案需要人工复核确认', '', riskLevel),
      stopReason: canClose ? 'manual_review_required' : 'close_not_available',
    });
  }

  return {
    id: `close-${Date.now()}`,
    goal: '准备复核与结案',
    riskLevel,
    allowDemoAutoSubmit: canClose && riskLevel === 'low' && Boolean(context.demoAutoClose),
    allowedTools,
    expectedResult: '满足演示安全条件时提交结案，否则停在人工复核节点。',
    steps,
  };
}

export function createEvidencePlan(context: PageBusinessContext): PageTaskPlan {
  const riskLevel = contextRisk(context);
  return {
    id: `evidence-${Date.now()}`,
    goal: '定位工具证据与系统审计',
    riskLevel,
    allowDemoAutoSubmit: false,
    allowedTools,
    expectedResult: '页面滚动到证据链与审计明细。',
    steps: [
      step('scroll-evidence', 'scroll', 'sunpilot-evidence', '定位证据链', '', riskLevel),
      step('highlight-evidence', 'highlight', 'sunpilot-evidence', '高亮证据列表', '', riskLevel),
      step('scroll-audit', 'scroll', 'sunpilot-audit', '打开系统审计区域', '', riskLevel),
      step('verify-evidence', 'verify', 'sunpilot-evidence', '证据定位完成', '', riskLevel),
    ],
  };
}

export function createUnknownPlan(context: PageBusinessContext): PageTaskPlan {
  const riskLevel = contextRisk(context);
  return {
    id: `unknown-${Date.now()}`,
    goal: '等待明确的 PageAgent 任务',
    riskLevel,
    allowDemoAutoSubmit: false,
    allowedTools,
    expectedResult: '未执行页面动作。',
    steps: [
      {
        ...step('stop-unknown', 'stop', context.scene === 'call-intake' ? 'call-intake-workspace' : 'enterprise-ticket-detail', '未识别到可执行任务', '', riskLevel),
        stopReason: 'unknown_instruction',
      },
    ],
  };
}

export function createPageTaskPlan(context: PageBusinessContext, intent: PageAgentIntent = resolvePageAgentIntent(context.instruction, context).intent): PageTaskPlan {
  if (intent === 'call_intake') return createCallIntakePlan(context);
  if (intent === 'process_ticket') return createProcessPlan(context);
  if (intent === 'auto_reply') return createReplyPlan(context);
  if (intent === 'locate_evidence') return createEvidencePlan(context);
  if (intent === 'save_draft') return createSaveDraftPlan(context);
  if (intent === 'close_ticket') return createClosePlan(context);
  return createUnknownPlan(context);
}
