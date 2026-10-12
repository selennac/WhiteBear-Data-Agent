import { describe, expect, it } from 'vitest'

import type { ChartSpec, QueryResult } from '../types/api'
import { chartOptions } from './chart'

const result: QueryResult = {
  columns: [
    { name: 'date', data_type: 'date' },
    { name: 'sales', data_type: 'numeric' },
  ],
  rows: [
    ['2026-10-11', '222.00'],
    ['2026-10-10', '123.45'],
  ],
  row_count: 2,
  truncated: false,
  elapsed_ms: 1,
}
const spec: ChartSpec = {
  type: 'line',
  title: '销售趋势',
  x_column: 0,
  y_columns: [1],
  supported_types: ['line', 'bar'],
}

describe('chart data mapping', () => {
  it('sorts time points with their original decimal values and switches without changing results', () => {
    const before = structuredClone(result)
    const line = chartOptions(result, spec, 'line')
    const bar = chartOptions(result, spec, 'bar')
    expect(line.xAxis).toMatchObject({ data: ['2026-10-10', '2026-10-11'] })
    expect(line.series).toMatchObject([
      {
        type: 'line',
        data: [
          { value: 123.45, exact: '123.45' },
          { value: 222, exact: '222.00' },
        ],
      },
    ])
    expect(bar.series).toMatchObject([{ type: 'bar', data: [{ value: 123.45 }, { value: 222 }] }])
    expect(result).toEqual(before)
    expect(line.tooltip).toMatchObject({ renderMode: 'richText' })
  })
  it('keeps missing group values as gaps rather than inventing zeros', () => {
    const grouped: QueryResult = {
      ...result,
      columns: [...result.columns, { name: 'region', data_type: 'text' }],
      rows: [
        ['2026-10-10', '10.01', '华东'],
        ['2026-10-11', '20.02', '华南'],
      ],
    }
    const option = chartOptions(grouped, { ...spec, series_column: 2 }, 'line')
    expect(option.series).toMatchObject([
      { name: 'sales · 华东', data: [{ value: 10.01 }, { value: null }] },
      { name: 'sales · 华南', data: [{ value: null }, { value: 20.02 }] },
    ])
  })
  it('rejects truncated share charts and out-of-range fields', () => {
    const pie: ChartSpec = { ...spec, type: 'pie', supported_types: ['pie'] }
    expect(() => chartOptions({ ...result, truncated: true }, pie, 'pie')).toThrow('占比')
    expect(() => chartOptions(result, { ...spec, y_columns: [20] }, 'line')).toThrow('字段')
  })
  it('uses separate axes for metrics with different units', () => {
    const option = chartOptions(
      {
        ...result,
        columns: [...result.columns, { name: 'orders', data_type: 'int8' }],
        rows: [['2026-10-11', '222.00', 3]],
      },
      { ...spec, y_columns: [1, 2] },
      'line',
    )
    expect(option.series).toMatchObject([
      { name: 'sales', yAxisIndex: 0 },
      { name: 'orders', yAxisIndex: 1 },
    ])
  })
})

it('distinguishes repeated metric aliases in legends while preserving column positions', () => {
  const duplicated: QueryResult = {
    ...result,
    columns: [
      { name: 'day', data_type: 'date' },
      { name: 'amount', data_type: 'numeric' },
      { name: 'amount', data_type: 'numeric' },
    ],
    rows: [['2026-10-11', '1.01', '2.02']],
  }
  const option = chartOptions(duplicated, { ...spec, y_columns: [1, 2] }, 'bar')
  expect(option.series).toMatchObject([
    { name: 'amount（列2）', data: [{ exact: '1.01' }] },
    { name: 'amount（列3）', data: [{ exact: '2.02' }] },
  ])
})

it('keeps original monetary values and shows percentages in share tooltips', () => {
  const share: QueryResult = {
    ...result,
    columns: [
      { name: 'category', data_type: 'text' },
      { name: 'paid_sales', data_type: 'numeric' },
    ],
    rows: [
      ['食品', '123.45'],
      ['数码', '100.00'],
    ],
  }
  const option = chartOptions(
    share,
    { ...spec, type: 'pie', supported_types: ['pie', 'bar'] },
    'pie',
  )
  expect(option.series).toMatchObject([
    {
      type: 'pie',
      data: [
        { name: '食品', exact: '123.45' },
        { name: '数码', exact: '100.00' },
      ],
    },
  ])
  const tooltip = option.tooltip as { formatter: (params: unknown) => string }
  expect(
    tooltip.formatter({
      name: '食品',
      seriesName: '实付销售额',
      data: { exact: '123.45' },
      percent: 55.25,
    }),
  ).toContain('123.45 · 占比 55.25%')
})
