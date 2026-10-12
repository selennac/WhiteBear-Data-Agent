import type { AnalysisEvent, AnalysisRun } from '../types/api'

const eventTypes = new Set([
  'run_started',
  'node_status',
  'sql',
  'result',
  'chart',
  'summary',
  'run_completed',
  'stream_error',
])

function parseEvent(frame: string): AnalysisEvent | null {
  const lines = frame.split(/\r\n|\r|\n/)
  const data = lines
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).replace(/^ /, ''))
    .join('\n')
  if (!data) return null
  const value: unknown = JSON.parse(data)
  if (
    !value ||
    typeof value !== 'object' ||
    !('type' in value) ||
    typeof value.type !== 'string' ||
    !eventTypes.has(value.type) ||
    !('run_id' in value) ||
    typeof value.run_id !== 'string'
  ) {
    throw new Error('分析进度格式不正确，请刷新历史记录。')
  }
  const event = value as AnalysisEvent
  const name = lines
    .find((line) => line.startsWith('event:'))
    ?.slice(6)
    .trim()
  if (name && name !== event.type) throw new Error('分析进度格式不正确，请刷新历史记录。')
  if (
    (event.type === 'run_started' || event.type === 'run_completed') &&
    (!event.run || event.run.id !== event.run_id)
  ) {
    throw new Error('分析记录格式不正确，请刷新历史记录。')
  }
  if (event.type === 'run_completed' && event.run?.status === 'running') {
    throw new Error('分析尚未完成，请刷新历史记录。')
  }
  return event
}

export async function readAnalysisStream(
  response: Response,
  onEvent: (event: AnalysisEvent) => void,
): Promise<AnalysisRun> {
  if (!response.headers.get('Content-Type')?.includes('text/event-stream') || !response.body) {
    throw new Error('未收到分析进度，请刷新页面后重试。')
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let runId: string | null = null
  try {
    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })
      let boundary: RegExpExecArray | null
      while ((boundary = /\r\n\r\n|\n\n|\r\r/.exec(buffer))) {
        const frame = buffer.slice(0, boundary.index)
        buffer = buffer.slice(boundary.index + boundary[0].length)
        const event = parseEvent(frame)
        if (!event) continue
        if (event.type === 'run_started' && runId === null) runId = event.run_id
        if (!runId || event.run_id !== runId) {
          throw new Error('分析进度与当前运行不一致，请刷新历史记录。')
        }
        if (event.type === 'stream_error') {
          throw new Error(event.error_message || '分析状态未能保存，请刷新历史记录。')
        }
        onEvent(event)
        if (event.type === 'run_completed' && event.run) return event.run
      }
      if (buffer.length > 4 * 1024 * 1024) {
        throw new Error('分析进度超过大小限制，请缩小查询范围。')
      }
      if (done) throw new Error('分析连接已中断，正在确认运行状态。')
    }
  } finally {
    await reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
}
