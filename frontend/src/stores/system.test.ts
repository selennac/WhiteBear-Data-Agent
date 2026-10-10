import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getHealth } from '../services/api'
import { useSystemStore } from './system'

vi.mock('../services/api', () => ({ getHealth: vi.fn() }))

describe('backend connection status', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(getHealth).mockReset()
  })

  it('recovers from a failed connection and clears the previous error', async () => {
    const system = useSystemStore()
    vi.mocked(getHealth).mockRejectedValueOnce(new Error('连接失败'))
    await system.checkHealth()
    expect(system.status).toBe('unavailable')
    expect(system.error).toBe('连接失败')

    vi.mocked(getHealth).mockResolvedValueOnce({
      status: 'ok',
      app_name: 'WhiteBearDataAgent',
      version: '0.1.0',
    })
    await system.checkHealth()
    expect(system.status).toBe('connected')
    expect(system.version).toBe('0.1.0')
    expect(system.error).toBe('')
  })

  it('does not start duplicate requests while a check is pending', async () => {
    let resolveHealth!: (value: Awaited<ReturnType<typeof getHealth>>) => void
    vi.mocked(getHealth).mockReturnValueOnce(
      new Promise((resolve) => {
        resolveHealth = resolve
      }),
    )
    const system = useSystemStore()
    const pending = system.checkHealth()
    await system.checkHealth()
    expect(getHealth).toHaveBeenCalledTimes(1)
    resolveHealth({ status: 'ok', app_name: 'WhiteBearDataAgent', version: '0.1.0' })
    await pending
    expect(system.status).toBe('connected')
  })
})
