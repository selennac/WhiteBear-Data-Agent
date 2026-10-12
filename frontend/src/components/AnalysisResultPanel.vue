<script setup lang="ts">
import { ArrowUpRight } from 'lucide-vue-next'
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from 'reka-ui'
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import type { AnalysisRun } from '../types/api'
import { canContinue, metricLabels, nodeLabels, statusLabels } from '../utils/analysis'
import AnalysisConditions from './AnalysisConditions.vue'
import QueryResultTable from './QueryResultTable.vue'
import BaseButton from './ui/BaseButton.vue'
const QueryResultChart = defineAsyncComponent(() => import('./QueryResultChart.vue'))
const props = defineProps<{
  run: AnalysisRun
  turn: number
  contextRunId?: string
  busy: boolean
}>()
defineEmits<{ continue: [run: AnalysisRun] }>()
const tab = ref('trace')
const touched = ref(false)
const source = computed(() => {
  if (props.run.draft?.context_mode === 'follow_up') return props.run.input_context?.previous
  if (props.run.draft?.context_mode === 'clarification')
    return props.run.input_context?.clarification
  return null
})
const available = computed(() => ({
  chart: !!props.run.chart && !!props.run.result,
  table: !!props.run.result,
  sql: !!props.run.draft?.sql,
  trace: true,
}))
watch(
  () => props.run.id,
  () => {
    touched.value = false
  },
)
watch(
  () => [props.run.id, available.value.chart, available.value.table, available.value.sql],
  () => {
    if (!touched.value || !available.value[tab.value as keyof typeof available.value])
      tab.value = available.value.chart
        ? 'chart'
        : available.value.table
          ? 'table'
          : available.value.sql
            ? 'sql'
            : 'trace'
  },
  { immediate: true },
)
function selectTab(value: string | number) {
  tab.value = String(value)
  touched.value = true
}
function metricsLabel(ids: string[]) {
  return ids.map((id) => metricLabels[id] || id).join('、')
}
</script>

<template>
  <section class="result-panel" aria-label="分析结果">
    <header class="result-heading output-heading">
      <div class="result-meta">
        <span>正在查看 · 第 {{ turn }} 轮</span
        ><span class="badge" :class="run.status">{{ statusLabels[run.status] }}</span>
      </div>
      <h2>{{ run.draft?.resolved_question || run.question }}</h2>
      <AnalysisConditions :draft="run.draft" />
      <BaseButton
        v-if="canContinue(run)"
        variant="secondary"
        class="continue-button"
        :disabled="busy || contextRunId === run.id"
        @click="$emit('continue', run)"
        ><ArrowUpRight :size="15" aria-hidden="true" />{{
          contextRunId === run.id
            ? '追问已基于此结果'
            : run.status === 'clarification_required'
              ? '回答此澄清'
              : '从此结果追问'
        }}</BaseButton
      >
    </header>
    <TabsRoot class="result-tabs" :model-value="tab" @update:model-value="selectTab">
      <TabsList class="tab-list" aria-label="结果视图"
        ><TabsTrigger value="chart" :disabled="!available.chart">图表</TabsTrigger
        ><TabsTrigger value="table" :disabled="!available.table">表格</TabsTrigger
        ><TabsTrigger value="sql" :disabled="!available.sql">SQL</TabsTrigger
        ><TabsTrigger value="trace">执行记录</TabsTrigger></TabsList
      >
      <div class="result-scroll">
        <p v-if="run.status === 'cancelled'" class="muted">分析已停止，可以提交新问题。</p>
        <p v-else-if="run.error_message" class="error" role="alert">{{ run.error_message }}</p>
        <p v-if="run.status === 'clarification_required'" class="clarification">
          {{ run.draft?.clarification }}
        </p>
        <TabsContent value="chart" class="tab-content"
          ><QueryResultChart
            v-if="run.result && run.chart"
            :key="run.id"
            :result="run.result"
            :spec="run.chart"
            :message="run.chart_message"
        /></TabsContent>
        <TabsContent value="table" class="tab-content"
          ><p v-if="run.chart_message && !run.chart" class="muted">{{ run.chart_message }}</p>
          <QueryResultTable v-if="run.result" :result="run.result"
        /></TabsContent>
        <TabsContent value="sql" class="tab-content">
          <pre><code>{{ run.draft?.sql }}</code></pre>
        </TabsContent>
        <TabsContent value="trace" class="tab-content trace">
          <p v-if="!run.steps?.length" class="muted">正在准备分析…</p>
          <ol>
            <li v-for="(step, index) in run.steps" :key="index">
              <div>
                <strong>{{ nodeLabels[step.node] ?? step.node }}</strong
                ><span>{{
                  { running: '进行中', succeeded: '完成', failed: '失败', cancelled: '已停止' }[
                    step.status
                  ]
                }}</span>
              </div>
              <small>第 {{ Math.max(1, step.attempt) }} 次 · {{ step.elapsed_ms }} ms</small>
              <p v-if="step.detail">{{ step.detail }}</p>
            </li>
          </ol>
          <details>
            <summary>运行信息</summary>
            <p class="muted">
              模型：{{ run.model }} · 提示词：{{ run.prompt_version }} · 结构：{{
                run.schema_version?.slice(0, 12)
              }}
            </p>
            <p v-if="run.summary_prompt_version" class="muted">
              总结提示词：{{ run.summary_prompt_version }}
            </p>
            <p v-if="Object.keys(run.token_usage ?? {}).length" class="muted">
              Token 用量：{{
                Object.entries(run.token_usage ?? {})
                  .map(([name, value]) => `${name}: ${value}`)
                  .join(' · ')
              }}
            </p>
          </details>
        </TabsContent>
        <details v-if="run.draft" class="effective-context" aria-label="本轮分析口径">
          <summary>分析口径与继承条件</summary>
          <dl>
            <template v-if="source"
              ><dt>{{ run.draft.context_mode === 'clarification' ? '接续澄清' : '追问来源' }}</dt>
              <dd>{{ source.draft.resolved_question || source.question }}</dd></template
            >
            <template v-if="run.draft.resolved_question"
              ><dt>完整问题</dt>
              <dd>{{ run.draft.resolved_question }}</dd></template
            >
            <template v-if="run.draft.metrics?.length"
              ><dt>指标</dt>
              <dd>
                {{ metricsLabel(run.draft.metrics) }}
              </dd></template
            >
            <template v-if="run.draft.time_range"
              ><dt>时间范围</dt>
              <dd>{{ run.draft.time_range }}</dd></template
            >
            <template v-if="run.draft.filters"
              ><dt>筛选条件</dt>
              <dd>{{ run.draft.filters.join('；') || '无额外筛选' }}</dd></template
            >
            <template v-if="run.draft.group_by"
              ><dt>分组</dt>
              <dd>{{ run.draft.group_by.join('、') || '不分组' }}</dd></template
            >
          </dl>
          <ul v-if="run.draft.assumptions?.length">
            <li v-for="(assumption, index) in run.draft.assumptions" :key="index">
              {{ assumption }}
            </li>
          </ul>
        </details>
        <ul v-if="run.summary?.limitations?.length" class="limitations">
          <li v-for="(limitation, index) in run.summary.limitations" :key="index">
            {{ limitation }}
          </li>
        </ul>
      </div>
    </TabsRoot>
  </section>
</template>

<style scoped>
.result-panel {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
  background: var(--color-surface);
}
.result-heading {
  padding: 24px 24px 18px;
  border-bottom: 1px solid var(--color-border);
}
.result-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  color: var(--color-muted);
  font-size: 12px;
}
h2 {
  margin: 14px 0;
  font-size: 18px;
  line-height: 1.6;
  overflow-wrap: anywhere;
}
.badge {
  padding: 4px 8px;
  border-radius: 20px;
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
.badge.clarification_required {
  background: #fffbeb;
  color: #92400e;
}
.continue-button {
  margin-top: 14px;
  font-size: 12px;
  min-height: 34px;
}
.result-tabs {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}
.tab-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  padding: 12px 24px;
  border-bottom: 1px solid var(--color-border);
}
.tab-list button {
  border: 0;
  padding: 8px 12px;
  border-radius: 6px;
  background: transparent;
  color: var(--color-muted);
  font-size: 13px;
  cursor: pointer;
}
.tab-list button[data-state='active'] {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
.tab-list button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.result-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 24px;
}
.tab-content {
  outline-offset: 4px;
}
pre {
  margin: 0;
  padding: 16px;
  background: var(--color-background);
  border-radius: 8px;
  overflow: auto;
  font-size: 12px;
  line-height: 1.8;
}
.muted,
.limitations,
details,
.trace {
  font-size: 13px;
  color: var(--color-muted);
  line-height: 1.8;
  overflow-wrap: anywhere;
}
details {
  border-top: 1px solid var(--color-border);
  padding-top: 16px;
  margin-top: 20px;
}
summary {
  color: var(--color-text);
  font-weight: 500;
  cursor: pointer;
}
dl {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 8px 12px;
}
dt {
  color: var(--color-text);
}
dd {
  margin: 0;
}
.limitations {
  padding-left: 18px;
}
.trace ol {
  list-style: none;
  margin: 0;
  padding: 0;
}
.trace li {
  border-left: 2px solid var(--color-border);
  padding: 0 0 18px 14px;
}
.trace li > div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.trace strong {
  font-weight: 500;
  color: var(--color-text);
}
.trace small {
  font-size: 12px;
}
.trace p {
  margin: 6px 0;
}
.error,
.clarification {
  padding: 12px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.7;
}
.error {
  background: #fef2f2;
  color: #b91c1c;
}
.clarification {
  background: #fffbeb;
  color: #92400e;
}
button:focus-visible,
summary:focus-visible {
  outline: 3px solid var(--color-focus);
  outline-offset: 2px;
}
@media (max-width: 640px) {
  .result-heading {
    padding: 20px 16px 16px;
  }
  .tab-list {
    padding: 10px 16px;
    gap: 4px;
  }
  .result-scroll {
    padding: 16px;
  }
  h2 {
    font-size: 16px;
  }
}
</style>
