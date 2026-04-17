<template>
  <el-container class="app-layout">
    <!-- Top Bar -->
    <el-header class="app-header" height="56px">
      <div class="header-left">
        <el-button
          class="hamburger-btn"
          :icon="Expand"
          text
          @click="collapsed = !collapsed"
        />
        <router-link to="/" class="logo">团队知识库</router-link>
      </div>
      <div class="header-center">
        <el-input
          ref="searchInputRef"
          v-model="searchQuery"
          placeholder="搜索知识库... (⌘K)"
          @keyup.enter="doSearch"
          clearable
          class="search-input"
        />
      </div>
      <div class="header-right">
        <el-button
          :icon="isDark ? Sunny : Moon"
          circle
          size="small"
          @click="toggleTheme()"
        />
        <el-button
          :icon="SwitchButton"
          circle
          size="small"
          @click="handleLogout"
        />
      </div>
    </el-header>

    <!-- Body -->
    <el-container class="app-body">
      <!-- Mobile overlay -->
      <div
        v-if="collapsed"
        class="sidebar-overlay"
        @click="collapsed = false"
      />

      <!-- Sidebar -->
      <el-aside
        :width="sidebarVisible ? '220px' : '0px'"
        class="app-aside"
        :class="{ 'aside-open': sidebarVisible }"
      >
        <el-menu
          :default-active="activeMenu"
          :default-openeds="['wiki']"
          router
          @select="onMenuSelect"
        >
          <el-menu-item index="/">
            <el-icon><HomeFilled /></el-icon>
            <span>首页</span>
          </el-menu-item>
          <el-menu-item index="/chat">
            <el-icon><ChatDotRound /></el-icon>
            <span>AI 问答</span>
          </el-menu-item>
          <el-sub-menu index="wiki">
            <template #title>
              <el-icon><Collection /></el-icon>
              <span>知识库</span>
            </template>
            <el-menu-item index="/wiki">全部</el-menu-item>
            <el-menu-item index="/wiki?type=source">信息源</el-menu-item>
            <el-menu-item index="/wiki?type=entity">实体</el-menu-item>
            <el-menu-item index="/wiki?type=concept">概念</el-menu-item>
          </el-sub-menu>
          <el-menu-item index="/sources">
            <el-icon><FolderOpened /></el-icon>
            <span>文档管理</span>
          </el-menu-item>
          <el-menu-item index="/submit">
            <el-icon><Upload /></el-icon>
            <span>上传文档</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <!-- Main content -->
      <el-main class="app-main">
        <slot />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMediaQuery } from '@vueuse/core'
import { ElMessageBox, ElMessage } from 'element-plus'
import type { ComponentPublicInstance } from 'vue'
import {
  HomeFilled,
  ChatDotRound,
  Collection,
  FolderOpened,
  Upload,
  Expand,
  SwitchButton,
  Sunny,
  Moon,
} from '@element-plus/icons-vue'
import { isDark, toggleTheme } from '../composables/useTheme'

const searchQuery = ref('')
const route = useRoute()
const router = useRouter()
const collapsed = ref(false)
const searchInputRef = ref<ComponentPublicInstance | null>(null)

const isMobile = useMediaQuery('(max-width: 768px)')

const sidebarVisible = computed(() => {
  // Desktop: always visible; Mobile: controlled by collapsed toggle
  return !isMobile.value || collapsed.value
})

const activeMenu = computed(() => {
  const path = route.path
  const type = route.query.type as string | undefined
  if (path === '/wiki' && type) {
    return `/wiki?type=${type}`
  }
  return path
})

function doSearch() {
  if (searchQuery.value.trim()) {
    router.push({ path: '/wiki', query: { q: searchQuery.value } })
  }
}

function onMenuSelect() {
  // Close sidebar on mobile after selecting a menu item
  if (isMobile.value) {
    collapsed.value = false
  }
}

async function handleLogout() {
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
    /* user cancelled */
  }
}

function handleKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault()
    // el-input exposes focus via the component ref
    ;(searchInputRef.value as any)?.focus?.()
  }
}

onMounted(() => document.addEventListener('keydown', handleKeydown))
onUnmounted(() => document.removeEventListener('keydown', handleKeydown))
</script>

<style scoped>
/* ---- Layout shell ---- */
.app-layout {
  min-height: 100vh;
  background-color: var(--bg-primary);
}

/* ---- Top bar ---- */
.app-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 1000;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid var(--border);
  background-color: var(--bg-primary);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.hamburger-btn {
  display: none;
}

.logo {
  font-size: 18px;
  font-weight: 700;
  text-decoration: none;
  color: var(--text-primary);
  white-space: nowrap;
}

.header-center {
  flex: 1;
  display: flex;
  justify-content: center;
  padding: 0 24px;
}

.search-input {
  max-width: 480px;
  width: 100%;
}

.header-right {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}

/* ---- Body (below header) ---- */
.app-body {
  padding-top: 56px;
}

/* ---- Sidebar ---- */
.app-aside {
  position: fixed;
  top: 56px;
  left: 0;
  bottom: 0;
  overflow-y: auto;
  overflow-x: hidden;
  border-right: 1px solid var(--border);
  background-color: var(--bg-secondary);
  transition: width var(--transition, 0.15s ease);
  z-index: 999;
}

.app-aside .el-menu {
  border-right: none;
}

/* ---- Main content ---- */
.app-main {
  margin-left: 220px;
  padding: 24px;
  background-color: var(--bg-primary);
  min-height: calc(100vh - 56px);
}

/* ---- Mobile overlay ---- */
.sidebar-overlay {
  display: none;
}

/* ---- Responsive: mobile ---- */
@media (max-width: 768px) {
  .hamburger-btn {
    display: inline-flex;
  }

  .app-aside {
    position: fixed;
    top: 56px;
    left: 0;
    bottom: 0;
    width: 0;
    z-index: 1001;
  }

  .app-aside.aside-open {
    width: 220px !important;
  }

  .app-main {
    margin-left: 0;
  }

  .sidebar-overlay {
    display: block;
    position: fixed;
    inset: 0;
    top: 56px;
    background: rgba(0, 0, 0, 0.3);
    z-index: 1000;
  }

  .header-center {
    padding: 0 12px;
  }
}
</style>
