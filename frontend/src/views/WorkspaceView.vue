<script setup lang="ts">
import { Database } from 'lucide-vue-next'
import { computed, onMounted } from 'vue'
import { useSystemStore } from '../stores/system'
import DataStructureView from './DataStructureView.vue'
const system = useSystemStore()
const statusText = computed(() => {
  switch (system.status) {
    case 'connected':
      return `后端已连接 · v${system.version}`
    case 'unavailable':
      return '后端未连接'
    case 'checking':
      return '正在检查连接'
    default:
      return '等待连接'
  }
})
onMounted(() => void system.checkHealth())
</script>
<template>
  <div class="workspace">
    <header class="header">
      <a class="brand" href="/" aria-label="WhiteBearDataAgent 首页">
        <span class="brand-mark"><Database :size="22" aria-hidden="true" /></span>
        <span>WhiteBear<span class="brand-light">DataAgent</span></span>
      </a>
      <span class="section-label">数据结构</span>
      <button
        class="status"
        :class="system.status"
        :disabled="system.status === 'checking'"
        aria-label="检查后端连接"
        @click="system.checkHealth"
      >
        <span role="status">{{ statusText }}</span>
      </button>
    </header>
    <DataStructureView />
  </div>
</template>
<style scoped>
.workspace {
  min-height: 100vh;
}
.header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 24px;
  padding: 20px 32px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
}
.brand {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  color: var(--color-text);
  font-size: 18px;
  font-weight: 700;
  text-decoration: none;
}
.brand-mark {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: var(--radius-sm);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
.brand-light {
  font-weight: 400;
}
.section-label {
  color: var(--color-primary);
  font-size: 13px;
  padding-left: 24px;
  border-left: 1px solid var(--color-border);
}
.status {
  margin-left: auto;
  border: 0;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: 999px;
  background: var(--color-background);
  color: var(--color-muted);
  font-size: 13px;
}
.status:focus-visible {
  outline: 3px solid var(--color-focus);
  outline-offset: 3px;
}
.status.connected {
  background: #ecfdf5;
  color: #047857;
}
.status.unavailable {
  background: #fef2f2;
  color: #b91c1c;
}
@media (max-width: 640px) {
  .header {
    padding: 16px;
    gap: 12px;
  }
  .section-label {
    display: none;
  }
  .brand {
    font-size: 16px;
  }
}
</style>
