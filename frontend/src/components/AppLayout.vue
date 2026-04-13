<template>
  <el-container class="app-layout">
    <el-header class="app-header">
      <div class="header-left">
        <router-link to="/" class="logo">团队知识库</router-link>
      </div>
      <div class="header-center">
        <el-input
          v-model="searchQuery"
          placeholder="搜索知识库..."
          @keyup.enter="doSearch"
          clearable
          style="width: 400px"
        />
      </div>
      <div class="header-right">
        <router-link to="/submit">
          <el-button type="primary">提交新源</el-button>
        </router-link>
        <router-link to="/chat">
          <el-button>AI 问答</el-button>
        </router-link>
        <el-button size="small" @click="handleLogout">退出</el-button>
      </div>
    </el-header>
    <el-container>
      <el-aside width="220px" class="app-aside">
        <el-menu :default-active="$route.path" router>
          <el-menu-item index="/">首页</el-menu-item>
          <el-menu-item index="/wiki?type=source">信息源</el-menu-item>
          <el-menu-item index="/wiki?type=entity">实体</el-menu-item>
          <el-menu-item index="/wiki?type=concept">概念</el-menu-item>
          <el-menu-item index="/wiki?type=analysis">分析</el-menu-item>
        </el-menu>
      </el-aside>
      <el-main class="app-main">
        <slot />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const searchQuery = ref('')
const router = useRouter()

function doSearch() {
  if (searchQuery.value.trim()) {
    router.push({ path: '/wiki', query: { q: searchQuery.value } })
  }
}

function handleLogout() {
  localStorage.removeItem('token')
  router.push('/login')
}
</script>

<style scoped>
.app-layout { min-height: 100vh; }
.app-header { display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #eee; }
.logo { font-size: 20px; font-weight: bold; text-decoration: none; color: #333; }
.header-right { display: flex; gap: 8px; }
.app-aside { border-right: 1px solid #eee; padding-top: 12px; }
.app-main { padding: 24px; }
</style>
