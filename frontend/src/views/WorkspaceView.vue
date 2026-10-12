<script setup lang="ts">
import { Database } from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useSystemStore } from '../stores/system'
import DataStructureView from './DataStructureView.vue'
import AnalysisView from './AnalysisView.vue'
const system = useSystemStore()
const page = ref<'analysis' | 'schema'>('analysis')
const header = ref<HTMLElement | null>(null)
const headerHeight = ref(85)
let headerObserver: ResizeObserver | null = null
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
onMounted(() => {
  void system.checkHealth()
  headerObserver = new ResizeObserver(([entry]) => {
    if (entry) headerHeight.value = entry.target.getBoundingClientRect().height
  })
  if (header.value) headerObserver.observe(header.value)
})
onBeforeUnmount(() => headerObserver?.disconnect())
</script>
<template>
  <div class="workspace" :style="{ '--workspace-header-height': `${headerHeight}px` }">
    <header ref="header" class="header">
      <a class="brand" href="/" aria-label="WhiteBearDataAgent 首页">
        <span class="brand-mark"><Database :size="22" aria-hidden="true" /></span>
        <span>WhiteBear<span class="brand-light">DataAgent</span></span>
      </a>
      <nav class="page-nav" aria-label="工作台页面">
        <button
          type="button"
          :aria-pressed="page === 'analysis'"
          :class="{ active: page === 'analysis' }"
          @click="page = 'analysis'"
        >
          问数分析
        </button>
        <button
          type="button"
          :aria-pressed="page === 'schema'"
          :class="{ active: page === 'schema' }"
          @click="page = 'schema'"
        >
          数据结构
        </button>
      </nav>
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
    <AnalysisView v-show="page === 'analysis'" />
    <DataStructureView v-show="page === 'schema'" />
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
.page-nav {
  display: flex;
  gap: 8px;
}
.page-nav button {
  border: 0;
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  cursor: pointer;
  background: transparent;
  color: var(--color-muted);
  font-size: 13px;
}
.page-nav button.active {
  color: var(--color-primary);
  background: var(--color-primary-soft);
}
.page-nav button:focus-visible {
  outline: 3px solid var(--color-focus);
  outline-offset: 2px;
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
  .brand {
    font-size: 16px;
  }
}
</style>
