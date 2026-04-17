<template>
  <AppLayout>
    <div v-if="page" class="wiki-page">
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
        <div class="page-header">
          <div class="header-row">
            <el-tag>{{ page.type }}</el-tag>
            <div class="header-actions">
              <el-button size="small" :icon="Edit" @click="editing = true">编辑</el-button>
              <el-button size="small" :icon="Download" @click="downloadMarkdown">下载 Markdown</el-button>
            </div>
          </div>
          <h1>{{ page.title }}</h1>
          <div class="meta">
            更新于 {{ new Date(page.updated_at).toLocaleString('zh-CN') }}
            <span v-if="page.frontmatter?.author"> · {{ page.frontmatter.author }}</span>
          </div>
          <div class="tags" v-if="page.frontmatter?.tags?.length">
            <el-tag v-for="t in page.frontmatter.tags" :key="t" size="small" style="margin-right:4px">{{ t }}</el-tag>
          </div>
        </div>

        <el-divider />

        <MarkdownRenderer :content="page.content" />

        <el-divider />

        <div v-if="page.backlinks?.length" class="backlinks">
          <h3>反向链接 ({{ page.backlinks.length }})</h3>
          <ul>
            <li v-for="bl in page.backlinks" :key="bl.slug">
              <router-link :to="`/wiki/${bl.slug}`">{{ bl.title }}</router-link>
              <el-tag size="small" style="margin-left:8px">{{ bl.type }}</el-tag>
            </li>
          </ul>
        </div>
      </template>
    </div>
    <el-empty v-else-if="!loading" description="页面不存在" />
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Download, Edit } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import AppLayout from '../components/AppLayout.vue'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'
import WikiEditor from '../components/WikiEditor.vue'
import { getPage } from '../api/wiki'
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

async function downloadMarkdown() {
  if (!page.value) return
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

onMounted(load)
watch(() => route.params.slug, load)
</script>

<style scoped>
.page-header h1 { margin: 8px 0; color: var(--text-primary); }
.header-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.header-actions { display: flex; gap: 8px; }
.meta { color: var(--text-muted); font-size: 0.9em; }
.backlinks ul { list-style: none; padding: 0; }
.backlinks li { margin: 4px 0; }
.backlinks li a { color: var(--accent); }
.backlinks li a:hover { color: var(--accent-hover); }
@media (max-width: 640px) {
  .header-row { flex-direction: column; align-items: flex-start; }
}
</style>
