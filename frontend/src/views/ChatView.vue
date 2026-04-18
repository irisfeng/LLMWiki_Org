<template>
  <AppLayout>
    <div class="chat-shell">
      <!-- Header strip -->
      <div class="header-strip">
        <span class="strip-crumb">AI 问答</span>
        <span class="strip-meta">· Haiku 4.5 · 检索范围: 全库</span>
        <div style="flex:1"></div>
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
              <div v-for="(msg, i) in messages" :key="i" :class="['msg', msg.role]">
                <div class="msg-role">{{ msg.role === 'user' ? '你' : 'AI' }}</div>
                <div class="msg-bubble">
                  <MarkdownRenderer v-if="msg.role === 'assistant'" :content="msg.content" new-tab />
                  <span v-else>{{ msg.content }}</span>
                  <div
                    v-if="msg.role === 'assistant' && msg.referenced_pages?.length"
                    class="msg-refs"
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

              <div v-if="streaming" class="msg assistant">
                <div class="msg-role">AI</div>
                <div class="msg-bubble">
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
                  class="composer-send"
                  :disabled="!input.trim() || streaming"
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
          :referenced-pages="latestReferencedPages"
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
import { ref, nextTick, onMounted, computed, watch } from 'vue'
import { Plus, ChatLineSquare, ChatDotRound, Reading, Delete, Top } from '@element-plus/icons-vue'
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
  'RAG 和 Context Engineering 有什么区别？',
  '总结 Q2 产品战略备忘录的三个关键决定',
  '我们知识库里哪些文档还没被引用？',
  '最近上传的 Karpathy 文章讲了什么？',
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

const latestReferencedPages = computed<string[]>(() => {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const msg = messages.value[i]
    if (msg.role === 'assistant' && msg.referenced_pages?.length) {
      return msg.referenced_pages
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
      role: m.role,
      content: m.content,
      referenced_pages: m.referenced_pages || undefined,
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
              if (Array.isArray(info.referenced_pages)) pendingRefs = info.referenced_pages
            } catch { /* ignore */ }
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
  } catch {
    messages.value.push({ role: 'assistant', content: '抱歉，请求出错了。请稍后重试。' })
  }

  streaming.value = false
  scrollToBottom()
  loadSessions()
}

onMounted(() => {
  loadSessions()
  if (sessionId.value) loadHistory(sessionId.value)
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

.msg-refs { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.refs-label { font-family: var(--font-mono); font-size: 10px; color: var(--ink-4); letter-spacing: 0.1em; }
.ref-pill {
  font-family: var(--font-mono);
  font-size: 11px;
  padding: 2px 8px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--ink-3);
  text-decoration: none;
  transition: all var(--transition);
}
.ref-pill:hover { color: var(--accent-ink); border-color: var(--accent); }

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
