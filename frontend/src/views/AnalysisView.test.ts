import { createPinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'

import { cancelRun, createConversation, getConversations, streamQuestion } from '../services/api'
import type { AnalysisRun } from '../types/api'
import AnalysisView from './AnalysisView.vue'
import { useAnalysisStore } from '../stores/analysis'

vi.mock('../services/api', () => ({
  cancelRun: vi.fn(),
  createConversation: vi.fn(),
  getConversations: vi.fn(),
  getConversation: vi.fn(),
  streamQuestion: vi.fn(),
}))

beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(getConversations).mockResolvedValue([])
})

it('renders progress, stops analysis and enables the next submission', async () => {
  const run: AnalysisRun = {
    id: 'run-1',
    conversation_id: 'conversation-1',
    question: '订单数',
    status: 'running',
    created_at: '2026-10-11T12:00:00+08:00',
    reference_time: '2026-10-11T12:00:00+08:00',
    steps: [{ node: 'generate_query', status: 'running', attempt: 1, elapsed_ms: 0 }],
  }
  let finish!: (run: AnalysisRun) => void
  vi.mocked(getConversations).mockResolvedValue([])
  vi.mocked(createConversation).mockResolvedValue({
    id: run.conversation_id,
    title: '新建分析',
    datasource_id: 'business',
    created_at: run.created_at,
  })
  vi.mocked(streamQuestion).mockImplementation((_id, _question, receive) => {
    receive({ type: 'run_started', run_id: run.id, run })
    return new Promise((resolve) => {
      finish = resolve
    })
  })
  vi.mocked(cancelRun).mockImplementation(async () => {
    const cancelled: AnalysisRun = {
      ...run,
      status: 'cancelled',
      steps: [{ node: 'generate_query', status: 'cancelled', attempt: 1, elapsed_ms: 5 }],
    }
    finish(cancelled)
    return cancelled
  })
  const view = mount(AnalysisView, { global: { plugins: [createPinia()] } })
  await flushPromises()
  await vi.waitFor(() => expect(view.get('textarea').attributes('disabled')).toBeUndefined())
  await view.get('textarea').setValue('订单数')
  await view.get('form').trigger('submit')
  await vi.waitFor(() => expect(view.text()).toContain('正在生成查询方案'))
  const stop = view.findAll('button').find((button) => button.text() === '停止分析')
  expect(stop).toBeDefined()
  await stop!.trigger('click')
  await vi.waitFor(() => expect(view.get('.badge').text()).toBe('已停止'))
  expect(view.get('textarea').attributes('disabled')).toBeUndefined()
  expect(view.text()).toContain('可以提交新问题')
  view.unmount()
})

it('continues a clarification with a short answer and displays the complete conditions', async () => {
  const now = '2026-10-11T12:00:00+08:00'
  const pending: AnalysisRun = {
    id: 'clarify-1',
    conversation_id: 'conversation-1',
    question: '华东销售额按城市拆分',
    status: 'clarification_required',
    created_at: now,
    reference_time: now,
    draft: {
      action: 'clarify',
      clarification: '没有城市字段，是否使用客户区域？',
      resolved_question: '最近30天华东销售额按城市拆分',
    },
  }
  const continued: AnalysisRun = {
    ...pending,
    id: 'run-2',
    question: '用客户区域',
    status: 'succeeded',
    input_context: {
      clarification: {
        run_id: pending.id,
        question: pending.question,
        reference_time: now,
        draft: pending.draft!,
      },
    },
    draft: {
      action: 'query',
      context_mode: 'clarification',
      resolved_question: '最近30天华东实付销售额按客户区域拆分',
      metrics: ['paid_sales'],
      filters: ['客户区域=华东', '订单已支付'],
      group_by: ['客户区域'],
      time_range: '2026-09-11 至 2026-10-11',
      sql: 'SELECT 12',
    },
  }
  vi.mocked(createConversation).mockResolvedValue({
    id: pending.conversation_id,
    title: '新建分析',
    datasource_id: 'business',
    created_at: now,
  })
  vi.mocked(streamQuestion)
    .mockImplementationOnce(async (_id, _question, receive) => {
      receive({ type: 'run_completed', run_id: pending.id, run: pending })
      return pending
    })
    .mockImplementationOnce(async (_id, _question, receive) => {
      receive({ type: 'run_completed', run_id: continued.id, run: continued })
      return continued
    })
  const view = mount(AnalysisView, { global: { plugins: [createPinia()] } })
  await flushPromises()
  await view.get('textarea').setValue(pending.question)
  await view.get('form').trigger('submit')
  await flushPromises()
  expect(view.text()).toContain('直接在输入框回答即可继续')
  expect(view.text()).toContain('补充并继续')
  expect((view.get('textarea').element as HTMLTextAreaElement).value).toBe('')
  await view.get('textarea').setValue('用客户区域')
  await view.get('form').trigger('submit')
  await flushPromises()
  expect(streamQuestion).toHaveBeenLastCalledWith(
    pending.conversation_id,
    '用客户区域',
    expect.any(Function),
    expect.any(AbortSignal),
  )
  const conditions = view.get('[aria-label="本轮分析口径"]').text()
  expect(conditions).toContain('接续澄清')
  expect(conditions).toContain(continued.draft!.resolved_question)
  expect(conditions).toContain('实付销售额')
  expect(conditions).toContain('客户区域=华东')
  expect(conditions).toContain('客户区域')
  await view
    .findAll('button')
    .find((button) => button.text() === '新建分析')!
    .trigger('click')
  expect(view.find('.continuation').exists()).toBe(false)
  expect(view.get('textarea').attributes('placeholder')).toContain('最近 30 天的实付销售额')
  view.unmount()
})

it('keeps the latest valid continuation when viewing an older result or a failed run', async () => {
  const pinia = createPinia()
  const view = mount(AnalysisView, { global: { plugins: [pinia] } })
  await flushPromises()
  const state = useAnalysisStore(pinia)
  const run: AnalysisRun = {
    id: 'old',
    conversation_id: 'conversation-1',
    question: '旧问题',
    status: 'succeeded',
    created_at: '2026-10-11T12:00:00+08:00',
    reference_time: '2026-10-11T12:00:00+08:00',
    draft: { action: 'query', sql: 'SELECT 1' },
  }
  state.runs = [
    run,
    { ...run, id: 'latest', question: '最近7天华东销售额' },
    { ...run, id: 'failed', status: 'failed', question: '华南订单数' },
  ]
  state.selectedRun = run
  await flushPromises()
  expect(view.get('.continuation').text()).toContain('最近7天华东销售额')
  expect(view.get('.continuation').text()).not.toContain('华南订单数')
  expect(view.get('.output-heading').text()).toContain('旧问题')
  view.unmount()
})

it('restores summaries from history, escapes text and retains tables after summary failure', async () => {
  const pinia = createPinia()
  const view = mount(AnalysisView, { global: { plugins: [pinia] } })
  await flushPromises()
  const state = useAnalysisStore(pinia)
  const run: AnalysisRun = {
    id: 'summary-run',
    conversation_id: 'conversation-1',
    question: '销售额',
    status: 'succeeded',
    created_at: '2026-10-12T12:00:00+08:00',
    reference_time: '2026-10-12T12:00:00+08:00',
    result: {
      columns: [{ name: 'sales', data_type: 'numeric' }],
      rows: [['123.45']],
      row_count: 1,
      truncated: false,
      elapsed_ms: 1,
    },
    summary: {
      text: '<script>unsafe</script>销售额为123.45。',
      limitations: ['只依据已返回数据。'],
    },
  }
  state.selectedRun = run
  await flushPromises()
  expect(view.get('[aria-label="结果总结"]').text()).toContain('销售额为123.45')
  expect(view.get('[aria-label="结果总结"]').find('script').exists()).toBe(false)
  expect(view.get('td').text()).toBe('123.45')
  state.selectedRun = { ...run, summary: null, summary_error: '总结超过30秒，查询结果已保留。' }
  await flushPromises()
  expect(view.get('[aria-label="结果总结"]').text()).toContain('查询结果已保留')
  expect(view.get('td').text()).toBe('123.45')
  view.unmount()
})
