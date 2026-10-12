import { flushPromises, mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'

import type { ChartSpec, QueryResult } from '../types/api'
import QueryResultChart from './QueryResultChart.vue'

vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', props: ['option'], template: '<div class="chart-stub" />' },
}))

beforeEach(() => {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  )
})

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

async function selectChartType(view: VueWrapper, label: string) {
  await view.get('.chart-select-trigger').trigger('keydown', { key: 'Enter' })
  await flushPromises()
  const item = [...document.querySelectorAll<HTMLElement>('[role="option"]')].find((option) =>
    option.textContent?.includes(label),
  )
  expect(item).toBeDefined()
  item!.dispatchEvent(
    new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }),
  )
  await flushPromises()
}

it('switches chart type locally and restores the default for a new result', async () => {
  const view = mount(QueryResultChart, { attachTo: document.body, props: { result, spec } })
  expect(view.text()).toContain('销售额趋势')
  expect(view.get('.chart-select-trigger').text()).toContain('折线图')
  await selectChartType(view, '柱状图')
  expect(view.get('.chart-select-trigger').text()).toContain('柱状图')
  expect(view.findComponent({ name: 'VChart' }).props('option').series[0].type).toBe('bar')
  await view.setProps({ result: { ...result, rows: [['2026-10-12', '1.01']] } })
  await flushPromises()
  expect(view.get('.chart-select-trigger').text()).toContain('折线图')
  view.unmount()
})
it('shows a table fallback for invalid chart fields', () => {
  const view = mount(QueryResultChart, { props: { result, spec: { ...spec, x_column: 10 } } })
  expect(view.text()).toContain('查看下方结果表格')
  expect(view.find('.chart-stub').exists()).toBe(false)
  view.unmount()
})
