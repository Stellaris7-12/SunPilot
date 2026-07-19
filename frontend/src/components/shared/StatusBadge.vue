<script setup lang="ts">
import { computed } from 'vue'
import { riskMeta, statusMeta, type Tone } from '../../utils/business'

const props = defineProps<{ value: string; size?: 'sm' | 'md'; tone?: Tone }>()

const tone = computed(() => props.tone || statusMeta(props.value).tone || riskMeta(props.value, props.value).tone)
</script>

<template>
  <span class="badge" :class="[`badge--${size || 'sm'}`, `badge--${tone}`]">
    {{ value }}
  </span>
</template>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  min-height: 24px;
  padding: 3px 10px;
  border: 1px solid transparent;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  line-height: 1.2;
  white-space: nowrap;
}
.badge--md { min-height: 30px; padding: 5px 13px; font-size: 13px; }
.badge--green { background: var(--green-soft); border-color: rgba(47, 143, 103, 0.22); color: var(--green); }
.badge--blue { background: var(--blue-soft); border-color: rgba(40, 111, 154, 0.22); color: var(--blue); }
.badge--amber { background: var(--amber-soft); border-color: rgba(196, 134, 34, 0.24); color: var(--amber); }
.badge--red { background: var(--red-soft); border-color: rgba(196, 78, 78, 0.22); color: var(--red); }
.badge--neutral { background: var(--neutral-soft); border-color: var(--line); color: var(--muted); }
</style>
