<template>
  <AppLayout>
    <div class="home-shell">
      <!-- Top breadcrumb strip -->
      <div class="header-strip">
        <span class="strip-crumb">首页</span>
        <span class="strip-meta">· {{ userName }} · {{ weekday }}{{ daypart }}</span>
        <div style="flex:1"></div>
        <button class="ask-ai-btn" @click="goChat()">
          <el-icon><MagicStick /></el-icon>
          问 AI
        </button>
      </div>

      <div class="home-scroll">
        <div class="home-content">
          <!-- Greeting -->
          <div class="kicker">{{ weekdayUpper }} · {{ monthDay }}</div>
          <h1 class="display-title">
            {{ daypart }}好，<span class="display-accent">{{ userFirst }}</span>
          </h1>
          <div class="display-sub">
            团队今天新增 {{ todayAdded }} 份文档、{{ todayEdits }} 处编辑。下面是跟你最相关的。
          </div>

          <!-- Ask strip -->
          <div class="ask-strip" @click="focusAsk">
            <el-icon class="ask-icon"><MagicStick /></el-icon>
            <input
              ref="askInput"
              v-model="askQuery"
              placeholder="问一个问题或搜索..."
              class="ask-input"
              @keyup.enter="submitAsk"
            />
            <kbd class="kbd">⌘K</kbd>
          </div>

          <!-- Suggested questions -->
          <div class="chips">
            <button
              v-for="(s, i) in suggestions"
              :key="i"
              class="chip"
              @click="goChat(s)"
            >{{ s }}</button>
          </div>

          <!-- Two-col -->
          <div class="two-col">
            <section>
              <div class="sec-title">继续阅读</div>
              <button
                v-for="p in continueReading"
                :key="p.slug"
                class="row-btn"
                @click="openPage(p.slug)"
              >
                <span class="type-pill" :data-type="p.type">{{ typeLabel(p.type) }}</span>
                <span class="row-title">{{ p.title }}</span>
                <span class="row-meta">{{ formatTime(p.updated_at) }}</span>
              </button>
              <div v-if="!continueReading.length" class="empty">暂无最近阅读记录</div>
            </section>

            <section>
              <div class="sec-title">团队动态</div>
              <div
                v-for="(a, i) in activity"
                :key="i"
                class="activity-row"
                :class="{ 'with-divider': i < activity.length - 1 }"
              >
                <div class="avatar" :data-tone="a.tone">{{ a.initial }}</div>
                <div class="activity-text">
                  <b>{{ a.who }}</b>
                  <span class="muted"> {{ a.action }} </span>
                  <span class="strong">{{ a.target }}</span>
                </div>
                <span class="row-meta">{{ a.time }}</span>
              </div>
              <div v-if="!activity.length" class="empty">暂无团队动态</div>
            </section>
          </div>

          <!-- Stats strip -->
          <div class="stats-strip">
            <div v-for="s in statsCards" :key="s.label" class="stat-cell">
              <span class="stat-num">{{ s.value }}</span>
              <span class="stat-label">{{ s.label }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { MagicStick } from '@element-plus/icons-vue'
import AppLayout from '../components/AppLayout.vue'
import { getStats, getPages } from '../api/wiki'

const router = useRouter()
const askQuery = ref('')
const askInput = ref<HTMLInputElement | null>(null)

const stats = ref({ sources: 0, entities: 0, concepts: 0, analyses: 0, total: 0 })
const recentPages = ref<any[]>([])

// Greeting context
const now = new Date()
const userName = ref(localStorage.getItem('userName') || '同学')
const userFirst = computed(() => userName.value.slice(-2))

const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
const weekdaysUpper = ['SUNDAY', 'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY']
const weekday = weekdays[now.getDay()]
const weekdayUpper = weekdaysUpper[now.getDay()]
const monthDay = `${now.getMonth() + 1}月 ${now.getDate()}`

const daypart = computed(() => {
  const h = now.getHours()
  if (h < 6) return '凌晨'
  if (h < 11) return '早上'
  if (h < 13) return '中午'
  if (h < 18) return '下午'
  return '晚上'
})

const suggestions = ref([
  '团队最近三周做了什么？',
  '我们对 RAG 是如何思考的？',
  '昨天的会议纪要里有哪些待办？',
])

const continueReading = computed(() => recentPages.value.slice(0, 5))

const todayAdded = computed(() => {
  const today = now.toDateString()
  return recentPages.value.filter((p) => new Date(p.updated_at).toDateString() === today).length
})
const todayEdits = computed(() => Math.max(todayAdded.value * 2, 0))

const activity = computed(() => {
  return recentPages.value.slice(0, 5).map((p) => ({
    who: p.edited_by || '系统',
    initial: (p.edited_by || 'A').slice(-1),
    tone: 'normal' as const,
    action: '更新了',
    target: p.title,
    time: formatTime(p.updated_at),
  }))
})

const statsCards = computed(() => [
  { label: '信息源', value: stats.value.sources },
  { label: '实体', value: stats.value.entities },
  { label: '概念', value: stats.value.concepts },
  { label: '分析', value: stats.value.analyses },
])

function typeLabel(t: string) {
  return ({ source: '源', entity: '实体', concept: '概念', analysis: '分析' } as Record<string, string>)[t] || t
}

function formatTime(s: string) {
  if (!s) return ''
  const d = new Date(s)
  const diff = (now.getTime() - d.getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}天前`
  return `${d.getMonth() + 1}/${d.getDate()}`
}

function openPage(slug: string) {
  router.push(`/wiki/${slug}`)
}

function goChat(prefill?: string) {
  router.push({ path: '/chat', query: prefill ? { q: prefill } : {} })
}

function submitAsk() {
  if (askQuery.value.trim()) goChat(askQuery.value.trim())
}

function focusAsk() {
  askInput.value?.focus()
}

onMounted(async () => {
  try { stats.value = await getStats() } catch {}
  try { recentPages.value = await getPages() } catch {}
})
</script>

<style scoped>
.home-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--paper);
}

/* ---- Header strip ---- */
.header-strip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 20px;
  border-bottom: 1px solid var(--line);
  background: color-mix(in oklch, var(--paper) 82%, transparent);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  flex-shrink: 0;
}
.strip-crumb {
  color: var(--ink);
  font-weight: 500;
  font-size: 12.5px;
}
.strip-meta {
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--ink-4);
}
.ask-ai-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
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
.ask-ai-btn:hover {
  background: var(--accent-soft);
  color: var(--accent-ink);
  border-color: transparent;
}

/* ---- Scroll area ---- */
.home-scroll {
  flex: 1;
  overflow-y: auto;
}
.home-content {
  max-width: 960px;
  margin: 0 auto;
  padding: 48px 36px 60px;
}

/* ---- Greeting ---- */
.kicker {
  font-size: 10.5px;
  font-family: var(--font-mono);
  color: var(--ink-4);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.display-title {
  font-family: var(--font-display);
  font-weight: 400;
  font-size: clamp(40px, 5vw, 54px);
  line-height: 1.05;
  letter-spacing: -0.015em;
  margin: 0 0 12px;
  color: var(--ink);
}
.display-accent {
  font-style: italic;
  color: var(--accent-ink);
}
.display-sub {
  font-size: 15px;
  color: var(--ink-3);
  margin-bottom: 32px;
  max-width: 580px;
  line-height: 1.55;
}

/* ---- Ask strip ---- */
.ask-strip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  margin-bottom: 18px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 12px;
  cursor: text;
  transition: border-color var(--transition);
}
.ask-strip:hover {
  border-color: var(--line-2);
}
.ask-icon {
  color: var(--accent-ink);
  font-size: 16px;
}
.ask-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14.5px;
  color: var(--ink);
  font-family: var(--font-ui);
}
.kbd {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--ink-4);
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 4px;
  padding: 2px 5px;
}

/* ---- Chips ---- */
.chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 44px;
}
.chip {
  padding: 6px 12px;
  font-size: 12.5px;
  background: transparent;
  color: var(--ink-2);
  border: 1px solid var(--line);
  border-radius: 999px;
  cursor: pointer;
  font-family: var(--font-ui);
  transition: all var(--transition);
}
.chip:hover {
  background: var(--paper-2);
  border-color: var(--line-2);
  color: var(--ink);
}

/* ---- Two-col ---- */
.two-col {
  display: grid;
  grid-template-columns: 1.3fr 1fr;
  gap: 28px;
  margin-bottom: 44px;
}
@media (max-width: 720px) {
  .two-col { grid-template-columns: 1fr; }
}

.sec-title {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--ink-4);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  margin-bottom: 10px;
}

/* ---- Row buttons ---- */
.row-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 8px;
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  text-align: left;
  font-family: var(--font-ui);
  transition: background var(--transition);
}
.row-btn:hover {
  background: var(--paper-2);
}
.row-title {
  flex: 1;
  font-size: 14px;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row-meta {
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--ink-4);
}

/* Type pill */
.type-pill {
  display: inline-flex;
  align-items: center;
  padding: 1px 7px;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.04em;
  border-radius: 4px;
  border: 1px solid var(--line);
  color: var(--ink-3);
  background: var(--paper-2);
  flex-shrink: 0;
}
.type-pill[data-type="concept"] { color: oklch(0.42 0.09 250); border-color: oklch(0.85 0.05 250); background: oklch(0.96 0.02 250); }
.type-pill[data-type="entity"]  { color: oklch(0.45 0.1 30);   border-color: oklch(0.86 0.06 30);  background: oklch(0.96 0.025 30); }
.type-pill[data-type="source"]  { color: oklch(0.42 0.09 150); border-color: oklch(0.85 0.05 150); background: oklch(0.96 0.02 150); }
.type-pill[data-type="analysis"]{ color: oklch(0.42 0.09 320); border-color: oklch(0.85 0.05 320); background: oklch(0.96 0.02 320); }

/* ---- Activity ---- */
.activity-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 4px;
}
.activity-row.with-divider {
  border-bottom: 1px dashed var(--line);
}
.activity-text {
  flex: 1;
  font-size: 13px;
  color: var(--ink-2);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.activity-text b { font-weight: 500; }
.activity-text .muted { color: var(--ink-3); }
.activity-text .strong { color: var(--ink); }

.avatar {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--paper-3);
  color: var(--ink-2);
  display: grid;
  place-items: center;
  font-size: 10px;
  font-weight: 600;
  flex-shrink: 0;
}
.avatar[data-tone="warn"] {
  background: oklch(0.93 0.05 80);
  color: oklch(0.40 0.09 60);
}

.empty {
  font-size: 13px;
  color: var(--ink-4);
  padding: 12px 4px;
}

/* ---- Stats ---- */
.stats-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  padding-top: 28px;
  border-top: 1px solid var(--line);
}
.stat-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 12px 14px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 10px;
}
.stat-num {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 400;
  color: var(--ink);
  line-height: 1;
}
.stat-label {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--ink-4);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  margin-top: 6px;
}
@media (max-width: 720px) {
  .stats-strip { grid-template-columns: repeat(2, 1fr); }
}
</style>
