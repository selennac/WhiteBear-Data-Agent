import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import {
  createConversation,
  getConversation,
  getConversations,
  sendQuestion,
} from '../services/api'
import type { AnalysisRun, ConversationSummary } from '../types/api'

export const useAnalysisStore = defineStore('analysis', () => {
  const conversations = ref<ConversationSummary[]>([])
  const conversationId = ref<string | null>(null)
  const runs = ref<AnalysisRun[]>([])
  const selectedRun = ref<AnalysisRun | null>(null)
  const loading = ref(false)
  const sending = ref(false)
  const hasMore = ref(false)
  const error = ref('')
  const busy = computed(() => loading.value || sending.value)

  async function loadHistory(more = false) {
    if (busy.value) return
    loading.value = true
    error.value = ''
    try {
      const page = await getConversations(more ? conversations.value.length : 0)
      conversations.value = more ? [...conversations.value, ...page] : page
      hasMore.value = page.length === 50
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '无法读取历史记录'
    } finally {
      loading.value = false
    }
  }

  async function selectConversation(id: string) {
    if (busy.value) return
    loading.value = true
    error.value = ''
    try {
      const detail = await getConversation(id)
      conversationId.value = id
      runs.value = detail.runs
      selectedRun.value = detail.runs.at(-1) ?? null
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '无法读取分析记录'
    } finally {
      loading.value = false
    }
  }

  function newConversation() {
    if (busy.value) return
    conversationId.value = null
    runs.value = []
    selectedRun.value = null
    error.value = ''
  }

  async function submit(question: string) {
    if (busy.value || !question.trim()) return
    sending.value = true
    error.value = ''
    try {
      if (!conversationId.value) {
        const conversation = await createConversation()
        conversationId.value = conversation.id
        conversations.value.unshift(conversation)
      }
      const result = await sendQuestion(conversationId.value, question.trim())
      runs.value.push(result)
      selectedRun.value = result
      const conversation = conversations.value.find((item) => item.id === conversationId.value)
      if (conversation?.title === '新建分析') conversation.title = question.trim().slice(0, 100)
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '分析未能完成，请重试'
    } finally {
      sending.value = false
    }
  }

  return {
    conversations,
    conversationId,
    runs,
    selectedRun,
    loading,
    sending,
    busy,
    hasMore,
    error,
    loadHistory,
    selectConversation,
    newConversation,
    submit,
  }
})
