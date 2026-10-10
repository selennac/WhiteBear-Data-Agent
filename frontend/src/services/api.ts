import type { HealthResponse } from '../types/api'

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
