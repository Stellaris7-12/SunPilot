import type { PageAction, PageActionLogEntry, PageBusinessContext, PageTaskPlan } from '../../types';
import { SimulatorMask } from '../controller/SimulatorMask';

interface RunnerHooks {
  onLog: (entry: PageActionLogEntry) => void;
  onStatus: (status: PageActionLogEntry['status'], goal: string) => void;
  shouldStop?: () => boolean;
}

function nowText() {
  return new Date().toLocaleTimeString('zh-CN', { hour12: false });
}

function summarizeContext(context: PageBusinessContext) {
  const bits = [
    context.scene === 'call-intake' ? '通话发单' : '工单回单',
    context.ticketStatus ? `状态:${context.ticketStatus}` : '',
    context.riskLevel ? `风险:${context.riskLevel}` : '',
    context.callSummary ? `摘要:${context.callSummary.slice(0, 40)}` : '',
  ].filter(Boolean);
  return bits.join(' / ');
}

function byTarget(target: string): HTMLElement | null {
  const escaped = CSS.escape(target);
  return document.querySelector<HTMLElement>(`[data-page-agent-target="${escaped}"]`)
    || document.getElementById(target)
    || document.querySelector<HTMLElement>(`[name="${escaped}"]`);
}

function setFieldValue(element: HTMLElement, value: string) {
  if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) {
    element.focus();
    element.value = value;
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
    return;
  }
  if (element instanceof HTMLSelectElement) {
    element.focus();
    element.value = value;
    element.dispatchEvent(new Event('change', { bubbles: true }));
  }
}

export class PageActionRunner {
  private mask = new SimulatorMask();
  private stopped = false;

  stop() {
    this.stopped = true;
  }

  reset() {
    this.stopped = false;
  }

  async run(plan: PageTaskPlan, context: PageBusinessContext, hooks: RunnerHooks) {
    this.reset();
    hooks.onStatus('thinking', plan.goal);
    await this.mask.pause(260);

    for (const action of plan.steps) {
      if (this.stopped || hooks.shouldStop?.()) {
        this.writeLog(plan, context, action, 'stopped', '坐席已接管执行。', 0, hooks);
        break;
      }
      if (!plan.allowedTools.includes(action.type)) {
        this.writeLog(plan, context, action, 'error', '动作不在 TicketAgent 白名单内。', 0, hooks, 'policy_rejected');
        break;
      }
      const started = performance.now();
      hooks.onStatus('executing', action.label);
      try {
        const result = await this.execute(action);
        this.writeLog(plan, context, action, action.type === 'stop' ? 'stopped' : 'executed', result, performance.now() - started, hooks, action.stopReason || '');
        if (action.type === 'stop') break;
      } catch (error) {
        const message = error instanceof Error ? error.message : '页面动作执行失败';
        this.writeLog(plan, context, action, 'error', message, performance.now() - started, hooks, 'execution_error');
        break;
      }
    }

    hooks.onStatus(this.stopped ? 'stopped' : 'done', plan.goal);
    this.mask.hideHighlight();
  }

  private async execute(action: PageAction) {
    if (action.type === 'wait') {
      await this.mask.pause(900);
      return '等待页面或后端结果。';
    }
    if (action.type === 'stop') {
      await this.mask.pause(260);
      return action.stopReason || '已按策略停止。';
    }

    const element = byTarget(action.target);
    if (!element) throw new Error(`未找到页面目标：${action.target}`);

    if (action.type === 'observe' || action.type === 'highlight' || action.type === 'verify') {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      await this.mask.pause(320);
      await this.mask.highlight(element);
      return action.expected || '页面目标已确认。';
    }
    if (action.type === 'scroll') {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      await this.mask.pause(460);
      await this.mask.moveTo(element);
      await this.mask.highlight(element);
      return '已移动到目标区域。';
    }
    if (action.type === 'input') {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      await this.mask.pause(260);
      await this.mask.moveTo(element);
      await this.mask.highlight(element);
      setFieldValue(element, action.value || '');
      await this.mask.pause(Math.min(520 + String(action.value || '').length * 5, 1100));
      return '字段已写入页面。';
    }
    if (action.type === 'click') {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      await this.mask.pause(260);
      await this.mask.moveTo(element);
      await this.mask.highlight(element);
      await this.mask.click();
      element.click();
      await this.mask.pause(700);
      return '已点击白名单业务按钮。';
    }
    return '动作已完成。';
  }

  private writeLog(
    plan: PageTaskPlan,
    context: PageBusinessContext,
    action: PageAction,
    status: PageActionLogEntry['status'],
    result: string,
    durationMs: number,
    hooks: RunnerHooks,
    stopReason = '',
  ) {
    hooks.onLog({
      id: `${plan.id}-${action.id}-${Math.round(performance.now())}`,
      planId: plan.id,
      instruction: context.instruction,
      contextSummary: summarizeContext(context),
      tool: action.type,
      target: action.target,
      inputSummary: action.value ? `${action.value.slice(0, 48)}${action.value.length > 48 ? '...' : ''}` : '',
      status,
      result,
      durationMs: Math.round(durationMs),
      riskLevel: action.riskLevel || plan.riskLevel,
      stopReason,
      createdAt: nowText(),
    });
  }
}
