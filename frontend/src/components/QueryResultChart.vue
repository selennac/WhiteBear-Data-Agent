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
import { Check, ChevronDown } from 'lucide-vue-next'
import {
  SelectContent,
  SelectIcon,
  SelectItem,
  SelectItemIndicator,
  SelectItemText,
  SelectPortal,
  SelectRoot,
  SelectTrigger,
  SelectValue,
  SelectViewport,
} from 'reka-ui'
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
const names: Record<ChartSpec['type'], string> = { line: '折线图', bar: '柱状图', pie: '饼图' }
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
        <span :id="selectId" class="chart-select-label">图表类型</span>
        <SelectRoot v-model="type">
          <SelectTrigger class="chart-select-trigger" :aria-labelledby="selectId">
            <SelectValue>{{ names[type] }}</SelectValue>
            <SelectIcon class="chart-select-icon">
              <ChevronDown :size="14" aria-hidden="true" />
            </SelectIcon>
          </SelectTrigger>
          <SelectPortal>
            <SelectContent
              class="chart-select-menu"
              position="popper"
              align="end"
              :side-offset="6"
              :collision-padding="10"
            >
              <SelectViewport class="chart-select-menu-viewport">
                <SelectItem
                  v-for="kind in spec.supported_types"
                  :key="kind"
                  :value="kind"
                  class="chart-select-menu-item"
                >
                  <SelectItemIndicator class="chart-select-menu-indicator">
                    <Check :size="14" aria-hidden="true" />
                  </SelectItemIndicator>
                  <SelectItemText>{{ names[kind] }}</SelectItemText>
                </SelectItem>
              </SelectViewport>
            </SelectContent>
          </SelectPortal>
        </SelectRoot>
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
.chart-select-label {
  color: var(--color-muted);
  font-size: 13px;
}
.chart-select-trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: var(--color-surface);
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.5;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background-color 0.15s ease;
}
.chart-select-trigger:hover {
  border-color: var(--color-focus);
  background: var(--color-background);
}
.chart-select-trigger[data-state='open'] {
  border-color: var(--color-primary);
}
.chart-select-trigger:focus-visible {
  outline: 3px solid var(--color-focus);
  outline-offset: 2px;
}
.chart-select-icon {
  display: inline-flex;
  align-items: center;
  color: var(--color-muted);
  transition: transform 0.15s ease;
}
.chart-select-trigger[data-state='open'] .chart-select-icon {
  transform: rotate(180deg);
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

<!-- 下拉菜单通过 Portal 渲染到 body，拿不到本组件的 scoped 属性，故使用非 scoped 样式块。 -->
<style>
.chart-select-menu {
  z-index: 50;
  min-width: var(--reka-select-trigger-width);
  max-height: var(--reka-select-content-available-height);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.14);
  overflow: hidden;
}
.chart-select-menu-viewport {
  padding: 4px;
}
.chart-select-menu-item {
  position: relative;
  display: flex;
  align-items: center;
  padding: 7px 10px 7px 28px;
  border-radius: 6px;
  color: var(--color-text);
  font-size: 13px;
  cursor: pointer;
  user-select: none;
  outline: none;
}
.chart-select-menu-item[data-highlighted] {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
.chart-select-menu-item[data-state='checked'] {
  color: var(--color-primary);
  font-weight: 600;
}
.chart-select-menu-indicator {
  position: absolute;
  left: 8px;
  display: inline-flex;
  align-items: center;
  color: var(--color-primary);
}
</style>
