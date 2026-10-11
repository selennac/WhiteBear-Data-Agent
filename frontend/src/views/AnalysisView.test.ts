import { createPinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'

import { cancelRun, createConversation, getConversations, streamQuestion } from '../services/api'
import type { AnalysisRun } from '../types/api'
import AnalysisView from './AnalysisView.vue'

vi.mock('../services/api', () => ({
  cancelRun: vi.fn(),
  createConversation: vi.fn(),
  getConversations: vi.fn(),
  getConversation: vi.fn(),
  streamQuestion: vi.fn(),
}))

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
