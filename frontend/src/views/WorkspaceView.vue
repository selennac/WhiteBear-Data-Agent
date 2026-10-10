<script setup lang="ts">
import { Database, MessageSquare, RefreshCw, Terminal } from 'lucide-vue-next'
import { computed, onMounted } from 'vue'

import BaseButton from '../components/ui/BaseButton.vue'
import { useSystemStore } from '../stores/system'

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
      <span class="status" :class="system.status" role="status">{{ statusText }}</span>
    </header>

    <main class="main">
      <section class="welcome" aria-labelledby="welcome-title">
        <span class="eyebrow">自然语言数据分析工作台</span>
        <h1 id="welcome-title">从一个问题，开始理解数据。</h1>
        <p>项目基础已就绪。接下来连接业务数据，建立从自然语言到 SQL 的分析流程。</p>
      </section>

      <section class="setup-card" aria-labelledby="setup-title">
        <span class="card-icon"><Terminal :size="24" aria-hidden="true" /></span>
        <div class="setup-content">
          <h2 id="setup-title">基础服务检查</h2>
          <p>启动后端后，可在这里检查服务连接，并在 API 文档中查看接口。</p>
          <p v-if="system.error" class="error" role="alert">{{ system.error }}</p>
        </div>
        <BaseButton :disabled="system.status === 'checking'" @click="system.checkHealth">
          <RefreshCw :size="16" aria-hidden="true" />
          {{ system.status === 'checking' ? '检查中' : '检查连接' }}
        </BaseButton>
      </section>

      <div class="next-steps">
        <section class="feature-card">
          <Database :size="22" aria-hidden="true" />
          <h2>连接数据</h2>
          <p>查看表、字段和关联关系，补充业务口径。</p>
          <span class="planned">待实现</span>
        </section>
        <section class="feature-card">
          <MessageSquare :size="22" aria-hidden="true" />
          <h2>开始问数</h2>
          <p>用自然语言提问，查看 SQL、结果与执行过程。</p>
          <span class="planned">待实现</span>
        </section>
      </div>
      <p class="footnote">当前为基础骨架；数据源、会话和查询功能将在后续阶段接入。</p>
    </main>
  </div>
</template>

<style scoped>
.workspace {
  min-height: 100vh;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
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

.brand-mark,
.card-icon {
  display: grid;
  place-items: center;
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  border-radius: var(--radius-sm);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.brand-light {
  font-weight: 400;
}

.status {
  padding: 6px 12px;
  border-radius: 999px;
  background: var(--color-background);
  color: var(--color-muted);
  font-size: 13px;
}

.status.connected {
  background: #ecfdf5;
  color: #047857;
}

.main {
  width: min(880px, 100%);
  margin: 0 auto;
  padding: 72px 24px 40px;
}

.eyebrow {
  color: var(--color-primary);
  font-size: 14px;
  font-weight: 600;
}

h1 {
  margin: 16px 0;
  font-size: clamp(26px, 4vw, 36px);
  line-height: 1.4;
  letter-spacing: -0.03em;
}

h2 {
  margin: 0 0 8px;
  font-size: 16px;
}

p {
  margin: 0;
  color: var(--color-muted);
  line-height: 1.8;
}

.setup-card {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-top: 36px;
  padding: 24px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
}

.setup-content {
  flex: 1;
}

.setup-content p,
.feature-card p {
  font-size: 14px;
}

.error {
  margin-top: 8px;
  color: #b91c1c;
}

.next-steps {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
  margin-top: 24px;
}

.feature-card {
  padding: 24px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
}

.feature-card > svg {
  margin-bottom: 20px;
  color: var(--color-muted);
}

.planned {
  display: inline-block;
  margin-top: 20px;
  color: var(--color-muted);
  font-size: 12px;
}

.footnote {
  margin-top: 24px;
  font-size: 12px;
}

@media (max-width: 640px) {
  .header {
    padding: 16px;
  }

  .main {
    padding: 40px 16px;
  }

  .setup-card {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .setup-content {
    flex-basis: calc(100% - 64px);
  }

  .next-steps {
    grid-template-columns: 1fr;
  }
}
</style>
