<template>
  <AppLayout>
    <div class="chat-page">
      <div class="chat-header">
        <h2>AI 问答</h2>
        <div class="header-actions">
          <span v-if="sessionId" class="session-tag">会话已保存</span>
          <el-button size="small" :icon="Clock" @click="openHistory">历史</el-button>
          <el-button size="small" :icon="Refresh" @click="startNewConversation" :disabled="streaming">
            新对话
          </el-button>
        </div>
      </div>
      <div class="chat-container">
        <div class="messages" ref="messagesRef">
                <el-empty v-if="!messages.length && !streaming" description="开始一个问题，答案会从本知识库中检索" />
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
          <div v-if="streaming" class="message assistant">
            <div class="bubble">
              <MarkdownRenderer :content="streamContent" new-tab />
              <span class="cursor">|</span>
            </div>
          </div>
        </div>

        <div class="input-area">
          <el-input
            v-model="input"
            placeholder="输入问题..."
            @keyup.enter="sendMessage"
            :disabled="streaming"
          />
          <el-button type="primary" @click="sendMessage" :loading="streaming" style="margin-left: 8px">
            发送
          </el-button>
        </div>
      </div>
    </div>

    <el-drawer
      v-model="historyOpen"
      title="历史会话"
      direction="rtl"
      size="380px"
    >
      <div v-if="historyLoading" class="history-loading">加载中...</div>
      <el-empty v-else-if="!historyList.length" description="还没有历史会话" />
      <ul v-else class="history-list">
        <li
          v-for="s in historyList"
          :key="s.id"
          :class="['history-item', { active: s.id === sessionId }]"
          @click="switchToSession(s.id)"
        >
          <div class="history-title">{{ s.title }}</div>
          <div class="history-meta">
            <span>{{ formatTime(s.created_at) }}</span>
            <span class="msg-count">{{ s.message_count }} 条消息</span>
            <span v-if="s.user_name" class="msg-user">· {{ s.user_name }}</span>
          </div>
        </li>
      </ul>
    </el-drawer>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { Refresh, Clock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import AppLayout from '../components/AppLayout.vue'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'
import { streamChat, getSessionMessages, listSessions, type SessionSummary } from '../api/chat'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  referenced_pages?: string[]
}

const SESSION_KEY = 'wiki_chat_session_id'

const input = ref('')
const messages = ref<ChatMessage[]>([])
const streaming = ref(false)
const streamContent = ref('')
const sessionId = ref<string | undefined>(localStorage.getItem(SESSION_KEY) || undefined)
const messagesRef = ref<HTMLElement>()

const historyOpen = ref(false)
const historyLoading = ref(false)
const historyList = ref<SessionSummary[]>([])

async function openHistory() {
  historyOpen.value = true
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
  historyOpen.value = false
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
  ElMessage.success('已开始新对话')
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
}

onMounted(() => {
  if (sessionId.value) loadHistory(sessionId.value)
})
</script>

<style scoped>
.chat-page { max-width: 800px; margin: 0 auto; }
.chat-header { display: flex; align-items: center; justify-content: space-between; }
.header-actions { display: flex; gap: 8px; align-items: center; }
.session-tag { font-size: 12px; color: #909399; background: #f0f9eb; padding: 2px 8px; border-radius: 10px; }
.chat-container { display: flex; flex-direction: column; height: calc(100vh - 220px); }
.messages { flex: 1; overflow-y: auto; padding: 16px 0; }
.message { margin-bottom: 16px; display: flex; }
.message.user { justify-content: flex-end; }
.message.assistant { justify-content: flex-start; }
.bubble { max-width: 80%; padding: 12px 16px; border-radius: 12px; line-height: 1.6; }
.message.user .bubble { background: #409eff; color: white; border-bottom-right-radius: 4px; }
.message.assistant .bubble { background: #f4f4f5; border-bottom-left-radius: 4px; }
.refs { margin-top: 10px; padding-top: 8px; border-top: 1px dashed #dcdfe6; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; font-size: 12px; }
.refs-label { color: #909399; }
.ref-pill {
  display: inline-block; padding: 2px 10px; border-radius: 10px;
  background: #ecf5ff; color: #409eff; text-decoration: none;
  border: 1px solid #d9ecff; transition: background .15s;
}
.ref-pill:hover { background: #409eff; color: white; }
.input-area { display: flex; padding-top: 12px; border-top: 1px solid #eee; }
.history-loading { text-align: center; padding: 40px; color: #909399; }
.history-list { list-style: none; padding: 0; margin: 0; }
.history-item {
  padding: 12px 14px; border-radius: 8px; cursor: pointer;
  transition: background .15s; margin-bottom: 4px;
  border: 1px solid transparent;
}
.history-item:hover { background: #f5f7fa; }
.history-item.active { background: #ecf5ff; border-color: #d9ecff; }
.history-title {
  font-size: 14px; color: #303133; margin-bottom: 6px; line-height: 1.4;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.history-meta { font-size: 12px; color: #909399; display: flex; gap: 8px; flex-wrap: wrap; }
.msg-count { color: #67c23a; }
.msg-user { color: #909399; }
.cursor { animation: blink 1s infinite; }
@keyframes blink { 0%, 50% { opacity: 1; } 51%, 100% { opacity: 0; } }
@media (max-width: 640px) {
  .chat-container { height: calc(100vh - 240px); }
  .bubble { max-width: 92%; }
}
</style>
