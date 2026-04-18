<template>
  <AppLayout>
    <div class="wiki-list-page">
      <el-breadcrumb separator="/" class="page-breadcrumb">
        <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
        <el-breadcrumb-item>知识库</el-breadcrumb-item>
        <el-breadcrumb-item v-if="route.query.type">{{ typeLabel(route.query.type as string) }}</el-breadcrumb-item>
      </el-breadcrumb>

      <h2 class="page-title">{{ pageTitle }}</h2>

      <!-- Tag filter bar -->
      <div v-if="tags.length && !route.query.q" class="tag-filter">
        <span class="tag-filter-label">标签筛选：</span>
        <el-tag
          v-for="t in tags.slice(0, 20)"
          :key="t.tag"
          :type="selectedTag === t.tag ? '' : 'info'"
          :effect="selectedTag === t.tag ? 'dark' : 'plain'"
          class="tag-chip"
          @click="toggleTag(t.tag)"
          style="cursor:pointer"
        >
          {{ t.tag }} ({{ t.count }})
        </el-tag>
        <el-tag
          v-if="selectedTag"
          type="danger"
          effect="plain"
          class="tag-chip"
          @click="toggleTag('')"
          style="cursor:pointer"
        >
          清除筛选
        </el-tag>
      </div>

      <!-- Skeleton loading state -->
      <template v-if="loading">
        <div class="list-skeleton">
          <el-skeleton v-for="i in 5" :key="i" animated :rows="0" style="margin-bottom: 14px">
            <template #template>
              <div class="skeleton-row">
                <el-skeleton-item variant="button" style="width: 56px; height: 22px" />
                <el-skeleton-item variant="text" style="width: 240px" />
                <el-skeleton-item variant="text" style="width: 100px; margin-left: auto" />
              </div>
            </template>
          </el-skeleton>
        </div>
      </template>

      <!-- Empty state -->
      <template v-else-if="pages.length === 0">
        <div class="empty-state">
          <el-empty :image-size="120" description="">
            <template #description>
              <p class="empty-text">没有找到相关内容，试试在 AI 问答中提问？</p>
            </template>
            <router-link to="/chat">
              <el-button type="primary">
                <el-icon style="margin-right: 4px"><ChatDotRound /></el-icon>
                去提问
              </el-button>
            </router-link>
          </el-empty>
        </div>
      </template>

      <!-- Data table (desktop) -->
      <template v-else>
        <el-table :data="pages" class="desktop-table">
          <el-table-column prop="type" label="类型" width="100">
            <template #default="{ row }">
              <el-tag size="small">{{ row.type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="title" label="标题">
            <template #default="{ row }">
              <router-link :to="`/wiki/${row.slug}`" class="page-link">{{ row.title || row.slug }}</router-link>
            </template>
          </el-table-column>
          <el-table-column label="标签" width="200">
            <template #default="{ row }">
              <el-tag
                v-for="t in (row.frontmatter?.tags || [])"
                :key="t"
                size="small"
                :type="selectedTag === t ? '' : 'info'"
                :effect="selectedTag === t ? 'dark' : 'plain'"
                style="margin-right:4px; cursor:pointer"
                @click.stop="toggleTag(t)"
              >{{ t }}</el-tag>
            </template>
          </el-table-column>
        </el-table>

        <!-- Mobile card list -->
        <div class="mobile-list">
          <div v-for="row in pages" :key="row.slug" class="mobile-card">
            <div class="mobile-card-header">
              <el-tag size="small">{{ row.type }}</el-tag>
              <router-link :to="`/wiki/${row.slug}`" class="page-link">{{ row.title || row.slug }}</router-link>
            </div>
            <div v-if="row.frontmatter?.tags?.length" class="mobile-card-tags">
              <el-tag
                v-for="t in row.frontmatter.tags"
                :key="t"
                size="small"
                :type="selectedTag === t ? '' : 'info'"
                :effect="selectedTag === t ? 'dark' : 'plain'"
                style="cursor:pointer"
                @click.stop="toggleTag(t)"
              >{{ t }}</el-tag>
            </div>
          </div>
        </div>
      </template>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ChatDotRound } from '@element-plus/icons-vue'
import AppLayout from '../components/AppLayout.vue'
import { getPages, getTags } from '../api/wiki'

const route = useRoute()
const pages = ref<any[]>([])
const loading = ref(false)
const tags = ref<{ tag: string; count: number }[]>([])
const selectedTag = ref<string>('')

const typeMap: Record<string, string> = { source: '信息源', entity: '实体', concept: '概念', analysis: '分析' }

function typeLabel(type: string): string {
  return typeMap[type] || type
}

const pageTitle = computed(() => {
  const q = route.query.q as string
  if (q) return `搜索: ${q}`
  const type = route.query.type as string
  return typeMap[type] || '全部页面'
})

function toggleTag(tag: string) {
  selectedTag.value = selectedTag.value === tag ? '' : tag
  load()
}

async function load() {
  loading.value = true
  // Clear tag filter when in search mode (search API doesn't support tag param)
  if (route.query.q) {
    selectedTag.value = ''
  }
  try {
    pages.value = await getPages(
      route.query.type as string,
      route.query.q as string,
      selectedTag.value || undefined
    )
  } catch {}
  loading.value = false
}

async function loadTags() {
  try { tags.value = await getTags() } catch {}
}

onMounted(() => { load(); loadTags() })
watch(() => route.query, load)
</script>

<style scoped>
.wiki-list-page {
  max-width: 960px;
  margin: 0 auto;
}

.page-breadcrumb { margin-bottom: 16px; }
.page-breadcrumb :deep(.el-breadcrumb__separator) { color: var(--text-muted); }

.page-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 20px;
}

.page-link { color: var(--accent); text-decoration: none; }
.page-link:hover { color: var(--accent-hover); text-decoration: underline; }

.tag-filter { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 12px; }
.tag-filter-label { color: var(--text-muted); font-size: 13px; margin-right: 4px; }
.tag-chip { transition: all 0.2s ease; }

/* Mobile card list - hidden on desktop */
.mobile-list { display: none; }

/* Skeleton */
.list-skeleton {
  padding: 8px 0;
}

.skeleton-row {
  display: flex;
  align-items: center;
  gap: 12px;
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

@media (max-width: 640px) {
  .desktop-table { display: none; }
  .mobile-list { display: block; }
  .mobile-card {
    padding: 12px 14px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    margin-bottom: 8px;
  }
  .mobile-card-header {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .mobile-card-header .page-link {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    min-width: 0;
  }
  .mobile-card-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 6px;
  }
}
</style>
