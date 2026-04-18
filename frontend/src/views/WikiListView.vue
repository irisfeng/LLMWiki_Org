<template>
  <AppLayout>
    <div class="wiki-shell">
      <!-- Header strip -->
      <div class="header-strip">
        <span class="strip-crumb">知识库</span>
        <span class="strip-meta">· {{ pages.length }} 个页面</span>
        <div style="flex:1"></div>
        <div class="view-seg">
          <button :class="['seg-btn', { active: view === 'cards' }]" @click="view = 'cards'">卡片</button>
          <button :class="['seg-btn', { active: view === 'list' }]" @click="view = 'list'">列表</button>
        </div>
        <button class="new-btn" @click="openUploadModal">
          <el-icon><Plus /></el-icon>新建
        </button>
      </div>

      <div class="wiki-scroll">
        <div class="wiki-content">
          <!-- Hero -->
          <div class="hero">
            <div class="kicker">LIBRARY</div>
            <h1 class="display-title">
              整个<span class="display-accent">工作区</span>的知识
            </h1>
            <p class="display-sub">
              按 LLM-Wiki 范式组织：信息源是事实的来源、实体是被提及的人/事物、概念是跨文档抽象出的想法、分析是团队得出的结论。
            </p>
          </div>

          <!-- Stats strip (4 type cards) -->
          <div class="stats-strip">
            <button
              v-for="(s, i) in statCards"
              :key="s.k"
              class="stat-cell"
              :class="{ active: filter === s.k }"
              :data-last="i === 3"
              @click="setFilter(s.k)"
            >
              <div class="stat-row">
                <span class="stat-num">{{ s.count }}</span>
                <span class="type-pill" :data-type="s.k">{{ s.label }}</span>
              </div>
              <div class="stat-sub">{{ s.sub }}</div>
            </button>
          </div>

          <!-- Filter + sort bar -->
          <div class="filter-bar">
            <div class="tabs">
              <button
                v-for="t in filterTabs"
                :key="t.k"
                class="tab"
                :class="{ active: filter === t.k }"
                @click="setFilter(t.k)"
              >
                {{ t.label }}
                <span class="tab-count">{{ t.count }}</span>
              </button>
            </div>
            <div style="flex:1"></div>
            <span class="sort-label">排序</span>
            <button
              v-for="k in sortKeys"
              :key="k.k"
              class="sort-btn"
              :class="{ active: sort === k.k }"
              @click="sort = k.k as any"
            >{{ k.label }}</button>
          </div>

          <!-- Tag filter (shown when no search and tags exist) -->
          <div v-if="tags.length && !route.query.q" class="tag-row">
            <span class="tag-row-label">标签</span>
            <button
              v-for="t in tags.slice(0, 12)"
              :key="t.tag"
              class="tag-chip"
              :class="{ active: selectedTag === t.tag }"
              @click="toggleTag(t.tag)"
            >{{ t.tag }} <span class="tag-count">{{ t.count }}</span></button>
            <button v-if="selectedTag" class="tag-chip clear" @click="toggleTag('')">清除</button>
          </div>

          <!-- Loading skeleton -->
          <template v-if="loading">
            <div class="card-grid">
              <div v-for="i in 6" :key="i" class="card-skel">
                <el-skeleton animated :rows="3" />
              </div>
            </div>
          </template>

          <!-- Empty -->
          <template v-else-if="!filteredPages.length">
            <div class="empty-block">
              <p class="empty-text">没有找到相关内容{{ route.query.q ? `: "${route.query.q}"` : '' }}</p>
              <router-link to="/chat" class="empty-cta">
                <el-icon><ChatDotRound /></el-icon>
                试试在 AI 问答中提问
              </router-link>
            </div>
          </template>

          <!-- Card grid -->
          <div v-else-if="view === 'cards'" class="card-grid">
            <router-link
              v-for="p in pagedPages"
              :key="p.slug"
              :to="`/wiki/${p.slug}`"
              class="page-card"
            >
              <div class="card-head">
                <span class="type-pill" :data-type="p.type">{{ typeLabel(p.type) }}</span>
                <span v-if="p.type === 'source' && formatLabel(p.source_filename)" class="format-pill">
                  {{ formatLabel(p.source_filename) }}
                </span>
              </div>
              <div class="card-title">{{ p.title || p.slug }}</div>
              <div v-if="p.summary || p.frontmatter?.description" class="card-excerpt">
                {{ p.summary || p.frontmatter?.description }}
              </div>
              <div class="card-foot">
                <span>{{ formatDate(p.updated_at) }}</span>
                <span v-if="p.frontmatter?.tags?.length" class="card-tags">
                  {{ p.frontmatter.tags.slice(0, 2).join(' · ') }}
                </span>
              </div>
            </router-link>
          </div>

          <!-- List view -->
          <div v-else class="list-view">
            <router-link
              v-for="p in pagedPages"
              :key="p.slug"
              :to="`/wiki/${p.slug}`"
              class="list-row"
            >
              <span class="type-pill" :data-type="p.type">{{ typeLabel(p.type) }}</span>
              <span v-if="p.type === 'source' && formatLabel(p.source_filename)" class="format-pill">
                {{ formatLabel(p.source_filename) }}
              </span>
              <span class="row-title">{{ p.title || p.slug }}</span>
              <span class="row-tags">
                <span v-for="t in (p.frontmatter?.tags || []).slice(0, 3)" :key="t" class="row-tag">#{{ t }}</span>
              </span>
              <span class="row-date">{{ formatDate(p.updated_at) }}</span>
            </router-link>
          </div>

          <!-- Pagination -->
          <div v-if="totalPages > 1" class="pager">
            <button class="pg-btn" :disabled="currentPage <= 1" @click="currentPage--">‹ 上一页</button>
            <span class="pg-info">
              <span class="pg-cur">{{ currentPage }}</span>
              <span class="pg-sep">/</span>
              <span class="pg-total">{{ totalPages }}</span>
              <span class="pg-meta">· 共 {{ filteredPages.length }} 项</span>
            </span>
            <button class="pg-btn" :disabled="currentPage >= totalPages" @click="currentPage++">下一页 ›</button>
            <select v-model="pageSize" class="pg-size">
              <option :value="12">12 / 页</option>
              <option :value="24">24 / 页</option>
              <option :value="48">48 / 页</option>
              <option :value="96">96 / 页</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ChatDotRound, Plus } from '@element-plus/icons-vue'
import AppLayout from '../components/AppLayout.vue'
import { getPages, getTags, getStats } from '../api/wiki'
import { openUploadModal, registerUploadDone } from '../composables/useUploadModal'

const route = useRoute()
const router = useRouter()
const pages = ref<any[]>([])
const loading = ref(false)
const tags = ref<{ tag: string; count: number }[]>([])
const selectedTag = ref<string>('')
const stats = ref({ sources: 0, entities: 0, concepts: 0, analyses: 0, total: 0 })

const view = ref<'cards' | 'list'>('cards')
const sort = ref<'recent' | 'alpha' | 'health'>('recent')
const filter = ref<'all' | 'source' | 'entity' | 'concept' | 'analysis'>('all')

// Pagination
const currentPage = ref(1)
const pageSize = ref(24)

const typeMap: Record<string, string> = { source: '信息源', entity: '实体', concept: '概念', analysis: '分析' }
function typeLabel(t: string) { return typeMap[t] || t }

const formatMap: Record<string, string> = {
  pdf: 'PDF',
  doc: 'Word', docx: 'Word',
  ppt: 'PPT', pptx: 'PPT',
  xls: 'Excel', xlsx: 'Excel', csv: 'CSV',
  md: 'Markdown', markdown: 'Markdown',
  txt: 'TXT',
  html: 'HTML', htm: 'HTML',
  json: 'JSON',
  rtf: 'RTF',
  epub: 'EPUB',
}
function formatLabel(filename?: string | null): string {
  if (!filename) return ''
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  return formatMap[ext] || (ext ? ext.toUpperCase() : '')
}

const statCards = computed(() => [
  { k: 'source',   label: '信息源', count: stats.value.sources,  sub: '原始文档' },
  { k: 'entity',   label: '实体',   count: stats.value.entities, sub: '人 · 组织 · 物' },
  { k: 'concept',  label: '概念',   count: stats.value.concepts, sub: '抽象主题' },
  { k: 'analysis', label: '分析',   count: stats.value.analyses, sub: '团队结论' },
])

const filterTabs = computed(() => [
  { k: 'all',      label: '全部',   count: stats.value.total },
  { k: 'source',   label: '信息源', count: stats.value.sources },
  { k: 'entity',   label: '实体',   count: stats.value.entities },
  { k: 'concept',  label: '概念',   count: stats.value.concepts },
  { k: 'analysis', label: '分析',   count: stats.value.analyses },
])

const sortKeys = [
  { k: 'recent', label: '最近' },
  { k: 'alpha',  label: '字母' },
  { k: 'health', label: '健康度' },
]

const filteredPages = computed(() => {
  let arr = filter.value === 'all' ? pages.value : pages.value.filter((p) => p.type === filter.value)
  if (selectedTag.value) {
    arr = arr.filter((p) => Array.isArray(p.frontmatter?.tags) && p.frontmatter.tags.includes(selectedTag.value))
  }
  if (sort.value === 'alpha') {
    arr = [...arr].sort((a, b) => (a.title || a.slug).localeCompare(b.title || b.slug, 'zh'))
  } else if (sort.value === 'recent') {
    arr = [...arr].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
  }
  return arr
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredPages.value.length / pageSize.value)))
const pagedPages = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredPages.value.slice(start, start + pageSize.value)
})

// Reset to first page when filter/sort/tag/pageSize changes
watch([filter, selectedTag, sort, pageSize], () => { currentPage.value = 1 })
// Clamp current page if it overflows after filter change
watch(totalPages, (n) => { if (currentPage.value > n) currentPage.value = n })

function setFilter(k: string) {
  filter.value = k as any
  // sync URL for sharability
  if (k === 'all') router.push({ path: '/wiki' })
  else router.push({ path: '/wiki', query: { type: k } })
}

function toggleTag(tag: string) {
  // Pure client-side filter — no refetch needed
  selectedTag.value = selectedTag.value === tag ? '' : tag
}

function formatDate(s: string) {
  if (!s) return ''
  const d = new Date(s)
  const now = new Date()
  const diff = (now.getTime() - d.getTime()) / 1000
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}天前`
  return `${d.getMonth() + 1}/${d.getDate()}`
}

async function load() {
  loading.value = true
  if (route.query.q) selectedTag.value = ''
  try {
    // Fetch all pages once; filtering by type/tag happens client-side
    pages.value = await getPages(undefined, route.query.q as string)
  } catch {}
  loading.value = false
}

async function loadTags() {
  try { tags.value = await getTags() } catch {}
}

async function loadStats() {
  try { stats.value = await getStats() } catch {}
}

// Hydrate filter from URL on mount
onMounted(() => {
  const t = route.query.type as string
  if (t && ['source', 'entity', 'concept', 'analysis'].includes(t)) filter.value = t as any
  load(); loadTags(); loadStats()
})

// Refresh list when uploads complete
registerUploadDone(() => { load(); loadStats() })

watch(() => route.query.q, load)
watch(() => route.query.type, (t) => {
  filter.value = (t && ['source', 'entity', 'concept', 'analysis'].includes(t as string)) ? (t as any) : 'all'
})
</script>

<style scoped>
.wiki-shell {
  display: flex;
  flex-direction: column;
  min-height: 100%;
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
.view-seg {
  display: inline-flex;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 2px;
}
.seg-btn {
  padding: 4px 12px;
  font-size: 12px;
  background: transparent;
  border: none;
  color: var(--ink-3);
  border-radius: 6px;
  cursor: pointer;
  font-family: var(--font-ui);
}
.seg-btn.active { background: var(--paper); color: var(--ink); box-shadow: var(--shadow-sm); }
.new-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  background: var(--ink);
  color: var(--paper);
  border-radius: 7px;
  font-size: 12.5px;
  text-decoration: none;
  font-family: var(--font-ui);
  transition: background var(--transition);
}
.new-btn:hover { background: var(--ink-2); color: var(--paper); text-decoration: none; }
.strip-link {
  padding: 5px 12px;
  font-size: 12.5px; color: var(--ink-3);
  text-decoration: none;
  border: 1px solid var(--line); border-radius: 999px;
  transition: all var(--transition);
}
.strip-link:hover { color: var(--ink); background: var(--paper-2); text-decoration: none; }

/* Scroll body */
.wiki-scroll { flex: 1; }
.wiki-content {
  max-width: 1040px;
  margin: 0 auto;
  padding: 40px 36px 60px;
}

/* Hero */
.hero { margin-bottom: 28px; }
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
  font-size: clamp(36px, 4.5vw, 52px);
  line-height: 1.05;
  letter-spacing: -0.015em;
  margin: 0 0 10px;
  color: var(--ink);
}
.display-accent { font-style: italic; color: var(--accent-ink); }
.display-sub {
  font-size: 15px;
  color: var(--ink-3);
  max-width: 620px;
  line-height: 1.6;
  margin: 0;
}

/* Stats strip — 4 type cards */
.stats-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--paper-2);
  margin-bottom: 26px;
  overflow: hidden;
}
.stat-cell {
  padding: 18px 20px;
  background: transparent;
  border: none;
  border-right: 1px solid var(--line);
  cursor: pointer;
  text-align: left;
  color: var(--ink);
  transition: background var(--transition);
}
.stat-cell[data-last="true"] { border-right: none; }
.stat-cell:hover { background: var(--paper); }
.stat-cell.active { background: var(--paper); box-shadow: inset 0 -2px 0 var(--accent); }
.stat-row { display: flex; align-items: baseline; gap: 8px; }
.stat-num {
  font-family: var(--font-display);
  font-size: 34px;
  line-height: 1;
  font-weight: 400;
}
.stat-sub {
  margin-top: 8px;
  font-size: 12px;
  color: var(--ink-3);
  font-family: var(--font-mono);
}

/* Type pill */
.type-pill {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.04em;
  border-radius: 4px;
  border: 1px solid var(--line);
  color: var(--ink-3);
  background: var(--paper-2);
}
.type-pill[data-type="concept"]  { color: oklch(0.42 0.09 250); border-color: oklch(0.85 0.05 250); background: oklch(0.96 0.02 250); }
.type-pill[data-type="entity"]   { color: oklch(0.45 0.1 30);   border-color: oklch(0.86 0.06 30);  background: oklch(0.96 0.025 30); }
.type-pill[data-type="source"]   { color: oklch(0.42 0.09 150); border-color: oklch(0.85 0.05 150); background: oklch(0.96 0.02 150); }

/* Format pill (file type for source cards) */
.format-pill {
  display: inline-flex;
  align-items: center;
  padding: 1px 7px;
  margin-left: 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.04em;
  border-radius: 4px;
  border: 1px solid oklch(0.88 0.03 85);
  color: oklch(0.42 0.09 85);
  background: oklch(0.97 0.02 85);
}
.type-pill[data-type="analysis"] { color: oklch(0.42 0.09 320); border-color: oklch(0.85 0.05 320); background: oklch(0.96 0.02 320); }

/* Filter bar */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 18px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line);
  flex-wrap: wrap;
}
.tabs { display: inline-flex; gap: 4px; flex-wrap: wrap; }
.tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  font-size: 12.5px;
  border-radius: 999px;
  cursor: pointer;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink-2);
  font-family: var(--font-ui);
  transition: all var(--transition);
}
.tab.active { border-color: var(--ink); background: var(--ink); color: var(--paper); }
.tab-count { font-size: 10.5px; font-family: var(--font-mono); opacity: 0.7; }

.sort-label { font-size: 11.5px; color: var(--ink-4); font-family: var(--font-mono); }
.sort-btn {
  padding: 4px 10px;
  font-size: 12px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--ink-3);
  cursor: pointer;
  font-family: var(--font-ui);
}
.sort-btn.active { background: var(--paper-3); color: var(--ink); font-weight: 500; }

/* Tag row */
.tag-row { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 18px; }
.tag-row-label { font-family: var(--font-mono); font-size: 10.5px; color: var(--ink-4); margin-right: 4px; letter-spacing: 0.1em; }
.tag-chip {
  padding: 3px 10px;
  font-size: 11.5px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink-3);
  cursor: pointer;
  font-family: var(--font-ui);
  transition: all var(--transition);
}
.tag-chip:hover { border-color: var(--line-2); color: var(--ink-2); }
.tag-chip.active { border-color: var(--ink); background: var(--ink); color: var(--paper); }
.tag-chip.clear { color: oklch(0.5 0.13 25); border-color: oklch(0.85 0.06 25); }
.tag-count { font-family: var(--font-mono); opacity: 0.7; margin-left: 2px; }

/* Cards */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}
.page-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px 18px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 12px;
  text-decoration: none;
  color: var(--ink);
  transition: all var(--transition);
  min-height: 140px;
}
.page-card:hover {
  border-color: var(--line-2);
  background: var(--paper);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
  text-decoration: none;
}
.card-head { display: flex; align-items: center; gap: 8px; }
.card-title {
  font-size: 15.5px;
  font-weight: 500;
  color: var(--ink);
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-excerpt {
  font-size: 12.5px;
  color: var(--ink-3);
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
  padding-top: 6px;
  font-size: 11px;
  color: var(--ink-4);
  font-family: var(--font-mono);
}
.card-tags { color: var(--ink-3); }
.card-skel {
  padding: 16px 18px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 12px;
}

/* List view */
.list-view {
  border: 1px solid var(--line);
  border-radius: 12px;
  overflow: hidden;
  background: var(--paper-2);
}
.list-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 18px;
  border-bottom: 1px solid var(--line);
  text-decoration: none;
  color: var(--ink-2);
  transition: background var(--transition);
}
.list-row:last-child { border-bottom: none; }
.list-row:hover { background: var(--paper-3); text-decoration: none; }
.row-title {
  flex: 1;
  font-size: 14px;
  color: var(--ink);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row-tags { display: flex; gap: 4px; flex-shrink: 0; }
.row-tag {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--ink-4);
}
.row-date {
  font-size: 11px;
  color: var(--ink-4);
  font-family: var(--font-mono);
  flex-shrink: 0;
  min-width: 70px;
  text-align: right;
}

/* Pagination */
.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 28px 0 8px;
  flex-wrap: wrap;
}
.pg-btn {
  padding: 6px 14px;
  font-size: 13px;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 8px;
  color: var(--ink-2);
  cursor: pointer;
  font-family: var(--font-ui);
  transition: all var(--transition);
}
.pg-btn:hover:not(:disabled) {
  background: var(--paper-2);
  border-color: var(--line-2);
  color: var(--ink);
}
.pg-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.pg-info {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--ink-3);
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
}
.pg-cur { color: var(--ink); font-weight: 500; font-size: 14px; }
.pg-sep { color: var(--ink-4); }
.pg-total { color: var(--ink-2); }
.pg-meta { color: var(--ink-4); margin-left: 6px; }
.pg-size {
  padding: 5px 10px;
  font-size: 12.5px;
  font-family: var(--font-ui);
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 7px;
  color: var(--ink-2);
  cursor: pointer;
}

/* Empty state */
.empty-block {
  padding: 60px 20px;
  background: var(--paper-2);
  border: 1px dashed var(--line);
  border-radius: 12px;
  text-align: center;
}
.empty-text { color: var(--ink-3); margin-bottom: 16px; }
.empty-cta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  background: var(--ink);
  color: var(--paper);
  border-radius: 8px;
  text-decoration: none;
  font-size: 13px;
}
.empty-cta:hover { background: var(--ink-2); color: var(--paper); text-decoration: none; }

@media (max-width: 720px) {
  .stats-strip { grid-template-columns: repeat(2, 1fr); }
  .stat-cell { border-right: none; border-bottom: 1px solid var(--line); }
  .stat-cell[data-last="true"] { border-bottom: none; }
  .wiki-content { padding: 24px 18px 40px; }
}
</style>
