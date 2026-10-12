import type { AnalysisRun } from '../types/api'

export const metricLabels: Record<string, string> = {
  paid_sales: '实付销售额',
  paid_orders: '支付订单数',
  average_order_value: '客单价',
  successful_refunds: '成功退款额',
}
export const statusLabels = {
  running: '运行中',
  succeeded: '查询成功',
  failed: '分析失败',
  cancelled: '已停止',
  clarification_required: '需要澄清',
}
export const nodeLabels: Record<string, string> = {
  load_context: '加载数据结构与业务口径',
  generate_query: '生成查询方案',
  validate_sql: '校验 SQL',
  execute_query: '执行只读查询',
  build_chart: '准备图表',
  summarize_result: '总结查询结果',
}
export function timeRangeLabel(value: string) {
  const dates = value.match(/\d{4}-\d{2}-\d{2}/g)
  return dates?.length === 2 ? `${dates[0]} 至 ${dates[1]}` : value
}
export function canContinue(run: AnalysisRun) {
  return ['succeeded', 'clarification_required'].includes(run.status) && !!run.draft
}
