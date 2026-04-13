<template>
  <AppLayout>
    <div class="home">
      <h1>团队知识库</h1>
      <p>团队智能知识库 — 基于 LLM Wiki 模式</p>

      <el-row :gutter="20" style="margin-top: 24px">
        <el-col :span="6" v-for="s in statsCards" :key="s.label">
          <el-card shadow="hover">
            <div class="stat-card">
              <span class="stat-num">{{ s.value }}</span>
              <span class="stat-label">{{ s.label }}</span>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <h2 style="margin-top: 32px">最近更新</h2>
      <el-table :data="recentPages" style="width: 100%">
        <el-table-column prop="type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题">
          <template #default="{ row }">
            <router-link :to="`/wiki/${row.slug}`">{{ row.title }}</router-link>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="180">
          <template #default="{ row }">{{ new Date(row.updated_at).toLocaleString('zh-CN') }}</template>
        </el-table-column>
      </el-table>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import AppLayout from '../components/AppLayout.vue'
import { getStats, getPages } from '../api/wiki'

const stats = ref({ sources: 0, entities: 0, concepts: 0, analyses: 0, total: 0 })
const recentPages = ref<any[]>([])

const statsCards = computed(() => [
  { label: '信息源', value: stats.value.sources },
  { label: '实体', value: stats.value.entities },
  { label: '概念', value: stats.value.concepts },
  { label: '分析', value: stats.value.analyses },
])

onMounted(async () => {
  try { stats.value = await getStats() } catch {}
  try { recentPages.value = await getPages() } catch {}
})
</script>

<style scoped>
.stat-card { text-align: center; }
.stat-num { display: block; font-size: 2em; font-weight: bold; color: #409eff; }
.stat-label { color: #999; }
</style>
