<template>
  <AppLayout>
    <div class="chat-page">
      <!-- Mobile header bar -->
      <div class="chat-topbar">
        <el-button
          class="topbar-btn sidebar-toggle"
          :icon="ChatLineSquare"
          text
          @click="sidebarOpen = !sidebarOpen"
        />
        <h2 class="topbar-title">AI 问答</h2>
        <div class="topbar-actions">
          <span v-if="sessionId" class="session-indicator">
            <el-icon :size="12"><CircleCheck /></el-icon>
            已保存
          </span>
          <el-button
            class="topbar-btn explorer-toggle"
            :icon="Reading"
            text
            @click="explorerVisible = !explorerVisible"
          />
        </div>
      </div>

      <div class="chat-body">
        <!-- Left sidebar: session history -->
        <aside
          class="history-sidebar"
          :class="{ open: sidebarOpen }"
        >
          <div class="sidebar-header">
            <span class="sidebar-label">历史会话</span>
            <el-button size="small" :icon="Plus" @click="startNewConversation" :disabled="streaming">
              新对话
            </el-button>
          </div>
          <div v-if="historyLoading" class="sidebar-loading">加载中...</div>
          <el-empty v-else-if="!historyList.length" description="还没有历史会话" :image-size="60" />
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
              <el-button
                class="session-delete-btn"
                :icon="Delete"
                text
                size="small"
                :disabled="streaming"
                @click="handleDeleteSession(s.id, $event)"
              />
            </li>
          </ul>
        </aside>

        <!-- Mobile sidebar overlay -->
        <div
          v-if="sidebarOpen"
          class="sidebar-overlay"
          @click="sidebarOpen = false"
        />

        <!-- Center: conversation -->
        <div class="chat-center">
          <div class="messages" ref="messagesRef">
            <!-- Empty state with suggested questions -->
            <div v-if="!messages.length && !streaming" class="empty-state">
              <div class="empty-icon">
                <el-icon :size="48"><ChatDotRound /></el-icon>
              </div>
              <p class="empty-text">开始一个问题，答案会从本知识库中检索</p>
              <div class="suggestions">
                <button
                  v-for="(q, idx) in suggestedQuestions"
                  :key="idx"
                  class="suggestion-card"
                  @click="askSuggested(q)"
                >
                  {{ q }}
                </button>
              </div>
            </div>

            <!-- Message list -->
            <div v-for="(msg, i) in messages" :key="i" :class="['message', msg.role]">
              <div class="bubble">
                <MarkdownRenderer v-if="msg.role === 'assistant'" :content="msg.content" new-tab />
                <span v-else>{{ msg.content }}</span>
                <div
                  v-if="msg.role === 'assistant' && msg.referenced_pages && msg.referenced_pages.length"
                  class="refs"
                >
                  <span class="refs-label">参考：</span>
                  <a
                    v-for="slug in msg.referenced_pages"
                    :key="slug"
                    :href="`/wiki/${slug}`"
                    target="_blank"
                    rel="noopener"
                    class="ref-pill"
                  >{{ slug }}</a>
                </div>
              </div>
            </div>

            <!-- Streaming message -->
            <div v-if="streaming" class="message assistant">
              <div class="bubble">
                <MarkdownRenderer :content="streamContent" new-tab />
                <span class="typing-indicator">
                  <span class="dot"></span>
                  <span class="dot"></span>
                  <span class="dot"></span>
                </span>
              </div>
            </div>
          </div>

          <div class="input-area">
            <el-input
              v-model="input"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 4 }"
              placeholder="输入问题... (Enter 发送, Shift+Enter 换行)"
              :disabled="streaming"
              @keydown="handleInputKeydown"
            />
            <el-button
              type="primary"
              @click="sendMessage"
              :loading="streaming"
              class="send-btn"
            >
              发送
            </el-button>
          </div>
        </div>

        <!-- Right panel: knowledge explorer -->
        <ChatExplorer
          v-model:visible="explorerVisible"
          :referenced-pages="latestReferencedPages"
        />

        <!-- Explorer overlay on tablet/mobile -->
        <div
          v-if="explorerVisible"
          class="explorer-overlay"
          @click="explorerVisible = false"
        />
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, computed, watch } from 'vue'
import { Plus, ChatLineSquare, CircleCheck, ChatDotRound, Reading, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import AppLayout from '../components/AppLayout.vue'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'
import ChatExplorer from '../components/ChatExplorer.vue'
import { streamChat, getSessionMessages, listSessions, deleteSession, type SessionSummary } from '../api/chat'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  referenced_pages?: string[]
}

const SESSION_KEY = 'wiki_chat_session_id'

const suggestedQuestions = [
  '知识库里有哪些主题？',
  '最近上传的文档讲了什么？',
  '帮我总结一下所有信息源的核心观点',
  '什么是 RAG？',
]

const input = ref('')
const messages = ref<ChatMessage[]>([])
const streaming = ref(false)
const streamContent = ref('')
const sessionId = ref<string | undefined>(localStorage.getItem(SESSION_KEY) || undefined)
const messagesRef = ref<HTMLElement>()

const historyLoading = ref(false)
const historyList = ref<SessionSummary[]>([])
const sidebarOpen = ref(false)
const explorerVisible = ref(false)

// Compute the referenced pages from the latest assistant message
const latestReferencedPages = computed<string[]>(() => {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const msg = messages.value[i]
    if (msg.role === 'assistant' && msg.referenced_pages?.length) {
      return msg.referenced_pages
    }
  }
  return []
})

// Auto-show explorer when new references come in
watch(latestReferencedPages, (pages) => {
  if (pages.length > 0) {
    explorerVisible.value = true
  }
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
    if (sameDay) {
      return '今天 ' + d.toTimeString().slice(0, 5)
    }
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return iso
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

async function loadHistory(id: string) {
  try {
    const rows = await getSessionMessages(id)
    messages.value = rows.map((m) => ({
      role: m.role,
      content: m.content,
      referenced_pages: m.referenced_pages || undefined,
    }))
    scrollToBottom()
  } catch (err) {
    // Session expired / invalid / deleted — wipe local id silently
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
  event.stopPropagation() // Don't trigger session switch
  if (streaming.value) return // Guard: don't delete during streaming
  try {
    await ElMessageBox.confirm('确定删除这个会话？所有消息将被永久删除。', '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch { return } // User cancelled

  try {
    await deleteSession(id)
    historyList.value = historyList.value.filter(s => s.id !== id)
    // If we deleted the current session, start a new one
    if (sessionId.value === id) {
      startNewConversation()
    }
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

  messages.value.push({ role: 'user', content: text })
  input.value = ''
  streaming.value = true
  streamContent.value = ''
  scrollToBottom()

  let pendingRefs: string[] = []

  try {
    const response = await streamChat(text, sessionId.value)
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
        if (line === '') {
          currentEvent = 'message' // SSE event boundary
          continue
        }
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim()
          continue
        }
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (currentEvent === 'done') {
            try {
              const info = JSON.parse(data)
              if (info.session_id) {
                sessionId.value = info.session_id
                localStorage.setItem(SESSION_KEY, info.session_id)
              }
              if (Array.isArray(info.referenced_pages)) {
                pendingRefs = info.referenced_pages
              }
            } catch {
              /* ignore malformed done payload */
            }
          } else if (currentEvent === 'error') {
            streamContent.value += `\n\n⚠️ ${data}`
          } else {
            streamContent.value += data
            scrollToBottom()
          }
        }
      }
    }

    messages.value.push({
      role: 'assistant',
      content: streamContent.value,
      referenced_pages: pendingRefs.length ? pendingRefs : undefined,
    })
    streamContent.value = ''
  } catch (err) {
    messages.value.push({ role: 'assistant', content: '抱歉，请求出错了。请稍后重试。' })
  }

  streaming.value = false
  scrollToBottom()

  // Refresh session list after a new message so the sidebar stays current
  loadSessions()
}

onMounted(() => {
  loadSessions()
  if (sessionId.value) loadHistory(sessionId.value)
})
</script>

<style scoped>
/* ====== Page shell ====== */
.chat-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 56px);
  margin: -24px;
  overflow: hidden;
}

/* ====== Top bar (mobile actions + title) ====== */
.chat-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  border-bottom: 1px solid var(--border);
  background-color: var(--bg-primary);
  flex-shrink: 0;
}

.topbar-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.topbar-btn {
  color: var(--text-secondary);
}

.session-indicator {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--success);
  background-color: var(--success-soft);
  padding: 2px 8px;
  border-radius: 10px;
}

/* Hide sidebar toggle on desktop — sidebar is always visible */
.sidebar-toggle {
  display: none;
}

/* ====== Three-column body ====== */
.chat-body {
  display: flex;
  flex: 1;
  overflow: hidden;
  position: relative;
}

/* ====== Left sidebar: history ====== */
.history-sidebar {
  width: 240px;
  min-width: 240px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  background-color: var(--bg-secondary);
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.sidebar-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
}

.sidebar-loading {
  text-align: center;
  padding: 40px 16px;
  color: var(--text-muted);
  font-size: 13px;
}

.session-list {
  list-style: none;
  padding: 8px;
  margin: 0;
  overflow-y: auto;
  flex: 1;
}

.session-item {
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background-color var(--transition);
  margin-bottom: 2px;
  border: 1px solid transparent;
}

.session-item:hover {
  background-color: var(--bg-hover);
}

.session-item.active {
  background-color: var(--accent-soft);
  border-color: var(--accent);
}

.session-title {
  font-size: 13px;
  color: var(--text-primary);
  margin-bottom: 4px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.session-meta {
  font-size: 11px;
  color: var(--text-muted);
  display: flex;
  gap: 8px;
}

.session-count {
  color: var(--success);
}

.session-item {
  position: relative;
}

.session-delete-btn {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  opacity: 0;
  transition: opacity var(--transition);
  color: var(--text-muted);
}

.session-delete-btn:hover {
  color: var(--danger);
}

.session-item:hover .session-delete-btn {
  opacity: 1;
}

.sidebar-overlay {
  display: none;
}

/* ====== Center: conversation ====== */
.chat-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

/* Empty state */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  text-align: center;
  padding: 24px;
}

.empty-icon {
  color: var(--text-muted);
  margin-bottom: 12px;
  opacity: 0.5;
}

.empty-text {
  color: var(--text-muted);
  font-size: 14px;
  margin: 0 0 24px 0;
}

.suggestions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  max-width: 480px;
  width: 100%;
}

.suggestion-card {
  padding: 14px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background-color: var(--bg-card);
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.5;
  text-align: left;
  cursor: pointer;
  transition: border-color var(--transition), box-shadow var(--transition);
}

.suggestion-card:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-sm);
}

/* Messages */
.message {
  margin-bottom: 16px;
  display: flex;
}

.message.user {
  justify-content: flex-end;
}

.message.assistant {
  justify-content: flex-start;
}

.bubble {
  max-width: 80%;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  line-height: 1.6;
}

.message.user .bubble {
  background-color: var(--accent);
  color: var(--text-inverse);
  border-bottom-right-radius: 4px;
}

.message.assistant .bubble {
  background-color: var(--bg-secondary);
  color: var(--text-primary);
  border-bottom-left-radius: 4px;
}

.refs {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed var(--border);
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  font-size: 12px;
}

.refs-label {
  color: var(--text-muted);
}

.ref-pill {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 10px;
  background-color: var(--accent-soft);
  color: var(--accent);
  text-decoration: none;
  border: 1px solid var(--border);
  transition: background-color var(--transition), color var(--transition);
}

.ref-pill:hover {
  background-color: var(--accent);
  color: var(--text-inverse);
}

/* Typing indicator: 3-dot bounce */
.typing-indicator {
  display: inline-flex;
  gap: 4px;
  padding: 4px 0;
  vertical-align: middle;
}

.typing-indicator .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: var(--text-muted);
  animation: bounce 1.4s ease-in-out infinite;
}

.typing-indicator .dot:nth-child(2) {
  animation-delay: 0.16s;
}

.typing-indicator .dot:nth-child(3) {
  animation-delay: 0.32s;
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  40% {
    transform: translateY(-6px);
    opacity: 1;
  }
}

/* Input area */
.input-area {
  display: flex;
  align-items: flex-end;
  padding: 12px 24px 16px;
  border-top: 1px solid var(--border);
  gap: 8px;
  background-color: var(--bg-primary);
}

.input-area :deep(.el-textarea__inner) {
  resize: none;
}

.send-btn {
  flex-shrink: 0;
  height: 36px;
}

/* Explorer overlay (tablet) */
.explorer-overlay {
  display: none;
}

/* ====== Responsive: Desktop (>=1024px) ====== */
@media (min-width: 1024px) {
  .sidebar-toggle {
    display: none;
  }
}

/* ====== Responsive: Tablet (768-1023px) ====== */
@media (max-width: 1023px) {
  .history-sidebar {
    display: none;
  }

  .sidebar-toggle {
    display: inline-flex;
  }

  .history-sidebar.open {
    display: flex;
    position: fixed;
    top: 56px;
    left: 0;
    bottom: 0;
    z-index: 1002;
    box-shadow: var(--shadow-lg);
  }

  .sidebar-overlay {
    display: block;
    position: fixed;
    inset: 0;
    top: 56px;
    background: rgba(0, 0, 0, 0.3);
    z-index: 1001;
  }

  .explorer-overlay {
    display: block;
    position: fixed;
    inset: 0;
    top: 56px;
    background: rgba(0, 0, 0, 0.3);
    z-index: 1000;
  }
}

/* ====== Responsive: Mobile (<768px) ====== */
@media (max-width: 767px) {
  .chat-topbar {
    padding: 8px 12px;
  }

  .history-sidebar {
    display: none;
  }

  .sidebar-toggle {
    display: inline-flex;
  }

  .history-sidebar.open {
    display: flex;
    position: fixed;
    top: 56px;
    left: 0;
    bottom: 0;
    z-index: 1002;
    box-shadow: var(--shadow-lg);
  }

  .sidebar-overlay {
    display: block;
    position: fixed;
    inset: 0;
    top: 56px;
    background: rgba(0, 0, 0, 0.3);
    z-index: 1001;
  }

  .explorer-overlay {
    display: block;
    position: fixed;
    inset: 0;
    top: 56px;
    background: rgba(0, 0, 0, 0.3);
    z-index: 1000;
  }

  .messages {
    padding: 16px 12px;
  }

  .input-area {
    padding: 10px 12px 14px;
  }

  .bubble {
    max-width: 92%;
  }

  .suggestions {
    grid-template-columns: 1fr;
  }
}
</style>
