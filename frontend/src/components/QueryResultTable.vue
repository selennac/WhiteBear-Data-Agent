<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { QueryResult } from '../types/api'
import BaseButton from './ui/BaseButton.vue'

const props = defineProps<{ result: QueryResult }>()
const page = ref(1)
const sortColumn = ref<number | null>(null)
const ascending = ref(true)
const pageCount = computed(() => Math.max(1, Math.ceil(props.result.rows.length / 50)))
const sortedRows = computed(() => {
  const index = sortColumn.value
  if (index === null) return props.result.rows
  const numeric = /int|numeric|float|decimal/i.test(props.result.columns[index]?.data_type ?? '')
  return [...props.result.rows].sort((left, right) => {
    const a = left[index]
    const b = right[index]
    let order: number
    if (a == null || b == null) order = a == null ? (b == null ? 0 : 1) : -1
    else if (numeric && Number.isFinite(Number(a)) && Number.isFinite(Number(b)))
      order = Number(a) - Number(b)
    else order = String(a).localeCompare(String(b), 'zh-CN', { numeric: true })
    return ascending.value ? order : -order
  })
})
const visibleRows = computed(() => sortedRows.value.slice((page.value - 1) * 50, page.value * 50))
watch(
  () => props.result,
  () => {
    page.value = 1
    sortColumn.value = null
  },
)

function sort(index: number) {
  ascending.value = sortColumn.value === index ? !ascending.value : true
  sortColumn.value = index
  page.value = 1
}
</script>

<template>
  <div class="result-table">
    <div class="result-info">
      <span>返回 {{ result.row_count }} 行 · 查询耗时 {{ result.elapsed_ms }} ms</span>
      <span v-if="result.truncated" class="truncated" role="status"
        >结果已截断（最多 1,000 行 / 2 MB），请缩小查询范围。</span
      >
    </div>
    <div
      v-if="result.rows.length"
      class="table-scroll"
      tabindex="0"
      aria-label="查询结果，可横向滚动"
    >
      <table>
        <caption class="sr-only">
          分析查询结果
        </caption>
        <thead>
          <tr>
            <th
              v-for="(column, index) in result.columns"
              :key="index"
              scope="col"
              :aria-sort="sortColumn === index ? (ascending ? 'ascending' : 'descending') : 'none'"
            >
              <button type="button" @click="sort(index)">
                {{ column.name }}
                <span aria-hidden="true">{{
                  sortColumn === index ? (ascending ? '↑' : '↓') : '↕'
                }}</span>
              </button>
              <small>{{ column.data_type }}</small>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, rowIndex) in visibleRows" :key="rowIndex">
            <td
              v-for="(cell, columnIndex) in row"
              :key="columnIndex"
              :class="{ null: cell === null }"
            >
              {{ cell === null ? 'NULL' : cell }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else class="empty">查询成功，当前条件下没有数据。</p>
    <div v-if="pageCount > 1" class="pagination">
      <BaseButton variant="secondary" :disabled="page <= 1" @click="page--">上一页</BaseButton>
      <span>第 {{ page }} / {{ pageCount }} 页 · 每页 50 行</span>
      <BaseButton variant="secondary" :disabled="page >= pageCount" @click="page++"
        >下一页</BaseButton
      >
    </div>
  </div>
</template>

<style scoped>
.result-info {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
  color: var(--color-muted);
  font-size: 13px;
}
.truncated {
  color: #92400e;
}
.table-scroll {
  overflow: auto;
  max-height: 600px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}
table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 13px;
}
th,
td {
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
}
th {
  background: var(--color-background);
  position: sticky;
  top: 0;
}
th button {
  border: 0;
  padding: 0;
  background: transparent;
  color: var(--color-text);
  cursor: pointer;
  font-weight: 600;
}
th small {
  display: block;
  margin-top: 4px;
  color: var(--color-muted);
  font-weight: 400;
}
button:focus-visible,
.table-scroll:focus-visible {
  outline: 3px solid var(--color-focus);
  outline-offset: 2px;
}
.null,
.empty {
  color: var(--color-muted);
}
.pagination {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
  margin-top: 16px;
  font-size: 13px;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}
</style>
