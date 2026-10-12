import { readAnalysisStream } from './stream'
import type {
  AnalysisEvent,
  AnalysisRun,
  ConversationDetail,
  ConversationSummary,
  DatasourceSchema,
  DatasourceSummary,
  HealthResponse,
  MetadataPatch,
} from '../types/api'

async function request<T>(path: string, options: RequestInit = {}, timeoutMs = 20000): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    signal: options.signal ?? AbortSignal.timeout(timeoutMs),
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
  })
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null)
    const detail =
      payload &&
      typeof payload === 'object' &&
      'detail' in payload &&
      typeof payload.detail === 'string'
        ? payload.detail
        : `请求失败（HTTP ${response.status}）`
    throw new Error(detail)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const getDatasources = () => request<DatasourceSummary[]>('/datasources')
export const getDatasourceSchema = () => request<DatasourceSchema>('/datasources/business/schema')
export const syncDatasource = () =>
  request<DatasourceSchema>('/datasources/business/sync', { method: 'POST' })
export const patchMetadata = (patch: MetadataPatch) =>
  request<DatasourceSchema>('/datasources/business/metadata', {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })

export const getConversations = (offset = 0) =>
  request<ConversationSummary[]>(`/conversations?offset=${offset}`)
export const createConversation = (signal?: AbortSignal) =>
  request<ConversationSummary>('/conversations', { method: 'POST', body: '{}', signal })
export const getConversation = (id: string) => request<ConversationDetail>(`/conversations/${id}`)
export const deleteConversation = (id: string) =>
  request<void>(`/conversations/${id}`, { method: 'DELETE' })
export const sendQuestion = (id: string, question: string, contextRunId?: string) =>
  request<AnalysisRun>(
    `/conversations/${id}/messages`,
    { method: 'POST', body: JSON.stringify({ question, context_run_id: contextRunId }) },
    300000,
  )

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch('/api/v1/health', {
    signal: AbortSignal.timeout(5000),
    headers: { Accept: 'application/json' },
  })

  if (!response.ok) {
    throw new Error(`健康检查失败（HTTP ${response.status}）`)
  }

  const payload: unknown = await response.json()
  if (
    typeof payload !== 'object' ||
    payload === null ||
    !('status' in payload) ||
    payload.status !== 'ok' ||
    !('app_name' in payload) ||
    typeof payload.app_name !== 'string' ||
    !('version' in payload) ||
    typeof payload.version !== 'string'
  ) {
    throw new Error('健康检查返回格式不正确')
  }

  return { status: payload.status, app_name: payload.app_name, version: payload.version }
}

export const cancelRun = (id: string) =>
  request<AnalysisRun>('/runs/' + id + '/cancel', { method: 'POST' })

export async function streamQuestion(
  id: string,
  question: string,
  onEvent: (event: AnalysisEvent) => void,
  signal: AbortSignal,
  contextRunId?: string,
): Promise<AnalysisRun> {
  const response = await fetch('/api/v1/conversations/' + id + '/messages/stream', {
    method: 'POST',
    headers: { Accept: 'text/event-stream', 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, context_run_id: contextRunId }),
    signal: AbortSignal.any([signal, AbortSignal.timeout(300000)]),
  })
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null)
    const detail =
      payload &&
      typeof payload === 'object' &&
      'detail' in payload &&
      typeof payload.detail === 'string'
        ? payload.detail
        : '请求失败（HTTP ' + response.status + '）'
    throw new Error(detail)
  }
  return readAnalysisStream(response, onEvent)
}
