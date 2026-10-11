import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getDatasources, getDatasourceSchema, patchMetadata, syncDatasource } from '../services/api'
import type { DatasourceSchema } from '../types/api'
import { useDatasourceStore } from './datasource'

vi.mock('../services/api', () => ({
  getDatasources: vi.fn(),
  getDatasourceSchema: vi.fn(),
  syncDatasource: vi.fn(),
  patchMetadata: vi.fn(),
}))
const schema: DatasourceSchema = {
  datasource_id: 'business',
  schema_name: 'whitebear_business',
  schema_version: 'v1',
  tables: [{ name: 'orders', description: '订单', columns: [], relationships: [] }],
  metrics: { version: '1', default_time_range_days: 30, metrics: [] },
}

describe('data structure state', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    setActivePinia(createPinia())
    vi.mocked(getDatasources).mockResolvedValue([
      { id: 'business', name: '电商业务数据', configured: true, schema_name: 'whitebear_business' },
    ])
  })
  it('shows setup without calling the database when no source is configured', async () => {
    vi.mocked(getDatasources).mockResolvedValue([
      {
        id: 'business',
        name: '电商业务数据',
        configured: false,
        schema_name: 'whitebear_business',
      },
    ])
    const data = useDatasourceStore()
    await data.load()
    expect(data.schema).toBeNull()
    expect(getDatasourceSchema).not.toHaveBeenCalled()
    expect(data.loading).toBe(false)
  })
  it('keeps existing data on errors and recovers when syncing again', async () => {
    vi.mocked(getDatasourceSchema).mockResolvedValue(schema)
    const data = useDatasourceStore()
    await data.load()
    expect(data.selectedTable).toBe('orders')
    vi.mocked(syncDatasource).mockRejectedValueOnce(new Error('数据库不可用'))
    await data.load('sync')
    expect(data.schema).toEqual(schema)
    expect(data.error).toBe('数据库不可用')
    vi.mocked(syncDatasource).mockResolvedValueOnce(schema)
    await data.load('sync')
    expect(data.error).toBe('')
  })
  it('persists edited descriptions and uses the response from the server', async () => {
    vi.mocked(patchMetadata).mockResolvedValue(schema)
    const data = useDatasourceStore()
    const patch = { tables: { orders: '订单' } }
    await data.load('patch', patch)
    expect(patchMetadata).toHaveBeenCalledWith(patch)
    expect(data.schema).toEqual(schema)
  })
})
