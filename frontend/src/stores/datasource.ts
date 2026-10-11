import { defineStore } from 'pinia'
import { ref } from 'vue'

import { getDatasources, getDatasourceSchema, patchMetadata, syncDatasource } from '../services/api'
import type { DatasourceSchema, DatasourceSummary, MetadataPatch } from '../types/api'

export const useDatasourceStore = defineStore('datasource', () => {
  const sources = ref<DatasourceSummary[]>([])
  const schema = ref<DatasourceSchema | null>(null)
  const loading = ref(false)
  const error = ref('')
  const selectedTable = ref('customers')

  async function load(operation: 'read' | 'sync' | 'patch' = 'read', patch?: MetadataPatch) {
    if (loading.value) return
    loading.value = true
    error.value = ''
    try {
      sources.value = await getDatasources()
      if (!sources.value.some((source) => source.configured)) {
        schema.value = null
        return
      }
      const result =
        operation === 'patch' && patch
          ? await patchMetadata(patch)
          : operation === 'sync'
            ? await syncDatasource()
            : await getDatasourceSchema()
      schema.value = result
      if (!result.tables.some((table) => table.name === selectedTable.value)) {
        selectedTable.value = result.tables[0]?.name || ''
      }
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '暂时无法读取数据源'
    } finally {
      loading.value = false
    }
  }

  return { sources, schema, loading, error, selectedTable, load }
})
