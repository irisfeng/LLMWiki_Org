<template>
  <div class="app-shell">
    <!-- Rail Navigation -->
    <nav class="rail">
      <div class="rail-top">
        <router-link to="/" class="rail-logo">W</router-link>
        <button
          v-for="item in navItems"
          :key="item.path"
          :class="['rail-btn', { active: isActive(item) }]"
          @click="navigateTo(item)"
        >
          <el-icon class="rail-icon"><component :is="item.icon" /></el-icon>
          <span class="rail-label">{{ item.label }}</span>
        </button>
      </div>
      <div class="rail-bottom">
        <button class="rail-btn" @click="toggleTheme()">
          <el-icon class="rail-icon"><component :is="isDark ? Sunny : Moon" /></el-icon>
          <span class="rail-label">{{ isDark ? '浅色' : '深色' }}</span>
        </button>
        <button class="rail-btn" @click="handleLogout">
          <el-icon class="rail-icon"><SwitchButton /></el-icon>
          <span class="rail-label">退出</span>
        </button>
      </div>
    </nav>

    <!-- Sidebar toggle (visible when sidebar is collapsed) -->
    <button
      v-if="!sidebarOpen && !isMobile"
      class="sidebar-expand-btn"
      @click="sidebarOpen = true"
      title="展开侧边栏"
    >
      <el-icon :size="14"><ArrowRight /></el-icon>
    </button>

    <!-- WikiTree Sidebar -->
    <aside class="wiki-tree" :class="{ collapsed: !sidebarOpen }">
      <div class="tree-header">
        <button class="sidebar-collapse-btn" @click="sidebarOpen = false" title="收起侧边栏">
          <el-icon :size="12"><ArrowLeft /></el-icon>
        </button>
        <div class="tree-search">
          <el-input
            ref="searchInputRef"
            v-model="searchQuery"
            placeholder="搜索... ⌘K"
            size="small"
            @keyup.enter="doSearch"
            clearable
          />
        </div>
        <router-link to="/submit" class="tree-upload-btn" @click="closeSidebarOnMobile">
          <el-icon><Upload /></el-icon>
          上传
        </router-link>
      </div>
      <div class="tree-body">
        <div class="tree-section">
          <div class="tree-section-title">知识库</div>
          <router-link
            to="/wiki"
            :class="['tree-item', { active: route.path === '/wiki' && !route.query.type }]"
            @click="closeSidebarOnMobile"
          >全部页面</router-link>
          <router-link
            to="/wiki?type=source"
            :class="['tree-item', { active: route.query.type === 'source' }]"
            @click="closeSidebarOnMobile"
          >信息源</router-link>
          <router-link
            to="/wiki?type=entity"
            :class="['tree-item', { active: route.query.type === 'entity' }]"
            @click="closeSidebarOnMobile"
          >实体</router-link>
          <router-link
            to="/wiki?type=concept"
            :class="['tree-item', { active: route.query.type === 'concept' }]"
            @click="closeSidebarOnMobile"
          >概念</router-link>
        </div>
        <div class="tree-divider"></div>
        <div class="tree-section">
          <router-link
            to="/sources"
            :class="['tree-item', { active: route.path === '/sources' }]"
            @click="closeSidebarOnMobile"
          >文档管理</router-link>
          <router-link
            to="/lint"
            :class="['tree-item', { active: route.path === '/lint' }]"
            @click="closeSidebarOnMobile"
          >健康检查</router-link>
        </div>
      </div>
    </aside>

    <!-- Mobile overlay for sidebar -->
    <div
      v-if="isMobile && sidebarOpen"
      class="sidebar-overlay"
      @click="sidebarOpen = false"
    />

    <!-- Main Content -->
    <main class="main-content" :class="{ 'sidebar-collapsed': !sidebarOpen }">
      <slot />
    </main>
  </div>
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
  DataAnalysis,
  SwitchButton,
  Sunny,
  Moon,
  ArrowLeft,
  ArrowRight,
} from '@element-plus/icons-vue'
import { isDark, toggleTheme } from '../composables/useTheme'

interface NavItem {
  path: string
  icon: typeof HomeFilled
  label: string
  /** Routes that this nav item should match for active state */
  matchPaths?: string[]
}

const navItems: NavItem[] = [
  { path: '/', icon: HomeFilled, label: '首页' },
  { path: '/chat', icon: ChatDotRound, label: '问答' },
  { path: '/wiki', icon: Collection, label: '知识库', matchPaths: ['/wiki'] },
  { path: '/sources', icon: FolderOpened, label: '文档', matchPaths: ['/sources', '/submit'] },
  { path: '/lint', icon: DataAnalysis, label: '检查' },
]

const searchQuery = ref('')
const route = useRoute()
const router = useRouter()
const sidebarOpen = ref(true)
const searchInputRef = ref<ComponentPublicInstance | null>(null)

const isMobile = useMediaQuery('(max-width: 768px)')

function isActive(item: NavItem): boolean {
  const currentPath = route.path
  if (item.path === '/' && currentPath === '/') return true
  if (item.path === '/') return false
  if (item.matchPaths) {
    return item.matchPaths.some((p) => currentPath.startsWith(p))
  }
  return currentPath.startsWith(item.path)
}

function navigateTo(item: NavItem) {
  if (isActive(item)) {
    // Clicking the already-active rail item toggles the sidebar
    sidebarOpen.value = !sidebarOpen.value
  } else {
    router.push(item.path)
    sidebarOpen.value = true
  }
}

function closeSidebarOnMobile() {
  if (isMobile.value) {
    sidebarOpen.value = false
  }
}

function doSearch() {
  if (searchQuery.value.trim()) {
    router.push({ path: '/wiki', query: { q: searchQuery.value } })
    closeSidebarOnMobile()
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
    ;(searchInputRef.value as any)?.focus?.()
  }
}

onMounted(() => document.addEventListener('keydown', handleKeydown))
onUnmounted(() => document.removeEventListener('keydown', handleKeydown))
</script>

<style scoped>
/* ---- App Shell ---- */
.app-shell {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}

/* ---- Rail ---- */
.rail {
  width: 68px;
  flex-shrink: 0;
  background: var(--paper-2);
  border-right: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 14px 0 12px;
  align-items: center;
  z-index: 10;
}

.rail-top,
.rail-bottom {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.rail-logo {
  width: 34px;
  height: 34px;
  background: var(--ink);
  color: var(--paper);
  border-radius: 9px;
  display: grid;
  place-items: center;
  font-family: var(--font-display);
  font-style: italic;
  font-size: 18px;
  font-weight: 600;
  text-decoration: none;
  margin-bottom: 12px;
  transition: opacity var(--transition);
}
.rail-logo:hover {
  opacity: 0.85;
  text-decoration: none;
}

.rail-btn {
  width: 52px;
  height: 48px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  border: none;
  background: transparent;
  border-radius: 9px;
  cursor: pointer;
  margin-bottom: 2px;
  color: var(--ink-3);
  transition: all var(--transition);
  padding: 0;
  font-family: var(--font-ui);
}

.rail-btn:hover {
  background: color-mix(in oklch, var(--paper) 60%, transparent);
}

.rail-btn.active {
  background: var(--paper);
  color: var(--accent-ink);
  box-shadow: inset 0 0 0 1px var(--line), var(--shadow-sm);
}

.rail-icon {
  width: 17px;
  height: 17px;
  font-size: 17px;
}

.rail-btn:not(.active) .rail-icon {
  stroke-width: 1.5;
}
.rail-btn.active .rail-icon {
  stroke-width: 1.8;
}

.rail-label {
  font-size: 9.5px;
  font-weight: 500;
  letter-spacing: 0.01em;
  line-height: 1;
}

/* ---- WikiTree Sidebar ---- */
.wiki-tree {
  width: 240px;
  flex-shrink: 0;
  background: var(--paper);
  border-right: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: width 0.28s cubic-bezier(0.2, 0.8, 0.2, 1),
              border-color 0.28s cubic-bezier(0.2, 0.8, 0.2, 1),
              opacity 0.2s ease;
  z-index: 5;
}

.wiki-tree .tree-header,
.wiki-tree .tree-body {
  opacity: 1;
  transition: opacity 0.18s ease 0.08s; /* slight delay so width starts first */
}

.wiki-tree.collapsed {
  width: 0;
  border-right-color: transparent;
}

.wiki-tree.collapsed .tree-header,
.wiki-tree.collapsed .tree-body {
  opacity: 0;
  transition: opacity 0.1s ease; /* fade out faster than fade in */
}

/* Sidebar toggle buttons */
.sidebar-collapse-btn {
  position: absolute;
  top: 16px;
  right: 10px;
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--paper-2);
  color: var(--ink-4);
  cursor: pointer;
  z-index: 2;
  transition: all var(--transition);
}
.sidebar-collapse-btn:hover {
  background: var(--paper-3);
  color: var(--ink-2);
  border-color: var(--line-2);
}

.sidebar-expand-btn {
  width: 20px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: var(--paper-2);
  border-right: 1px solid var(--line);
  color: var(--ink-4);
  cursor: pointer;
  transition: all var(--transition);
}
.sidebar-expand-btn:hover {
  background: var(--paper-3);
  color: var(--ink-2);
}

.tree-header {
  padding: 14px 14px 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex-shrink: 0;
  position: relative;
}

.tree-search :deep(.el-input__wrapper) {
  background: var(--paper-2);
  box-shadow: 0 0 0 1px var(--line) inset;
  border-radius: 8px;
}

.tree-upload-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 7px 10px;
  background: var(--ink);
  color: var(--paper);
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  transition: background var(--transition);
  font-family: var(--font-ui);
}
.tree-upload-btn:hover {
  background: var(--ink-2);
  text-decoration: none;
  color: var(--paper);
}

.tree-body {
  flex: 1;
  overflow-y: auto;
  padding: 6px 10px;
}

.tree-section {
  margin-bottom: 4px;
}

.tree-section-title {
  padding: 6px 10px 4px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--ink-4);
}

.tree-item {
  display: block;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 13.5px;
  color: var(--ink-2);
  text-decoration: none;
  transition: all var(--transition);
}
.tree-item:hover {
  background: var(--paper-2);
  text-decoration: none;
  color: var(--ink-2);
}
.tree-item.active {
  background: var(--accent-soft);
  color: var(--accent-ink);
  font-weight: 500;
}

.tree-divider {
  height: 1px;
  background: var(--line);
  margin: 8px 10px;
}

/* ---- Mobile Overlay ---- */
.sidebar-overlay {
  position: fixed;
  inset: 0;
  left: 68px;
  background: rgba(0, 0, 0, 0.3);
  z-index: 4;
}

/* ---- Main Content ---- */
.main-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--paper);
  min-width: 0;
}

/* ---- Mobile ---- */
@media (max-width: 768px) {
  .rail {
    width: 0;
    padding: 0;
    border: none;
    overflow: hidden;
    display: none;
  }

  .wiki-tree {
    position: fixed;
    z-index: 1001;
    top: 0;
    left: 0;
    bottom: 0;
    box-shadow: var(--shadow-lg);
  }
  .wiki-tree.collapsed {
    width: 0;
    box-shadow: none;
  }

  .sidebar-overlay {
    left: 0;
    z-index: 1000;
  }
}
</style>
