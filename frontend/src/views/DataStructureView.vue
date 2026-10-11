<script setup lang="ts">
import { BookOpen, Database, GitBranch, Pencil, RefreshCw, Table2 } from 'lucide-vue-next'
import { computed, onMounted, ref, watch } from 'vue'

import BaseButton from '../components/ui/BaseButton.vue'
import { useDatasourceStore } from '../stores/datasource'

const data = useDatasourceStore()
const current = computed(() =>
  data.schema?.tables.find((table) => table.name === data.selectedTable),
)
const editing = ref(false)
const tableDescription = ref('')
const columnDescriptions = ref<Record<string, string>>({})
const notice = ref('')
const labels: Record<string, string> = {
  customers: '客户',
  categories: '商品分类',
  products: '商品',
  orders: '订单',
  order_items: '订单明细',
  refunds: '退款',
}

function formatTime(value: string | undefined) {
  return value
    ? new Intl.DateTimeFormat('zh-CN', {
        timeZone: 'Asia/Shanghai',
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(new Date(value))
    : '—'
}

function edit() {
  if (!current.value) return
  tableDescription.value = current.value.description || ''
  columnDescriptions.value = Object.fromEntries(
    current.value.columns.map((column) => [column.name, column.description || '']),
  )
  editing.value = true
  notice.value = ''
}

async function save() {
  if (!current.value) return
  const name = current.value.name
  await data.load('patch', {
    tables: { [name]: tableDescription.value },
    columns: { [name]: columnDescriptions.value },
  })
  if (!data.error) {
    editing.value = false
    notice.value = '业务说明已保存'
  }
}

watch(
  () => data.selectedTable,
  () => {
    editing.value = false
    notice.value = ''
  },
)
onMounted(() => void data.load())
</script>

<template>
  <main class="structure">
    <div class="page-heading">
      <div>
        <span class="eyebrow">数据基础 · PostgreSQL</span>
        <h1>先认识数据，再开始分析。</h1>
        <p>查看电商数据结构、关联关系和指标口径，为每一次问数建立清晰的依据。</p>
      </div>
      <BaseButton :disabled="data.loading || editing" @click="data.load('sync')">
        <RefreshCw :size="16" aria-hidden="true" />
        {{ data.loading ? '读取中' : '同步结构' }}
      </BaseButton>
    </div>

    <div v-if="data.error" class="error-banner" role="alert">
      <span>{{ data.error }}</span>
      <button :disabled="data.loading" @click="data.load()">重新读取</button>
    </div>
    <p v-if="notice" class="notice" role="status">{{ notice }}</p>
    <p v-if="data.loading && !data.schema" class="empty" role="status">正在读取数据源…</p>

    <section v-else-if="!data.schema && !data.error" class="setup" aria-labelledby="setup-title">
      <Database :size="32" aria-hidden="true" />
      <h2 id="setup-title">准备你的电商业务数据</h2>
      <p>在后端配置数据库连接，然后初始化并生成最近一年的业务数据。</p>
      <pre>
python -m app.cli db init
python -m app.cli business generate</pre>
      <p>完成后点击“同步结构”，即可浏览六张业务表和指标定义。</p>
    </section>

    <template v-if="data.schema">
      <section class="dataset-card" aria-label="数据源概况">
        <div class="source-name">
          <span class="source-icon"><Database :size="24" aria-hidden="true" /></span>
          <div>
            <h2>电商业务数据</h2>
            <p>{{ data.schema.tables.length }} 张表 · Asia/Shanghai</p>
          </div>
        </div>
        <template v-if="data.schema.dataset">
          <div>
            <span class="stat-label">支付订单 · 最近 30 天</span
            ><strong>{{ data.schema.dataset.recent_30_days_paid_orders.toLocaleString() }}</strong>
          </div>
          <div>
            <span class="stat-label">实付销售额 · 最近 30 天</span
            ><strong
              >¥
              {{
                Number(data.schema.dataset.recent_30_days_sales).toLocaleString('zh-CN', {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })
              }}</strong
            >
          </div>
          <div class="coverage">
            <span class="stat-label">数据覆盖范围</span>
            <p>
              {{ formatTime(data.schema.dataset.coverage_start) }} —
              {{ formatTime(data.schema.dataset.coverage_end) }}
            </p>
            <small>生成于 {{ formatTime(data.schema.dataset.generated_at) }}</small>
          </div>
        </template>
        <p v-else>结构已就绪，还没有业务数据。运行 business generate 后重新读取。</p>
      </section>

      <div class="browser">
        <aside class="table-nav" aria-label="业务表">
          <h2>
            业务表 <span>{{ data.schema.tables.length }}</span>
          </h2>
          <button
            v-for="table in data.schema.tables"
            :key="table.name"
            :class="{ selected: data.selectedTable === table.name }"
            :aria-pressed="data.selectedTable === table.name"
            :disabled="data.loading"
            @click="data.selectedTable = table.name"
          >
            <Table2 :size="18" aria-hidden="true" />
            <span
              ><strong>{{ labels[table.name] || table.name }}</strong
              ><small>{{ table.name }}</small></span
            >
            <span v-if="data.schema.dataset" class="row-count">{{
              data.schema.dataset.row_counts[table.name]?.toLocaleString()
            }}</span>
          </button>
        </aside>

        <section
          v-if="current"
          class="table-detail"
          aria-labelledby="table-title"
          :aria-busy="data.loading"
        >
          <div class="detail-heading">
            <div>
              <span class="eyebrow">{{ data.schema.schema_name }}.{{ current.name }}</span>
              <h2 id="table-title">{{ labels[current.name] || current.name }}</h2>
            </div>
            <BaseButton v-if="!editing" :disabled="data.loading" @click="edit">
              <Pencil :size="15" aria-hidden="true" />
              <span>编辑说明</span>
            </BaseButton>
            <div v-else class="edit-actions">
              <button :disabled="data.loading" @click="editing = false">取消</button>
              <BaseButton :disabled="data.loading" @click="save">保存说明</BaseButton>
            </div>
          </div>
          <textarea
            v-if="editing"
            v-model="tableDescription"
            aria-label="表业务说明"
            maxlength="2000"
            rows="2"
          />
          <p v-else class="table-description">{{ current.description || '暂无业务说明' }}</p>
          <div class="column-table">
            <table>
              <thead>
                <tr>
                  <th>字段</th>
                  <th>类型</th>
                  <th>约束</th>
                  <th>业务说明</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="column in current.columns" :key="column.name">
                  <td>
                    <code>{{ column.name }}</code>
                  </td>
                  <td class="type-cell">{{ column.data_type }}</td>
                  <td>
                    <span v-if="column.primary_key" class="key-badge">主键</span
                    ><span v-else class="constraint">{{ column.nullable ? '可空' : '必填' }}</span>
                  </td>
                  <td>
                    <input
                      v-if="editing"
                      v-model="columnDescriptions[column.name]"
                      :aria-label="`${column.name} 业务说明`"
                      maxlength="2000"
                    /><span v-else>{{ column.description || '—' }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="relationships">
            <h3><GitBranch :size="16" aria-hidden="true" />关联关系</h3>
            <p v-if="!current.relationships.length">此表没有外键关联，可被其他业务表引用。</p>
            <button
              v-for="relation in current.relationships"
              :key="relation.columns.join(',')"
              :disabled="data.loading"
              @click="data.selectedTable = relation.referred_table"
            >
              <code>{{ current.name }}.{{ relation.columns.join(', ') }}</code
              ><span>→</span
              ><code>{{ relation.referred_table }}.{{ relation.referred_columns.join(', ') }}</code>
            </button>
          </div>
        </section>
      </div>

      <section class="metrics" aria-labelledby="metrics-title">
        <div class="metrics-heading">
          <h2 id="metrics-title"><BookOpen :size="20" aria-hidden="true" />业务口径</h2>
          <span
            >版本 {{ data.schema.metrics.version }} · 默认最近
            {{ data.schema.metrics.default_time_range_days }} 天</span
          >
        </div>
        <div class="metric-grid">
          <article v-for="metric in data.schema.metrics.metrics" :key="metric.id">
            <h3>{{ metric.label }}</h3>
            <p>{{ metric.description }}</p>
            <span
              >时间字段 <code>{{ metric.time_column }}</code></span
            >
          </article>
        </div>
      </section>
      <p class="footnote">
        自然语言问数、SQL 执行与图表将在下一阶段接入。<span v-if="data.schema.synced_at"
          >结构同步于 {{ formatTime(data.schema.synced_at) }}</span
        >
      </p>
    </template>
  </main>
</template>

<style scoped>
.structure {
  max-width: 1440px;
  margin: 0 auto;
  padding: 40px 32px;
}
.page-heading,
.detail-heading,
.dataset-card,
.source-name,
.metrics-heading,
.edit-actions {
  display: flex;
  align-items: center;
  gap: 20px;
}
.page-heading,
.detail-heading,
.metrics-heading {
  justify-content: space-between;
}
.page-heading {
  margin-bottom: 28px;
}
.eyebrow {
  font-size: 12px;
  color: var(--color-primary);
  font-weight: 600;
}
h1 {
  font-size: clamp(24px, 3vw, 32px);
  letter-spacing: -0.03em;
  margin: 10px 0 12px;
}
h2 {
  font-size: 16px;
  margin: 0;
}
h3 {
  font-size: 14px;
  margin: 0 0 12px;
}
p {
  color: var(--color-muted);
  font-size: 14px;
  line-height: 1.7;
  margin: 0;
}
button {
  cursor: pointer;
}
button:disabled {
  cursor: wait;
  opacity: 0.65;
}
button:focus-visible,
input:focus-visible,
textarea:focus-visible {
  outline: 3px solid var(--color-focus);
  outline-offset: 2px;
}
.dataset-card,
.table-nav,
.table-detail,
.metrics,
.setup {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
}
.dataset-card {
  padding: 24px;
  flex-wrap: wrap;
  justify-content: space-between;
  margin-bottom: 24px;
}
.source-icon {
  color: var(--color-primary);
  background: var(--color-primary-soft);
  border-radius: 12px;
  padding: 12px;
  display: grid;
  place-items: center;
}
.source-name {
  gap: 12px;
}
.source-name p {
  font-size: 12px;
  margin-top: 5px;
}
.stat-label {
  display: block;
  color: var(--color-muted);
  font-size: 12px;
  margin-bottom: 7px;
}
.dataset-card strong {
  display: block;
  font-size: 22px;
  font-variant-numeric: tabular-nums;
}
.coverage p,
.coverage small {
  font-size: 12px;
}
.coverage small {
  display: block;
  color: var(--color-muted);
  margin-top: 5px;
}
.browser {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}
.table-nav {
  padding: 16px 12px;
}
.table-nav h2 {
  padding: 8px 12px 20px;
  display: flex;
  justify-content: space-between;
}
.table-nav h2 span {
  color: var(--color-muted);
  font-weight: 400;
}
.table-nav button {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  text-align: left;
  padding: 12px;
  border: 0;
  border-radius: 8px;
  color: var(--color-muted);
  background: transparent;
  margin-bottom: 4px;
}
.table-nav button:hover {
  background: var(--color-background);
}
.table-nav button.selected {
  color: var(--color-primary);
  background: var(--color-primary-soft);
}
.table-nav strong,
.table-nav small {
  display: block;
}
.table-nav strong {
  font-size: 14px;
  font-weight: 600;
}
.table-nav small {
  font-size: 11px;
  margin-top: 4px;
}
.row-count {
  margin-left: auto;
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}
.table-detail {
  padding: 24px;
  overflow: hidden;
}
.detail-heading h2 {
  margin-top: 7px;
  font-size: 22px;
}
.table-description {
  margin: 16px 0 24px;
}
.column-table {
  overflow-x: auto;
  margin-top: 20px;
}
table {
  border-collapse: collapse;
  width: 100%;
  text-align: left;
  font-size: 13px;
}
th {
  background: var(--color-background);
  color: var(--color-muted);
  font-size: 12px;
  font-weight: 500;
}
th,
td {
  padding: 14px 12px;
  border-bottom: 1px solid var(--color-border);
}
td {
  line-height: 1.7;
}
code {
  font-family: Consolas, monospace;
  font-size: 12px;
}
.type-cell {
  color: var(--color-muted);
  font-size: 12px;
  white-space: nowrap;
}
.key-badge {
  color: var(--color-primary);
  background: var(--color-primary-soft);
  padding: 3px 7px;
  border-radius: 4px;
  font-size: 11px;
  white-space: nowrap;
}
.constraint {
  color: var(--color-muted);
  font-size: 12px;
  white-space: nowrap;
}
.relationships {
  padding-top: 24px;
}
.relationships h3,
.metrics-heading h2 {
  display: flex;
  align-items: center;
  gap: 8px;
}
.relationships button {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  border: 1px solid var(--color-border);
  background: var(--color-background);
  padding: 10px 12px;
  color: var(--color-primary);
  border-radius: 6px;
  margin-top: 8px;
  text-align: left;
  overflow-wrap: anywhere;
}
.metrics {
  padding: 24px;
  margin-top: 24px;
}
.metrics-heading > span {
  font-size: 12px;
  color: var(--color-muted);
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 24px;
  margin-top: 24px;
}
.metric-grid article {
  border-left: 2px solid var(--color-border);
  padding-left: 16px;
}
.metric-grid p {
  font-size: 13px;
}
.metric-grid article > span {
  display: block;
  color: var(--color-muted);
  font-size: 11px;
  margin-top: 16px;
  overflow-wrap: anywhere;
}
.footnote {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  margin-top: 24px;
}
.error-banner {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  background: #fef2f2;
  color: #b91c1c;
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 20px;
  font-size: 14px;
}
.error-banner button,
.edit-actions > button {
  background: transparent;
  border: 0;
  color: inherit;
  white-space: nowrap;
  text-decoration: underline;
}
.notice {
  color: #047857;
  margin-bottom: 16px;
}
.empty,
.setup {
  text-align: center;
  padding: 48px 24px;
}
.setup > svg {
  color: var(--color-primary);
  margin-bottom: 20px;
}
.setup h2 {
  font-size: 22px;
  margin-bottom: 16px;
}
.setup pre {
  display: inline-block;
  max-width: 100%;
  overflow-x: auto;
  background: var(--color-background);
  padding: 16px;
  line-height: 1.8;
  text-align: left;
  font-size: 13px;
}
textarea,
input {
  color: var(--color-text);
  width: 100%;
  border: 1px solid var(--color-border);
  padding: 8px;
  border-radius: 6px;
  background: var(--color-background);
}
textarea {
  margin-top: 16px;
  resize: vertical;
}
@media (max-width: 1000px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 760px) {
  .structure {
    padding: 24px 16px;
  }
  .page-heading,
  .metrics-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 16px;
  }
  .browser {
    grid-template-columns: 1fr;
    gap: 16px;
  }
  .table-nav {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }
  .table-nav h2 {
    width: 100%;
    padding-bottom: 8px;
  }
  .table-nav button {
    width: calc(50% - 2px);
  }
  .dataset-card {
    align-items: flex-start;
    gap: 24px;
  }
  .source-name,
  .coverage {
    width: 100%;
  }
  .table-detail {
    padding: 20px 16px;
  }
  .detail-heading {
    gap: 12px;
    flex-wrap: wrap;
  }
  .metric-grid {
    grid-template-columns: 1fr;
  }
  .relationships code {
    overflow-wrap: anywhere;
  }
}
</style>
