<script setup lang="ts">
import type { AnalysisRun } from '../types/api'
import { metricLabels, timeRangeLabel } from '../utils/analysis'
defineProps<{ draft?: AnalysisRun['draft'] }>()
</script>

<template>
  <div v-if="draft" class="condition-chips" aria-label="继承条件">
    <span v-if="draft.time_range" :title="draft.time_range">{{
      timeRangeLabel(draft.time_range)
    }}</span>
    <span v-for="metric in draft.metrics" :key="metric">{{ metricLabels[metric] || metric }}</span>
    <span v-if="draft.group_by?.length" :title="draft.group_by.join('、')">{{
      draft.group_by.join('、')
    }}</span>
    <span v-if="draft.filters?.length" :title="draft.filters.join('；')"
      >{{ draft.filters.length }} 项筛选</span
    >
  </div>
</template>

<style scoped>
.condition-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
}
.condition-chips span {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 4px 8px;
  border-radius: 6px;
  background: var(--color-background);
  color: var(--color-muted);
  font-size: 12px;
}
</style>
