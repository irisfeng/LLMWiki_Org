<template>
  <AppLayout>
    <div class="wiki-shell">
      <!-- Header strip -->
      <div class="header-strip">
        <span class="strip-link" @click="$router.push('/wiki')">知识库</span>
        <el-icon class="sep"><ArrowRight /></el-icon>
        <span v-if="page?.type" class="strip-link" @click="$router.push({ path: '/wiki', query: { type: page.type } })">{{ typeLabel(page.type) }}</span>
        <el-icon class="sep"><ArrowRight /></el-icon>
        <span class="strip-cur">{{ page?.title || (loading ? '加载中…' : '未找到') }}</span>
        <div style="flex:1"></div>
        <span class="health-pill">
          <el-icon><CircleCheck /></el-icon>
          健康 95
        </span>
        <button v-if="page && !editing" class="strip-btn" @click="downloadMarkdown">
          <el-icon><Download /></el-icon>
          {{ page.source ? '下载原文' : '下载 MD' }}
        </button>
        <button v-if="page && !editing" class="strip-btn" @click="editing = true">
          <el-icon><EditPen /></el-icon>
          编辑
        </button>
        <button v-if="page" class="strip-btn primary" @click="emitAskAI">
          <el-icon><MagicStick /></el-icon>
          问 AI
        </button>
      </div>

      <div class="page-scroll">
        <div class="page-content" v-if="page">
          <!-- Edit mode -->
          <WikiEditor
            v-if="editing"
            :content="page.content"
            :slug="page.slug"
            @saved="onSaved"
            @cancel="editing = false"
          />

          <!-- Read mode -->
          <template v-else>
            <!-- meta strip -->
            <div class="meta-row">
              <span class="type-pill" :data-type="page.type">{{ typeLabel(page.type) }}</span>
              <span class="meta-text">
                上传于 {{ formatDate(page.updated_at) }}
                <template v-if="page.frontmatter?.author"> · {{ page.frontmatter.author }}</template>
                <template v-else-if="page.source?.submitted_by"> · {{ page.source.submitted_by }}</template>
              </span>
            </div>

            <!-- Title (serif italic) -->
            <h1 class="display-title">{{ page.title }}</h1>
            <div v-if="subtitle" class="display-sub">{{ subtitle }}</div>

            <!-- Tags -->
            <div v-if="page.frontmatter?.tags?.length" class="tag-row">
              <span v-for="t in page.frontmatter.tags" :key="t" class="tag">#{{ t }}</span>
            </div>

            <!-- Source hero card (only for type=source with linked file) -->
            <div v-if="page.source" class="source-hero">
              <div class="hero-thumb" :data-ext="fileExt">
                <span class="thumb-label">{{ fileExt }}</span>
              </div>
              <div class="hero-meta">
                <div class="hero-kicker">ORIGINAL DOCUMENT</div>
                <div class="hero-filename">{{ page.source.filename }}</div>
                <div class="hero-stats">
                  <span v-if="readMin">约 {{ readMin }} 分钟阅读</span>
                  <span v-if="page.source.status">· {{ statusLabel(page.source.status) }}</span>
                  <span v-if="page.source.created_at">· 上传 {{ formatDate(page.source.created_at) }}</span>
                </div>
                <a class="hero-cta" :href="downloadUrl" target="_blank" rel="noopener">
                  下载原文
                  <el-icon><ArrowRight /></el-icon>
                </a>
              </div>
            </div>

            <!-- Body -->
            <div class="prose">
              <MarkdownRenderer :content="page.content" />
            </div>

            <!-- Connections (backlinks) -->
            <section v-if="page.backlinks?.length" class="connections">
              <div class="conn-head">反向链接 · {{ page.backlinks.length }}</div>
              <div class="conn-list">
                <router-link
                  v-for="bl in page.backlinks"
                  :key="bl.slug"
                  :to="`/wiki/${bl.slug}`"
                  class="conn-item"
                >
                  <span class="type-pill" :data-type="bl.type">{{ typeLabel(bl.type) }}</span>
                  <span class="conn-title">{{ bl.title }}</span>
                </router-link>
              </div>
            </section>
          </template>
        </div>

        <el-empty v-else-if="!loading" description="页面不存在" />
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import { Download, EditPen, ArrowRight, CircleCheck, MagicStick } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import AppLayout from '../components/AppLayout.vue'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'
import WikiEditor from '../components/WikiEditor.vue'
import { getPage, sourceDownloadUrl } from '../api/wiki'
import api from '../api/client'

const route = useRoute()
const page = ref<any>(null)
const loading = ref(true)
const editing = ref(false)

async function load() {
  loading.value = true
  const slug = route.params.slug as string
  try { page.value = await getPage(slug) } catch { page.value = null }
  loading.value = false
}

async function onSaved() {
  editing.value = false
  await load()
}

const fileExt = computed(() => {
  const fname = page.value?.source?.filename || ''
  const m = fname.match(/\.([a-zA-Z0-9]+)$/)
  return (m ? m[1] : 'FILE').toUpperCase()
})

const downloadUrl = computed(() => {
  if (page.value?.source?.id) return sourceDownloadUrl(page.value.source.id)
  return ''
})

const readMin = computed(() => {
  const c = (page.value?.content || '').length
  if (!c) return 0
  return Math.max(1, Math.round(c / 500))
})

const subtitle = computed(() => {
  const fm = page.value?.frontmatter || {}
  if (fm.subtitle) return fm.subtitle
  if (fm.author && fm.venue) return `${fm.author} · ${fm.venue}`
  if (fm.description) return fm.description
  return ''
})

function statusLabel(s: string) {
  return ({ pending: '待处理', processing: '处理中', completed: '已处理', failed: '处理失败' } as Record<string, string>)[s] || s
}

function typeLabel(type: string): string {
  return ({ source: '信息源', entity: '实体', concept: '概念', analysis: '分析' } as Record<string, string>)[type] || type
}

function formatDate(iso: string) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diff = (now.getTime() - d.getTime()) / 1000
  if (diff < 86400 && d.toDateString() === now.toDateString()) return '今天 ' + d.toTimeString().slice(0, 5)
  if (diff < 86400 * 7) return `${Math.max(1, Math.floor(diff / 86400))}天前`
  return d.toLocaleDateString('zh-CN')
}

async function downloadMarkdown() {
  if (!page.value) return
  // For source pages, prefer the original file
  if (page.value.source?.id) {
    window.open(sourceDownloadUrl(page.value.source.id), '_blank')
    return
  }
  try {
    const resp = await api.get(`/wiki/pages/${page.value.slug}/download`, { responseType: 'blob' })
    const blob = new Blob([resp.data], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${page.value.slug}.md`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    ElMessage.error('下载失败：' + (e?.message || '未知错误'))
  }
}

function emitAskAI() {
  // Simple keyboard-trigger to AppLayout's drawer (⌘J / Ctrl+J)
  window.dispatchEvent(new KeyboardEvent('keydown', { key: 'j', metaKey: true, ctrlKey: true }))
}

onMounted(load)
watch(() => route.params.slug, load)
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
  position: sticky;
  top: 0;
  z-index: 5;
}
.strip-link {
  color: var(--ink-3);
  font-size: 12.5px;
  cursor: pointer;
  font-family: var(--font-ui);
  transition: color var(--transition);
}
.strip-link:hover { color: var(--ink); }
.sep { color: var(--ink-4); font-size: 11px; }
.strip-cur {
  color: var(--ink);
  font-weight: 500;
  font-size: 12.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 360px;
}
.health-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  font-family: var(--font-mono);
  font-size: 11.5px;
  background: oklch(0.95 0.04 150);
  color: oklch(0.4 0.1 150);
  border-radius: 999px;
}
.strip-btn {
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
.strip-btn:hover { background: var(--paper-2); color: var(--ink); }
.strip-btn.primary { background: var(--accent-soft); color: var(--accent-ink); border-color: transparent; }
.strip-btn.primary:hover { background: oklch(0.92 0.035 150); }

/* Scroll body */
.page-scroll { flex: 1; }
.page-content {
  max-width: 760px;
  margin: 0 auto;
  padding: 48px 36px 80px;
}

/* Meta */
.meta-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}
.meta-text {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--ink-3);
}
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
.type-pill[data-type="analysis"] { color: oklch(0.42 0.09 320); border-color: oklch(0.85 0.05 320); background: oklch(0.96 0.02 320); }

/* Title */
.display-title {
  font-family: var(--font-display);
  font-weight: 400;
  font-size: clamp(34px, 4.2vw, 50px);
  line-height: 1.1;
  letter-spacing: -0.015em;
  margin: 0 0 10px;
  color: var(--ink);
}
.display-sub {
  font-family: var(--font-display);
  font-style: italic;
  font-size: 20px;
  color: var(--ink-3);
  margin-bottom: 22px;
  line-height: 1.4;
}

/* Tags */
.tag-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 26px; }
.tag {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--ink-3);
  padding: 2px 8px;
  border: 1px solid var(--line);
  border-radius: 999px;
}

/* Source hero card */
.source-hero {
  display: flex;
  gap: 22px;
  padding: 22px 24px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 14px;
  margin-bottom: 32px;
  transition: all var(--transition);
}
.source-hero:hover {
  border-color: var(--line-2);
  box-shadow: var(--shadow-md);
}
.hero-thumb {
  flex-shrink: 0;
  width: 88px;
  height: 112px;
  border-radius: 8px;
  background: var(--paper);
  border: 1px solid var(--line);
  display: grid;
  place-items: center;
  position: relative;
  overflow: hidden;
}
.hero-thumb::before {
  content: '';
  position: absolute;
  inset: 18px 12px;
  background: repeating-linear-gradient(
    to bottom,
    var(--line) 0,
    var(--line) 1px,
    transparent 1px,
    transparent 8px
  );
  opacity: 0.5;
}
.thumb-label {
  position: absolute;
  top: 6px;
  left: 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  background: oklch(0.55 0.18 25);
  color: var(--paper);
  border-radius: 4px;
  letter-spacing: 0.04em;
}
.hero-thumb[data-ext="DOCX"] .thumb-label { background: oklch(0.55 0.16 250); }
.hero-thumb[data-ext="PPTX"] .thumb-label,
.hero-thumb[data-ext="PPT"] .thumb-label { background: oklch(0.6 0.16 30); }
.hero-thumb[data-ext="XLSX"] .thumb-label { background: oklch(0.55 0.13 150); }
.hero-thumb[data-ext="MD"] .thumb-label   { background: var(--ink-3); }
.hero-thumb[data-ext="HTML"] .thumb-label { background: oklch(0.55 0.13 200); }

.hero-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 0;
}
.hero-kicker {
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.14em;
  color: var(--ink-4);
  text-transform: uppercase;
  margin-bottom: 6px;
}
.hero-filename {
  font-family: var(--font-mono);
  font-size: 15px;
  color: var(--ink);
  margin-bottom: 8px;
  word-break: break-all;
}
.hero-stats {
  font-size: 12px;
  color: var(--ink-3);
  margin-bottom: 10px;
}
.hero-stats span { margin-right: 4px; }
.hero-cta {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--accent-ink);
  text-decoration: none;
  font-weight: 500;
  font-family: var(--font-ui);
}
.hero-cta:hover { color: var(--ink); text-decoration: none; }

/* Prose */
.prose {
  font-size: 16px;
  line-height: 1.75;
  color: var(--ink-2);
}
.prose :deep(p) { margin: 0 0 18px; font-family: var(--font-ui); }
.prose :deep(h1) {
  font-family: var(--font-display);
  font-size: 32px;
  font-weight: 400;
  line-height: 1.2;
  letter-spacing: -0.01em;
  margin: 36px 0 14px;
  color: var(--ink);
}
.prose :deep(h2) {
  font-family: var(--font-display);
  font-size: 26px;
  font-weight: 400;
  line-height: 1.25;
  letter-spacing: -0.01em;
  margin: 32px 0 12px;
  color: var(--ink);
}
.prose :deep(h3) {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 400;
  line-height: 1.3;
  margin: 24px 0 10px;
  color: var(--ink);
}
.prose :deep(strong) { color: var(--ink); font-weight: 600; }
.prose :deep(a) {
  color: var(--accent-ink);
  text-decoration: none;
  border-bottom: 1px solid var(--accent-soft);
  transition: border-color var(--transition);
}
.prose :deep(a:hover) { border-bottom-color: var(--accent); }
.prose :deep(ul), .prose :deep(ol) { padding-left: 22px; margin: 0 0 18px; }
.prose :deep(li) { margin-bottom: 6px; line-height: 1.7; }
.prose :deep(code) {
  font-family: var(--font-mono);
  font-size: 13.5px;
  background: var(--paper-2);
  padding: 1px 6px;
  border-radius: 4px;
  color: var(--ink);
}
.prose :deep(pre) {
  background: var(--paper-2);
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid var(--line);
  overflow-x: auto;
  margin: 18px 0;
}
.prose :deep(blockquote) {
  margin: 18px 0;
  padding: 12px 18px;
  border-left: 3px solid var(--accent);
  background: var(--accent-soft);
  border-radius: 0 10px 10px 0;
  font-family: var(--font-display);
  font-style: italic;
  color: var(--accent-ink);
}
.prose :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 18px 0;
  font-size: 13.5px;
}
.prose :deep(th), .prose :deep(td) {
  padding: 8px 12px;
  border-bottom: 1px solid var(--line);
  text-align: left;
}
.prose :deep(th) {
  font-family: var(--font-mono);
  font-size: 11.5px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--ink-3);
}

/* Connections */
.connections {
  margin-top: 48px;
  padding-top: 22px;
  border-top: 1px solid var(--line);
}
.conn-head {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--ink-4);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  margin-bottom: 12px;
}
.conn-list { display: flex; flex-direction: column; gap: 2px; }
.conn-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 6px;
  text-decoration: none;
  color: var(--ink-2);
  transition: background var(--transition);
}
.conn-item:hover { background: var(--paper-2); text-decoration: none; }
.conn-title {
  font-size: 13.5px;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 720px) {
  .page-content { padding: 28px 18px 60px; }
  .source-hero { gap: 14px; padding: 16px 18px; }
  .hero-thumb { width: 64px; height: 80px; }
  .strip-cur { max-width: 160px; }
}
</style>
