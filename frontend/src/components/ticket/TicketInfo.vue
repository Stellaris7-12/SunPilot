<script setup lang="ts">
import { computed } from 'vue'
import type { AiProcessResult, Ticket } from '../../types'
import { caseConclusion, evidenceIds, nextOwner, riskMeta, scenarioFamily, statusMeta, suggestedAction } from '../../utils/business'
import StatusBadge from '../shared/StatusBadge.vue'

const props = defineProps<{ ticket: Ticket; result?: AiProcessResult | null; processing?: boolean }>()

const family = computed(() => scenarioFamily(props.ticket, props.result))
const status = computed(() => statusMeta(props.ticket.status))
const risk = computed(() => riskMeta(props.ticket.riskLevel, props.ticket.riskLabel))
const ids = computed(() => evidenceIds(props.result))
const conclusion = computed(() => caseConclusion(props.ticket, props.result))
const action = computed(() => suggestedAction(props.ticket, props.result, props.processing))
</script>

<template>
  <section class="case-brief">
    <div class="brief-main">
      <span class="section-title">案件卷宗</span>
      <h2>{{ family.label }}</h2>
      <p>{{ conclusion }}</p>
      <div class="brief-badges">
        <StatusBadge :value="status.label" :tone="status.tone" size="md" />
        <StatusBadge :value="risk.label" :tone="risk.tone" size="md" />
      </div>
    </div>

    <div class="dossier-strip" aria-label="案件关键信息">
      <div>
        <span>下一负责人</span>
        <strong>{{ nextOwner(result, ticket.status) }}</strong>
      </div>
      <div>
        <span>建议动作</span>
        <strong>{{ action }}</strong>
      </div>
      <div>
        <span>证据编号</span>
        <strong class="mono">{{ ids.length ? ids.join(' / ') : '待生成' }}</strong>
      </div>
    </div>

    <div class="info-grid">
      <div class="info-item">
        <label>客户</label>
        <span>{{ ticket.customerName }}</span>
      </div>
      <div class="info-item">
        <label>手机号</label>
        <span class="mono">{{ ticket.phone }}</span>
      </div>
      <div class="info-item">
        <label>卡号后四位</label>
        <span class="mono">{{ ticket.cardLast4 }}</span>
      </div>
      <div class="info-item">
        <label>创建时间</label>
        <span>{{ ticket.createdAt }}</span>
      </div>
      <div class="info-item wide">
        <label>坐席关注点</label>
        <span>{{ family.deskFocus }}</span>
      </div>
      <div class="info-item wide">
        <label>状态说明</label>
        <span>{{ status.description }}</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.case-brief {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
}
.brief-main {
  padding: 22px;
  background:
    linear-gradient(90deg, rgba(47, 143, 103, 0.12), transparent 42%),
    var(--panel);
}
h2 {
  margin-top: 8px;
  font-size: 28px;
  line-height: 1.15;
}
.brief-main p {
  max-width: 880px;
  margin-top: 10px;
  color: var(--ink-2);
  font-size: 15px;
  line-height: 1.7;
}
.brief-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}
.dossier-strip {
  display: grid;
  grid-template-columns: 0.8fr 1fr 1.4fr;
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
  background: var(--ink);
  color: #fff;
}
.dossier-strip > div {
  min-width: 0;
  padding: 14px 18px;
  border-right: 1px solid rgba(255, 255, 255, 0.16);
}
.dossier-strip > div:last-child { border-right: none; }
.dossier-strip span {
  display: block;
  color: rgba(255, 255, 255, 0.7);
  font-size: 12px;
  font-weight: 800;
}
.dossier-strip strong {
  display: block;
  margin-top: 5px;
  overflow-wrap: anywhere;
  font-size: 14px;
}
.info-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1px;
  background: var(--line);
}
.info-item {
  min-width: 0;
  padding: 14px 16px;
  background: var(--panel-2);
}
.info-item.wide { grid-column: span 2; }
label {
  display: block;
  margin-bottom: 5px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
.info-item span {
  display: block;
  overflow-wrap: anywhere;
  font-size: 14px;
  line-height: 1.45;
}
@media (max-width: 920px) {
  .dossier-strip, .info-grid { grid-template-columns: 1fr; }
  .info-item.wide { grid-column: span 1; }
}
</style>
