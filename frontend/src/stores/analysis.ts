import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import {
  cancelRun,
  createConversation,
  getConversation,
  getConversations,
  streamQuestion,
} from '../services/api'
import type { AnalysisEvent, AnalysisRun, ConversationSummary } from '../types/api'

export const useAnalysisStore = defineStore('analysis', () => {
  const conversations = ref<ConversationSummary[]>([])
  const conversationId = ref<string | null>(null)
  const runs = ref<AnalysisRun[]>([])
  const selectedRun = ref<AnalysisRun | null>(null)
  const loading = ref(false)
  const sending = ref(false)
  const stopping = ref(false)
  const hasMore = ref(false)
  const error = ref('')
  const busy = computed(() => loading.value || sending.value || stopping.value)
  let controller: AbortController | null = null
  const activeRunId = ref<string | null>(null)
  const progress = computed(() => {
    if (stopping.value) return '正在停止分析…'
    if (!sending.value) return ''
    const step = activeRunId.value
      ? selectedRun.value?.steps?.find((item) => item.status === 'running')
      : null
    const labels: Record<string, string> = {
      load_context: '正在加载数据结构与业务口径…',
      generate_query: '正在生成查询方案…',
      validate_sql: '正在校验 SQL…',
      execute_query: '正在执行只读查询…',
      build_chart: '正在准备图表…',
      summarize_result: '正在总结查询结果…',
    }
    if (step)
      return (
        (labels[step.node] ?? '正在分析…') +
        (step.attempt > 1 ? '（第 ' + step.attempt + ' 次尝试）' : '')
      )
    return activeRunId.value ? '正在保存分析结果…' : '正在准备分析…'
  })

  function acceptRun(run: AnalysisRun) {
    const index = runs.value.findIndex((item) => item.id === run.id)
    if (index < 0) runs.value.push(run)
    else runs.value[index] = run
    selectedRun.value = run
  }

  function receive(event: AnalysisEvent) {
    if (event.type === 'run_started' && event.run) {
      activeRunId.value = event.run_id
      acceptRun(event.run)
    } else if (event.type === 'run_completed' && event.run) {
      acceptRun(event.run)
    } else {
      const run = runs.value.find((item) => item.id === event.run_id)
      if (!run) return
      if (event.type === 'node_status' && event.step) {
        run.steps ??= []
        const stepUpdate = event.step
        const index = run.steps.findIndex(
          (step) => step.node === stepUpdate.node && step.attempt === stepUpdate.attempt,
        )
        if (index < 0) run.steps.push(stepUpdate)
        else run.steps[index] = stepUpdate
        run.schema_version = event.schema_version || run.schema_version
        run.token_usage = event.token_usage
      } else if (event.type === 'sql') run.draft = event.draft
      else if (event.type === 'result') run.result = event.result
      else if (event.type === 'chart') {
        run.chart = event.chart
        run.chart_message = event.chart_message
      } else if (event.type === 'summary') {
        run.summary = event.summary
        run.summary_error = event.summary_error
        run.summary_prompt_version = event.summary_prompt_version
      }
    }
  }

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
    const requestController = new AbortController()
    controller = requestController
    activeRunId.value = null
    sending.value = true
    error.value = ''
    try {
      if (!conversationId.value) {
        const conversation = await createConversation(requestController.signal)
        conversationId.value = conversation.id
        conversations.value.unshift(conversation)
      }
      if (requestController.signal.aborted) return
      const conversation = conversations.value.find((item) => item.id === conversationId.value)
      if (conversation?.title === '新建分析') conversation.title = question.trim().slice(0, 100)
      const result = await streamQuestion(
        conversationId.value,
        question.trim(),
        receive,
        requestController.signal,
      )
      acceptRun(result)
    } catch (cause) {
      if (activeRunId.value && selectedRun.value?.status === 'running') {
        try {
          acceptRun(await cancelRun(activeRunId.value))
        } catch {
          error.value = '连接已中断，无法确认运行状态，请刷新历史记录。'
        }
      } else if (!requestController.signal.aborted) {
        error.value = cause instanceof Error ? cause.message : '分析未能完成，请重试'
      }
    } finally {
      controller = null
      activeRunId.value = null
      sending.value = false
    }
  }

  async function stop() {
    if (stopping.value) return
    const id =
      activeRunId.value ?? (selectedRun.value?.status === 'running' ? selectedRun.value.id : null)
    const requestController = controller
    stopping.value = true
    error.value = ''
    try {
      if (id) acceptRun(await cancelRun(id))
      requestController?.abort()
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '无法停止分析，请重试'
    } finally {
      stopping.value = false
    }
  }

  function disconnect() {
    controller?.abort()
  }

  return {
    conversations,
    conversationId,
    runs,
    selectedRun,
    loading,
    sending,
    stopping,
    busy,
    hasMore,
    error,
    progress,
    loadHistory,
    selectConversation,
    newConversation,
    submit,
    stop,
    disconnect,
  }
})
