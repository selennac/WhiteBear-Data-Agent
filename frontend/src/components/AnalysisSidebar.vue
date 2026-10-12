<script setup lang="ts">
import { MessageSquare, Plus, RefreshCw, Trash2 } from 'lucide-vue-next'
import { useAnalysisStore } from '../stores/analysis'
import type { ConversationSummary } from '../types/api'
import BaseButton from './ui/BaseButton.vue'
const analysis = useAnalysisStore()
defineEmits<{
  new: []
  select: [id: string]
  remove: [conversation: ConversationSummary, trigger: HTMLElement]
}>()
function date(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    month: 'short',
    day: 'numeric',
  }).format(new Date(value))
}
</script>

<template>
  <aside class="history" aria-label="历史分析">
    <BaseButton class="new-analysis" :disabled="analysis.busy" @click="$emit('new')"
      ><Plus :size="17" aria-hidden="true" />新建分析</BaseButton
    >
    <div class="history-heading">
      <h2>历史会话</h2>
      <button
        type="button"
        class="icon-button"
        aria-label="刷新历史会话"
        :disabled="analysis.busy"
        @click="analysis.loadHistory()"
      >
        <RefreshCw :size="15" aria-hidden="true" />
      </button>
    </div>
    <div class="history-list">
      <p v-if="!analysis.conversations.length" class="empty">开始提问后，会话将保存在这里。</p>
      <div
        v-for="conversation in analysis.conversations"
        :key="conversation.id"
        class="history-row"
        :class="{ selected: analysis.conversationId === conversation.id }"
      >
        <button
          type="button"
          class="history-item"
          :disabled="analysis.busy"
          :aria-pressed="analysis.conversationId === conversation.id"
          :title="conversation.title"
          @click="$emit('select', conversation.id)"
        >
          <MessageSquare :size="16" aria-hidden="true" /><span
            ><strong>{{ conversation.title }}</strong
            ><small>{{ date(conversation.created_at) }}</small></span
          >
        </button>
        <button
          type="button"
          class="icon-button delete-conversation"
          :aria-label="`删除会话：${conversation.title}`"
          :disabled="analysis.busy"
          @click="$emit('remove', conversation, $event.currentTarget as HTMLElement)"
        >
          <Trash2 :size="15" aria-hidden="true" />
        </button>
      </div>
      <BaseButton
        v-if="analysis.hasMore"
        variant="secondary"
        :disabled="analysis.busy"
        @click="analysis.loadHistory(true)"
        >加载更多</BaseButton
      >
    </div>
    <div class="source-info"><span class="source-dot" />电商业务数据</div>
  </aside>
</template>

<style scoped>
.history {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 20px 12px 16px;
  background: var(--color-surface);
}
.new-analysis {
  width: 100%;
}
.history-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 24px 8px 10px;
}
.history-heading h2 {
  font-size: 12px;
  color: var(--color-muted);
  margin: 0;
  font-weight: 500;
}
.history-list {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}
.history-row {
  display: flex;
  align-items: center;
  border-radius: 8px;
  margin-bottom: 5px;
}
.history-row.selected {
  background: var(--color-primary-soft);
}
.history-item {
  display: flex;
  align-items: center;
  gap: 9px;
  flex: 1;
  min-width: 0;
  padding: 10px 8px;
  border: 0;
  background: transparent;
  text-align: left;
  color: var(--color-text);
}
.history-item > svg {
  flex-shrink: 0;
  color: var(--color-muted);
}
.history-item > span {
  min-width: 0;
}
.history-item strong {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 500;
}
.history-item small {
  display: block;
  color: var(--color-muted);
  font-size: 11px;
  margin-top: 4px;
}
.selected .history-item {
  color: var(--color-primary);
}
.icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border: 0;
  background: transparent;
  color: var(--color-muted);
  border-radius: 6px;
}
.delete-conversation {
  margin-right: 4px;
}
.icon-button:hover {
  background: var(--color-background);
  color: var(--color-text);
}
.delete-conversation:hover {
  color: #b91c1c;
}
.empty {
  padding: 12px 8px;
  font-size: 13px;
  color: var(--color-muted);
  line-height: 1.7;
}
.source-info {
  display: flex;
  align-items: center;
  gap: 8px;
  border-top: 1px solid var(--color-border);
  padding: 16px 8px 0;
  margin-top: 16px;
  font-size: 12px;
  color: var(--color-muted);
}
.source-dot {
  width: 7px;
  height: 7px;
  background: var(--color-primary);
  border-radius: 50%;
}
button {
  cursor: pointer;
}
button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
button:focus-visible {
  outline: 3px solid var(--color-focus);
  outline-offset: 2px;
}
@media (pointer: coarse) {
  .icon-button {
    width: 44px;
    height: 44px;
  }
}
</style>
