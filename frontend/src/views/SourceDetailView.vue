<template>
  <AppLayout>
    <div class="source-shell">
      <div class="header-strip">
        <router-link to="/wiki" class="strip-crumb-link">知识库</router-link>
        <span class="strip-sep">/</span>
        <span class="strip-crumb">信息源详情</span>
        <div style="flex:1"></div>
        <button class="strip-link" :disabled="!source" @click="doReingest">
          <el-icon><Refresh /></el-icon>重新解析
        </button>
        <button class="strip-link danger" :disabled="!source" @click="doDelete">
          <el-icon><Delete /></el-icon>删除
        </button>
      </div>

      <div class="source-scroll">
        <div class="source-content">
          <div v-if="loading" class="empty-card">加载中…</div>
          <div v-else-if="!source" class="empty-card">信息源不存在或已被删除</div>
          <template v-else>
            <!-- Hero -->
            <div class="source-hero">
              <div class="file-thumb" :data-kind="fileKind">
                <span class="file-ext">{{ fileExt }}</span>
                <div class="thumb-stripe"></div>
              </div>
              <div class="hero-main">
                <div class="kicker">SOURCE</div>
                <h1 class="hero-title">{{ source.filename }}</h1>
                <div class="hero-meta">
                  <span class="status-pill" :data-status="source.status">{{ statusLabel(source.status) }}</span>
                  <span>{{ formatDate(source.created_at) }}</span>
                  <span v-if="source.submitted_by">· {{ source.submitted_by }}</span>
                  <span v-if="source.generated_pages_count">
                    · 生成了 {{ source.generated_pages_count }} 个页面
                  </span>
                </div>
                <div v-if="source.error_message" class="hero-error">
                  ⚠️ {{ source.error_message }}
                </div>
                <div class="hero-actions">
                  <button
                    class="primary-btn"
                    :disabled="source.status !== 'done'"
                    @click="showPreview = !showPreview"
                  >
                    <el-icon><View /></el-icon>{{ showPreview ? '收起预览' : '预览原文' }}
                  </button>
                  <button class="ghost-btn" @click="download">
                    <el-icon><Download /></el-icon>下载原文
                  </button>
                </div>
              </div>
            </div>

            <!-- Preview pane -->
            <div v-if="showPreview" class="preview-block">
              <div class="sec-head">
                <span class="sec-kicker">PREVIEW</span>
                <span class="sec-title">原文内容</span>
                <div style="flex:1"></div>
                <span v-if="previewData?.truncated" class="sec-meta">
                  已截断（共 {{ Math.round((previewData?.total_length || 0) / 1000) }}K 字符）
                </span>
              </div>
              <div v-if="previewLoading" class="empty-card">加载中…</div>
              <div v-else-if="previewData" class="preview-content">
                <MarkdownRenderer :content="previewData.preview" new-tab />
              </div>
              <div v-else class="empty-card">无法预览该文档</div>
            </div>

            <!-- Generated pages -->
            <div class="pages-block">
              <div class="sec-head">
                <span class="sec-kicker">PAGES</span>
                <span class="sec-title">由此源生成的页面</span>
                <div style="flex:1"></div>
                <span class="sec-meta">{{ pages.length }} 条</span>
              </div>
              <div v-if="!pages.length" class="empty-card">
                {{ source.status === 'done' ? '未生成任何页面' : '等待解析完成后会在此显示' }}
              </div>
              <ul v-else class="pages-list">
                <li v-for="p in pages" :key="p.id" class="page-row">
                  <span class="type-pill" :data-type="p.type">{{ p.type }}</span>
                  <router-link :to="`/wiki/${p.slug}`" class="page-link">{{ p.title }}</router-link>
                  <span class="page-date">{{ formatDate(p.updated_at) }}</span>
                </li>
              </ul>
            </div>
          </template>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Delete, View, Download } from '@element-plus/icons-vue'
import AppLayout from '../components/AppLayout.vue'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'
import {
  getSource,
  getSourcePages,
  getSourcePreview,
  reingestSource,
  deleteSource,
} from '../api/sources'
import api from '../api/client'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const source = ref<any>(null)
const pages = ref<any[]>([])
const showPreview = ref(false)
const previewLoading = ref(false)
const previewData = ref<any>(null)

const fileExt = computed(() => {
  const n = source.value?.filename || ''
  const dot = n.lastIndexOf('.')
  return dot < 0 ? 'FILE' : n.slice(dot + 1).toUpperCase().slice(0, 4)
})
const fileKind = computed(() => {
  const ext = fileExt.value.toLowerCase()
  if (['pdf'].includes(ext)) return 'pdf'
  if (['md', 'txt'].includes(ext)) return 'text'
  if (['docx', 'doc'].includes(ext)) return 'word'
  if (['pptx', 'ppt'].includes(ext)) return 'ppt'
  if (['xlsx', 'xls', 'csv'].includes(ext)) return 'excel'
  if (['html', 'htm'].includes(ext)) return 'web'
  return 'other'
})

function statusLabel(s: string) {
  return { pending: '等待', processing: '处理中', done: '已完成', failed: '失败' }[s] || s
}
function formatDate(iso?: string) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) return `今天 ${d.toTimeString().slice(0, 5)}`
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

async function load() {
  const id = route.params.id as string
  loading.value = true
  try {
    const [s, p] = await Promise.all([getSource(id), getSourcePages(id)])
    source.value = s
    pages.value = p
  } catch (e: any) {
    source.value = null
    ElMessage.error('加载失败：' + (e?.response?.data?.detail || e?.message || '未知'))
  } finally {
    loading.value = false
  }
}

async function ensurePreview() {
  if (previewData.value || !source.value) return
  previewLoading.value = true
  try {
    previewData.value = await getSourcePreview(source.value.id)
  } catch (e: any) {
    ElMessage.error('预览失败：' + (e?.response?.data?.detail || e?.message || '未知'))
  } finally {
    previewLoading.value = false
  }
}

// Watch showPreview toggle
import { watch } from 'vue'
watch(showPreview, (v) => { if (v) ensurePreview() })

async function download() {
  try {
    const resp = await api.get(`/sources/${source.value.id}/file`, { responseType: 'blob' })
    const blob = new Blob([resp.data])
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = source.value.filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    ElMessage.error('下载失败：' + (e?.message || '未知'))
  }
}

async function doReingest() {
  try {
    await reingestSource(source.value.id)
    ElMessage.success('已重新加入处理队列')
    source.value.status = 'pending'
    setTimeout(load, 2000)
  } catch (e: any) {
    ElMessage.error('失败：' + (e?.response?.data?.detail || e?.message))
  }
}

async function doDelete() {
  let cascade = false
  try {
    await ElMessageBox.confirm(
      `确定删除「${source.value.filename}」？`,
      '删除确认',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
        message: h('div', null, [
          h('p', null, '删除后原始文件将被移除。'),
          h('p', { style: 'margin-top:8px' }, [
            h('label', { style: 'cursor:pointer;display:flex;align-items:center;gap:6px' }, [
              h('input', {
                type: 'checkbox',
                onChange: (e: Event) => { cascade = (e.target as HTMLInputElement).checked },
              }),
              '同时删除生成的知识页面',
            ]),
          ]),
        ]),
      },
    )
  } catch { return }
  try {
    const resp = await deleteSource(source.value.id, cascade)
    const msg = cascade && resp.deleted_pages
      ? `已删除文档及 ${resp.deleted_pages} 个关联页面`
      : '已删除文档'
    ElMessage.success(msg)
    router.push('/wiki')
  } catch (e: any) {
    ElMessage.error('删除失败：' + (e?.message || '未知'))
  }
}

onMounted(load)
</script>

<style scoped>
.source-shell { display: flex; flex-direction: column; height: 100%; background: var(--paper); }

.header-strip {
  position: sticky; top: 0; z-index: 10;
  display: flex; align-items: center; gap: 10px;
  padding: 11px 20px;
  background: color-mix(in srgb, var(--paper) 82%, transparent);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--line);
  font-size: 13px;
}
.strip-crumb-link { color: var(--ink-3); text-decoration: none; }
.strip-crumb-link:hover { color: var(--ink); }
.strip-sep { color: var(--ink-4); }
.strip-crumb { color: var(--ink); font-weight: 500; }
.strip-link {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 5px 12px; font-size: 12.5px; color: var(--ink-3);
  background: transparent; border: 1px solid var(--line);
  border-radius: 999px; cursor: pointer; transition: all .15s;
}
.strip-link:hover:not(:disabled) { color: var(--ink); background: var(--paper-2); }
.strip-link.danger:hover:not(:disabled) { color: oklch(0.50 0.15 25); border-color: oklch(0.80 0.10 25); }
.strip-link:disabled { opacity: 0.4; cursor: not-allowed; }

.source-scroll { flex: 1; overflow-y: auto; }
.source-content { max-width: 880px; margin: 0 auto; padding: 40px 36px 80px; }

.source-hero {
  display: grid; grid-template-columns: 140px 1fr; gap: 28px;
  padding: 28px; margin-bottom: 28px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 14px;
}
.file-thumb {
  position: relative; height: 160px;
  border-radius: 10px;
  background: var(--paper);
  border: 1px solid var(--line);
  display: grid; place-items: center;
  overflow: hidden;
}
.file-thumb[data-kind="pdf"] { background: oklch(0.97 0.02 25); border-color: oklch(0.85 0.08 25); }
.file-thumb[data-kind="word"] { background: oklch(0.97 0.02 250); border-color: oklch(0.85 0.08 250); }
.file-thumb[data-kind="ppt"] { background: oklch(0.97 0.02 60); border-color: oklch(0.85 0.08 60); }
.file-thumb[data-kind="excel"] { background: oklch(0.97 0.02 150); border-color: oklch(0.85 0.08 150); }
.thumb-stripe {
  position: absolute; top: 0; right: 12px; width: 2px; height: 100%;
  background: repeating-linear-gradient(
    to bottom,
    var(--line),
    var(--line) 6px,
    transparent 6px,
    transparent 12px
  );
}
.file-ext {
  font-family: var(--font-mono);
  font-size: 22px; font-weight: 600;
  color: var(--ink);
  letter-spacing: 0.04em;
}
.file-thumb[data-kind="pdf"] .file-ext { color: oklch(0.45 0.15 25); }
.file-thumb[data-kind="word"] .file-ext { color: oklch(0.45 0.15 250); }
.file-thumb[data-kind="ppt"] .file-ext { color: oklch(0.50 0.15 60); }
.file-thumb[data-kind="excel"] .file-ext { color: oklch(0.45 0.15 150); }

.hero-main { min-width: 0; }
.kicker {
  font-family: var(--font-mono); font-size: 11px;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--ink-4); margin-bottom: 8px;
}
.hero-title {
  font-family: var(--font-display); font-size: clamp(22px, 3vw, 30px);
  font-weight: 400; line-height: 1.2;
  color: var(--ink); margin: 0 0 12px;
  word-break: break-all;
}
.hero-meta {
  display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
  font-size: 12.5px; color: var(--ink-4); font-family: var(--font-mono);
  margin-bottom: 14px;
}
.hero-error {
  margin-bottom: 14px; padding: 10px 12px;
  background: oklch(0.97 0.03 25); color: oklch(0.45 0.15 25);
  border: 1px solid oklch(0.88 0.08 25); border-radius: 8px;
  font-size: 12.5px; line-height: 1.5;
}
.hero-actions { display: flex; gap: 8px; flex-wrap: wrap; }

.status-pill {
  display: inline-flex; align-items: center;
  padding: 2px 10px; font-size: 11px;
  border-radius: 999px; border: 1px solid var(--line);
  color: var(--ink-3);
}
.status-pill[data-status="done"] { border-color: oklch(0.85 0.08 150); color: oklch(0.45 0.12 150); background: oklch(0.97 0.02 150); }
.status-pill[data-status="processing"] { border-color: oklch(0.85 0.08 60); color: oklch(0.50 0.12 60); background: oklch(0.97 0.02 60); }
.status-pill[data-status="failed"] { border-color: oklch(0.85 0.10 25); color: oklch(0.50 0.15 25); background: oklch(0.97 0.03 25); }
.status-pill[data-status="pending"] { background: var(--paper); }

.primary-btn {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 8px 16px; background: var(--ink); color: var(--paper);
  border: none; border-radius: 999px;
  font-size: 13px; font-weight: 500; cursor: pointer;
  transition: opacity .15s;
}
.primary-btn:hover:not(:disabled) { opacity: 0.85; }
.primary-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.ghost-btn {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 8px 16px; background: var(--paper); color: var(--ink);
  border: 1px solid var(--line); border-radius: 999px;
  font-size: 13px; cursor: pointer; transition: all .15s;
}
.ghost-btn:hover { background: var(--paper-2); }

.sec-head {
  display: flex; align-items: baseline; gap: 10px;
  padding-bottom: 10px; margin-bottom: 12px;
  border-bottom: 1px solid var(--line);
}
.sec-kicker { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--ink-4); }
.sec-title { font-size: 15px; color: var(--ink); font-weight: 500; }
.sec-meta { font-size: 12px; color: var(--ink-4); font-family: var(--font-mono); }

.preview-block { margin-bottom: 32px; }
.preview-content {
  padding: 20px 24px; background: var(--paper-2);
  border: 1px solid var(--line); border-radius: 12px;
  line-height: 1.7; font-size: 14px;
}

.pages-block { margin-bottom: 24px; }
.pages-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 2px; }
.page-row {
  display: grid; grid-template-columns: auto 1fr auto; gap: 12px;
  align-items: center;
  padding: 10px 12px; border-radius: 8px;
  font-size: 13.5px;
}
.page-row:hover { background: var(--paper-2); }
.page-link { color: var(--ink); text-decoration: none; }
.page-link:hover { color: oklch(0.45 0.12 150); }
.page-date { color: var(--ink-4); font-family: var(--font-mono); font-size: 11.5px; }

.type-pill {
  display: inline-flex; align-items: center;
  padding: 2px 10px;
  font-family: var(--font-mono); font-size: 11px;
  border: 1px solid var(--line); border-radius: 999px;
  background: var(--paper);
}
.type-pill[data-type="concept"] { border-color: oklch(0.85 0.08 250); color: oklch(0.45 0.15 250); background: oklch(0.97 0.02 250); }
.type-pill[data-type="entity"] { border-color: oklch(0.85 0.08 30); color: oklch(0.50 0.15 30); background: oklch(0.97 0.02 30); }
.type-pill[data-type="source"] { border-color: oklch(0.85 0.08 150); color: oklch(0.45 0.15 150); background: oklch(0.97 0.02 150); }
.type-pill[data-type="analysis"] { border-color: oklch(0.85 0.08 320); color: oklch(0.45 0.15 320); background: oklch(0.97 0.02 320); }

.empty-card {
  padding: 32px; text-align: center;
  background: var(--paper-2); border: 1px dashed var(--line); border-radius: 12px;
  color: var(--ink-4); font-size: 13px;
}

@media (max-width: 720px) {
  .source-content { padding: 24px 18px 60px; }
  .source-hero { grid-template-columns: 1fr; padding: 20px; }
  .file-thumb { height: 120px; }
}
</style>
