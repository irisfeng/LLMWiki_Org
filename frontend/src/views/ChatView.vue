<template>
  <AppLayout>
    <div class="chat-shell">
      <!-- Header strip -->
      <div class="header-strip">
        <span class="strip-crumb">AI 问答</span>
        <span class="strip-meta">· qwen3.6-plus · 检索范围: 全库</span>
        <div style="flex:1"></div>
        <div class="mode-switch" role="tablist" aria-label="回答模式">
          <button
            v-for="opt in MODE_OPTIONS"
            :key="opt.value"
            :class="['mode-pill', { active: chatMode === opt.value }]"
            :disabled="streaming"
            :title="opt.hint"
            role="tab"
            :aria-selected="chatMode === opt.value"
            @click="setMode(opt.value)"
          >{{ opt.label }}</button>
        </div>
        <button
          v-if="messages.length"
          class="explorer-toggle"
          :class="{ active: explorerVisible }"
          @click="explorerVisible = !explorerVisible"
        >
          <el-icon><Reading /></el-icon>
          <span>引用</span>
        </button>
        <button
          v-if="messages.length"
          class="explorer-toggle"
          @click="copyConversation"
          title="复制整段对话"
        >
          <el-icon><DocumentCopy /></el-icon>
          <span>复制</span>
        </button>
        <button
          class="new-conv-btn"
          :disabled="streaming"
          @click="startNewConversation"
        >
          <el-icon><Plus /></el-icon>
          <span>新对话</span>
        </button>
      </div>

      <div class="chat-body">
        <!-- History sidebar -->
        <aside class="history-sidebar" :class="{ open: sidebarOpen }">
          <div class="history-head">
            <span class="history-label">历史会话</span>
          </div>
          <div v-if="historyLoading" class="history-loading">加载中…</div>
          <div v-else-if="!historyList.length" class="history-empty">暂无历史</div>
          <ul v-else class="session-list">
            <li
              v-for="s in historyList"
              :key="s.id"
              :class="['session-item', { active: s.id === sessionId }]"
              @click="switchToSession(s.id)"
            >
              <div class="session-title">{{ s.title }}</div>
              <div class="session-meta">
                <span>{{ formatTime(s.created_at) }}</span>
                <span class="session-count">{{ s.message_count }} 条</span>
              </div>
              <button
                class="session-delete"
                :disabled="streaming"
                @click="handleDeleteSession(s.id, $event)"
                title="删除会话"
              >
                <el-icon><Delete /></el-icon>
              </button>
            </li>
          </ul>
        </aside>

        <!-- Mobile overlay -->
        <div v-if="sidebarOpen" class="sidebar-overlay" @click="sidebarOpen = false" />

        <!-- Center -->
        <div class="chat-center">
          <template v-if="!messages.length && !streaming">
            <div class="empty-hero">
              <div class="hero-kicker">ASK THE WIKI</div>
              <h1 class="hero-title">
                问一个<span class="hero-italic">问题</span>
              </h1>
              <p class="hero-sub">答案直接从你的知识库中检索，带引用来源。</p>

              <div class="composer hero-composer">
                <el-icon class="composer-spark"><ChatDotRound /></el-icon>
                <input
                  v-model="input"
                  class="composer-input"
                  placeholder="例如：RAG 和 Context Engineering 有什么区别？"
                  @keydown.enter.prevent="sendMessage"
                />
                <button
                  class="composer-send"
                  :disabled="!input.trim() || streaming"
                  @click="sendMessage"
                >
                  <el-icon><Top /></el-icon>
                </button>
              </div>

              <div class="hero-chips">
                <button
                  v-for="(q, i) in suggestedQuestions"
                  :key="i"
                  class="hero-chip"
                  @click="askSuggested(q)"
                >{{ q }}</button>
              </div>
            </div>
          </template>

          <template v-else>
            <div class="messages" ref="messagesRef">
              <div v-for="(msg, i) in messages" :key="i" :class="['msg', msg.role]" :data-msg-idx="i">
                <div class="msg-role">{{ msg.role === 'user' ? '你' : 'AI' }}</div>
                <div class="msg-bubble">
                  <!-- Pipeline card (assistant only, top) -->
                  <div v-if="msg.role === 'assistant' && msg.pipeline?.length" class="pipeline-card">
                    <div class="pipeline-head">
                      <span class="pipeline-label">⚙ Pipeline</span>
                      <div class="pipeline-stages">
                        <span
                          v-for="s in msg.pipeline"
                          :key="s.name"
                          :class="['pl-stage', `pl-${s.status}`]"
                        >
                          <span class="pl-name">{{ stageLabel(s.name) }}</span>
                          <span v-if="s.ms !== undefined" class="pl-ms">{{ s.ms }}ms</span>
                          <span v-else class="pl-running">…</span>
                        </span>
                      </div>
                      <span class="pipeline-total">耗时 {{ (totalMs(msg.pipeline)/1000).toFixed(1) }}s</span>
                    </div>
                    <div v-if="msg.reasoning" class="reasoning-block">
                      <button class="reasoning-toggle" @click="msg.reasoningOpen = !msg.reasoningOpen">
                        <span>🧠 思考过程</span>
                        <span class="toggle-caret">{{ msg.reasoningOpen ? '▾' : '▸' }}</span>
                      </button>
                      <div v-if="msg.reasoningOpen" class="reasoning-body">{{ msg.reasoning }}</div>
                    </div>
                  </div>

                  <!-- Source chips row (compact; details in right drawer) -->
                  <div
                    v-if="msg.role === 'assistant' && msg.sources?.length"
                    class="source-chips-row"
                  >
                    <span class="chips-label">检索到 {{ msg.sources.length }} 个来源</span>
                    <button
                      v-for="s in msg.sources"
                      :key="s.index"
                      class="source-chip"
                      :class="`chip-type-${s.type}`"
                      :title="s.title"
                      @click="focusSource(msg, s.slug)"
                    >
                      <span class="chip-num">{{ s.index }}</span>
                      <span class="chip-title">{{ s.title }}</span>
                    </button>
                  </div>

                  <MarkdownRenderer
                    v-if="msg.role === 'assistant'"
                    :content="msg.content"
                    new-tab
                    @click.capture="handleAnswerClick($event, i)"
                  />
                  <span v-else>{{ msg.content }}</span>

                  <!-- Action row (assistant only) -->
                  <div v-if="msg.role === 'assistant' && msg.id" class="msg-actions">
                    <button class="msg-action" @click="copyAnswer(msg)">
                      <el-icon><DocumentCopy /></el-icon>
                      <span>复制</span>
                    </button>
                    <div class="rating-group">
                      <button
                        class="msg-action"
                        :class="{ active: msg.rating === 'like' }"
                        @click="rateMessage(msg, 'like')"
                        title="回答有帮助"
                      >
                        <el-icon><CircleCheck /></el-icon>
                      </button>
                      <button
                        class="msg-action"
                        :class="{ active: msg.rating === 'dislike' }"
                        @click="rateMessage(msg, 'dislike')"
                        title="回答不准确"
                      >
                        <el-icon><CircleClose /></el-icon>
                      </button>
                    </div>
                    <button
                      class="msg-action primary"
                      :disabled="savingAnalysisId === msg.id"
                      @click="saveAsAnalysis(msg)"
                    >
                      <el-icon><Plus /></el-icon>
                      <span v-if="msg.savedSlug">已存为分析页面</span>
                      <span v-else-if="savingAnalysisId === msg.id">保存中…</span>
                      <span v-else>存为分析页面</span>
                    </button>
                    <a
                      v-if="msg.savedSlug"
                      class="msg-action link"
                      :href="`/wiki/${msg.savedSlug}`"
                      target="_blank"
                      rel="noopener"
                    >查看 →</a>
                    <div class="msg-menu-wrap" style="position:relative">
                      <button class="msg-action" @click.stop="toggleMsgMenu(i)" title="更多操作">
                        <el-icon><MoreFilled /></el-icon>
                      </button>
                      <div v-if="activeMenuIdx === i" class="msg-menu-dropdown" :style="{ top: '100%', right: 0 }">
                        <button v-if="msg.role === 'assistant'" @click="retryMessage(msg, i)">重新生成</button>
                        <button @click="deleteMessage(msg.id, i)">删除</button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="streaming" class="msg assistant">
                <div class="msg-role">AI</div>
                <div class="msg-bubble">
                  <div v-if="streamPipeline.length" class="pipeline-card">
                    <div class="pipeline-head">
                      <span class="pipeline-label">⚙ Pipeline</span>
                      <div class="pipeline-stages">
                        <span
                          v-for="s in streamPipeline"
                          :key="s.name"
                          :class="['pl-stage', `pl-${s.status}`]"
                        >
                          <span class="pl-name">{{ stageLabel(s.name) }}</span>
                          <span v-if="s.ms !== undefined" class="pl-ms">{{ s.ms }}ms</span>
                          <span v-else class="pl-running">…</span>
                        </span>
                      </div>
                      <span v-if="totalMs(streamPipeline) > 0" class="pipeline-total">耗时 {{ (totalMs(streamPipeline)/1000).toFixed(1) }}s</span>
                    </div>
                    <div v-if="streamReasoning" class="reasoning-block">
                      <button class="reasoning-toggle" @click="streamReasoningOpen = !streamReasoningOpen">
                        <span>🧠 思考中…</span>
                        <span class="toggle-caret">{{ streamReasoningOpen ? '▾' : '▸' }}</span>
                      </button>
                      <div v-if="streamReasoningOpen" class="reasoning-body">{{ streamReasoning }}</div>
                    </div>
                  </div>
                  <MarkdownRenderer :content="streamContent" new-tab />
                  <span class="typing">
                    <span class="dot" /><span class="dot" /><span class="dot" />
                  </span>
                </div>
              </div>
            </div>

            <div class="composer-wrap">
              <div class="composer">
                <textarea
                  v-model="input"
                  class="composer-input multiline"
                  rows="1"
                  placeholder="继续问…  (Enter 发送, Shift+Enter 换行)"
                  :disabled="streaming"
                  @keydown="handleInputKeydown"
                />
                <button
                  v-if="streaming"
                  class="composer-send streaming"
                  @click="stopStream"
                  title="停止生成"
                >
                  <el-icon><VideoPause /></el-icon>
                </button>
                <button
                  v-else
                  class="composer-send"
                  :disabled="!input.trim()"
                  @click="sendMessage"
                >
                  <el-icon><Top /></el-icon>
                </button>
              </div>
            </div>
          </template>
        </div>

        <!-- Right: Knowledge Explorer -->
        <ChatExplorer
          v-model:visible="explorerVisible"
          :referenced-pages="activeAssistantSlugs || latestReferencedPages"
          :focus-slug="focusedSourceSlug"
        />
      </div>

      <!-- Mobile floating sidebar toggle -->
      <button
        class="floating-sidebar-toggle"
        @click="sidebarOpen = !sidebarOpen"
        :title="sidebarOpen ? '关闭历史' : '打开历史'"
      >
        <el-icon><ChatLineSquare /></el-icon>
      </button>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Plus, ChatLineSquare, ChatDotRound, Reading, Delete, Top, DocumentCopy, VideoPause, CircleCheck, CircleClose, MoreFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import AppLayout from '../components/AppLayout.vue'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'
import ChatExplorer from '../components/ChatExplorer.vue'
import { streamChat, getSessionMessages, listSessions, deleteSession, saveMessageAsAnalysis, rateMessage as rateMessageApi, deleteChatMessage, updateChatMessage, type SessionSummary, type ChatSource, type ChatMode } from '../api/chat'
import { getSuggestions } from '../api/wiki'

interface PipelineStage {
  name: 'retrieve' | 'think' | 'generate'
  status: 'start' | 'done'
  ms?: number
  count?: number
}
interface ChatMessage {
  id?: string
  role: 'user' | 'assistant'
  content: string
  reasoning?: string
  sources?: ChatSource[]
  savedSlug?: string
  pipeline?: PipelineStage[]
  mode?: ChatMode
  reasoningOpen?: boolean
  rating?: 'like' | 'dislike'
}

const SESSION_KEY = 'wiki_chat_session_id'

const SUGGESTION_FALLBACK = [
  '最近新增了哪些知识？',
  '帮我总结团队的关键讨论',
  '有哪些待跟进的事项？',
]
const suggestedQuestions = ref<string[]>(SUGGESTION_FALLBACK)

const input = ref('')
const messages = ref<ChatMessage[]>([])
const streaming = ref(false)
const streamContent = ref('')
const sessionId = ref<string | undefined>(localStorage.getItem(SESSION_KEY) || undefined)
const messagesRef = ref<HTMLElement>()

const historyLoading = ref(false)
const historyList = ref<SessionSummary[]>([])
const activeMenuIdx = ref<number | null>(null)
const sidebarOpen = ref(false)
const explorerVisible = ref(false)
const savingAnalysisId = ref<string | null>(null)
const chatMode = ref<ChatMode>((localStorage.getItem('wiki_chat_mode') as ChatMode) || 'cited')
const streamPipeline = ref<PipelineStage[]>([])
const streamReasoning = ref('')
const streamReasoningOpen = ref(true)
let abortController: AbortController | null = null
let wasStopped = false

const MODE_OPTIONS: { value: ChatMode; label: string; hint: string }[] = [
  { value: 'concise', label: '简明',   hint: '直接回答，不思考' },
  { value: 'cited',   label: '带引用', hint: '思考 + 引用（默认）' },
  { value: 'deep',    label: '深度分析', hint: '长思考 + 展开分析' },
]
function setMode(m: ChatMode) {
  if (streaming.value) return
  chatMode.value = m
  localStorage.setItem('wiki_chat_mode', m)
}

const STAGE_LABELS: Record<PipelineStage['name'], string> = {
  retrieve: '检索',
  think: '思考',
  generate: '生成',
}
function stageLabel(n: PipelineStage['name']) { return STAGE_LABELS[n] }
function totalMs(stages: PipelineStage[] | undefined): number {
  if (!stages) return 0
  return stages.filter(s => s.status === 'done').reduce((a, s) => a + (s.ms || 0), 0)
}

// Normalize legacy referenced_pages (string[]) to new ChatSource[] shape.
function normalizeSources(refs: ChatSource[] | string[] | null | undefined): ChatSource[] | undefined {
  if (!refs || refs.length === 0) return undefined
  const first = refs[0]
  if (typeof first === 'string') {
    return (refs as string[]).map((slug, i) => ({
      index: i + 1,
      slug,
      title: slug,
      type: 'source',
      score: 0,
      excerpt: '',
    }))
  }
  return refs as ChatSource[]
}

const TYPE_LABELS: Record<string, string> = {
  concept: '概念',
  entity: '实体',
  source: '信源',
  analysis: '分析',
}
function typeLabel(t: string): string {
  return TYPE_LABELS[t] || t
}

function handleAnswerClick(e: MouseEvent, msgIdx: number) {
  const target = (e.target as HTMLElement).closest('.citation') as HTMLElement | null
  if (!target) return
  e.preventDefault()
  e.stopPropagation()
  const srcIdx = Number(target.dataset.srcIdx)
  if (!srcIdx) return
  const msg = messages.value[msgIdx]
  const source = msg?.sources?.find(s => s.index === srcIdx)
  if (source) focusSource(msg, source.slug)
}

const focusedSourceSlug = ref<string | null>(null)
function focusSource(msg: ChatMessage, slug: string) {
  // Make sure the drawer has the right context (latestReferencedPages is
  // derived from the *last* assistant message; if user clicks an older one,
  // temporarily surface those slugs).
  explorerVisible.value = true
  focusedSourceSlug.value = slug
  // Reset the flash trigger so re-clicks re-animate on the same slug.
  nextTick(() => {
    setTimeout(() => { if (focusedSourceSlug.value === slug) focusedSourceSlug.value = null }, 1400)
  })
  // If msg isn't the latest, pass its slug list down so the drawer loads them.
  activeAssistantSlugs.value = msg.sources?.map(s => s.slug) || null
}

// When set, overrides latestReferencedPages in the drawer props. Cleared when user switches drawer state.
const activeAssistantSlugs = ref<string[] | null>(null)

async function copyAnswer(msg: ChatMessage) {
  try {
    await navigator.clipboard.writeText(msg.content)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}

async function copyConversation() {
  const lines = messages.value.map(msg => {
    const role = msg.role === 'user' ? '【用户】' : '【AI】'
    return `${role}\n${msg.content}\n`
  }).join('\n---\n\n')
  try {
    await navigator.clipboard.writeText(lines)
    ElMessage.success('对话已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

async function rateMessage(msg: ChatMessage, rating: 'like' | 'dislike') {
  if (!msg.id) return
  try {
    await rateMessageApi(msg.id, rating)
    // Toggle off if same rating is clicked again
    if (msg.rating === rating) {
      msg.rating = undefined
    } else {
      msg.rating = rating
    }
  } catch (e: any) {
    ElMessage.error('操作失败：' + (e?.message || '未知错误'))
  }
}

function toggleMsgMenu(i: number) {
  activeMenuIdx.value = activeMenuIdx.value === i ? null : i
}

async function retryMessage(msg: ChatMessage, idx: number) {
  activeMenuIdx.value = null
  // Find preceding user message
  if (idx === 0 || messages.value[idx - 1].role !== 'user') {
    ElMessage.warning('无法重新生成：找不到对应的用户问题')
    return
  }
  const userMsg = messages.value[idx - 1]
  // Drop the old user message too — sendMessage() will re-push it from input.
  messages.value = messages.value.slice(0, idx - 1)
  input.value = userMsg.content
  await sendMessage()
}

async function deleteMessage(msgId: string | undefined, idx: number) {
  activeMenuIdx.value = null
  if (!msgId) {
    // For unsaved/in-progress messages, just remove from UI
    messages.value.splice(idx, 1)
    return
  }
  try {
    await deleteChatMessage(msgId)
    messages.value.splice(idx, 1)
    ElMessage.success('已删除')
  } catch (e: any) {
    ElMessage.error('删除失败：' + (e?.message || '未知错误'))
  }
}

async function saveAsAnalysis(msg: ChatMessage) {
  if (!msg.id || savingAnalysisId.value) return
  savingAnalysisId.value = msg.id
  try {
    const res = await saveMessageAsAnalysis(msg.id)
    msg.savedSlug = res.slug
    ElMessage.success(`已保存为分析页面：${res.title}`)
  } catch (e: any) {
    ElMessage.error('保存失败：' + (e?.message || '未知错误'))
  } finally {
    savingAnalysisId.value = null
  }
}

const latestReferencedPages = computed<string[]>(() => {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const msg = messages.value[i]
    if (msg.role === 'assistant' && msg.sources?.length) {
      return msg.sources.map(s => s.slug)
    }
  }
  return []
})

watch(latestReferencedPages, (pages) => {
  if (pages.length > 0) explorerVisible.value = true
})

async function loadSessions() {
  historyLoading.value = true
  try {
    historyList.value = await listSessions()
  } catch (err: any) {
    ElMessage.error('加载历史失败：' + (err?.message || '未知错误'))
  } finally {
    historyLoading.value = false
  }
}

async function switchToSession(id: string) {
  if (streaming.value) return
  sidebarOpen.value = false
  sessionId.value = id
  localStorage.setItem(SESSION_KEY, id)
  messages.value = []
  streamContent.value = ''
  await loadHistory(id)
}

function formatTime(iso: string) {
  try {
    const d = new Date(iso)
    const now = new Date()
    const sameDay = d.toDateString() === now.toDateString()
    if (sameDay) return '今天 ' + d.toTimeString().slice(0, 5)
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch { return iso }
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  })
}

async function loadHistory(id: string) {
  try {
    const rows = await getSessionMessages(id)
    messages.value = rows.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      sources: normalizeSources(m.referenced_pages),
      rating: m.rating as 'like' | 'dislike' | undefined,
    }))
    scrollToBottom()
  } catch {
    localStorage.removeItem(SESSION_KEY)
    sessionId.value = undefined
  }
}

function startNewConversation() {
  if (streaming.value) return
  localStorage.removeItem(SESSION_KEY)
  sessionId.value = undefined
  messages.value = []
  streamContent.value = ''
  explorerVisible.value = false
  ElMessage.success('已开始新对话')
}

async function handleDeleteSession(id: string, event: Event) {
  event.stopPropagation()
  if (streaming.value) return
  try {
    await ElMessageBox.confirm('确定删除这个会话？所有消息将被永久删除。', '删除确认', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
    })
  } catch { return }
  try {
    await deleteSession(id)
    historyList.value = historyList.value.filter(s => s.id !== id)
    if (sessionId.value === id) startNewConversation()
    ElMessage.success('会话已删除')
  } catch (e: any) {
    ElMessage.error('删除失败：' + (e?.message || '未知错误'))
  }
}

function handleInputKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

function askSuggested(question: string) {
  input.value = question
  sendMessage()
}

async function sendMessage() {
  const text = input.value.trim()
  if (!text || streaming.value) return

  wasStopped = false
  messages.value.push({ role: 'user', content: text })
  input.value = ''
  streaming.value = true
  streamContent.value = ''
  streamPipeline.value = []
  streamReasoning.value = ''
  streamReasoningOpen.value = true
  scrollToBottom()

  let pendingSources: ChatSource[] = []
  let pendingMessageId: string | undefined

  try {
    abortController = new AbortController()
    const response = await streamChat(text, sessionId.value, undefined, chatMode.value, abortController.signal)
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let currentEvent = 'message'

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (line === '') { currentEvent = 'message'; continue }
        if (line.startsWith('event: ')) { currentEvent = line.slice(7).trim(); continue }
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (currentEvent === 'done') {
            try {
              const info = JSON.parse(data)
              if (info.session_id) {
                sessionId.value = info.session_id
                localStorage.setItem(SESSION_KEY, info.session_id)
              }
              if (info.message_id) pendingMessageId = info.message_id
              if (Array.isArray(info.sources)) pendingSources = info.sources as ChatSource[]
            } catch { /* ignore */ }
          } else if (currentEvent === 'error') {
            let message = data
            try {
              const parsed = JSON.parse(data)
              if (parsed?.error && typeof parsed.error === 'string') {
                message = parsed.error
              }
            } catch { /* keep raw data */ }
            streamContent.value += `\n\n⚠️ ${message}`
          } else if (currentEvent === 'stage') {
            try {
              const s = JSON.parse(data) as PipelineStage
              const prev = streamPipeline.value.findIndex(x => x.name === s.name)
              if (prev >= 0) streamPipeline.value.splice(prev, 1, s)
              else streamPipeline.value.push(s)
            } catch { /* ignore */ }
          } else if (currentEvent === 'reasoning') {
            streamReasoning.value += data
            scrollToBottom()
          } else {
            streamContent.value += data
            scrollToBottom()
          }
        }
      }
    }

    messages.value.push({
      id: pendingMessageId,
      role: 'assistant',
      content: streamContent.value,
      reasoning: streamReasoning.value || undefined,
      sources: pendingSources.length ? pendingSources : undefined,
      pipeline: streamPipeline.value.length ? [...streamPipeline.value] : undefined,
      mode: chatMode.value,
      reasoningOpen: false,
    })
    streamContent.value = ''
    streamReasoning.value = ''
    streamPipeline.value = []
  } catch (e: any) {
    if (e.name === 'AbortError' || wasStopped) {
      // User stopped — keep partial content as draft
      if (streamContent.value) {
        messages.value.push({
          role: 'assistant',
          content: streamContent.value + '\n\n_（生成已停止）_',
        })
      }
    } else {
      messages.value.push({ role: 'assistant', content: '抱歉，请求出错了。请稍后重试。' })
    }
  }

  abortController = null
  streaming.value = false
  scrollToBottom()
  loadSessions()
}

function stopStream() {
  wasStopped = true
  abortController?.abort()
}

const route = useRoute()
const router = useRouter()

onMounted(async () => {
  loadSessions()
  if (sessionId.value) loadHistory(sessionId.value)
  try {
    const bubbles = await getSuggestions(4)
    if (bubbles.length) suggestedQuestions.value = bubbles
  } catch {}
  // Close menu when clicking outside
  document.addEventListener('click', closeMsgMenu)

  // Auto-send if navigated with ?q= from command palette
  const qParam = (route.query.q as string | undefined)?.trim()
  if (qParam) {
    input.value = qParam
    router.replace({ path: route.path, query: {} })
    await nextTick()
    sendMessage()
  }
})

function closeMsgMenu() {
  activeMenuIdx.value = null
}

onBeforeUnmount(() => {
  document.removeEventListener('click', closeMsgMenu)
})
</script>

<style scoped>
.chat-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--paper);
}

/* Header strip */
.header-strip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 20px;
  border-bottom: 1px solid var(--line);
  background: color-mix(in oklch, var(--paper) 82%, transparent);
  backdrop-filter: blur(8px);
  flex-shrink: 0;
}
.strip-crumb { color: var(--ink); font-weight: 500; font-size: 12.5px; }
.strip-meta { font-family: var(--font-mono); font-size: 11.5px; color: var(--ink-4); }

.explorer-toggle, .new-conv-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink-2);
  border-radius: 7px;
  font-size: 12.5px;
  cursor: pointer;
  font-family: var(--font-ui);
  transition: all var(--transition);
}
.explorer-toggle:hover, .new-conv-btn:hover { background: var(--paper-2); }
.explorer-toggle.active { background: var(--accent-soft); color: var(--accent-ink); border-color: transparent; }
.new-conv-btn { background: var(--ink); color: var(--paper); border-color: transparent; }
.new-conv-btn:hover { background: var(--ink-2); color: var(--paper); }
.new-conv-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* Body */
.chat-body {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
}

/* History sidebar */
.history-sidebar {
  width: 240px;
  flex-shrink: 0;
  background: var(--paper-2);
  border-right: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.history-head { padding: 14px 16px 8px; flex-shrink: 0; }
.history-label {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--ink-4);
  letter-spacing: 0.14em;
  text-transform: uppercase;
}
.history-loading, .history-empty {
  padding: 16px;
  font-size: 12.5px;
  color: var(--ink-4);
  font-style: italic;
}

.session-list {
  list-style: none;
  margin: 0;
  padding: 4px 8px 18px;
  overflow-y: auto;
  flex: 1;
}
.session-item {
  position: relative;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 2px;
  transition: background var(--transition);
}
.session-item:hover { background: var(--paper-3); }
.session-item.active { background: var(--paper); box-shadow: inset 0 0 0 1px var(--line-2); }
.session-title {
  font-size: 13px;
  color: var(--ink);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 4px;
  padding-right: 18px;
}
.session-meta {
  display: flex;
  justify-content: space-between;
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--ink-4);
}
.session-count { color: var(--ink-3); }
.session-delete {
  position: absolute;
  right: 8px;
  top: 8px;
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border: none;
  background: transparent;
  color: var(--ink-4);
  border-radius: 5px;
  cursor: pointer;
  opacity: 0;
  transition: all var(--transition);
}
.session-item:hover .session-delete { opacity: 1; }
.session-delete:hover { background: oklch(0.93 0.06 25); color: oklch(0.45 0.15 25); }
.session-delete:disabled { opacity: 0.3; cursor: not-allowed; }

/* Center */
.chat-center {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--paper);
  overflow: hidden;
}

/* Empty hero */
.empty-hero {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px 36px 60px;
  max-width: 720px;
  margin: 0 auto;
  width: 100%;
}
.hero-kicker {
  font-size: 10.5px;
  font-family: var(--font-mono);
  color: var(--ink-4);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.hero-title {
  font-family: var(--font-display);
  font-weight: 400;
  font-size: clamp(40px, 5vw, 56px);
  line-height: 1.05;
  letter-spacing: -0.015em;
  margin: 0 0 12px;
  color: var(--ink);
  text-align: center;
}
.hero-italic { font-style: italic; color: var(--accent-ink); }
.hero-sub { font-size: 14.5px; color: var(--ink-3); margin: 0 0 28px; text-align: center; }
.hero-composer { width: 100%; margin-bottom: 18px; }
.hero-chips { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.hero-chip {
  padding: 6px 14px;
  background: transparent;
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--ink-2);
  font-size: 12.5px;
  cursor: pointer;
  font-family: var(--font-ui);
  transition: all var(--transition);
}
.hero-chip:hover { background: var(--paper-2); border-color: var(--line-2); color: var(--ink); }

/* Composer */
.composer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 12px;
  transition: border-color var(--transition);
}
.composer:focus-within { border-color: var(--line-2); box-shadow: var(--shadow-sm); }
.composer-spark { color: var(--accent-ink); font-size: 16px; }
.composer-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14.5px;
  color: var(--ink);
  font-family: var(--font-ui);
  resize: none;
  line-height: 1.5;
  max-height: 120px;
}
.composer-input.multiline { min-height: 22px; }
.composer-send {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  background: var(--ink);
  color: var(--paper);
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: opacity var(--transition);
  flex-shrink: 0;
}
.composer-send:disabled { opacity: 0.4; cursor: not-allowed; }
.composer-send:hover:not(:disabled) { background: var(--ink-2); }
.composer-send.streaming {
  background: var(--red, #ef4444);
  animation: pulse-red 1.5s infinite;
}
@keyframes pulse-red {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

/* Messages */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 28px 36px 16px;
  display: flex;
  flex-direction: column;
  gap: 22px;
}
.msg {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: 760px;
  margin: 0 auto;
  width: 100%;
}
.msg-role {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.14em;
  color: var(--ink-4);
  text-transform: uppercase;
}
.msg.user .msg-role { color: var(--accent-ink); }
.msg-bubble { font-size: 14.5px; line-height: 1.7; color: var(--ink); }
.msg.user .msg-bubble {
  align-self: flex-end;
  background: var(--accent-soft);
  color: var(--accent-ink);
  padding: 12px 16px;
  border-radius: 12px;
  max-width: 85%;
}
.msg-bubble :deep(p) { margin: 0 0 10px; }
.msg-bubble :deep(p:last-child) { margin-bottom: 0; }
.msg-bubble :deep(code) {
  font-family: var(--font-mono);
  font-size: 12.5px;
  background: var(--paper-2);
  padding: 1px 5px;
  border-radius: 4px;
}
.msg-bubble :deep(pre) {
  background: var(--paper-2);
  padding: 12px 14px;
  border-radius: 8px;
  overflow-x: auto;
  border: 1px solid var(--line);
}

/* Mode switch pills in header */
.mode-switch {
  display: inline-flex;
  gap: 2px;
  padding: 2px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 8px;
  margin-right: 8px;
}
.mode-pill {
  padding: 4px 10px;
  font-size: 12px;
  border: none;
  background: transparent;
  color: var(--ink-3);
  border-radius: 6px;
  cursor: pointer;
  font-family: var(--font-ui);
  transition: all var(--transition);
}
.mode-pill:hover:not(:disabled) { color: var(--ink); }
.mode-pill:disabled { opacity: 0.5; cursor: not-allowed; }
.mode-pill.active {
  background: var(--ink);
  color: var(--paper);
}

/* Pipeline card (shown above source strip / answer) */
.pipeline-card {
  margin: 0 0 12px;
  padding: 10px 12px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 8px;
}
.pipeline-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.pipeline-label {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--ink-4);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.pipeline-stages {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}
.pl-stage {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  font-size: 11px;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--ink-3);
  font-family: var(--font-mono);
}
.pl-stage.pl-done { color: var(--ink-2); border-color: var(--ink-5, #dcd8d0); }
.pl-stage.pl-start {
  color: var(--accent-ink, var(--ink-2));
  border-color: var(--accent, var(--ink-3));
  animation: pl-pulse 1.4s ease-in-out infinite;
}
@keyframes pl-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}
.pl-ms { color: var(--ink-4); font-size: 10.5px; }
.pl-running { color: var(--accent-ink, var(--ink-4)); }
.pipeline-total {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--ink-4);
}

.reasoning-block {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--line);
}
.reasoning-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px;
  font-size: 11.5px;
  background: transparent;
  border: none;
  color: var(--ink-3);
  cursor: pointer;
  font-family: var(--font-ui);
}
.reasoning-toggle:hover { color: var(--ink); }
.toggle-caret { font-family: var(--font-mono); color: var(--ink-4); }
.reasoning-body {
  margin-top: 6px;
  padding: 10px 12px;
  background: var(--paper);
  border: 1px dashed var(--line);
  border-radius: 6px;
  font-size: 12.5px;
  line-height: 1.65;
  color: var(--ink-3);
  white-space: pre-wrap;
  font-family: var(--font-mono);
  max-height: 320px;
  overflow-y: auto;
}

/* Source chips (compact, single wrap; details live in right drawer) */
.source-chips-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin: 0 0 12px;
  padding: 8px 10px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 8px;
}
.chips-label {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--ink-4);
  letter-spacing: 0.06em;
  margin-right: 4px;
}
.source-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  max-width: 220px;
  padding: 3px 8px 3px 4px;
  font-size: 11.5px;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--ink-2);
  font-family: var(--font-ui);
  cursor: pointer;
  transition: all var(--transition);
}
.source-chip:hover {
  border-color: var(--accent);
  color: var(--ink);
}
.chip-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 17px;
  height: 17px;
  font-size: 10.5px;
  font-family: var(--font-mono);
  background: var(--ink);
  color: var(--paper);
  border-radius: 50%;
  font-weight: 600;
  flex-shrink: 0;
}
.chip-title {
  max-width: 190px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chip-type-concept  { border-color: #e8c7a8; }
.chip-type-concept .chip-num  { background: #b85c38; }
.chip-type-entity   { border-color: #b8d4ea; }
.chip-type-entity .chip-num   { background: #3b6ea5; }
.chip-type-source   { border-color: #bed9b8; }
.chip-type-source .chip-num   { background: #4a7a4a; }
.chip-type-analysis { border-color: #cfbfe0; }
.chip-type-analysis .chip-num { background: #6b4a8a; }

/* Inline citation badges within the answer text */
.msg-bubble :deep(sup.citation) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  padding: 0 5px;
  margin: 0 1px;
  vertical-align: super;
  font-size: 10.5px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--ink-2);
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 4px;
  cursor: pointer;
  transition: all var(--transition);
  user-select: none;
  line-height: 1.4;
}
.msg-bubble :deep(sup.citation:hover) {
  color: var(--paper);
  background: var(--ink);
  border-color: var(--ink);
}

/* Action row under each AI answer */
.msg-actions {
  display: flex;
  gap: 6px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed var(--line);
  flex-wrap: wrap;
}
.msg-action {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  font-size: 12px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink-3);
  border-radius: 6px;
  cursor: pointer;
  font-family: var(--font-ui);
  text-decoration: none;
  transition: all var(--transition);
}
.msg-action:hover:not(:disabled) { color: var(--ink); border-color: var(--ink-3); }
.msg-action:disabled { opacity: 0.6; cursor: not-allowed; }
.msg-action.primary {
  color: var(--accent-ink, var(--ink));
  border-color: var(--accent, var(--ink-3));
}
.msg-action.primary:hover:not(:disabled) {
  background: var(--accent, var(--ink));
  color: var(--paper);
}
.msg-action.link { color: var(--accent-ink, var(--ink)); }
.rating-group { display: flex; gap: 2px; }
.rating-group .msg-action { padding: 5px 8px; }
.msg-action.active { color: var(--accent, #3b82f6); border-color: var(--accent, #3b82f6); background: var(--accent-soft, #eff6ff); }
.msg-menu-dropdown {
  position: absolute;
  z-index: 100;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow-md);
  overflow: hidden;
  min-width: 120px;
}
.msg-menu-dropdown button {
  display: block;
  width: 100%;
  padding: 8px 14px;
  font-size: 13px;
  text-align: left;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--ink);
  font-family: var(--font-ui);
}
.msg-menu-dropdown button:hover { background: var(--paper-2); }

/* Typing */
.typing { display: inline-flex; gap: 3px; margin-left: 4px; }
.typing .dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: var(--ink-4);
  animation: blink 1.2s infinite;
}
.typing .dot:nth-child(2) { animation-delay: 0.2s; }
.typing .dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0%, 100% { opacity: 0.3; } 50% { opacity: 1; } }

/* Bottom composer */
.composer-wrap {
  padding: 12px 36px 18px;
  border-top: 1px solid var(--line);
  background: var(--paper);
  flex-shrink: 0;
}
.composer-wrap .composer { max-width: 760px; margin: 0 auto; }

/* Floating sidebar toggle (mobile) */
.floating-sidebar-toggle {
  position: fixed;
  left: 80px;
  bottom: 22px;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: var(--paper);
  color: var(--ink-2);
  border: 1px solid var(--line);
  display: none;
  place-items: center;
  cursor: pointer;
  box-shadow: var(--shadow-md);
  z-index: 30;
}

.sidebar-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 999;
}

@media (max-width: 768px) {
  .history-sidebar {
    position: fixed;
    z-index: 1000;
    top: 0;
    left: 0;
    bottom: 0;
    transform: translateX(-100%);
    transition: transform 0.28s ease;
    box-shadow: var(--shadow-lg);
  }
  .history-sidebar.open { transform: translateX(0); }
  .floating-sidebar-toggle { display: grid; }
  .messages { padding: 20px 18px 12px; }
  .composer-wrap { padding: 10px 18px 14px; }
  .empty-hero { padding: 24px 18px 40px; }
}
</style>
