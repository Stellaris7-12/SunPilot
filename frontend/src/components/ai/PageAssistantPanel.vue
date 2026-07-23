<script setup lang="ts">
import AgentPanel from '../../page-agent/panel/AgentPanel.vue'
import type { AiProcessResult, Ticket } from '../../types'

defineProps<{
  ticket?: Ticket
  result?: AiProcessResult | null
  processing?: boolean
}>()

const emit = defineEmits<{
  fillReply: []
  checkTicket: []
  locateTools: []
  scrollReview: []
  process: []
}>()

function noop() {
  // Legacy wrapper only maps old reply-side events into SunPilot.
}
</script>

<template>
  <AgentPanel
    @generate-draft="noop"
    @submit-draft="noop"
    @start-ai-process="emit('process')"
    @scroll-reply="emit('scrollReview')"
    @scroll-missing="emit('checkTicket')"
    @open-human-confirm="emit('checkTicket')"
  />
</template>
