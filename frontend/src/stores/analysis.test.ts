import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  cancelRun,
  createConversation,
  deleteConversation,
  getConversation,
  getConversations,
  streamQuestion,
} from '../services/api'
import type { AnalysisRun, ConversationSummary } from '../types/api'
import { useAnalysisStore } from './analysis'

vi.mock('../services/api', () => ({
  cancelRun: vi.fn(),
  createConversation: vi.fn(),
  deleteConversation: vi.fn(),
  getConversation: vi.fn(),
  getConversations: vi.fn(),
  streamQuestion: vi.fn(),
}))
const conversation: ConversationSummary = {
  id: 'conversation-1',
  datasource_id: 'business',
  title: '新建分析',
  created_at: '2026-10-11T12:00:00+08:00',
}
const run: AnalysisRun = {
  id: 'run-1',
  conversation_id: conversation.id,
  question: '订单数',
  status: 'succeeded',
  created_at: conversation.created_at,
  reference_time: conversation.created_at,
  result: {
    columns: [{ name: 'count', data_type: 'int8' }],
    rows: [[12]],
    row_count: 1,
    truncated: false,
    elapsed_ms: 1,
  },
}

describe('streaming analysis state', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    setActivePinia(createPinia())
    vi.mocked(createConversation).mockResolvedValue({ ...conversation })
    let sequence = 0
    vi.mocked(streamQuestion).mockImplementation(async (_id, question, receive) => {
      const result = { ...run, id: 'run-' + ++sequence, question }
      receive({ type: 'run_started', run_id: result.id, run: { ...result, status: 'running' } })
      receive({ type: 'run_completed', run_id: result.id, run: result })
      return result
    })
  })

  it('creates one conversation and preserves returned results', async () => {
    const state = useAnalysisStore()
    await state.submit(' 订单数 ')
    await state.submit('销售额')
    expect(createConversation).toHaveBeenCalledTimes(1)
    expect(streamQuestion).toHaveBeenNthCalledWith(
      1,
      conversation.id,
      '订单数',
      expect.any(Function),
      expect.any(AbortSignal),
      undefined,
    )
    expect(state.selectedRun).toEqual({ ...run, id: 'run-2', question: '销售额' })
    expect(state.runs).toHaveLength(2)
    expect(state.conversations[0]?.title).toBe('订单数')
  })

  it('does not duplicate submissions or switch history while running', async () => {
    let finish!: (value: AnalysisRun) => void
    vi.mocked(streamQuestion).mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve
        }),
    )
    const state = useAnalysisStore()
    const pending = state.submit('订单数')
    await vi.waitFor(() => expect(streamQuestion).toHaveBeenCalledOnce())
    await state.submit('另一个问题')
    await state.selectConversation('other')
    state.newConversation()
    expect(state.conversationId).toBe(conversation.id)
    expect(getConversation).not.toHaveBeenCalled()
    finish(run)
    await pending
    expect(state.busy).toBe(false)
  })

  it('keeps prior results when the next request fails and can recover', async () => {
    const state = useAnalysisStore()
    await state.submit('订单数')
    vi.mocked(streamQuestion).mockRejectedValueOnce(new Error('模型未配置'))
    await state.submit('销售额')
    expect(state.selectedRun).toEqual(run)
    expect(state.error).toBe('模型未配置')
    await state.submit('销售额')
    expect(state.error).toBe('')
  })

  it('restores persisted history and clears it when starting a new analysis', async () => {
    vi.mocked(getConversations).mockResolvedValue([conversation])
    vi.mocked(getConversation).mockResolvedValue({ ...conversation, runs: [run] })
    const state = useAnalysisStore()
    await state.loadHistory()
    await state.selectConversation(conversation.id)
    expect(state.selectedRun).toEqual(run)
    state.newConversation()
    expect(state.runs).toEqual([])
    expect(state.conversationId).toBeNull()
  })

  it('updates a running step in place and shows SQL before completion', async () => {
    let finish!: (value: AnalysisRun) => void
    vi.mocked(streamQuestion).mockImplementation((_id, _question, receive) => {
      receive({
        type: 'run_started',
        run_id: run.id,
        run: { ...run, status: 'running', result: null, steps: [] },
      })
      receive({
        type: 'node_status',
        run_id: run.id,
        step: {
          node: 'generate_query',
          status: 'running',
          attempt: 1,
          elapsed_ms: 0,
        },
      })
      receive({ type: 'sql', run_id: run.id, draft: { action: 'query', sql: 'SELECT 12' } })
      receive({
        type: 'node_status',
        run_id: run.id,
        step: {
          node: 'generate_query',
          status: 'succeeded',
          attempt: 1,
          elapsed_ms: 10,
        },
      })
      return new Promise((resolve) => {
        finish = resolve
      })
    })
    const state = useAnalysisStore()
    const pending = state.submit('订单数')
    await vi.waitFor(() => expect(state.selectedRun?.draft?.sql).toBe('SELECT 12'))
    expect(state.runs).toHaveLength(1)
    expect(state.selectedRun?.steps).toHaveLength(1)
    expect(state.selectedRun?.status).toBe('running')
    finish(run)
    await pending
    expect(state.runs).toHaveLength(1)
    expect(state.busy).toBe(false)
  })

  it('waits for the persisted cancellation then permits the next question', async () => {
    let finish!: (value: AnalysisRun) => void
    const cancelled: AnalysisRun = { ...run, status: 'cancelled', result: null }
    vi.mocked(streamQuestion).mockImplementationOnce((_id, _question, receive) => {
      receive({
        type: 'run_started',
        run_id: run.id,
        run: { ...run, status: 'running', result: null },
      })
      return new Promise((resolve) => {
        finish = resolve
      })
    })
    vi.mocked(cancelRun).mockImplementationOnce(async () => {
      finish(cancelled)
      return cancelled
    })
    const state = useAnalysisStore()
    const pending = state.submit('订单数')
    await vi.waitFor(() => expect(state.selectedRun?.status).toBe('running'))
    await state.stop()
    await pending
    expect(cancelRun).toHaveBeenCalledWith(run.id)
    expect(state.selectedRun?.status).toBe('cancelled')
    expect(state.busy).toBe(false)
    expect(state.error).toBe('')
    await state.submit('销售额')
    expect(state.selectedRun?.status).toBe('succeeded')
  })

  it('recovers the saved status after a stream disconnect', async () => {
    const cancelled: AnalysisRun = { ...run, status: 'cancelled', result: null }
    vi.mocked(streamQuestion).mockImplementationOnce(async (_id, _question, receive) => {
      receive({ type: 'run_started', run_id: run.id, run: { ...run, status: 'running' } })
      throw new Error('disconnected')
    })
    vi.mocked(cancelRun).mockResolvedValueOnce(cancelled)
    const state = useAnalysisStore()
    await state.submit('订单数')
    expect(state.selectedRun).toEqual(cancelled)
    expect(state.error).toBe('')
    expect(state.busy).toBe(false)
  })

  it('keeps an unconfirmed stop actionable when the cancel request fails', async () => {
    let finish!: (value: AnalysisRun) => void
    vi.mocked(streamQuestion).mockImplementationOnce((_id, _question, receive) => {
      receive({ type: 'run_started', run_id: run.id, run: { ...run, status: 'running' } })
      return new Promise((resolve) => {
        finish = resolve
      })
    })
    vi.mocked(cancelRun).mockRejectedValueOnce(new Error('应用数据库暂不可用'))
    const state = useAnalysisStore()
    const pending = state.submit('订单数')
    await vi.waitFor(() => expect(state.selectedRun?.status).toBe('running'))
    await state.stop()
    expect(state.sending).toBe(true)
    expect(state.selectedRun?.status).toBe('running')
    expect(state.stopping).toBe(false)
    expect(state.error).toContain('应用数据库')
    finish(run)
    await pending
  })
})

it('uses an explicit older result as the next context and advances after success', async () => {
  setActivePinia(createPinia())
  const first: AnalysisRun = { ...run, id: 'first', draft: { action: 'query', sql: 'SELECT 1' } }
  const latest: AnalysisRun = { ...first, id: 'latest', question: '最近7天' }
  const state = useAnalysisStore()
  state.conversationId = conversation.id
  state.runs = [first, latest]
  state.selectedRun = first
  expect(state.continuation?.id).toBe(latest.id)
  expect(state.followUpFrom(first)).toBe(true)
  vi.mocked(streamQuestion).mockResolvedValue({ ...first, id: 'branch', question: '按品类' })
  await state.submit('按品类')
  expect(streamQuestion).toHaveBeenLastCalledWith(
    conversation.id,
    '按品类',
    expect.any(Function),
    expect.any(AbortSignal),
    first.id,
  )
  expect(state.continuation?.id).toBe('branch')
})

it('keeps progress and cancellation on the active run while viewing an older result', async () => {
  setActivePinia(createPinia())
  const state = useAnalysisStore()
  state.conversationId = conversation.id
  state.runs = [{ ...run, id: 'old' }]
  state.selectedRun = state.runs[0]!
  let finish!: (value: AnalysisRun) => void
  vi.mocked(streamQuestion).mockImplementationOnce((_id, _question, receive) => {
    receive({
      type: 'run_started',
      run_id: run.id,
      run: {
        ...run,
        status: 'running',
        result: null,
        steps: [{ node: 'execute_query', status: 'running', attempt: 1, elapsed_ms: 0 }],
      },
    })
    return new Promise((resolve) => {
      finish = resolve
    })
  })
  const pending = state.submit('订单数')
  await vi.waitFor(() => expect(state.sending).toBe(true))
  state.selectedRun = state.runs[0]!
  expect(state.progress).toContain('执行只读查询')
  vi.mocked(cancelRun).mockImplementationOnce(async () => {
    const stopped = { ...run, status: 'cancelled' as const }
    finish(stopped)
    return stopped
  })
  await state.stop()
  await pending
  expect(cancelRun).toHaveBeenCalledWith(run.id)
  expect(state.selectedRun.id).toBe('old')
  expect(state.runs[1]?.status).toBe('cancelled')
})

it('deletes only the requested conversation and clears an active deleted conversation', async () => {
  setActivePinia(createPinia())
  vi.mocked(deleteConversation).mockResolvedValue(undefined)
  const state = useAnalysisStore()
  state.conversations = [conversation, { ...conversation, id: 'other' }]
  state.conversationId = conversation.id
  state.runs = [run]
  state.selectedRun = run
  expect(await state.removeConversation('other')).toBe(true)
  expect(state.selectedRun).toEqual(run)
  expect(await state.removeConversation(conversation.id)).toBe(true)
  expect(state.conversations).toEqual([])
  expect(state.conversationId).toBeNull()
  expect(state.selectedRun).toBeNull()
})

it('retains history after a delete failure and blocks deletion during analysis', async () => {
  setActivePinia(createPinia())
  const state = useAnalysisStore()
  state.conversations = [conversation]
  vi.mocked(deleteConversation).mockRejectedValueOnce(new Error('删除失败'))
  expect(await state.removeConversation(conversation.id)).toBe(false)
  expect(state.conversations).toHaveLength(1)
  expect(state.error).toBe('删除失败')
  state.sending = true
  expect(await state.removeConversation(conversation.id)).toBe(false)
  expect(deleteConversation).toHaveBeenCalledTimes(1)
})

it('receives chart and summary before the saved terminal event and restores them from history', async () => {
  setActivePinia(createPinia())
  const chart = {
    title: '销售额',
    type: 'bar' as const,
    x_column: 0,
    y_columns: [1],
    supported_types: ['bar' as const],
  }
  const summary = { text: '查询返回12行。', limitations: ['仅已返回数据。'] }
  let finish!: (value: AnalysisRun) => void
  vi.mocked(createConversation).mockResolvedValue(conversation)
  vi.mocked(streamQuestion).mockImplementation((_id, _question, receive) => {
    receive({ type: 'run_started', run_id: run.id, run: { ...run, status: 'running' } })
    receive({ type: 'chart', run_id: run.id, chart, chart_message: '结果已截断。' })
    receive({ type: 'summary', run_id: run.id, summary, summary_prompt_version: 'summary-v1' })
    return new Promise((resolve) => {
      finish = resolve
    })
  })
  const state = useAnalysisStore()
  const pending = state.submit('销售额')
  await vi.waitFor(() => expect(state.selectedRun?.summary).toEqual(summary))
  expect(state.selectedRun?.chart).toEqual(chart)
  expect(state.selectedRun?.status).toBe('running')
  const saved = { ...run, chart, summary }
  finish(saved)
  await pending
  vi.mocked(getConversation).mockResolvedValue({ ...conversation, runs: [saved] })
  await state.selectConversation(conversation.id)
  expect(state.selectedRun?.summary).toEqual(summary)
  expect(state.selectedRun?.chart).toEqual(chart)
})
