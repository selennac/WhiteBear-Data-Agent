import { defineStore } from 'pinia'
import { ref } from 'vue'

import { getHealth } from '../services/api'

export const useSystemStore = defineStore('system', () => {
  const status = ref<'idle' | 'checking' | 'connected' | 'unavailable'>('idle')
  const version = ref('')
  const error = ref('')

  async function checkHealth() {
    if (status.value === 'checking') return

    status.value = 'checking'
    error.value = ''
    version.value = ''
    try {
      const health = await getHealth()
      version.value = health.version
      status.value = 'connected'
    } catch (cause) {
      status.value = 'unavailable'
      error.value = cause instanceof Error ? cause.message : '暂时无法连接后端服务'
    }
  }

  return { status, version, error, checkHealth }
})
