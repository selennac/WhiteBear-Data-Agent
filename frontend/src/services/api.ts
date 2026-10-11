import type {
  DatasourceSchema,
  DatasourceSummary,
  HealthResponse,
  MetadataPatch,
} from '../types/api'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    signal: AbortSignal.timeout(20000),
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
