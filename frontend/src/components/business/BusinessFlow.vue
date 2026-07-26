<script setup lang="ts">
import { computed } from 'vue'
import type { BusinessFlowStage } from './types'

const props = defineProps<{
  stages: BusinessFlowStage[]
  compact?: boolean
}>()

function stageLabel(status: BusinessFlowStage['status']) {
  return {
    waiting: '未开始',
    running: '处理中',
    done: '已完成',
    blocked: '需补充',
  }[status]
}

const doneCount = computed(() => props.stages.filter(s => s.status === 'done').length)

// 当前阶段：优先处理中，其次需补充，再次最后一个已完成，兜底取首个
const current = computed(() => {
  const running = props.stages.find(s => s.status === 'running')
  if (running) return running
  const blocked = props.stages.find(s => s.status === 'blocked')
  if (blocked) return blocked
  const done = [...props.stages].reverse().find(s => s.status === 'done')
  return done || props.stages[0] || null
})

const caption = computed(() => {
  const c = current.value
  if (!c) return ''
  return `${c.label} · ${stageLabel(c.status)}`
})
</script>

<template>
  <div class="business-flow" :class="{ compact }">
    <div class="flow-bar">
      <div
        v-for="stage in stages"
        :key="stage.id"
        class="flow-seg"
        :class="stage.status"
        :title="`${stage.label}：${stageLabel(stage.status)}`"
      />
    </div>
    <div v-if="!compact" class="flow-caption">
      <span class="flow-caption-current">{{ caption }}</span>
      <span class="flow-caption-count">{{ doneCount }}/{{ stages.length }}</span>
    </div>
  </div>
</template>

<style scoped>
/* 分段进度条：七个阶段压成一条彩色进度条，按状态着色，悬停看名称 */
.business-flow {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.flow-bar {
  display: flex;
  gap: 2px;
  height: 26px;
  padding: 2px;
  border-radius: 8px;
  background: var(--line);
}
.flow-seg {
  flex: 1 1 0;
  min-width: 0;
  border-radius: 4px;
  background: #e7edf3;
  transition: background 0.2s ease;
}
.flow-seg:first-child { border-radius: 6px 4px 4px 6px; }
.flow-seg:last-child { border-radius: 4px 6px 6px 4px; }
.flow-seg.done { background: var(--green); }
.flow-seg.running {
  background: var(--blue);
  animation: flowPulse 1.6s ease-in-out infinite;
}
.flow-seg.blocked { background: var(--amber); }
.flow-seg.waiting { background: #e7edf3; }
@keyframes flowPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.62; }
}
.flow-caption {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}
.flow-caption-current {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 800;
  color: var(--ink);
}
.flow-caption-count {
  flex: 0 0 auto;
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 700;
  color: var(--muted);
}
/* 紧凑模式：仅色条，无标题，用于左右分栏的两段拼接 */
.business-flow.compact .flow-bar {
  height: 20px;
}
</style>
