<script setup lang="ts">
import type { BusinessFlowStage } from './types'

defineProps<{
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
</script>

<template>
  <div class="business-flow" :class="{ compact }">
    <div v-for="stage in stages" :key="stage.id" class="flow-node" :class="stage.status">
      <span>{{ stage.label }}</span>
      <strong>{{ stageLabel(stage.status) }}</strong>
    </div>
  </div>
</template>

<style scoped>
.business-flow {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(128px, 1fr));
  gap: 1px;
  background: var(--line);
}
.business-flow.compact {
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
}
.flow-node {
  min-width: 0;
  min-height: 62px;
  display: grid;
  align-content: center;
  gap: 5px;
  padding: 9px;
  background: #fff;
  box-shadow: inset 0 3px 0 var(--line-dark);
}
.flow-node.done {
  box-shadow: inset 0 3px 0 var(--green);
}
.flow-node.running {
  box-shadow: inset 0 3px 0 var(--blue);
  background: #f2f8fc;
}
.flow-node.blocked {
  box-shadow: inset 0 3px 0 var(--amber);
  background: #fff8ea;
}
.flow-node span {
  font-size: 12px;
  font-weight: 900;
}
.flow-node strong {
  color: var(--ink-soft);
  font-size: 12px;
}
</style>
