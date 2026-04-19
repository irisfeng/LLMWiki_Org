<template>
  <Teleport to="body">
    <transition name="cp-fade">
      <div v-if="open" class="cp-overlay" @mousedown.self="close">
        <div class="cp-panel" role="dialog" aria-label="命令面板">
          <div class="cp-search">
            <el-icon class="cp-search-icon"><Search /></el-icon>
            <input
              ref="inputRef"
              v-model="query"
              type="text"
              placeholder="搜索 · 跳转 · 提问 AI…"
              autocomplete="off"
              spellcheck="false"
              @keydown="onKeydown"
            />
            <kbd class="cp-esc">ESC</kbd>
          </div>

          <div class="cp-body" ref="bodyRef">
            <!-- 跳转 -->
            <section v-if="visibleJumps.length" class="cp-section">
              <div class="cp-section-title">跳转</div>
              <button
                v-for="(item, i) in visibleJumps"
                :key="'j-' + item.slug"
                :class="['cp-item', { active: activeIndex === jumpIdx(i) }]"
                @mouseenter="activeIndex = jumpIdx(i)"
                @click="runItem(flatItems[jumpIdx(i)])"
              >
                <el-icon class="cp-item-icon"><Document /></el-icon>
                <span class="cp-item-title">{{ item.title }}</span>
                <span class="cp-item-meta">{{ typeLabel(item.type) }} · {{ item.snippet ? '匹配' : '页面' }}</span>
              </button>
            </section>

            <!-- 操作 -->
            <section v-if="visibleActions.length" class="cp-section">
              <div class="cp-section-title">操作</div>
              <button
                v-for="(a, i) in visibleActions"
                :key="'a-' + a.id"
                :class="['cp-item', { active: activeIndex === actionIdx(i) }]"
                @mouseenter="activeIndex = actionIdx(i)"
                @click="runItem(flatItems[actionIdx(i)])"
              >
                <el-icon class="cp-item-icon"><component :is="a.icon" /></el-icon>
                <span class="cp-item-title">{{ a.title }}</span>
                <span class="cp-item-meta">{{ a.hint || '' }}</span>
              </button>
            </section>

            <!-- 最近 -->
            <section v-if="visibleRecents.length && !query.trim()" class="cp-section">
              <div class="cp-section-title">最近</div>
              <button
                v-for="(r, i) in visibleRecents"
                :key="'r-' + r.slug"
                :class="['cp-item', { active: activeIndex === recentIdx(i) }]"
                @mouseenter="activeIndex = recentIdx(i)"
                @click="runItem(flatItems[recentIdx(i)])"
              >
                <el-icon class="cp-item-icon"><Clock /></el-icon>
                <span class="cp-item-title">{{ r.title }}</span>
                <span class="cp-item-meta">{{ typeLabel(r.type) }}</span>
              </button>
            </section>

            <div v-if="!flatItems.length" class="cp-empty">
              <div class="cp-empty-title">没有找到结果</div>
              <div class="cp-empty-hint">按 Enter 将 “{{ query }}” 发送给 AI</div>
            </div>
          </div>

          <div class="cp-footer">
            <span><kbd>↵</kbd> 打开</span>
            <span><kbd>↑</kbd><kbd>↓</kbd> 选择</span>
            <span><kbd>esc</kbd> 关闭</span>
            <span class="cp-footer-right">TeamWiki</span>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Search, Document, Clock, Plus, Upload, Share, DataAnalysis, MagicStick } from '@element-plus/icons-vue'
import { getPages } from '../api/wiki'
import { openUploadModal } from '../composables/useUploadModal'

interface PageHit {
  slug: string
  title: string
  type: string
  snippet?: string
}
interface ActionItem {
  id: string
  title: string
  hint?: string
  icon: any
  run: () => void
}
type FlatItem =
  | { kind: 'jump'; data: PageHit }
  | { kind: 'action'; data: ActionItem }
  | { kind: 'recent'; data: PageHit }

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'ask-ai', q: string): void }>()

const router = useRouter()
const query = ref('')
const results = ref<PageHit[]>([])
const recents = ref<PageHit[]>([])
const activeIndex = ref(0)
const inputRef = ref<HTMLInputElement | null>(null)
const bodyRef = ref<HTMLElement | null>(null)
let searchTimer: number | undefined

function typeLabel(t: string) {
  return { source: '来源', entity: '实体', concept: '概念', analysis: '分析' }[t] || t
}

function close() {
  emit('close')
}

const actions = computed<ActionItem[]>(() => {
  const q = query.value.trim()
  const list: ActionItem[] = []
  if (q) {
    list.push({
      id: 'ask-ai',
      title: `向 AI 提问：“${q}”`,
      hint: '↵',
      icon: MagicStick,
      run: () => {
        emit('ask-ai', q)
        close()
      },
    })
  }
  list.push(
    { id: 'upload', title: '上传文档 / 新建页面', hint: '', icon: Upload, run: () => { close(); openUploadModal() } },
    { id: 'graph', title: '查看关系图谱', hint: '', icon: Share, run: () => { close(); router.push('/graph') } },
    { id: 'lint', title: '健康检查', hint: '', icon: DataAnalysis, run: () => { close(); router.push('/lint') } },
  )
  return list
})

const visibleJumps = computed(() => results.value)
const visibleActions = computed(() => actions.value)
const visibleRecents = computed(() => (query.value.trim() ? [] : recents.value.slice(0, 5)))

const flatItems = computed<FlatItem[]>(() => [
  ...visibleJumps.value.map((p) => ({ kind: 'jump' as const, data: p })),
  ...visibleActions.value.map((a) => ({ kind: 'action' as const, data: a })),
  ...visibleRecents.value.map((p) => ({ kind: 'recent' as const, data: p })),
])

function jumpIdx(i: number) { return i }
function actionIdx(i: number) { return visibleJumps.value.length + i }
function recentIdx(i: number) { return visibleJumps.value.length + visibleActions.value.length + i }

function runItem(item: FlatItem | undefined) {
  if (!item) return
  if (item.kind === 'jump' || item.kind === 'recent') {
    close()
    router.push(`/wiki/${item.data.slug}`)
  } else {
    item.data.run()
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') { e.preventDefault(); close(); return }
  const len = flatItems.value.length
  if (e.key === 'ArrowDown') { e.preventDefault(); activeIndex.value = (activeIndex.value + 1) % Math.max(1, len); scrollActiveIntoView(); return }
  if (e.key === 'ArrowUp') { e.preventDefault(); activeIndex.value = (activeIndex.value - 1 + len) % Math.max(1, len); scrollActiveIntoView(); return }
  if (e.key === 'Enter') {
    e.preventDefault()
    if (!len && query.value.trim()) {
      emit('ask-ai', query.value.trim())
      close()
      return
    }
    runItem(flatItems.value[activeIndex.value])
  }
}

function scrollActiveIntoView() {
  nextTick(() => {
    const el = bodyRef.value?.querySelector('.cp-item.active') as HTMLElement | null
    el?.scrollIntoView({ block: 'nearest' })
  })
}

async function doSearch(q: string) {
  if (!q.trim()) { results.value = []; return }
  try {
    const data = await getPages(undefined, q)
    results.value = (Array.isArray(data) ? data : []).slice(0, 8)
  } catch { results.value = [] }
}

async function loadRecents() {
  try {
    const data = await getPages()
    recents.value = (Array.isArray(data) ? data : []).slice(0, 5)
  } catch { recents.value = [] }
}

watch(query, (q) => {
  activeIndex.value = 0
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => doSearch(q), 180)
})

watch(
  () => props.open,
  async (v) => {
    if (v) {
      query.value = ''
      results.value = []
      activeIndex.value = 0
      await loadRecents()
      nextTick(() => inputRef.value?.focus())
    }
  },
)
</script>

<style scoped>
.cp-overlay {
  position: fixed;
  inset: 0;
  background: rgba(10, 10, 14, 0.42);
  backdrop-filter: blur(4px);
  z-index: 2000;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding-top: 14vh;
}
.cp-panel {
  width: min(640px, 92vw);
  background: var(--el-bg-color, #fff);
  border: 1px solid var(--el-border-color-light, #e4e7ed);
  border-radius: 12px;
  box-shadow: 0 20px 60px -10px rgba(0, 0, 0, 0.3), 0 2px 8px rgba(0, 0, 0, 0.08);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: 68vh;
}
.cp-search {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
}
.cp-search-icon { color: var(--el-text-color-secondary, #909399); font-size: 18px; }
.cp-search input {
  flex: 1;
  font-size: 15px;
  background: transparent;
  border: 0;
  outline: 0;
  color: var(--el-text-color-primary, #303133);
}
.cp-esc {
  font: 500 11px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
  padding: 3px 6px;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 4px;
  color: var(--el-text-color-secondary, #909399);
}
.cp-body { overflow-y: auto; padding: 6px 0; }
.cp-section { padding: 4px 0 10px; }
.cp-section-title {
  padding: 8px 16px 6px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--el-text-color-secondary, #909399);
  text-transform: uppercase;
}
.cp-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 9px 16px;
  background: transparent;
  border: 0;
  cursor: pointer;
  text-align: left;
  color: var(--el-text-color-primary, #303133);
  font-size: 14px;
}
.cp-item.active { background: var(--el-fill-color-light, #f5f7fa); }
.cp-item-icon { color: var(--el-text-color-secondary, #909399); font-size: 16px; }
.cp-item-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cp-item-meta {
  font-size: 12px;
  color: var(--el-text-color-placeholder, #a8abb2);
  flex-shrink: 0;
}
.cp-empty { padding: 32px 16px; text-align: center; }
.cp-empty-title { font-size: 14px; color: var(--el-text-color-regular, #606266); margin-bottom: 4px; }
.cp-empty-hint { font-size: 12px; color: var(--el-text-color-placeholder, #a8abb2); }
.cp-footer {
  display: flex;
  gap: 14px;
  padding: 8px 16px;
  border-top: 1px solid var(--el-border-color-lighter, #ebeef5);
  font-size: 11px;
  color: var(--el-text-color-secondary, #909399);
  background: var(--el-fill-color-lighter, #fafafa);
}
.cp-footer kbd {
  display: inline-block;
  min-width: 16px;
  padding: 1px 5px;
  margin-right: 4px;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 3px;
  font: 500 10px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace;
  background: var(--el-bg-color, #fff);
}
.cp-footer-right { margin-left: auto; }

.cp-fade-enter-active, .cp-fade-leave-active { transition: opacity 0.12s ease; }
.cp-fade-enter-from, .cp-fade-leave-to { opacity: 0; }
.cp-fade-enter-active .cp-panel, .cp-fade-leave-active .cp-panel {
  transition: transform 0.14s ease, opacity 0.14s ease;
}
.cp-fade-enter-from .cp-panel, .cp-fade-leave-to .cp-panel {
  transform: translateY(-6px) scale(0.99);
  opacity: 0;
}
</style>
