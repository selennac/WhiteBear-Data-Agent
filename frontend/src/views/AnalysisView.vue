<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import QueryResultTable from '../components/QueryResultTable.vue'
import BaseButton from '../components/ui/BaseButton.vue'
import { useAnalysisStore } from '../stores/analysis'

const analysis = useAnalysisStore()
const question = ref('')
const examples = [
  '最近 30 天的实付销售额和支付订单数',
  '最近 30 天每天的销售额趋势',
  '最近 30 天销售额最高的五个商品',
]
const run = computed(() => analysis.selectedRun)
const statusLabel = {
  running: '运行中',
  succeeded: '查询成功',
  failed: '分析失败',
  cancelled: '已停止',
  clarification_required: '需要澄清',
}
const nodeLabel: Record<string, string> = {
  load_context: '加载数据结构与业务口径',
  generate_query: '生成查询方案',
  validate_sql: '校验 SQL',
  execute_query: '执行只读查询',
}
onMounted(() => void analysis.loadHistory())
onBeforeUnmount(() => analysis.disconnect())

async function submit() {
  await analysis.submit(question.value)
}

function newAnalysis() {
  analysis.newConversation()
  question.value = ''
}
</script>

<template>
  <div class="analysis-layout">
    <aside class="history" aria-label="历史分析">
      <BaseButton :disabled="analysis.busy" @click="newAnalysis">新建分析</BaseButton>
      <div class="history-heading">
        <h2>历史会话</h2>
        <button type="button" :disabled="analysis.busy" @click="analysis.loadHistory()">
          刷新
        </button>
      </div>
      <p v-if="!analysis.conversations.length" class="muted">提交问题后，分析会保存在这里。</p>
      <button
        v-for="conversation in analysis.conversations"
        :key="conversation.id"
        type="button"
        class="history-item"
        :class="{ selected: analysis.conversationId === conversation.id }"
        :disabled="analysis.busy"
        :aria-pressed="analysis.conversationId === conversation.id"
        @click="analysis.selectConversation(conversation.id)"
      >
        {{ conversation.title }}
      </button>
      <BaseButton
        v-if="analysis.hasMore"
        variant="secondary"
        :disabled="analysis.busy"
        @click="analysis.loadHistory(true)"
        >加载更多</BaseButton
      >
    </aside>

    <main class="analysis-main">
      <section class="panel composer">
        <div class="eyebrow">电商业务数据</div>
        <h1>用问题开始分析</h1>
        <p class="muted">查询销售、订单和退款。未指定时间时默认最近 30 天，每个问题独立分析。</p>
        <form @submit.prevent="submit">
          <label for="analysis-question" class="question-label">分析问题</label>
          <textarea
            id="analysis-question"
            v-model="question"
            maxlength="2000"
            rows="3"
            :disabled="analysis.busy"
            placeholder="例如：最近 30 天的实付销售额和支付订单数"
            required
          />
          <div class="submit-row">
            <span class="muted">{{ question.length }} / 2000</span>
            <BaseButton
              v-if="analysis.sending"
              variant="secondary"
              :disabled="analysis.stopping"
              @click="analysis.stop()"
              >{{ analysis.stopping ? '正在停止…' : '停止分析' }}</BaseButton
            >
            <BaseButton v-else type="submit" :disabled="analysis.busy || !question.trim()">{{
              analysis.sending ? '正在分析…' : '开始分析'
            }}</BaseButton>
          </div>
        </form>
        <div class="examples">
          <button
            v-for="example in examples"
            :key="example"
            type="button"
            :disabled="analysis.busy"
            @click="question = example"
          >
            {{ example }}
          </button>
        </div>
        <p v-if="analysis.sending" class="progress" role="status">
          {{ analysis.progress }}
        </p>
        <p v-if="analysis.loading" class="muted" role="status">正在读取历史记录…</p>
        <p v-if="analysis.error" class="error" role="alert">{{ analysis.error }}</p>
      </section>

      <nav v-if="analysis.runs.length > 1" class="run-history" aria-label="本会话最近 50 次分析">
        <button
          v-for="item in analysis.runs"
          :key="item.id"
          type="button"
          :aria-pressed="run?.id === item.id"
          :class="{ selected: run?.id === item.id }"
          :disabled="analysis.busy"
          @click="analysis.selectedRun = item"
        >
          {{ item.question }}
        </button>
      </nav>

      <section v-if="run" class="panel output" :aria-label="statusLabel[run.status]">
        <div class="output-heading">
          <h2>{{ run.question }}</h2>
          <span class="badge" :class="run.status">{{ statusLabel[run.status] }}</span>
        </div>
        <p v-if="run.status === 'running' && !analysis.sending" class="muted">
          该记录尚未完成。刷新会话查看状态，或停止此运行后重新提交问题。
          <BaseButton variant="secondary" :disabled="analysis.busy" @click="analysis.stop()">
            停止此运行
          </BaseButton>
        </p>
        <p v-if="run.status === 'cancelled'" class="muted" role="status">
          分析已停止，可以提交新问题。
        </p>
        <p v-else-if="run.error_message" class="error" role="alert">{{ run.error_message }}</p>
        <p v-if="run.status === 'clarification_required'" class="clarification">
          {{ run.draft?.clarification }} 请将口径补充到问题后重新提交。
        </p>
        <div v-if="run.draft?.time_range" class="context">
          <strong>时间范围</strong><span>{{ run.draft.time_range }}</span>
        </div>
        <ul v-if="run.draft?.assumptions?.length" class="assumptions">
          <li v-for="(assumption, index) in run.draft.assumptions" :key="index">
            {{ assumption }}
          </li>
        </ul>
        <QueryResultTable v-if="run.result" :result="run.result" />
        <details v-if="run.draft?.sql" class="sql" open>
          <summary>SQL</summary>
          <pre><code>{{ run.draft.sql }}</code></pre>
        </details>
        <details class="trace" :open="analysis.sending">
          <summary>执行记录 · {{ run.steps?.length ?? 0 }} 步</summary>
          <ol>
            <li v-for="(step, index) in run.steps" :key="index">
              <span>{{ nodeLabel[step.node] ?? step.node }}</span
              ><span
                >{{
                  { running: '进行中', succeeded: '完成', failed: '失败', cancelled: '已停止' }[
                    step.status
                  ]
                }}
                · 第 {{ Math.max(1, step.attempt) }} 次 · {{ step.elapsed_ms }} ms</span
              >
              <p v-if="step.detail">{{ step.detail }}</p>
            </li>
          </ol>
          <p class="muted">
            模型：{{ run.model }} · 提示词：{{ run.prompt_version }} · 结构：{{
              run.schema_version?.slice(0, 12)
            }}
          </p>
          <p v-if="Object.keys(run.token_usage ?? {}).length" class="muted">
            Token 用量：{{
              Object.entries(run.token_usage ?? {})
                .map(([name, value]) => `${name}: ${value}`)
                .join(' · ')
            }}
          </p>
        </details>
      </section>
    </main>
  </div>
</template>

<style scoped>
.analysis-layout {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  min-height: calc(100vh - 90px);
}
.history {
  padding: 24px 16px;
  border-right: 1px solid var(--color-border);
  background: var(--color-surface);
}
.history > .base-button {
  width: 100%;
}
.history-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 24px 0 12px;
}
.history-heading h2 {
  font-size: 13px;
  color: var(--color-muted);
  margin: 0;
}
.history-heading button {
  border: 0;
  background: transparent;
  color: var(--color-primary);
  cursor: pointer;
  font-size: 13px;
}
.history-item {
  display: block;
  width: 100%;
  padding: 12px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  text-align: left;
  color: var(--color-text);
  cursor: pointer;
  font-size: 13px;
  overflow-wrap: anywhere;
}
.selected {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
.analysis-main {
  padding: 32px;
  max-width: 1400px;
  width: 100%;
  margin: 0 auto;
}
.panel {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 28px;
}
.eyebrow {
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 600;
}
h1 {
  font-size: 24px;
  margin: 12px 0;
}
.muted {
  color: var(--color-muted);
  font-size: 13px;
  line-height: 1.7;
}
.question-label {
  display: block;
  margin: 24px 0 8px;
  font-size: 13px;
  font-weight: 600;
}
textarea {
  display: block;
  width: 100%;
  padding: 14px;
  resize: vertical;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-background);
  color: var(--color-text);
  line-height: 1.6;
}
.submit-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}
.examples {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 20px;
}
.examples button,
.run-history button {
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  background: var(--color-background);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--color-muted);
  cursor: pointer;
}
.run-history {
  display: flex;
  gap: 8px;
  overflow: auto;
  margin: 20px 0;
}
.run-history button {
  max-width: 300px;
  flex-shrink: 0;
  text-align: left;
}
.run-history button.selected {
  color: var(--color-primary);
  border-color: var(--color-primary);
}
.progress {
  color: var(--color-primary);
  font-size: 13px;
}
.error {
  background: #fef2f2;
  color: #b91c1c;
  padding: 14px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  line-height: 1.6;
}
.clarification {
  padding: 14px;
  background: #fffbeb;
  color: #92400e;
  border-radius: var(--radius-sm);
}
.output {
  margin-top: 24px;
}
.output-heading {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
h2 {
  font-size: 17px;
  margin: 0;
  overflow-wrap: anywhere;
}
.badge {
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 12px;
  background: var(--color-background);
  color: var(--color-muted);
  white-space: nowrap;
}
.badge.succeeded {
  background: #ecfdf5;
  color: #047857;
}
.badge.failed {
  background: #fef2f2;
  color: #b91c1c;
}
.context {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 13px;
  margin-bottom: 12px;
}
.assumptions {
  color: var(--color-muted);
  font-size: 13px;
  line-height: 1.8;
  padding-left: 20px;
}
details {
  margin-top: 24px;
  border-top: 1px solid var(--color-border);
  padding-top: 16px;
}
summary {
  cursor: pointer;
  font-weight: 600;
  font-size: 13px;
}
pre {
  overflow: auto;
  max-height: 400px;
  padding: 16px;
  background: var(--color-background);
  border-radius: var(--radius-sm);
  line-height: 1.7;
  font-size: 12px;
}
.trace ol {
  padding-left: 20px;
}
.trace li {
  font-size: 12px;
  padding: 8px 0;
  color: var(--color-muted);
}
.trace li > span + span {
  margin-left: 12px;
}
button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
button:focus-visible,
textarea:focus-visible,
summary:focus-visible {
  outline: 3px solid var(--color-focus);
  outline-offset: 2px;
}
@media (max-width: 900px) {
  .analysis-layout {
    grid-template-columns: 180px minmax(0, 1fr);
  }
  .analysis-main {
    padding: 20px;
  }
  .panel {
    padding: 20px;
  }
}
@media (max-width: 640px) {
  .analysis-layout {
    grid-template-columns: minmax(0, 1fr);
  }
  .history {
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
    max-height: 220px;
    overflow: auto;
  }
  .history-heading {
    margin-top: 16px;
  }
  .analysis-main {
    padding: 16px;
  }
  .panel {
    padding: 16px;
  }
  h1 {
    font-size: 21px;
  }
}
</style>
