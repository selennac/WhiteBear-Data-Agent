<script setup lang="ts">
import { computed, onErrorCaptured, ref, useId, watch } from 'vue'
import { use } from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  AriaComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

import type { ChartSpec, QueryResult } from '../types/api'
import { chartOptions } from '../utils/chart'

use([
  BarChart,
  LineChart,
  PieChart,
  AriaComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  SVGRenderer,
])
const props = defineProps<{ result: QueryResult; spec: ChartSpec; message?: string }>()
const selectId = useId()
const type = ref<ChartSpec['type']>(props.spec.type)
const failed = ref(false)
const names = { line: '折线图', bar: '柱状图', pie: '饼图' }
watch(
  () => [props.spec, props.result],
  () => {
    type.value = props.spec.type
    failed.value = false
  },
)
const option = computed(() => {
  try {
    return chartOptions(props.result, props.spec, type.value)
  } catch {
    return null
  }
})
onErrorCaptured(() => {
  failed.value = true
  return false
})
</script>

<template>
  <section class="result-chart" aria-label="查询结果图表">
    <div class="chart-heading">
      <h3>{{ spec.title }}</h3>
      <div class="chart-select">
        <label :for="selectId">图表类型</label>
        <select :id="selectId" v-model="type">
          <option v-for="kind in spec.supported_types" :key="kind" :value="kind">
            {{ names[kind] }}
          </option>
        </select>
      </div>
    </div>
    <p v-if="message" class="chart-note" role="status">{{ message }}</p>
    <div
      v-if="option && !failed"
      class="chart-scroll"
      :tabindex="spec.y_columns.length > 2 ? 0 : undefined"
      aria-label="图表内容，可横向滚动"
    >
      <VChart
        class="chart"
        :style="{ minWidth: spec.y_columns.length > 2 ? '640px' : '0' }"
        :option="option"
        :init-options="{ renderer: 'svg' }"
        autoresize
      />
    </div>
    <p v-else class="chart-note" role="status">图表暂不可用，请查看下方结果表格。</p>
    <p class="chart-footnote">
      图表使用本次返回数据；切换类型复用当前结果。悬浮查看原始数值，精确金额以表格为准。
    </p>
  </section>
</template>

<style scoped>
.result-chart {
  margin-bottom: 24px;
  padding: 20px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}
.chart-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
h3 {
  margin: 0;
  font-size: 15px;
  overflow-wrap: anywhere;
}
.chart-scroll {
  overflow-x: auto;
}
.chart-select {
  display: flex;
  align-items: center;
  gap: 8px;
}
label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--color-muted);
  font-size: 13px;
}
select {
  padding: 6px 10px;
  background: var(--color-surface);
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-radius: 6px;
}
select:focus-visible {
  outline: 3px solid var(--color-focus);
  outline-offset: 2px;
}
.chart {
  height: 360px;
  width: 100%;
}
.chart-note {
  color: #92400e;
  font-size: 13px;
}
.chart-footnote {
  margin: 8px 0 0;
  color: var(--color-muted);
  font-size: 12px;
}
@media (max-width: 640px) {
  .result-chart {
    padding: 12px;
  }
  .chart {
    height: 300px;
  }
}
</style>
