<template>
  <AppLayout>
    <div class="chat-page">
      <h2>AI 问答</h2>
      <div class="chat-container">
        <div class="messages" ref="messagesRef">
          <div v-for="(msg, i) in messages" :key="i" :class="['message', msg.role]">
            <div class="bubble">
              <MarkdownRenderer v-if="msg.role === 'assistant'" :content="msg.content" />
              <span v-else>{{ msg.content }}</span>
            </div>
          </div>
          <div v-if="streaming" class="message assistant">
            <div class="bubble">
              <MarkdownRenderer :content="streamContent" />
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
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import AppLayout from '../components/AppLayout.vue'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'
import { streamChat } from '../api/chat'

const input = ref('')
const messages = ref<Array<{ role: string; content: string }>>([])
const streaming = ref(false)
const streamContent = ref('')
const sessionId = ref<string | undefined>()
const messagesRef = ref<HTMLElement>()

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

async function sendMessage() {
  const text = input.value.trim()
  if (!text || streaming.value) return

  messages.value.push({ role: 'user', content: text })
  input.value = ''
  streaming.value = true
  streamContent.value = ''
  scrollToBottom()

  try {
    const response = await streamChat(text, sessionId.value)
    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          streamContent.value += data
          scrollToBottom()
        }
        if (line.startsWith('event: done')) {
          // Next data line has session info
        }
      }
    }

    messages.value.push({ role: 'assistant', content: streamContent.value })
    streamContent.value = ''
  } catch (err) {
    messages.value.push({ role: 'assistant', content: '抱歉，请求出错了。请稍后重试。' })
  }

  streaming.value = false
  scrollToBottom()
}
</script>

<style scoped>
.chat-page { max-width: 800px; margin: 0 auto; }
.chat-container { display: flex; flex-direction: column; height: calc(100vh - 200px); }
.messages { flex: 1; overflow-y: auto; padding: 16px 0; }
.message { margin-bottom: 16px; display: flex; }
.message.user { justify-content: flex-end; }
.message.assistant { justify-content: flex-start; }
.bubble { max-width: 80%; padding: 12px 16px; border-radius: 12px; line-height: 1.6; }
.message.user .bubble { background: #409eff; color: white; border-bottom-right-radius: 4px; }
.message.assistant .bubble { background: #f4f4f5; border-bottom-left-radius: 4px; }
.input-area { display: flex; padding-top: 12px; border-top: 1px solid #eee; }
.cursor { animation: blink 1s infinite; }
@keyframes blink { 0%, 50% { opacity: 1; } 51%, 100% { opacity: 0; } }
</style>
