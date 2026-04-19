<template>
  <Teleport to="body">
    <transition name="drawer-fade">
      <div v-if="open" class="drawer-backdrop" @click="$emit('close')" />
    </transition>
    <transition name="drawer-slide">
      <aside v-if="open" class="ai-drawer" @click.stop>
        <header class="dr-head">
          <div class="dr-title">
            <el-icon class="dr-spark"><MagicStick /></el-icon>
            <span>问 AI</span>
          </div>
          <div class="dr-actions">
            <button class="ghost-btn" @click="goFullChat" title="进入完整对话">
              <el-icon><FullScreen /></el-icon>
            </button>
            <button class="ghost-btn" @click="$emit('close')" title="关闭">
              <el-icon><Close /></el-icon>
            </button>
          </div>
        </header>

        <div class="dr-body" ref="bodyRef">
          <!-- Empty state -->
          <div v-if="!messages.length && !streaming" class="dr-empty">
            <div class="empty-kicker">SUGGESTED</div>
            <button
              v-for="(q, i) in suggestions"
              :key="i"
              class="suggest-btn"
              @click="ask(q)"
            >{{ q }}</button>
          </div>

          <!-- Messages -->
          <div v-for="(m, i) in messages" :key="i" :class="['msg', m.role]">
            <div class="msg-role">{{ m.role === 'user' ? '你' : 'AI' }}</div>
            <div class="msg-text" v-html="renderMarkdown(m.content)"></div>
            <div v-if="m.role === 'assistant' && m.refs?.length" class="msg-refs">
              <div class="refs-label">参考来源</div>
              <a
                v-for="slug in m.refs"
                :key="slug"
                :href="`/wiki/${slug}`"
                target="_blank"
                class="ref-pill"
              >{{ slug }}</a>
            </div>
          </div>
        </div>

        <footer class="dr-foot">
          <div class="composer">
            <textarea
              ref="inputRef"
              v-model="draft"
              placeholder="问一个问题..."
              rows="1"
              :disabled="streaming"
              @keydown.enter.prevent="onEnter"
            ></textarea>
            <button class="send-btn" :disabled="!draft.trim() || streaming" @click="submit">
              <el-icon><Top /></el-icon>
            </button>
          </div>
          <div class="composer-meta">
            <span>{{ streaming ? '正在思考…' : '回车发送 · Shift+回车 换行' }}</span>
          </div>
        </footer>
      </aside>
    </transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Close, FullScreen, MagicStick, Top } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import { streamChat } from '../api/chat'

interface Msg {
  role: 'user' | 'assistant'
  content: string
  refs?: string[]
}

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const router = useRouter()
const bodyRef = ref<HTMLDivElement | null>(null)
const inputRef = ref<HTMLTextAreaElement | null>(null)
const draft = ref('')
const messages = ref<Msg[]>([])
const sessionId = ref<string | undefined>(undefined)
const streaming = ref(false)

const suggestions = [
  '团队最近做了什么？',
  '我们对 RAG 的思考',
  '昨天的会议要点',
]

const md = new MarkdownIt({ html: false, breaks: true, linkify: true })
function renderMarkdown(s: string) { return DOMPurify.sanitize(md.render(s)) }

watch(() => props.open, (v) => {
  if (v) nextTick(() => inputRef.value?.focus())
})

function onEnter(e: KeyboardEvent) {
  if (e.shiftKey) {
    draft.value += '\n'
    return
  }
  submit()
}

function ask(q: string) {
  draft.value = q
  submit()
}

function goFullChat() {
  router.push({ path: '/chat', query: messages.value.length ? { resume: sessionId.value || '' } : {} })
  emit('close')
}

async function submit() {
  const content = draft.value.trim()
  if (!content || streaming.value) return
  draft.value = ''
  messages.value.push({ role: 'user', content })
  messages.value.push({ role: 'assistant', content: '', refs: [] })
  scrollToBottom()
  streaming.value = true

  try {
    const res = await streamChat(content, sessionId.value)
    if (!res.body) throw new Error('No stream')
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let currentEvent = 'message'
    const last = messages.value[messages.value.length - 1]

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (line === '') { currentEvent = 'message'; continue }
        if (line.startsWith('event: ')) { currentEvent = line.slice(7).trim(); continue }
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6)
        if (currentEvent === 'done') {
          try {
            const info = JSON.parse(data)
            if (info.session_id) {
              sessionId.value = info.session_id
              localStorage.setItem('wiki_chat_session_id', info.session_id)
            }
            if (Array.isArray(info.sources)) last.refs = info.sources
          } catch { /* ignore */ }
        } else if (currentEvent === 'error') {
          last.content = (last.content || '') + '\n\n_服务暂时不可用，请稍后重试。_'
        } else {
          // 'message' event: raw text token
          last.content += data
          scrollToBottom()
        }
      }
    }
  } catch (e) {
    const last = messages.value[messages.value.length - 1]
    if (last) last.content = (last.content || '') + '\n\n_出错了，请稍后再试。_'
  } finally {
    streaming.value = false
    scrollToBottom()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (bodyRef.value) bodyRef.value.scrollTop = bodyRef.value.scrollHeight
  })
}
</script>

<style scoped>
.drawer-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(31, 28, 24, 0.18);
  z-index: 998;
  backdrop-filter: blur(2px);
}
.ai-drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 420px;
  max-width: 95vw;
  background: var(--paper);
  border-left: 1px solid var(--line);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  z-index: 999;
}

/* Animations */
.drawer-fade-enter-active, .drawer-fade-leave-active { transition: opacity 0.2s ease; }
.drawer-fade-enter-from, .drawer-fade-leave-to { opacity: 0; }
.drawer-slide-enter-active, .drawer-slide-leave-active { transition: transform 0.28s cubic-bezier(0.2, 0.8, 0.2, 1); }
.drawer-slide-enter-from, .drawer-slide-leave-to { transform: translateX(100%); }

/* Header */
.dr-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--line);
  flex-shrink: 0;
}
.dr-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-display);
  font-size: 18px;
  color: var(--ink);
}
.dr-spark { color: var(--accent-ink); }
.dr-actions { display: flex; gap: 4px; }
.ghost-btn {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border: none;
  background: transparent;
  border-radius: 6px;
  color: var(--ink-3);
  cursor: pointer;
  transition: all var(--transition);
}
.ghost-btn:hover { background: var(--paper-2); color: var(--ink); }

/* Body */
.dr-body {
  flex: 1;
  overflow-y: auto;
  padding: 18px 18px 12px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.dr-empty { display: flex; flex-direction: column; gap: 8px; }
.empty-kicker {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--ink-4);
  letter-spacing: 0.14em;
  margin-bottom: 4px;
}
.suggest-btn {
  text-align: left;
  padding: 10px 14px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 10px;
  color: var(--ink-2);
  font-size: 13.5px;
  cursor: pointer;
  font-family: var(--font-ui);
  transition: all var(--transition);
}
.suggest-btn:hover {
  background: var(--paper-3);
  border-color: var(--line-2);
  color: var(--ink);
}

/* Messages */
.msg {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.msg-role {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.14em;
  color: var(--ink-4);
  text-transform: uppercase;
}
.msg.user .msg-role { color: var(--accent-ink); }
.msg-text {
  font-size: 14px;
  line-height: 1.65;
  color: var(--ink);
}
.msg-text :deep(p) { margin: 0 0 8px; }
.msg-text :deep(p:last-child) { margin-bottom: 0; }
.msg-text :deep(code) {
  font-family: var(--font-mono);
  font-size: 12.5px;
  background: var(--paper-2);
  padding: 1px 5px;
  border-radius: 4px;
}
.msg-text :deep(pre) {
  background: var(--paper-2);
  padding: 10px 12px;
  border-radius: 8px;
  overflow-x: auto;
}
.msg.user .msg-text {
  padding: 10px 14px;
  background: var(--accent-soft);
  color: var(--accent-ink);
  border-radius: 10px;
  align-self: flex-end;
  max-width: 90%;
}

.msg-refs {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.refs-label {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--ink-4);
  letter-spacing: 0.1em;
  margin-right: 4px;
}
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

/* Footer */
.dr-foot {
  padding: 12px 16px 14px;
  border-top: 1px solid var(--line);
  background: var(--paper);
  flex-shrink: 0;
}
.composer {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 8px 8px 8px 12px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 12px;
  transition: border-color var(--transition);
}
.composer:focus-within { border-color: var(--line-2); }
.composer textarea {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  resize: none;
  font-size: 14px;
  font-family: var(--font-ui);
  color: var(--ink);
  line-height: 1.5;
  max-height: 140px;
  min-height: 22px;
}
.send-btn {
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
}
.send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.send-btn:hover:not(:disabled) { background: var(--ink-2); }

.composer-meta {
  margin-top: 6px;
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--ink-4);
}

@media (max-width: 480px) {
  .ai-drawer { width: 100vw; }
}
</style>
