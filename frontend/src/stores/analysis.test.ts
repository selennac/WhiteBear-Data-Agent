import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  createConversation,
  getConversation,
  getConversations,
  sendQuestion,
} from '../services/api'
import type { AnalysisRun, ConversationSummary } from '../types/api'
import { useAnalysisStore } from './analysis'

vi.mock('../services/api', () => ({
  createConversation: vi.fn(),
  getConversation: vi.fn(),
  getConversations: vi.fn(),
  sendQuestion: vi.fn(),
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

describe('single-question analysis state', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    setActivePinia(createPinia())
    vi.mocked(createConversation).mockResolvedValue({ ...conversation })
    vi.mocked(sendQuestion).mockResolvedValue(run)
  })

  it('creates one conversation and preserves returned results', async () => {
    const state = useAnalysisStore()
    await state.submit(' 订单数 ')
    await state.submit('销售额')
    expect(createConversation).toHaveBeenCalledTimes(1)
    expect(sendQuestion).toHaveBeenNthCalledWith(1, conversation.id, '订单数')
    expect(state.selectedRun).toEqual(run)
    expect(state.runs).toHaveLength(2)
    expect(state.conversations[0]?.title).toBe('订单数')
  })

  it('does not duplicate submissions or switch history while running', async () => {
    let finish!: (value: AnalysisRun) => void
    vi.mocked(sendQuestion).mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve
        }),
    )
    const state = useAnalysisStore()
    const pending = state.submit('订单数')
    await vi.waitFor(() => expect(sendQuestion).toHaveBeenCalledOnce())
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
    vi.mocked(sendQuestion).mockRejectedValueOnce(new Error('模型未配置'))
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
})
