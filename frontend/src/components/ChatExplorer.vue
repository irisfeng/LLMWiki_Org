<template>
  <transition name="explorer-slide">
    <aside v-if="visible" class="chat-explorer">
      <div class="explorer-header">
        <h3 class="explorer-title">知识探索</h3>
        <el-button
          :icon="Close"
          text
          size="small"
          class="explorer-close"
          @click="$emit('update:visible', false)"
        />
      </div>

      <div v-if="loading" class="explorer-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>加载中...</span>
      </div>

      <div v-else-if="!referencedPages.length" class="explorer-empty">
        <el-empty description="对话中暂无引用页面" :image-size="80" />
      </div>

      <div v-else class="explorer-body">
        <!-- Referenced sources -->
        <section class="explorer-section">
          <h4 class="section-label">引用来源</h4>
          <div class="source-cards">
            <a
              v-for="page in pageDetails"
              :key="page.slug"
              :href="`/wiki/${page.slug}`"
              target="_blank"
              rel="noopener"
              class="source-card"
            >
              <div class="source-card-head">
                <span class="source-card-title">{{ page.title || page.slug }}</span>
                <el-tag v-if="page.type" size="small" class="source-card-tag">{{ page.type }}</el-tag>
              </div>
              <p class="source-card-preview">{{ truncate(page.content, 80) }}</p>
            </a>
          </div>
        </section>

        <!-- Related pages -->
        <section v-if="relatedPages.length" class="explorer-section">
          <h4 class="section-label">相关页面</h4>
          <ul class="related-list">
            <li v-for="rp in relatedPages" :key="rp.slug">
              <a
                :href="`/wiki/${rp.slug}`"
                target="_blank"
                rel="noopener"
                class="related-item"
              >
                <span class="related-title">{{ rp.title || rp.slug }}</span>
                <el-tag v-if="rp.type" size="small" type="info">{{ rp.type }}</el-tag>
              </a>
            </li>
          </ul>
        </section>
      </div>
    </aside>
  </transition>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Close, Loading } from '@element-plus/icons-vue'
import { getPage, getRelatedPages } from '../api/wiki'

interface PageDetail {
  slug: string
  title?: string
  type?: string
  content?: string
}

const props = defineProps<{
  referencedPages: string[]
  visible: boolean
}>()

defineEmits<{
  'update:visible': [value: boolean]
}>()

const loading = ref(false)
const pageDetails = ref<PageDetail[]>([])
const relatedPages = ref<PageDetail[]>([])

function truncate(text: string | undefined, max: number): string {
  if (!text) return ''
  const clean = text.replace(/\n+/g, ' ').trim()
  return clean.length > max ? clean.slice(0, max) + '...' : clean
}

watch(
  () => props.referencedPages,
  async (slugs) => {
    if (!slugs.length) {
      pageDetails.value = []
      relatedPages.value = []
      return
    }

    loading.value = true
    try {
      // Fetch all referenced page details in parallel
      const details = await Promise.all(
        slugs.map(async (slug) => {
          try {
            return await getPage(slug)
          } catch {
            return { slug, title: slug } as PageDetail
          }
        }),
      )
      pageDetails.value = details

      // Fetch related pages for the first referenced page
      if (slugs.length > 0) {
        try {
          const related = await getRelatedPages(slugs[0])
          relatedPages.value = Array.isArray(related) ? related : []
        } catch {
          relatedPages.value = []
        }
      }
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.chat-explorer {
  width: 300px;
  min-width: 300px;
  height: 100%;
  border-left: 1px solid var(--border);
  background-color: var(--bg-secondary);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.explorer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.explorer-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.explorer-close {
  color: var(--text-muted);
}

.explorer-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px 16px;
  color: var(--text-muted);
  font-size: 14px;
}

.explorer-empty {
  padding: 40px 16px;
}

.explorer-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.explorer-section {
  margin-bottom: 20px;
}

.section-label {
  margin: 0 0 10px 4px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}

.source-cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.source-card {
  display: block;
  padding: 12px;
  border-radius: var(--radius-sm);
  background-color: var(--bg-card);
  border: 1px solid var(--border);
  text-decoration: none;
  transition: border-color var(--transition), box-shadow var(--transition);
  cursor: pointer;
}

.source-card:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-sm);
}

.source-card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.source-card-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-card-tag {
  flex-shrink: 0;
}

.source-card-preview {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.related-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.related-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  text-decoration: none;
  transition: background-color var(--transition);
}

.related-item:hover {
  background-color: var(--bg-hover);
}

.related-title {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Slide transition */
.explorer-slide-enter-active,
.explorer-slide-leave-active {
  transition: all 0.2s ease;
}

.explorer-slide-enter-from,
.explorer-slide-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

@media (max-width: 1023px) {
  .chat-explorer {
    position: fixed;
    top: 56px;
    right: 0;
    bottom: 0;
    z-index: 1001;
    box-shadow: var(--shadow-lg);
  }
}
</style>
