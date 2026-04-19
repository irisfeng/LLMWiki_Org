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
          <span v-if="isActive(item)" class="rail-active-bar" />
          <el-icon class="rail-icon"><component :is="item.icon" /></el-icon>
          <span class="rail-label">{{ item.label }}</span>
        </button>
      </div>
      <div class="rail-bottom">
        <button class="rail-ghost" @click="toggleTheme()" :title="isDark ? '切换浅色' : '切换深色'">
          <el-icon><component :is="isDark ? Sunny : Moon" /></el-icon>
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
      <!-- Workspace header -->
      <div class="ws-header">
        <div class="ws-kicker">WORKSPACE</div>
        <div class="ws-row">
          <div class="ws-title">
            团队<span class="ws-italic">知识库</span>
          </div>
          <button class="sidebar-collapse-btn" @click="sidebarOpen = false" title="收起侧边栏">
            <el-icon :size="12"><ArrowLeft /></el-icon>
          </button>
        </div>
      </div>

      <!-- Inline search -->
      <div class="search-wrap">
        <div class="search-box">
          <el-icon class="search-icon"><Search /></el-icon>
          <input
            ref="searchInputRef"
            v-model="searchQuery"
            placeholder="搜索 · ⌘K"
            @keyup.enter="doSearch"
          />
          <kbd class="kbd">⌘K</kbd>
        </div>
      </div>

      <!-- Primary action -->
      <div class="primary-actions">
        <button class="upload-btn" @click="handleUploadClick">
          <el-icon><Upload /></el-icon>
          新建 / 上传
        </button>
      </div>

      <!-- Pinned -->
      <div class="section-block" v-if="pinned.length">
        <div class="sec-label">PINNED</div>
        <router-link
          v-for="p in pinned"
          :key="p.slug"
          :to="`/wiki/${p.slug}`"
          class="leaf"
          :class="{ active: route.params.slug === p.slug }"
          @click="closeSidebarOnMobile"
        >
          <span class="leaf-pill" :data-type="p.type">{{ typeShort(p.type) }}</span>
          <span class="leaf-title">{{ p.title }}</span>
          <el-icon class="leaf-pin"><StarFilled /></el-icon>
        </router-link>
      </div>

      <!-- Tree (collapsible categories) -->
      <div class="tree-scroll">
        <div class="sec-label inset">分类</div>
        <div v-for="folder in categories" :key="folder.key" class="folder">
          <button class="folder-row" @click="toggleFolder(folder.key)">
            <el-icon
              class="folder-chev"
              :class="{ open: openFolders[folder.key] }"
            ><CaretRight /></el-icon>
            <span class="folder-label">{{ folder.label }}</span>
            <span class="folder-count">{{ folder.count }}</span>
          </button>
          <div v-show="openFolders[folder.key]" class="folder-kids">
            <router-link
              :to="`/wiki?type=${folder.key}`"
              class="leaf small"
              :class="{ active: route.query.type === folder.key && !route.params.slug }"
              @click="closeSidebarOnMobile"
            >
              <span class="leaf-title muted">查看全部 {{ folder.label }}</span>
            </router-link>
          </div>
        </div>

        <div class="sec-label inset">工具</div>
        <router-link
          to="/wiki"
          class="leaf small"
          :class="{ active: route.path === '/wiki' && !route.query.type && !route.params.slug }"
          @click="closeSidebarOnMobile"
        >
          <span class="leaf-title">全部页面</span>
        </router-link>
        <router-link
          to="/lint"
          class="leaf small"
          :class="{ active: route.path === '/lint' }"
          @click="closeSidebarOnMobile"
        >
          <span class="leaf-title">健康检查</span>
        </router-link>
      </div>

      <!-- User footer -->
      <div class="user-footer">
        <div class="user-avatar">{{ userInitial }}</div>
        <div class="user-info">
          <span class="user-name">{{ userName }}</span>
          <span class="user-meta">{{ userRole }}</span>
        </div>
        <button class="icon-btn ghost" @click="handleLogout" title="退出">
          <el-icon><SwitchButton /></el-icon>
        </button>
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

    <!-- Floating AI button -->
    <button
      v-if="route.path !== '/chat'"
      class="ai-fab"
      :class="{ open: aiDrawerOpen }"
      @click="aiDrawerOpen = !aiDrawerOpen"
      title="问 AI · ⌘J"
    >
      <el-icon :size="18"><MagicStick /></el-icon>
    </button>

    <!-- AI Drawer -->
    <AIDrawer :open="aiDrawerOpen" @close="aiDrawerOpen = false" />

    <!-- Global Upload Modal -->
    <UploadModal />

    <!-- Command Palette (Cmd/Ctrl+K) -->
    <CommandPalette :open="paletteOpen" @close="paletteOpen = false" @ask-ai="handleAskAI" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMediaQuery } from '@vueuse/core'
import { ElMessageBox, ElMessage } from 'element-plus'
import type { ComponentPublicInstance } from 'vue'
import {
  HomeFilled,
  ChatDotRound,
  Collection,
  Share,
  Upload,
  DataAnalysis,
  SwitchButton,
  Sunny,
  Moon,
  ArrowLeft,
  ArrowRight,
  Search,
  Plus,
  StarFilled,
  CaretRight,
  MagicStick,
} from '@element-plus/icons-vue'
import { isDark, toggleTheme } from '../composables/useTheme'
import { getStats, getPages } from '../api/wiki'
import { openUploadModal } from '../composables/useUploadModal'
import AIDrawer from './AIDrawer.vue'
import UploadModal from './UploadModal.vue'
import CommandPalette from './CommandPalette.vue'

function handleUploadClick() {
  closeSidebarOnMobile()
  openUploadModal()
}

interface NavItem {
  path: string
  icon: typeof HomeFilled
  label: string
  matchPaths?: string[]
}

const navItems: NavItem[] = [
  { path: '/', icon: HomeFilled, label: '首页' },
  { path: '/chat', icon: ChatDotRound, label: '问答' },
  { path: '/wiki', icon: Collection, label: '知识库', matchPaths: ['/wiki'] },
  { path: '/graph', icon: Share, label: '关系图谱', matchPaths: ['/graph'] },
  { path: '/lint', icon: DataAnalysis, label: '检查' },
]

const searchQuery = ref('')
const route = useRoute()
const router = useRouter()
const sidebarOpen = ref(true)
const aiDrawerOpen = ref(false)
const paletteOpen = ref(false)
const pendingAskAI = ref('')
const searchInputRef = ref<ComponentPublicInstance | null>(null)

const isMobile = useMediaQuery('(max-width: 768px)')

// User
const userName = ref(localStorage.getItem('userName') || '当前用户')
const userRole = ref(localStorage.getItem('userRole') || '研发 · 可编辑')
const userInitial = computed(() => userName.value.slice(-1) || 'U')

// Stats / categories
interface Folder { key: string; label: string; count: number }
const categories = ref<Folder[]>([
  { key: 'source', label: 'Sources', count: 0 },
  { key: 'entity', label: 'Entities', count: 0 },
  { key: 'concept', label: 'Concepts', count: 0 },
  { key: 'analysis', label: 'Analyses', count: 0 },
])

const openFolders = reactive<Record<string, boolean>>({
  source: true,
  entity: true,
  concept: true,
  analysis: false,
})

function toggleFolder(key: string) {
  openFolders[key] = !openFolders[key]
}

// Pinned (top 2 most recent for now, until backend has pin field)
const pinned = ref<{ slug: string; title: string; type: string }[]>([])

function typeShort(t: string) {
  return ({ source: 'S', entity: 'E', concept: 'C', analysis: 'A' } as Record<string, string>)[t] || '·'
}

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
    sidebarOpen.value = !sidebarOpen.value
  } else {
    router.push(item.path)
    sidebarOpen.value = true
  }
}

function closeSidebarOnMobile() {
  if (isMobile.value) sidebarOpen.value = false
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
  } catch { /* user cancelled */ }
}

function handleKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
    e.preventDefault()
    paletteOpen.value = !paletteOpen.value
  }
  if ((e.metaKey || e.ctrlKey) && (e.key === 'j' || e.key === 'J')) {
    e.preventDefault()
    aiDrawerOpen.value = !aiDrawerOpen.value
  }
}

function handleAskAI(q: string) {
  pendingAskAI.value = q
  router.push({ path: '/chat', query: { q } })
}

onMounted(async () => {
  document.addEventListener('keydown', handleKeydown)
  try {
    const stats = await getStats()
    categories.value = [
      { key: 'source', label: 'Sources', count: stats.sources || 0 },
      { key: 'entity', label: 'Entities', count: stats.entities || 0 },
      { key: 'concept', label: 'Concepts', count: stats.concepts || 0 },
      { key: 'analysis', label: 'Analyses', count: stats.analyses || 0 },
    ]
  } catch {}
  try {
    const pages = await getPages()
    pinned.value = pages.slice(0, 2).map((p: any) => ({ slug: p.slug, title: p.title, type: p.type }))
  } catch {}
})
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

.rail-top, .rail-bottom {
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
  margin-bottom: 16px;
  transition: opacity var(--transition);
}
.rail-logo:hover { opacity: 0.85; text-decoration: none; }

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
  position: relative;
}
.rail-btn:hover {
  background: color-mix(in oklch, var(--paper) 60%, transparent);
}
.rail-btn.active {
  background: var(--paper);
  color: var(--accent-ink);
  box-shadow: inset 0 0 0 1px var(--line), var(--shadow-sm);
}
.rail-active-bar {
  position: absolute;
  left: -1px;
  top: 10px;
  bottom: 10px;
  width: 2px;
  background: var(--accent);
  border-radius: 0 2px 2px 0;
}
.rail-icon {
  width: 17px;
  height: 17px;
  font-size: 17px;
}
.rail-label {
  font-size: 9.5px;
  font-weight: 500;
  letter-spacing: 0.01em;
  line-height: 1;
}
.rail-ghost {
  width: 40px;
  height: 36px;
  display: grid;
  place-items: center;
  border: none;
  background: transparent;
  color: var(--ink-3);
  border-radius: 8px;
  cursor: pointer;
  transition: all var(--transition);
}
.rail-ghost:hover {
  background: color-mix(in oklch, var(--paper) 60%, transparent);
  color: var(--ink-2);
}

/* ---- WikiTree Sidebar ---- */
.wiki-tree {
  width: 268px;
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
.wiki-tree.collapsed { width: 0; border-right-color: transparent; }
.wiki-tree.collapsed > * {
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.1s ease;
}

/* ---- Workspace header ---- */
.ws-header {
  padding: 16px 18px 8px;
  flex-shrink: 0;
}
.ws-kicker {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.14em;
  color: var(--ink-4);
}
.ws-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 4px;
}
.ws-title {
  font-family: var(--font-display);
  font-size: 22px;
  line-height: 1.1;
  letter-spacing: -0.01em;
  color: var(--ink);
}
.ws-italic {
  font-style: italic;
  color: var(--accent-ink);
}

/* ---- Search ---- */
.search-wrap { padding: 4px 14px 8px; flex-shrink: 0; }
.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 8px;
  color: var(--ink-3);
}
.search-box:focus-within { border-color: var(--line-2); }
.search-icon { font-size: 13px; }
.search-box input {
  border: none;
  outline: none;
  background: transparent;
  flex: 1;
  color: var(--ink);
  font-size: 13px;
  font-family: var(--font-ui);
  min-width: 0;
}
.kbd {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--ink-4);
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 4px;
  padding: 1px 5px;
}

/* ---- Primary actions ---- */
.primary-actions {
  padding: 0 14px 12px;
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
.upload-btn {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 7px 10px;
  font-size: 12.5px;
  font-weight: 500;
  background: var(--ink);
  color: var(--paper);
  border: none;
  border-radius: 8px;
  text-decoration: none;
  cursor: pointer;
  font-family: var(--font-ui);
  transition: background var(--transition);
}
.upload-btn:hover { background: var(--ink-2); color: var(--paper); text-decoration: none; }
.icon-btn {
  width: 34px;
  height: 32px;
  display: grid;
  place-items: center;
  background: var(--paper-2);
  color: var(--ink-2);
  border: 1px solid var(--line);
  border-radius: 8px;
  cursor: pointer;
  text-decoration: none;
  transition: all var(--transition);
}
.icon-btn:hover { background: var(--paper-3); color: var(--ink); text-decoration: none; }
.icon-btn.ghost { background: transparent; border-color: transparent; }
.icon-btn.ghost:hover { background: var(--paper-2); }

/* ---- Sections ---- */
.section-block {
  padding: 0 10px 8px;
  flex-shrink: 0;
}
.sec-label {
  padding: 6px 10px 4px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.14em;
  color: var(--ink-4);
}
.sec-label.inset { padding-left: 10px; }

/* ---- Tree scroll ---- */
.tree-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 4px 10px 18px;
}

/* ---- Folder ---- */
.folder { margin-bottom: 2px; }
.folder-row {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 6px 10px;
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-family: var(--font-ui);
  text-align: left;
  transition: background var(--transition);
}
.folder-row:hover { background: var(--paper-2); }
.folder-chev {
  font-size: 11px;
  color: var(--ink-4);
  transition: transform var(--transition);
}
.folder-chev.open { transform: rotate(90deg); }
.folder-label {
  font-weight: 500;
  font-size: 12.5px;
  color: var(--ink-2);
  flex: 1;
}
.folder-count {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--ink-4);
}
.folder-kids { padding-left: 18px; }

/* ---- Leaf ---- */
.leaf {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 13px;
  color: var(--ink-2);
  text-decoration: none;
  transition: all var(--transition);
}
.leaf:hover { background: var(--paper-2); text-decoration: none; color: var(--ink); }
.leaf.active { background: var(--accent-soft); color: var(--accent-ink); }
.leaf.small { padding: 4px 10px; font-size: 12.5px; }

.leaf-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.leaf-title.muted { color: var(--ink-3); font-style: italic; }
.leaf-pin { font-size: 11px; color: oklch(0.65 0.13 75); flex-shrink: 0; }

.leaf-pill {
  display: inline-grid;
  place-items: center;
  width: 18px;
  height: 18px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  border-radius: 4px;
  border: 1px solid var(--line);
  color: var(--ink-3);
  background: var(--paper-2);
  flex-shrink: 0;
}
.leaf-pill[data-type="concept"]  { color: oklch(0.42 0.09 250); background: oklch(0.96 0.02 250); border-color: oklch(0.85 0.05 250); }
.leaf-pill[data-type="entity"]   { color: oklch(0.45 0.1 30);   background: oklch(0.96 0.025 30); border-color: oklch(0.86 0.06 30); }
.leaf-pill[data-type="source"]   { color: oklch(0.42 0.09 150); background: oklch(0.96 0.02 150); border-color: oklch(0.85 0.05 150); }
.leaf-pill[data-type="analysis"] { color: oklch(0.42 0.09 320); background: oklch(0.96 0.02 320); border-color: oklch(0.85 0.05 320); }

/* ---- User footer ---- */
.user-footer {
  padding: 10px 14px;
  border-top: 1px solid var(--line);
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  background: var(--paper);
}
.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: oklch(0.76 0.09 40);
  color: var(--paper);
  display: grid;
  place-items: center;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}
.user-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}
.user-name { font-size: 12.5px; font-weight: 500; color: var(--ink); }
.user-meta { font-size: 11px; color: var(--ink-4); }

/* ---- Sidebar toggle buttons ---- */
.sidebar-collapse-btn {
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--paper-2);
  color: var(--ink-4);
  cursor: pointer;
  transition: all var(--transition);
}
.sidebar-collapse-btn:hover {
  background: var(--paper-3);
  color: var(--ink-2);
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

/* ---- Floating AI button ---- */
.ai-fab {
  position: fixed;
  right: 22px;
  bottom: 22px;
  width: 46px;
  height: 46px;
  border-radius: 50%;
  background: var(--ink);
  color: var(--paper);
  border: none;
  display: grid;
  place-items: center;
  cursor: pointer;
  box-shadow: var(--shadow-md);
  z-index: 50;
  transition: all var(--transition);
}
.ai-fab:hover { transform: translateY(-2px); box-shadow: var(--shadow-lg); }
.ai-fab.open { background: var(--accent); }

/* ---- Mobile ---- */
@media (max-width: 768px) {
  .rail { display: none; }
  .wiki-tree {
    position: fixed;
    z-index: 1001;
    top: 0;
    left: 0;
    bottom: 0;
    box-shadow: var(--shadow-lg);
  }
  .wiki-tree.collapsed { width: 0; box-shadow: none; }
  .sidebar-overlay { left: 0; z-index: 1000; }
}
</style>
