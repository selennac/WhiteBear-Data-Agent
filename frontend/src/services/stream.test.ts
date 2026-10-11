import { describe, expect, it } from 'vitest'

import type { AnalysisEvent, AnalysisRun } from '../types/api'
import { readAnalysisStream } from './stream'

const run: AnalysisRun = {
  id: 'run-1',
  conversation_id: 'conversation-1',
  question: '订单数',
  status: 'running',
  created_at: '2026-10-11T12:00:00+08:00',
  reference_time: '2026-10-11T12:00:00+08:00',
}
const started: AnalysisEvent = { type: 'run_started', run_id: run.id, run }
const completed: AnalysisEvent = {
  type: 'run_completed',
  run_id: run.id,
  run: { ...run, status: 'succeeded' },
}
function frame(event: AnalysisEvent) {
  return 'event: ' + event.type + '\r\ndata: ' + JSON.stringify(event) + '\r\n\r\n'
}
function response(source: string, split = 3) {
  const bytes = new TextEncoder().encode(source)
  return new Response(
    new ReadableStream({
      start(controller) {
        for (let i = 0; i < bytes.length; i += split) controller.enqueue(bytes.slice(i, i + split))
        controller.close()
      },
    }),
    { headers: { 'Content-Type': 'text/event-stream; charset=utf-8' } },
  )
}

describe('analysis SSE reader', () => {
  it('handles fragmented Chinese UTF-8, CRLF, comments and multiple events', async () => {
    const events: AnalysisEvent[] = []
    const result = await readAnalysisStream(
      response(': heartbeat\r\n\r\n' + frame(started) + frame(completed), 1),
      (event) => events.push(event),
    )
    expect(events.map((event) => event.type)).toEqual(['run_started', 'run_completed'])
    expect(events[0]?.run?.question).toBe('订单数')
    expect(result.status).toBe('succeeded')
  })

  it('requires a persisted terminal event', async () => {
    await expect(readAnalysisStream(response(frame(started)), () => undefined)).rejects.toThrow(
      '连接已中断',
    )
  })

  it('rejects an event for a different run', async () => {
    await expect(
      readAnalysisStream(
        response(frame(started) + frame({ ...completed, run_id: 'other' })),
        () => undefined,
      ),
    ).rejects.toThrow()
  })

  it('reports storage failure without presenting success', async () => {
    const failure: AnalysisEvent = {
      type: 'stream_error',
      run_id: run.id,
      error_message: '状态未能保存',
    }
    await expect(
      readAnalysisStream(response(frame(started) + frame(failure)), () => undefined),
    ).rejects.toThrow('状态未能保存')
  })

  it('accepts cancellation as a terminal state', async () => {
    const event: AnalysisEvent = { ...completed, run: { ...run, status: 'cancelled' } }
    const result = await readAnalysisStream(
      response(frame(started) + frame(event)),
      () => undefined,
    )
    expect(result.status).toBe('cancelled')
  })
})
