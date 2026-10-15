<script setup lang="ts">
import {
  ArrowDown,
  ArrowUp,
  ArrowUpRight,
  BarChart3,
  Menu,
  MessageSquare,
  X,
} from 'lucide-vue-next'
import {
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogOverlay,
  AlertDialogPortal,
  AlertDialogRoot,
  AlertDialogTitle,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogOverlay,
  DialogPortal,
  DialogRoot,
  DialogTitle,
} from 'reka-ui'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AnalysisConditions from '../components/AnalysisConditions.vue'
import AnalysisResultPanel from '../components/AnalysisResultPanel.vue'
import AnalysisSidebar from '../components/AnalysisSidebar.vue'
import BaseButton from '../components/ui/BaseButton.vue'
import { useAnalysisStore } from '../stores/analysis'
import type { AnalysisRun, ConversationSummary } from '../types/api'
import { canContinue, statusLabels } from '../utils/analysis'

const analysis = useAnalysisStore()
const question = ref('')
const questionInput = ref<HTMLTextAreaElement | null>(null)
const messages = ref<HTMLElement | null>(null)
const layout = ref<HTMLElement | null>(null)
const followingLatest = ref(true)
const expandedSummaries = ref<Set<string>>(new Set())
const resultOpen = ref(false)
const historyOpen = ref(false)
const desktopQuery = window.matchMedia('(min-width: 1280px)')
const mobileQuery = window.matchMedia('(max-width: 640px)')
const isDesktop = ref(desktopQuery.matches)
const isMobile = ref(mobileQuery.matches)
const deleteTarget = ref<ConversationSummary | null>(null)
const deleteOpen = ref(false)
let deleteTrigger: HTMLElement | null = null
const examples = [
  '最近 30 天的实付销售额和支付订单数',
  '最近 30 天每天的销售额趋势',
  '最近 30 天销售额最高的五个商品',
]
const continuation = computed(() => analysis.continuation)
const run = computed(() => analysis.selectedRun)
const conversationTitle = computed(
  () =>
    analysis.conversations.find((item) => item.id === analysis.conversationId)?.title || '新建分析',
)
const selectedTurn = computed(() =>
  Math.max(1, analysis.runs.findIndex((item) => item.id === run.value?.id) + 1),
)
const continuationTurn = computed(
  () => analysis.runs.findIndex((item) => item.id === continuation.value?.id) + 1,
)
const suggestions = computed(() => {
  if (!continuation.value || continuation.value.status === 'clarification_required') return []
  const group = continuation.value.draft?.group_by?.join(' ') || ''
  return [
    group.includes('品类') || group.includes('categor') ? '按商品拆分' : '按品类拆分',
    '改成最近 7 天',
    '按天查看趋势',
  ]
})
function resize() {
  isDesktop.value = desktopQuery.matches
  isMobile.value = mobileQuery.matches
  if (isDesktop.value) resultOpen.value = false
  if (!isMobile.value) historyOpen.value = false
}
onMounted(() => {
  void analysis.loadHistory()
  desktopQuery.addEventListener('change', resize)
  mobileQuery.addEventListener('change', resize)
})
onBeforeUnmount(() => {
  analysis.disconnect()
  desktopQuery.removeEventListener('change', resize)
  mobileQuery.removeEventListener('change', resize)
})
function trackScroll() {
  const element = messages.value
  if (element)
    followingLatest.value = element.scrollHeight - element.scrollTop - element.clientHeight < 100
}
async function scrollLatest() {
  await nextTick()
  if (messages.value) messages.value.scrollTop = messages.value.scrollHeight
  followingLatest.value = true
}
watch(
  () => analysis.conversationId,
  () => void scrollLatest(),
)
watch(
  () => analysis.runs.length,
  () => {
    if (followingLatest.value || analysis.sending) void scrollLatest()
  },
)
watch(
  () => [analysis.runs.at(-1)?.status, analysis.runs.at(-1)?.summary, analysis.progress],
  () => {
    if (followingLatest.value) void scrollLatest()
  },
)
async function submit() {
  const submitted = question.value.trim()
  if (!submitted || analysis.busy) return
  question.value = ''
  followingLatest.value = true
  await analysis.submit(submitted)
  if (analysis.error && !question.value.trim()) question.value = submitted
  await nextTick()
  questionInput.value?.focus()
}
function keydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
    event.preventDefault()
    void submit()
  }
}
function fillQuestion(value: string) {
  question.value = value
  questionInput.value?.focus()
}
function toggleSummary(id: string) {
  if (expandedSummaries.value.has(id)) expandedSummaries.value.delete(id)
  else expandedSummaries.value.add(id)
}
function viewResult(item: AnalysisRun) {
  analysis.selectedRun = item
  if (!isDesktop.value) resultOpen.value = true
}
async function continueFrom(item: AnalysisRun) {
  if (!analysis.followUpFrom(item)) return
  resultOpen.value = false
  await nextTick()
  questionInput.value?.focus()
}
function newAnalysis() {
  analysis.newConversation()
  question.value = ''
  historyOpen.value = false
  resultOpen.value = false
  questionInput.value?.focus()
}
async function selectConversation(id: string) {
  await analysis.selectConversation(id)
  if (!analysis.error) {
    question.value = ''
    historyOpen.value = false
    resultOpen.value = false
  }
}
function requestDelete(conversation: ConversationSummary, trigger: HTMLElement) {
  deleteTarget.value = conversation
  deleteTrigger = trigger
  deleteOpen.value = true
}
async function confirmDelete() {
  if (!deleteTarget.value) return
  const current = analysis.conversationId === deleteTarget.value.id
  if (await analysis.removeConversation(deleteTarget.value.id)) {
    deleteOpen.value = false
    if (current) {
      question.value = ''
      resultOpen.value = false
      historyOpen.value = false
    }
  }
}
function restoreDeleteFocus(event: Event) {
  event.preventDefault()
  if (deleteTrigger?.isConnected) deleteTrigger.focus()
  else {
    const focusTarget =
      layout.value?.querySelector<HTMLButtonElement>('.new-analysis') ?? questionInput.value
    focusTarget?.focus()
  }
}
</script>

<template>
  <div ref="layout" class="analysis-layout" :class="{ 'with-result': isDesktop }">
    <AnalysisSidebar
      v-if="!isMobile"
      class="sidebar"
      @new="newAnalysis"
      @select="selectConversation"
      @remove="requestDelete"
    />
    <main class="conversation">
      <header class="conversation-heading">
        <button
          v-if="isMobile"
          type="button"
          class="icon-button"
          aria-label="打开历史会话"
          @click="historyOpen = true"
        >
          <Menu :size="18" aria-hidden="true" />
        </button>
        <div>
          <h1>{{ conversationTitle }}</h1>
          <span
            >电商业务数据<span v-if="analysis.runs.length">
              · {{ analysis.runs.length }} 轮分析</span
            ></span
          >
        </div>
        <button
          v-if="!isDesktop && run"
          type="button"
          class="result-toggle"
          @click="resultOpen = true"
        >
          <BarChart3 :size="16" aria-hidden="true" />查看结果
        </button>
      </header>
      <div
        ref="messages"
        class="messages"
        role="region"
        aria-label="分析对话"
        @scroll="trackScroll"
      >
        <section v-if="!analysis.runs.length && !analysis.sending" class="welcome">
          <span class="welcome-icon"><MessageSquare :size="24" aria-hidden="true" /></span>
          <h2>从一个问题开始探索数据</h2>
          <p>查询销售、订单和退款，再继续追问、拆分维度或调整时间范围。</p>
          <div class="examples">
            <button
              v-for="example in examples"
              :key="example"
              type="button"
              :disabled="analysis.busy"
              @click="fillQuestion(example)"
            >
              {{ example }}<ArrowUpRight :size="16" aria-hidden="true" />
            </button>
          </div>
          <small>未指定时间的新问题默认查询最近 30 天。</small>
        </section>
        <article
          v-for="(item, index) in analysis.runs"
          :key="item.id"
          class="turn"
          :class="{ 'viewing-turn': run?.id === item.id }"
          :aria-label="`第 ${index + 1} 轮分析`"
        >
          <div class="user-message">{{ item.question }}</div>
          <div class="assistant-message">
            <div class="turn-meta">
              <span>第 {{ index + 1 }} 轮</span
              ><span class="badge" :class="item.status">{{ statusLabels[item.status] }}</span>
            </div>
            <p v-if="item.status === 'clarification_required'" class="clarification">
              {{ item.draft?.clarification
              }}<span v-if="continuation?.id === item.id" class="muted"
                >直接在输入框回答即可继续。</span
              >
            </p>
            <p v-else-if="item.status === 'cancelled'" class="muted">
              分析已停止，可以提交新问题。
            </p>
            <p v-else-if="item.error_message" class="error" role="alert">
              {{ item.error_message }}
            </p>
            <section
              v-if="item.summary || item.summary_error"
              class="result-summary"
              aria-label="结果总结"
            >
              <p
                v-if="item.summary"
                class="summary-text"
                :class="{
                  'compact-summary':
                    item.summary.text.length > 300 && !expandedSummaries.has(item.id),
                }"
              >
                {{ item.summary.text }}
              </p>
              <button
                v-if="item.summary && item.summary.text.length > 300"
                type="button"
                class="summary-toggle"
                :aria-expanded="expandedSummaries.has(item.id)"
                @click="toggleSummary(item.id)"
              >
                {{ expandedSummaries.has(item.id) ? '收起总结' : '查看完整总结' }}
              </button>
              <p v-if="!item.summary" class="muted">{{ item.summary_error }}</p>
            </section>
            <p v-else-if="item.result" class="muted">
              已返回 {{ item.result.row_count }} 行结果{{
                item.status === 'running' ? '，正在准备图表与总结…' : '。'
              }}
            </p>
            <p v-else-if="item.status === 'running'" class="progress" role="status">
              {{
                analysis.activeRunId === item.id
                  ? analysis.progress
                  : '该分析尚未完成，可刷新会话查看状态或停止后重新提交。'
              }}
            </p>
            <AnalysisConditions :draft="item.draft" />
            <div class="turn-actions">
              <button
                type="button"
                class="view-result"
                :aria-pressed="run?.id === item.id"
                @click="viewResult(item)"
              >
                <BarChart3 :size="15" aria-hidden="true" />{{
                  run?.id === item.id && isDesktop ? '正在查看' : '查看结果'
                }}</button
              ><button
                v-if="canContinue(item) && continuation?.id !== item.id"
                type="button"
                :disabled="analysis.busy"
                @click="continueFrom(item)"
              >
                {{ item.status === 'clarification_required' ? '回答此澄清' : '从此结果追问'
                }}<ArrowUpRight :size="14" aria-hidden="true" /></button
              ><button
                v-if="item.status === 'running' && !analysis.sending"
                type="button"
                :disabled="analysis.busy"
                @click="analysis.stop(item.id)"
              >
                停止此运行
              </button>
            </div>
          </div>
        </article>
        <div v-if="analysis.pendingQuestion" class="turn pending">
          <div class="user-message">{{ analysis.pendingQuestion }}</div>
          <p class="progress" role="status">正在准备分析…</p>
        </div>
        <p v-if="analysis.loading" class="muted" role="status">正在读取历史记录…</p>
      </div>
      <button
        v-if="!followingLatest && analysis.runs.length"
        type="button"
        class="latest-button"
        @click="scrollLatest"
      >
        <ArrowDown :size="14" aria-hidden="true" />回到最新
      </button>
      <section class="composer">
        <div v-if="continuation" class="continuation" aria-label="追问来源" role="status">
          <span
            >{{ continuation.status === 'clarification_required' ? '待补充条件' : '追问基于' }} · 第
            {{ continuationTurn }} 轮</span
          ><strong :title="continuation.draft?.resolved_question || continuation.question">{{
            continuation.draft?.resolved_question || continuation.question
          }}</strong
          ><AnalysisConditions :draft="continuation.draft" />
        </div>
        <div v-if="suggestions.length" class="suggestions">
          <button
            v-for="suggestion in suggestions"
            :key="suggestion"
            type="button"
            @click="fillQuestion(suggestion)"
          >
            {{ suggestion }}
          </button>
        </div>
        <p v-if="analysis.error" class="error" role="alert">{{ analysis.error }}</p>
        <form @submit.prevent="submit">
          <label for="analysis-question" class="sr-only">分析问题</label
          ><textarea
            id="analysis-question"
            ref="questionInput"
            v-model="question"
            maxlength="2000"
            rows="2"
            :disabled="analysis.loading || !!analysis.deletingId"
            :placeholder="
              continuation?.status === 'clarification_required'
                ? '直接回答澄清问题，例如：用客户区域'
                : continuation
                  ? '继续追问，或修改当前分析条件…'
                  : '例如：最近 30 天的实付销售额和支付订单数'
            "
            @keydown="keydown"
          />
          <div class="submit-row">
            <span class="muted"
              >Enter 发送 · Shift+Enter 换行<span v-if="question.length > 1800">
                · {{ question.length }}/2000</span
              ></span
            ><BaseButton
              v-if="analysis.sending || analysis.stopping"
              variant="secondary"
              :disabled="analysis.stopping"
              @click="analysis.stop()"
              >{{ analysis.stopping ? '正在停止…' : '停止分析' }}</BaseButton
            ><BaseButton v-else type="submit" :disabled="analysis.busy || !question.trim()"
              >{{ continuation?.status === 'clarification_required' ? '补充并继续' : '发送'
              }}<ArrowUp :size="16" aria-hidden="true"
            /></BaseButton>
          </div>
        </form>
      </section>
    </main>
    <aside v-if="isDesktop" class="result-area">
      <AnalysisResultPanel
        v-if="run"
        :run="run"
        :turn="selectedTurn"
        :context-run-id="continuation?.id"
        :busy="analysis.busy"
        @continue="continueFrom"
      />
      <div v-else class="result-empty">
        <BarChart3 :size="28" aria-hidden="true" />
        <h2>分析结果将在这里展示</h2>
        <p>查看图表、表格和分析口径，随时从某一轮结果继续追问。</p>
      </div>
    </aside>
    <DialogRoot v-model:open="resultOpen"
      ><DialogPortal
        ><DialogOverlay class="workspace-overlay" /><DialogContent
          class="result-drawer"
          @close-auto-focus.prevent="questionInput?.focus()"
          ><div class="drawer-heading">
            <DialogTitle>分析结果</DialogTitle
            ><DialogClose class="icon-button" aria-label="关闭分析结果"
              ><X :size="18" aria-hidden="true"
            /></DialogClose>
          </div>
          <DialogDescription class="sr-only"
            >查看选中分析的图表、表格、SQL 和执行记录。</DialogDescription
          ><AnalysisResultPanel
            v-if="run"
            :run="run"
            :turn="selectedTurn"
            :context-run-id="continuation?.id"
            :busy="analysis.busy"
            @continue="continueFrom" /></DialogContent></DialogPortal
    ></DialogRoot>
    <DialogRoot v-model:open="historyOpen"
      ><DialogPortal
        ><DialogOverlay class="workspace-overlay" /><DialogContent
          class="history-drawer"
          @close-auto-focus.prevent="questionInput?.focus()"
          ><div class="drawer-heading">
            <DialogTitle>历史会话</DialogTitle
            ><DialogClose class="icon-button" aria-label="关闭历史会话"
              ><X :size="18" aria-hidden="true"
            /></DialogClose>
          </div>
          <DialogDescription class="sr-only">新建、选择或删除分析会话。</DialogDescription
          ><AnalysisSidebar
            @new="newAnalysis"
            @select="selectConversation"
            @remove="requestDelete" /></DialogContent></DialogPortal
    ></DialogRoot>
    <AlertDialogRoot v-model:open="deleteOpen"
      ><AlertDialogPortal
        ><AlertDialogOverlay class="workspace-overlay delete-overlay" /><AlertDialogContent
          class="delete-dialog"
          @escape-key-down="analysis.deletingId && $event.preventDefault()"
          @close-auto-focus="restoreDeleteFocus"
          ><AlertDialogTitle class="delete-title">删除会话？</AlertDialogTitle
          ><AlertDialogDescription class="delete-description"
            >「{{
              deleteTarget?.title
            }}」中的问题、查询结果和运行记录会一并删除，无法恢复。</AlertDialogDescription
          >
          <p v-if="analysis.error" class="error" role="alert">{{ analysis.error }}</p>
          <div class="delete-actions">
            <AlertDialogCancel as-child
              ><BaseButton variant="secondary" :disabled="!!analysis.deletingId"
                >取消</BaseButton
              ></AlertDialogCancel
            ><BaseButton
              class="danger-button"
              :disabled="!!analysis.deletingId"
              @click="confirmDelete"
              >{{ analysis.deletingId ? '正在删除…' : '确认删除' }}</BaseButton
            >
          </div></AlertDialogContent
        ></AlertDialogPortal
      ></AlertDialogRoot
    >
  </div>
</template>

<style scoped>
.analysis-layout {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  height: calc(100dvh - var(--workspace-header-height, 85px));
  min-height: 480px;
}
.analysis-layout.with-result {
  grid-template-columns: 220px minmax(320px, 0.9fr) minmax(440px, 1.1fr);
}
.sidebar {
  border-right: 1px solid var(--color-border);
}
.conversation {
  display: flex;
  flex-direction: column;
  position: relative;
  min-width: 0;
  min-height: 0;
}
.conversation-heading {
  display: flex;
  align-items: center;
  gap: 12px;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
}
.conversation-heading > div {
  min-width: 0;
}
h1 {
  font-size: 16px;
  margin: 0 0 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.conversation-heading span {
  color: var(--color-muted);
  font-size: 12px;
}
.result-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  border-radius: 7px;
  padding: 8px;
  font-size: 12px;
  color: var(--color-primary);
}
.messages {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  padding: 24px;
  overscroll-behavior: contain;
}
.welcome {
  max-width: 560px;
  margin: 36px auto;
}
.welcome-icon {
  display: inline-grid;
  place-items: center;
  padding: 12px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  border-radius: 12px;
}
.welcome h2 {
  font-size: 23px;
  margin: 20px 0 12px;
}
.welcome p {
  color: var(--color-muted);
  font-size: 14px;
  line-height: 1.8;
}
.welcome small {
  color: var(--color-muted);
  font-size: 12px;
}
.examples {
  display: grid;
  gap: 10px;
  margin: 24px 0 16px;
}
.examples button {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  border: 1px solid var(--color-border);
  padding: 14px;
  border-radius: 8px;
  background: var(--color-surface);
  color: var(--color-text);
  font-size: 13px;
  text-align: left;
  line-height: 1.6;
}
.examples svg {
  flex-shrink: 0;
  color: var(--color-muted);
}
.turn {
  margin-bottom: 30px;
  overflow-wrap: anywhere;
}
.user-message {
  margin-left: auto;
  max-width: 90%;
  width: fit-content;
  padding: 12px 16px;
  background: #eaf0f9;
  border-radius: 12px 12px 3px 12px;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
}
.assistant-message {
  margin-top: 18px;
  padding-left: 14px;
  border-left: 2px solid var(--color-border);
}
.viewing-turn .assistant-message {
  border-left-color: var(--color-primary);
}
.turn-meta {
  display: flex;
  gap: 10px;
  align-items: center;
  font-size: 12px;
  color: var(--color-muted);
}
.badge {
  border-radius: 20px;
  padding: 3px 8px;
  font-size: 11px;
  background: var(--color-surface);
}
.badge.succeeded {
  color: #047857;
}
.badge.failed {
  color: #b91c1c;
}
.badge.clarification_required {
  color: #92400e;
}
.summary-text {
  font-size: 14px;
  line-height: 1.85;
  white-space: pre-wrap;
  margin: 12px 0;
}
.compact-summary {
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.summary-toggle {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--color-primary);
  font-size: 12px;
  margin: 0 0 12px;
}
.turn-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
.turn-actions button,
.suggestions button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  border-radius: 6px;
  padding: 6px 9px;
  font-size: 12px;
  color: var(--color-muted);
}
.view-result[aria-pressed='true'] {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-soft);
}
.composer {
  padding: 16px 24px 20px;
  border-top: 1px solid var(--color-border);
  background: var(--color-surface);
}
.continuation {
  margin-bottom: 12px;
  min-width: 0;
}
.continuation > span {
  display: block;
  font-size: 11px;
  color: var(--color-primary);
  margin-bottom: 5px;
}
.continuation strong {
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 500;
  margin-bottom: 8px;
}
.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 10px 0;
}
form {
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 12px;
  background: var(--color-background);
  transition: border-color 0.15s ease;
}
form:focus-within {
  border-color: var(--color-primary);
}
textarea {
  display: block;
  width: 100%;
  border: 0;
  resize: none;
  color: var(--color-text);
  background: transparent;
  line-height: 1.7;
  font-size: 14px;
  padding: 0;
  min-height: 50px;
  max-height: 150px;
}
.submit-row {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}
.submit-row .muted {
  font-size: 11px;
}
.submit-row .base-button {
  font-size: 12px;
  min-height: 34px;
  padding: 6px 12px;
}
.muted,
.progress {
  font-size: 13px;
  line-height: 1.8;
  color: var(--color-muted);
}
.progress {
  color: var(--color-primary);
}
.error {
  color: #b91c1c;
  background: #fef2f2;
  border-radius: 8px;
  padding: 12px;
  font-size: 13px;
  line-height: 1.7;
}
.clarification {
  color: #92400e;
  font-size: 14px;
  line-height: 1.8;
}
.clarification .muted {
  display: block;
  margin-top: 6px;
}
.latest-button {
  align-self: center;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--color-border);
  border-radius: 20px;
  background: var(--color-surface);
  color: var(--color-primary);
  padding: 6px 12px;
  font-size: 12px;
  margin: 8px;
}
.result-area {
  border-left: 1px solid var(--color-border);
  min-width: 0;
  min-height: 0;
  background: var(--color-surface);
}
.result-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 36px;
  text-align: center;
  color: var(--color-muted);
}
.result-empty svg {
  color: var(--color-primary);
}
.result-empty h2 {
  font-size: 17px;
  color: var(--color-text);
  margin: 20px 0 8px;
}
.result-empty p {
  max-width: 280px;
  font-size: 13px;
  line-height: 1.8;
}
.icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  background: transparent;
  border-radius: 6px;
  padding: 8px;
  color: var(--color-muted);
}
.workspace-overlay {
  position: fixed;
  inset: 0;
  background: #0f172a66;
  z-index: 30;
}
.result-drawer,
.history-drawer {
  position: fixed;
  top: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  background: var(--color-surface);
  z-index: 31;
}
.result-drawer {
  right: 0;
  width: min(720px, 100%);
}
.history-drawer {
  left: 0;
  width: min(320px, 100%);
}
.drawer-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
}
.drawer-heading h2 {
  margin: 0;
  font-size: 15px;
}
.result-drawer .result-panel,
.history-drawer .history {
  flex: 1;
  min-height: 0;
  height: auto;
}
.delete-overlay {
  z-index: 40;
}
.delete-dialog {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: min(440px, calc(100% - 32px));
  padding: 24px;
  border-radius: 12px;
  background: var(--color-surface);
  z-index: 41;
  box-shadow: 0 12px 48px #0f172a33;
}
.delete-title {
  margin: 0 0 12px;
  font-size: 19px;
}
.delete-description {
  color: var(--color-muted);
  font-size: 14px;
  line-height: 1.8;
  overflow-wrap: anywhere;
}
.delete-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
}
.danger-button {
  background: #b91c1c;
  color: white;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
button {
  cursor: pointer;
}
button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
button:focus-visible {
  outline: 3px solid var(--color-focus);
  outline-offset: 3px;
}
/* 输入框的焦点反馈由外层 form 的 focus-within 边框呈现，避免叠加出双层边框 */
textarea:focus,
textarea:focus-visible {
  outline: none;
}
@media (max-width: 900px) {
  .analysis-layout {
    grid-template-columns: 190px minmax(0, 1fr);
  }
}
@media (max-width: 640px) {
  .analysis-layout {
    grid-template-columns: minmax(0, 1fr);
    min-height: 0;
  }
  .conversation-heading {
    padding: 12px 16px;
  }
  .messages {
    padding: 20px 16px;
  }
  .composer {
    padding: 12px 16px 16px;
  }
  .welcome {
    margin: 20px auto;
  }
  .welcome h2 {
    font-size: 21px;
  }
  textarea {
    font-size: 16px;
  }
  .submit-row .muted {
    font-size: 10px;
  }
}
@media (pointer: coarse) {
  .icon-button,
  .turn-actions button,
  .suggestions button,
  .result-toggle {
    min-height: 44px;
  }
}
</style>
