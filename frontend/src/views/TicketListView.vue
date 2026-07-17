<script setup lang="ts">
import { onMounted } from 'vue'
import { useTicketStore } from '../stores/ticket'
import AppSidebar from '../components/layout/AppSidebar.vue'

const store = useTicketStore()
onMounted(() => store.fetchTickets())
</script>
<template>
  <div class="list-layout">
    <AppSidebar />
    <main class="list-main">
      <div class="empty-hint">← 从左侧选择一个工单开始处理</div>
    </main>
  </div>
</template>
<style scoped>
.list-layout { display: flex; height: 100vh; }
.list-main { flex: 1; display: flex; align-items: center; justify-content: center; }
.empty-hint { color: var(--muted); font-size: 15px; }
</style>
