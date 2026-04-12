<template>
  <AppLayout>
    <div v-if="page" class="wiki-page">
      <div class="page-header">
        <el-tag>{{ page.type }}</el-tag>
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
    </div>
    <el-empty v-else-if="!loading" description="页面不存在" />
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '../components/AppLayout.vue'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'
import { getPage } from '../api/wiki'

const route = useRoute()
const page = ref<any>(null)
const loading = ref(true)

async function load() {
  loading.value = true
  const slug = route.params.slug as string
  try { page.value = await getPage(slug) } catch { page.value = null }
  loading.value = false
}

onMounted(load)
watch(() => route.params.slug, load)
</script>

<style scoped>
.page-header h1 { margin: 8px 0; }
.meta { color: #999; font-size: 0.9em; }
.backlinks ul { list-style: none; padding: 0; }
.backlinks li { margin: 4px 0; }
</style>
