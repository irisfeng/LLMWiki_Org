<template>
  <AppLayout>
    <div>
      <h2>{{ pageTitle }}</h2>
      <el-table :data="pages" v-loading="loading">
        <el-table-column prop="type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题">
          <template #default="{ row }">
            <router-link :to="`/wiki/${row.slug}`">{{ row.title || row.slug }}</router-link>
          </template>
        </el-table-column>
        <el-table-column label="Tags" width="200">
          <template #default="{ row }">
            <el-tag v-for="t in (row.frontmatter?.tags || [])" :key="t" size="small" style="margin-right:4px">{{ t }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '../components/AppLayout.vue'
import { getPages } from '../api/wiki'

const route = useRoute()
const pages = ref<any[]>([])
const loading = ref(false)

const pageTitle = computed(() => {
  const q = route.query.q as string
  if (q) return `搜索: ${q}`
  const type = route.query.type as string
  const map: Record<string, string> = { source: 'Sources', entity: 'Entities', concept: 'Concepts', analysis: 'Analyses' }
  return map[type] || '全部页面'
})

async function load() {
  loading.value = true
  try { pages.value = await getPages(route.query.type as string, route.query.q as string) } catch {}
  loading.value = false
}

onMounted(load)
watch(() => route.query, load)
</script>
