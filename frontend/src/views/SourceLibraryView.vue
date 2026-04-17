<template>
  <AppLayout>
    <div class="sources-page">
      <el-breadcrumb separator="/" class="page-breadcrumb">
        <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
        <el-breadcrumb-item>文档管理</el-breadcrumb-item>
      </el-breadcrumb>

      <div class="page-header">
        <h2>文档库</h2>
        <div class="header-actions">
          <el-button :icon="Refresh" @click="load" :loading="loading">刷新</el-button>
          <router-link to="/submit">
            <el-button type="primary" :icon="Plus">上传新文档</el-button>
          </router-link>
        </div>
      </div>

      <div class="filters">
        <el-radio-group v-model="typeFilter" size="default" @change="onFilterChange">
          <el-radio-button label="">全部 ({{ sources.length }})</el-radio-button>
          <el-radio-button
            v-for="t in availableTypes"
            :key="t.key"
            :label="t.key"
          >{{ t.label }} ({{ t.count }})</el-radio-button>
        </el-radio-group>
        <div class="filters-right">
          <el-radio-group v-model="statusFilter" size="default" @change="onFilterChange">
            <el-radio-button label="">全部状态</el-radio-button>
            <el-radio-button label="done">已处理</el-radio-button>
            <el-radio-button label="processing">处理中</el-radio-button>
            <el-radio-button label="pending">待处理</el-radio-button>
            <el-radio-button label="failed">失败</el-radio-button>
          </el-radio-group>
        </div>
      </div>

      <div class="search-bar">
        <el-input
          v-model="searchQuery"
          :prefix-icon="Search"
          placeholder="搜索文件名..."
          clearable
          style="max-width: 400px"
        />
        <div class="search-meta" v-if="filtered.length !== sources.length">
          共 {{ sources.length }} 个文档，筛选出 {{ filtered.length }} 个
        </div>
      </div>

      <!-- Skeleton loading state -->
      <template v-if="loading">
        <div class="source-skeleton">
          <el-skeleton v-for="i in 4" :key="i" animated :rows="0" style="margin-bottom: 12px">
            <template #template>
              <div class="skeleton-card">
                <el-skeleton-item variant="rect" style="width: 48px; height: 48px; border-radius: 10px" />
                <div class="skeleton-card-body">
                  <el-skeleton-item variant="h3" style="width: 200px; height: 18px" />
                  <div style="display: flex; gap: 8px; margin-top: 8px">
                    <el-skeleton-item variant="button" style="width: 50px; height: 20px" />
                    <el-skeleton-item variant="button" style="width: 50px; height: 20px" />
                    <el-skeleton-item variant="text" style="width: 80px" />
                  </div>
                </div>
                <div style="display: flex; gap: 6px; margin-left: auto">
                  <el-skeleton-item variant="button" style="width: 64px; height: 28px" />
                  <el-skeleton-item variant="button" style="width: 80px; height: 28px" />
                </div>
              </div>
            </template>
          </el-skeleton>
        </div>
      </template>

      <!-- Empty state -->
      <template v-else-if="!filtered.length">
        <div class="empty-state" v-if="sources.length === 0">
          <el-empty :image-size="120" description="">
            <template #description>
              <p class="empty-text">还没有文档，上传一份试试</p>
            </template>
            <router-link to="/submit">
              <el-button type="primary">
                <el-icon style="margin-right: 4px"><Plus /></el-icon>
                上传文档
              </el-button>
            </router-link>
          </el-empty>
        </div>
        <div class="empty-state" v-else>
          <el-empty :image-size="100" description="">
            <template #description>
              <p class="empty-text">没有匹配的文档，试试调整筛选条件</p>
            </template>
          </el-empty>
        </div>
      </template>

      <div v-else class="source-list">
        <div v-for="s in filtered" :key="s.id" class="source-card">
          <div class="source-icon" :style="{ background: typeMeta(s).color }">
            {{ typeMeta(s).emoji }}
          </div>
          <div class="source-main">
            <div class="source-title" :title="s.filename">{{ s.filename }}</div>
            <div class="source-meta">
              <el-tag size="small" :type="typeMeta(s).tagType" effect="plain">
                {{ typeMeta(s).label }}
              </el-tag>
              <el-tag size="small" :type="statusTagType(s.status)" effect="dark">
                {{ statusLabel(s.status) }}
              </el-tag>
              <span class="muted">{{ formatDate(s.created_at) }}</span>
              <span v-if="s.submitted_by" class="muted">· {{ s.submitted_by }}</span>
              <span v-if="s.generated_pages_count" class="pages-badge" @click="viewPages(s)">
                生成了 {{ s.generated_pages_count }} 个页面
              </span>
            </div>
            <div v-if="s.error_message" class="err-msg">⚠️ {{ s.error_message }}</div>
          </div>
          <div class="source-actions">
            <el-button size="small" :icon="Download" @click="download(s)">下载</el-button>
            <el-button
              size="small"
              :icon="Refresh"
              @click="reingest(s)"
              :disabled="s.status === 'processing'"
            >重新解析</el-button>
            <el-popconfirm
              title="确定删除这个文档？生成的 wiki 页面会保留但失去关联。"
              confirm-button-text="删除"
              cancel-button-text="取消"
              @confirm="doDelete(s)"
            >
              <template #reference>
                <el-button size="small" type="danger" :icon="Delete" plain>删除</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </div>
    </div>

    <el-drawer
      v-model="pagesDrawerOpen"
      :title="`${currentSource?.filename || ''} 生成的 ${generatedPages.length} 个页面`"
      direction="rtl"
      size="420px"
    >
      <el-empty v-if="!generatedPages.length" description="还没有生成的页面" />
      <ul v-else class="gen-page-list">
        <li v-for="p in generatedPages" :key="p.id" class="gen-page-item">
          <el-tag size="small" effect="plain">{{ p.type }}</el-tag>
          <router-link :to="`/wiki/${p.slug}`" class="gen-page-link" @click="pagesDrawerOpen = false">
            {{ p.title }}
          </router-link>
        </li>
      </ul>
    </el-drawer>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Download, Plus, Search, Delete } from '@element-plus/icons-vue'
import AppLayout from '../components/AppLayout.vue'
import { listSources, deleteSource, reingestSource, getSourcePages } from '../api/sources'
import api from '../api/client'

interface Source {
  id: string
  filename: string
  file_path: string | null
  status: 'pending' | 'processing' | 'done' | 'failed'
  error_message: string | null
  submitted_by: string | null
  created_at: string
  processed_at: string | null
  generated_pages_count: number
}

const sources = ref<Source[]>([])
const loading = ref(false)
const typeFilter = ref('')
const statusFilter = ref('')
const searchQuery = ref('')

const pagesDrawerOpen = ref(false)
const currentSource = ref<Source | null>(null)
const generatedPages = ref<any[]>([])

function detectType(s: Source): { key: string; label: string; emoji: string; color: string; tagType: string } {
  const name = (s.filename || '').toLowerCase()
  const ext = name.includes('.') ? name.split('.').pop() : ''
  if (name.startsWith('http://') || name.startsWith('https://')) {
    return { key: 'url', label: '网页', emoji: '🌐', color: '#ecf5ff', tagType: 'primary' }
  }
  if (ext === 'pdf') return { key: 'pdf', label: 'PDF', emoji: '📕', color: '#fef0f0', tagType: 'danger' }
  if (['doc', 'docx'].includes(ext!)) return { key: 'word', label: 'Word', emoji: '📘', color: '#ecf5ff', tagType: 'primary' }
  if (['ppt', 'pptx'].includes(ext!)) return { key: 'ppt', label: 'PPT', emoji: '📙', color: '#fdf6ec', tagType: 'warning' }
  if (['xls', 'xlsx', 'csv'].includes(ext!)) return { key: 'excel', label: 'Excel', emoji: '📗', color: '#f0f9eb', tagType: 'success' }
  if (ext === 'md') return { key: 'md', label: 'Markdown', emoji: '📝', color: '#f4f4f5', tagType: 'info' }
  if (ext === 'txt') return { key: 'txt', label: '文本', emoji: '📄', color: '#f4f4f5', tagType: 'info' }
  if (['html', 'htm'].includes(ext!)) return { key: 'html', label: '网页', emoji: '🌐', color: '#ecf5ff', tagType: 'primary' }
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext!)) return { key: 'image', label: '图片', emoji: '🖼', color: '#fdf6ec', tagType: 'warning' }
  return { key: 'other', label: '其他', emoji: '📎', color: '#f4f4f5', tagType: 'info' }
}

function typeMeta(s: Source) {
  return detectType(s)
}

const availableTypes = computed(() => {
  const map = new Map<string, { key: string; label: string; count: number }>()
  for (const s of sources.value) {
    const t = detectType(s)
    const entry = map.get(t.key) || { key: t.key, label: t.label, count: 0 }
    entry.count++
    map.set(t.key, entry)
  }
  return Array.from(map.values()).sort((a, b) => b.count - a.count)
})

const filtered = computed(() => {
  let list = sources.value
  if (typeFilter.value) list = list.filter((s) => detectType(s).key === typeFilter.value)
  if (statusFilter.value) list = list.filter((s) => s.status === statusFilter.value)
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    list = list.filter((s) => (s.filename || '').toLowerCase().includes(q))
  }
  return list
})

function statusLabel(s: string) {
  return { pending: '待处理', processing: '处理中', done: '已处理', failed: '失败' }[s] || s
}
function statusTagType(s: string) {
  return { pending: 'info', processing: 'warning', done: 'success', failed: 'danger' }[s] as any || 'info'
}

function formatDate(iso: string) {
  try {
    const d = new Date(iso)
    const now = new Date()
    const sameDay = d.toDateString() === now.toDateString()
    if (sameDay) return '今天 ' + d.toTimeString().slice(0, 5)
    const sameYear = d.getFullYear() === now.getFullYear()
    return d.toLocaleString('zh-CN', {
      year: sameYear ? undefined : 'numeric',
      month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return iso
  }
}

async function load() {
  loading.value = true
  try {
    sources.value = await listSources()
  } catch (err: any) {
    ElMessage.error('加载失败：' + (err?.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

function onFilterChange() { /* computed handles it */ }

async function download(s: Source) {
  try {
    const resp = await api.get(`/sources/${s.id}/file`, { responseType: 'blob' })
    const blob = new Blob([resp.data])
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = s.filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    ElMessage.error('下载失败：' + (e?.message || '未知错误'))
  }
}

async function reingest(s: Source) {
  try {
    await reingestSource(s.id)
    ElMessage.success('已加入处理队列')
    s.status = 'pending'
    setTimeout(load, 2000)
  } catch (e: any) {
    ElMessage.error('重新解析失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  }
}

async function doDelete(s: Source) {
  try {
    await deleteSource(s.id)
    ElMessage.success('已删除')
    sources.value = sources.value.filter((x) => x.id !== s.id)
  } catch (e: any) {
    ElMessage.error('删除失败：' + (e?.message || '未知错误'))
  }
}

async function viewPages(s: Source) {
  currentSource.value = s
  pagesDrawerOpen.value = true
  try {
    generatedPages.value = await getSourcePages(s.id)
  } catch (e: any) {
    ElMessage.error('加载失败：' + (e?.message || '未知错误'))
    generatedPages.value = []
  }
}

onMounted(load)
</script>

<style scoped>
.page-breadcrumb { margin-bottom: 16px; }
.page-breadcrumb :deep(.el-breadcrumb__separator) { color: var(--text-muted); }

.sources-page { max-width: 1100px; margin: 0 auto; }
.page-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.page-header h2 { margin: 0; color: var(--text-primary); }
.header-actions { display: flex; gap: 8px; }

.filters {
  display: flex; flex-wrap: wrap; gap: 16px; justify-content: space-between;
  margin-bottom: 12px;
}
.filters-right { display: flex; gap: 8px; }

.search-bar {
  display: flex; align-items: center; gap: 16px; margin-bottom: 16px;
}
.search-meta { color: var(--text-muted); font-size: 13px; }

/* Skeleton */
.source-skeleton {
  padding: 4px 0;
}

.skeleton-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}

.skeleton-card-body {
  flex: 1;
  min-width: 0;
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

.source-list { display: flex; flex-direction: column; gap: 10px; }
.source-card {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 16px; background: var(--bg-card);
  border: 1px solid var(--border); border-radius: var(--radius-md);
  transition: box-shadow var(--transition), border-color var(--transition);
}
.source-card:hover { border-color: var(--accent); box-shadow: var(--shadow-md); }
.source-icon {
  width: 48px; height: 48px; border-radius: var(--radius-md);
  display: flex; align-items: center; justify-content: center;
  font-size: 24px; flex-shrink: 0;
}
.source-main { flex: 1; min-width: 0; }
.source-title {
  font-weight: 500; font-size: 15px; color: var(--text-primary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  margin-bottom: 6px;
}
.source-meta {
  display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
  font-size: 13px;
}
.muted { color: var(--text-muted); }
.pages-badge {
  color: var(--accent); cursor: pointer; font-size: 13px;
  background: var(--accent-soft); padding: 2px 10px; border-radius: var(--radius-md);
  transition: background var(--transition);
}
.pages-badge:hover { background: var(--accent); color: var(--text-inverse); }
.err-msg { color: var(--danger); font-size: 13px; margin-top: 6px; }
.source-actions { display: flex; gap: 6px; flex-shrink: 0; }

.gen-page-list { list-style: none; padding: 0; margin: 0; }
.gen-page-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; border-radius: var(--radius-sm);
}
.gen-page-item:hover { background: var(--bg-hover); }
.gen-page-link {
  color: var(--accent); text-decoration: none;
  line-height: 1.4;
}
.gen-page-link:hover { text-decoration: underline; }

@media (max-width: 900px) {
  .source-card { flex-wrap: wrap; }
  .source-actions { width: 100%; justify-content: flex-end; }
  .filters { flex-direction: column; }
}
@media (max-width: 640px) {
  .page-header { flex-direction: column; align-items: flex-start; gap: 10px; }
  .header-actions { width: 100%; }
  .source-card { padding: 12px; gap: 10px; }
  .source-icon { width: 40px; height: 40px; font-size: 20px; }
  .source-actions { flex-wrap: wrap; }
  .source-actions :deep(.el-button) { flex: 1; min-width: 0; }
  .search-bar { flex-direction: column; align-items: stretch; }
  .search-bar .el-input { max-width: 100% !important; }
}
</style>
