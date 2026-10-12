import { mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'

import type { ChartSpec, QueryResult } from '../types/api'
import QueryResultChart from './QueryResultChart.vue'

vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', props: ['option'], template: '<div class="chart-stub" />' },
}))
const result: QueryResult = {
  columns: [
    { name: 'day', data_type: 'date' },
    { name: 'sales', data_type: 'numeric' },
  ],
  rows: [['2026-10-11', '123.45']],
  row_count: 1,
  truncated: false,
  elapsed_ms: 1,
}
const spec: ChartSpec = {
  title: '销售额趋势',
  type: 'line',
  x_column: 0,
  y_columns: [1],
  supported_types: ['line', 'bar'],
}

it('switches chart type locally and restores the default for a new result', async () => {
  const view = mount(QueryResultChart, { props: { result, spec } })
  expect(view.text()).toContain('销售额趋势')
  await view.get('select').setValue('bar')
  expect(view.findComponent({ name: 'VChart' }).props('option').series[0].type).toBe('bar')
  await view.setProps({ result: { ...result, rows: [['2026-10-12', '1.01']] } })
  expect(view.get('select').element.value).toBe('line')
  view.unmount()
})
it('shows a table fallback for invalid chart fields', () => {
  const view = mount(QueryResultChart, { props: { result, spec: { ...spec, x_column: 10 } } })
  expect(view.text()).toContain('查看下方结果表格')
  expect(view.find('.chart-stub').exists()).toBe(false)
  view.unmount()
})
