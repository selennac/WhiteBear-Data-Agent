import type { EChartsOption } from 'echarts'

import type { ChartSpec, QueryResult } from '../types/api'

const label = (value: unknown) => (value == null ? 'NULL' : String(value))
const key = (value: unknown): string => JSON.stringify(value) ?? 'null'
const numeric = (value: unknown): number | null => {
  if (value == null) return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function tooltip(params: unknown): string {
  const entries = Array.isArray(params) ? params : [params]
  return entries
    .map((entry) => {
      const item = entry as {
        name?: string
        seriesName?: string
        data?: { exact?: string }
        percent?: number
      }
      return [
        item.name,
        item.seriesName,
        item.data?.exact ?? 'NULL',
        item.percent == null ? '' : '占比 ' + item.percent.toFixed(2) + '%',
      ]
        .filter(Boolean)
        .join(' · ')
    })
    .join('\n')
}

export function chartOptions(
  result: QueryResult,
  spec: ChartSpec,
  type: ChartSpec['type'],
): EChartsOption {
  const indices = [
    spec.x_column,
    ...spec.y_columns,
    ...(spec.series_column == null ? [] : [spec.series_column]),
  ]
  if (
    !spec.supported_types.includes(type) ||
    indices.some(
      (index) => !Number.isInteger(index) || index < 0 || index >= result.columns.length,
    ) ||
    !spec.y_columns.length ||
    result.rows.some((row) => row.length !== result.columns.length)
  )
    throw new Error('图表字段与查询结果不一致。')
  const metricNames: Record<string, string> = {
    paid_sales: '实付销售额',
    paid_orders: '支付订单数',
    average_order_value: '客单价',
    successful_refunds: '成功退款额',
  }
  const metricName = (column: number) => {
    const original = result.columns[column]!.name
    const name = metricNames[original] ?? original
    return spec.y_columns.filter((index) => result.columns[index]!.name === original).length > 1
      ? name + '（列' + (column + 1) + '）'
      : name
  }
  const base: EChartsOption = {
    color: ['#2563eb', '#059669', '#d97706', '#7c3aed', '#db2777', '#0891b2'],
    animation: false,
    aria: {
      enabled: true,
      label: {
        description:
          spec.title +
          '。横轴为' +
          result.columns[spec.x_column]!.name +
          '，指标为' +
          spec.y_columns.map(metricName).join('、') +
          '，共' +
          result.rows.length +
          '行数据。原始数值请查看下方结果表格。',
      },
    },
    tooltip: {
      trigger: type === 'pie' ? 'item' : 'axis',
      renderMode: 'richText',
      formatter: tooltip,
    },
    legend: { type: 'scroll', bottom: 0 },
  }
  if (type === 'pie') {
    if (
      result.truncated ||
      result.rows.length > 8 ||
      spec.y_columns.length !== 1 ||
      spec.series_column != null
    )
      throw new Error('当前数据不适合占比图。')
    const column = spec.y_columns[0]!
    const data = result.rows.map((row) => ({
      name: label(row[spec.x_column]),
      value: numeric(row[column])!,
      exact: label(row[column]),
    }))
    if (
      data.some((item) => item.value == null || item.value < 0) ||
      !data.some((item) => item.value > 0)
    )
      throw new Error('占比图需要有效的非负数值。')
    return {
      ...base,
      series: [
        {
          type: 'pie',
          name: metricName(column),
          percentPrecision: 2,
          radius: ['35%', '65%'],
          center: ['50%', '45%'],
          data,
          label: { show: true, formatter: '{b}: {d}%', overflow: 'truncate', width: 120 },
        },
      ],
      media: [
        { query: { maxWidth: 400 }, option: { series: [{ type: 'pie', label: { show: false } }] } },
        { option: { series: [{ type: 'pie', label: { show: true } }] } },
      ],
    }
  }
  const categoryValues = new Map<string, unknown>()
  for (const row of result.rows) categoryValues.set(key(row[spec.x_column]), row[spec.x_column])
  const temporal = /date|timestamp/i.test(result.columns[spec.x_column]!.data_type)
  const categories = [...categoryValues.keys()]
  if (temporal)
    categories.sort((left, right) =>
      label(categoryValues.get(left)).localeCompare(label(categoryValues.get(right))),
    )
  const seriesValues =
    spec.series_column == null
      ? [null]
      : [...new Set(result.rows.map((row) => key(row[spec.series_column!])))]
  const series = spec.y_columns.flatMap((column) =>
    seriesValues.map((seriesKey) => {
      const rows = result.rows.filter(
        (row) => spec.series_column == null || key(row[spec.series_column]) === seriesKey,
      )
      const byCategory = new Map(rows.map((row) => [key(row[spec.x_column]), row[column]]))
      const name =
        metricName(column) +
        (spec.series_column == null ? '' : ' · ' + label(rows[0]?.[spec.series_column]))
      return {
        name,
        type,
        yAxisIndex: spec.y_columns.indexOf(column),
        connectNulls: false,
        data: categories.map((category) => ({
          value: numeric(byCategory.get(category)),
          exact: label(byCategory.get(category)),
        })),
      }
    }),
  )
  return {
    ...base,
    grid: {
      left: 65,
      right: Math.max(30, (spec.y_columns.length - 1) * 65),
      top: 45,
      bottom: categories.length > 30 ? 100 : 75,
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: categories.map((category) => label(categoryValues.get(category))),
      axisLabel: {
        hideOverlap: true,
        formatter: (value: string) =>
          temporal
            ? /T00:00:00/.test(value)
              ? value.slice(0, 10)
              : value.replace('T', ' ').slice(0, 16)
            : value,
      },
    },
    yAxis: spec.y_columns.map((column, index) => ({
      type: 'value',
      name: metricName(column),
      position: index === 0 ? 'left' : 'right',
      offset: Math.max(0, index - 1) * 65,
      splitLine: { show: index === 0 },
    })),
    dataZoom: categories.length > 30 ? [{ type: 'inside' }, { type: 'slider', bottom: 30 }] : [],
    series,
  }
}
