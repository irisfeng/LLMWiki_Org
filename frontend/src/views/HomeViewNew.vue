<template>
  <AppLayout>
    <div class="home-page">
      <!-- ============ Section 1: Welcome + Search Hero ============ -->
      <section class="hero">
        <h1 class="hero-title">团队知识库</h1>
        <p class="hero-subtitle">上传文档，自动结构化，随时提问</p>

        <div class="hero-search-wrapper">
          <el-input
            v-model="searchInput"
            size="large"
            :placeholder="currentPlaceholder"
            class="hero-search"
            @keyup.enter="handleSearch"
            clearable
          >
            <template #prefix>
              <el-icon :size="18"><Search /></el-icon>
            </template>
          </el-input>
        </div>

        <div class="quick-actions">
          <router-link to="/submit" class="quick-card">
            <span class="quick-icon">📤</span>
            <span class="quick-label">上传文档</span>
          </router-link>
          <router-link to="/chat" class="quick-card">
            <span class="quick-icon">💬</span>
            <span class="quick-label">AI 问答</span>
          </router-link>
          <router-link to="/wiki" class="quick-card">
            <span class="quick-icon">📚</span>
            <span class="quick-label">浏览知识库</span>
          </router-link>
        </div>
      </section>

      <!-- ============ Section 2: Stats Row ============ -->
      <section class="stats-section">
        <template v-if="statsLoading">
          <div class="stats-row">
            <div v-for="i in 4" :key="i" class="stat-card">
              <el-skeleton animated :rows="0">
                <template #template>
                  <el-skeleton-item variant="circle" style="width: 36px; height: 36px" />
                  <el-skeleton-item variant="h1" style="width: 48px; height: 28px; margin-top: 10px" />
                  <el-skeleton-item variant="text" style="width: 40px; margin-top: 6px" />
                </template>
              </el-skeleton>
            </div>
          </div>
        </template>
        <template v-else>
          <div class="stats-row">
            <router-link
              v-for="s in statsCards"
              :key="s.label"
              :to="s.to"
              class="stat-card stat-card--clickable"
            >
              <el-icon class="stat-icon" :size="28" :style="{ color: s.color }">
                <component :is="s.icon" />
              </el-icon>
              <span class="stat-number">{{ s.value }}</span>
              <span class="stat-label">{{ s.label }}</span>
            </router-link>
          </div>
        </template>
      </section>

      <!-- ============ Section 3: Recent Updates ============ -->
      <section class="recent-section">
        <h2 class="section-title">最近更新</h2>

        <template v-if="pagesLoading">
          <div class="recent-skeleton">
            <el-skeleton v-for="i in 5" :key="i" animated :rows="0" style="margin-bottom: 16px">
              <template #template>
                <div style="display: flex; align-items: center; gap: 12px">
                  <el-skeleton-item variant="button" style="width: 50px; height: 22px" />
                  <el-skeleton-item variant="text" style="width: 200px" />
                  <el-skeleton-item variant="text" style="width: 60px; margin-left: auto" />
                </div>
              </template>
            </el-skeleton>
          </div>
        </template>

        <template v-else-if="recentPages.length === 0">
          <div class="empty-state">
            <el-empty :image-size="120" description="">
              <template #description>
                <p class="empty-text">还没有知识，上传第一份文档开始吧</p>
              </template>
              <router-link to="/submit">
                <el-button type="primary">
                  <el-icon style="margin-right: 4px"><Upload /></el-icon>
                  上传文档
                </el-button>
              </router-link>
            </el-empty>
          </div>
        </template>

        <template v-else>
          <div
            v-for="group in visibleGroups"
            :key="group.label"
            class="recent-group"
          >
            <div class="group-label">{{ group.label }}</div>
            <div class="recent-list">
              <div
                v-for="page in group.items"
                :key="page.id"
                class="recent-item"
              >
                <el-tag
                  size="small"
                  :type="typeTagStyle(page.type)"
                  class="recent-type-tag"
                >
                  {{ typeLabel(page.type) }}
                </el-tag>
                <router-link :to="`/wiki/${page.slug}`" class="recent-title">
                  {{ page.title || page.slug }}
                </router-link>
                <span class="recent-time">{{ relativeTime(page.updated_at) }}</span>
              </div>
            </div>
          </div>

          <div v-if="olderGroup && !showOlder" class="expand-wrapper">
            <el-button text type="primary" @click="showOlder = true">
              展开更早的更新 ({{ olderGroup.items.length }})
            </el-button>
          </div>
        </template>
      </section>

      <!-- ============ Section 4: Browse by Type ============ -->
      <section class="browse-section">
        <h2 class="section-title">按类型浏览</h2>

        <div class="browse-grid">
          <div
            v-for="bt in browseTypes"
            :key="bt.type"
            class="browse-card"
          >
            <router-link :to="`/wiki?type=${bt.type}`" class="browse-header">
              <span class="browse-type-name">{{ bt.label }}</span>
              <el-tag size="small" round>{{ bt.count }}</el-tag>
            </router-link>
            <div class="browse-list">
              <router-link
                v-for="page in bt.recentPages"
                :key="page.id"
                :to="`/wiki/${page.slug}`"
                class="browse-item"
              >
                {{ page.title || page.slug }}
              </router-link>
              <span v-if="bt.recentPages.length === 0" class="browse-empty">暂无内容</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../components/AppLayout.vue'
import { getStats, getRecentPages } from '../api/wiki'
import { Search, Document, User, Collection, FolderOpened, Upload } from '@element-plus/icons-vue'

// ---- Router ----
const router = useRouter()

// ---- Search with rotating placeholder ----
const searchInput = ref('')
const placeholders = [
  '搜索知识或直接提问...',
  'RAG 是什么？',
  '最近上传的文档讲了什么？',
  '帮我总结一下核心观点',
]
const placeholderIndex = ref(0)
let placeholderTimer: ReturnType<typeof setInterval> | null = null

const currentPlaceholder = computed(() => placeholders[placeholderIndex.value])

function startPlaceholderRotation() {
  placeholderTimer = setInterval(() => {
    placeholderIndex.value = (placeholderIndex.value + 1) % placeholders.length
  }, 3000)
}

function handleSearch() {
  const q = searchInput.value.trim()
  if (!q) return
  const isQuestion = q.includes('？') || q.includes('?') || q.length > 15
  if (isQuestion) {
    router.push({ path: '/chat', query: { q } })
  } else {
    router.push({ path: '/wiki', query: { q } })
  }
}

// ---- Stats ----
const stats = ref({ sources: 0, entities: 0, concepts: 0, analyses: 0 })
const statsLoading = ref(true)

const statsCards = computed(() => [
  { label: '信息源', value: stats.value.sources, icon: Document, color: 'var(--accent)', to: '/wiki?type=source' },
  { label: '实体', value: stats.value.entities, icon: User, color: 'var(--success)', to: '/wiki?type=entity' },
  { label: '概念', value: stats.value.concepts, icon: Collection, color: 'var(--warning)', to: '/wiki?type=concept' },
  { label: '文档总数', value: totalDocs.value, icon: FolderOpened, color: 'var(--info)', to: '/sources' },
])

const totalDocs = computed(() =>
  stats.value.sources + stats.value.entities + stats.value.concepts + (stats.value.analyses || 0)
)

// ---- Recent pages ----
interface WikiPage {
  id: number
  type: string
  slug: string
  title: string
  frontmatter?: Record<string, unknown>
  updated_at: string
}

const recentPages = ref<WikiPage[]>([])
const pagesLoading = ref(true)
const showOlder = ref(false)

function dayCategory(dateStr: string): 'today' | 'yesterday' | 'older' {
  const d = new Date(dateStr)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)

  if (d >= today) return 'today'
  if (d >= yesterday) return 'yesterday'
  return 'older'
}

interface PageGroup {
  label: string
  key: string
  items: WikiPage[]
}

const groupedPages = computed<PageGroup[]>(() => {
  const groups: Record<string, WikiPage[]> = { today: [], yesterday: [], older: [] }
  for (const page of recentPages.value) {
    groups[dayCategory(page.updated_at)].push(page)
  }
  const result: PageGroup[] = []
  if (groups.today.length > 0) result.push({ label: '今天', key: 'today', items: groups.today })
  if (groups.yesterday.length > 0) result.push({ label: '昨天', key: 'yesterday', items: groups.yesterday })
  if (groups.older.length > 0) result.push({ label: '更早', key: 'older', items: groups.older })
  return result
})

const olderGroup = computed(() => groupedPages.value.find(g => g.key === 'older'))

const visibleGroups = computed(() => {
  if (showOlder.value) return groupedPages.value
  return groupedPages.value.filter(g => g.key !== 'older')
})

// ---- Browse by type ----
const browseTypes = computed(() => {
  const types = [
    { type: 'source', label: '信息源', count: stats.value.sources },
    { type: 'entity', label: '实体', count: stats.value.entities },
    { type: 'concept', label: '概念', count: stats.value.concepts },
  ]
  return types.map(t => ({
    ...t,
    recentPages: recentPages.value
      .filter(p => p.type === t.type)
      .slice(0, 3),
  }))
})

// ---- Helpers ----
function typeLabel(type: string): string {
  const map: Record<string, string> = { source: '信息源', entity: '实体', concept: '概念', analysis: '分析' }
  return map[type] || type
}

function typeTagStyle(type: string): '' | 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, '' | 'success' | 'warning' | 'danger' | 'info'> = {
    source: '',
    entity: 'success',
    concept: 'warning',
    analysis: 'info',
  }
  return map[type] ?? 'info'
}

function relativeTime(dateStr: string): string {
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diff = now - then
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}天前`
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

// ---- Lifecycle ----
onMounted(async () => {
  startPlaceholderRotation()
  const [statsResult, pagesResult] = await Promise.allSettled([
    getStats(),
    getRecentPages(20),
  ])
  if (statsResult.status === 'fulfilled') stats.value = statsResult.value
  statsLoading.value = false
  if (pagesResult.status === 'fulfilled') recentPages.value = pagesResult.value
  pagesLoading.value = false
})

onUnmounted(() => {
  if (placeholderTimer) clearInterval(placeholderTimer)
})
</script>

<style scoped>
/* ===== Page container ===== */
.home-page {
  max-width: 860px;
  margin: 0 auto;
  padding: 0 0 48px;
}

/* ===== Section 1: Hero ===== */
.hero {
  text-align: center;
  padding: 48px 0 40px;
}

.hero-title {
  font-size: 2rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 8px;
  letter-spacing: -0.02em;
}

.hero-subtitle {
  font-size: 1.05rem;
  color: var(--text-secondary);
  margin: 0 0 28px;
}

.hero-search-wrapper {
  max-width: 560px;
  margin: 0 auto 32px;
}

.hero-search :deep(.el-input__wrapper) {
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm), 0 0 0 1px var(--border);
  padding: 4px 16px;
  transition: box-shadow var(--transition), border-color var(--transition);
}

.hero-search :deep(.el-input__wrapper:hover),
.hero-search :deep(.el-input__wrapper.is-focus) {
  box-shadow: var(--shadow-md), 0 0 0 1px var(--accent);
}

/* Quick actions */
.quick-actions {
  display: flex;
  justify-content: center;
  gap: 16px;
  flex-wrap: wrap;
}

.quick-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 20px 28px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  text-decoration: none;
  color: var(--text-primary);
  transition: box-shadow var(--transition), border-color var(--transition), transform var(--transition);
  min-width: 120px;
}

.quick-card:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--accent);
  transform: translateY(-2px);
  text-decoration: none;
}

.quick-icon {
  font-size: 1.6rem;
  line-height: 1;
}

.quick-label {
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.quick-card:hover .quick-label {
  color: var(--accent);
}

/* ===== Section 2: Stats ===== */
.stats-section {
  margin-bottom: 40px;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 20px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--transition), border-color var(--transition), transform var(--transition);
}

.stat-card--clickable {
  text-decoration: none;
  color: inherit;
  cursor: pointer;
}

.stat-card--clickable:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--accent);
  transform: translateY(-2px);
  text-decoration: none;
}

.stat-icon {
  opacity: 0.85;
}

.stat-number {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.1;
}

.stat-label {
  font-size: 0.82rem;
  color: var(--text-muted);
  font-weight: 500;
}

/* ===== Section 3: Recent Updates ===== */
.recent-section {
  margin-bottom: 40px;
}

.section-title {
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}

.recent-group {
  margin-bottom: 16px;
}

.group-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 8px;
}

.recent-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.recent-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  transition: background-color var(--transition);
}

.recent-item:hover {
  background-color: var(--bg-hover);
}

.recent-type-tag {
  flex-shrink: 0;
  min-width: 48px;
  text-align: center;
}

.recent-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary);
  font-size: 0.92rem;
  text-decoration: none;
}

.recent-title:hover {
  color: var(--accent);
  text-decoration: none;
}

.recent-time {
  flex-shrink: 0;
  font-size: 0.78rem;
  color: var(--text-muted);
}

.expand-wrapper {
  text-align: center;
  margin-top: 4px;
}

/* Empty state */
.empty-state {
  text-align: center;
  padding: 48px 20px;
  background: var(--bg-card);
  border: 1px dashed var(--border);
  border-radius: var(--radius-md);
}

.empty-state :deep(.el-empty__image) {
  margin-bottom: 8px;
}

.empty-text {
  color: var(--text-secondary);
  margin: 0 0 4px;
  font-size: 1rem;
  line-height: 1.6;
}

.empty-state a {
  text-decoration: none;
}

/* Skeleton */
.recent-skeleton {
  padding: 0 12px;
}

/* ===== Section 4: Browse by Type ===== */
.browse-section {
  margin-bottom: 20px;
}

.browse-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.browse-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  transition: box-shadow var(--transition), border-color var(--transition);
}

.browse-card:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--accent);
}

.browse-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-light);
  text-decoration: none;
  color: var(--text-primary);
  transition: background-color var(--transition);
}

.browse-header:hover {
  background-color: var(--bg-hover);
  text-decoration: none;
}

.browse-type-name {
  font-weight: 600;
  font-size: 0.95rem;
}

.browse-list {
  padding: 10px 16px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.browse-item {
  font-size: 0.88rem;
  color: var(--text-secondary);
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 4px 0;
  transition: color var(--transition);
}

.browse-item:hover {
  color: var(--accent);
  text-decoration: none;
}

.browse-empty {
  font-size: 0.85rem;
  color: var(--text-muted);
  font-style: italic;
}

/* ===== Responsive ===== */
@media (max-width: 768px) {
  .hero {
    padding: 32px 0 28px;
  }

  .hero-title {
    font-size: 1.6rem;
  }

  .quick-actions {
    flex-direction: column;
    align-items: center;
  }

  .quick-card {
    width: 100%;
    max-width: 280px;
    flex-direction: row;
    justify-content: center;
    padding: 14px 20px;
  }

  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }

  .browse-grid {
    grid-template-columns: 1fr;
  }

  .recent-time {
    display: none;
  }
}

@media (max-width: 480px) {
  .hero-subtitle {
    font-size: 0.95rem;
  }
}
</style>
