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
        <el-button :icon="isDark ? Sunny : Moon" circle size="small" @click="toggleTheme()" />
        <el-dropdown trigger="click" @command="onUserCommand">
          <el-button>
            <el-icon style="margin-right: 4px"><User /></el-icon>
            团队成员
            <el-icon style="margin-left: 4px"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout" :icon="SwitchButton">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>
    <el-container>
      <el-aside width="220px" class="app-aside">
        <el-menu :default-active="$route.path" router>
          <el-menu-item index="/">首页</el-menu-item>
          <el-menu-item index="/sources">文档库</el-menu-item>
          <el-menu-item index="/wiki?type=source">信息源</el-menu-item>
          <el-menu-item index="/wiki?type=entity">实体</el-menu-item>
          <el-menu-item index="/wiki?type=concept">概念</el-menu-item>
          <!-- 分析 类型待实现：计划承载问答沉淀页 + 周报 Lint 结果，暂时隐藏 -->
          <!-- <el-menu-item index="/wiki?type=analysis">分析</el-menu-item> -->

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
import { ElMessageBox, ElMessage } from 'element-plus'
import { User, ArrowDown, SwitchButton, Sunny, Moon } from '@element-plus/icons-vue'
import { isDark, toggleTheme } from '../composables/useTheme'

const searchQuery = ref('')
const router = useRouter()

function doSearch() {
  if (searchQuery.value.trim()) {
    router.push({ path: '/wiki', query: { q: searchQuery.value } })
  }
}

async function onUserCommand(command: string) {
  if (command === 'logout') {
    try {
      await ElMessageBox.confirm('确定要退出登录吗？', '退出确认', {
        confirmButtonText: '退出',
        cancelButtonText: '取消',
        type: 'warning',
      })
      localStorage.removeItem('token')
      ElMessage.success('已退出登录')
      router.push('/login')
    } catch {
      /* 用户取消 */
    }
  }
}
</script>

<style scoped>
.app-layout { min-height: 100vh; background-color: var(--bg-primary); }
.app-header { display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--border); background-color: var(--bg-primary); }
.logo { font-size: 20px; font-weight: bold; text-decoration: none; color: var(--text-primary); }
.header-right { display: flex; gap: 8px; align-items: center; }
.app-aside { border-right: 1px solid var(--border); padding-top: 12px; background-color: var(--bg-secondary); }
.app-main { padding: 24px; background-color: var(--bg-primary); }
</style>
