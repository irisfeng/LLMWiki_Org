<template>
  <div class="wiki-editor">
    <div class="editor-toolbar">
      <span class="toolbar-title">编辑页面</span>
      <div class="toolbar-actions">
        <el-button @click="handleCancel">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </div>
    </div>

    <!-- Desktop: side-by-side | Mobile: tab switch -->
    <div class="editor-tabs-mobile">
      <el-radio-group v-model="activeTab" size="small">
        <el-radio-button value="edit">编辑</el-radio-button>
        <el-radio-button value="preview">预览</el-radio-button>
      </el-radio-group>
    </div>

    <div class="editor-body">
      <div class="editor-pane" :class="{ 'mobile-hidden': activeTab !== 'edit' }">
        <textarea
          ref="textareaRef"
          v-model="localContent"
          class="editor-textarea"
          placeholder="在此输入 Markdown 内容..."
          spellcheck="false"
        />
      </div>
      <div class="preview-pane" :class="{ 'mobile-hidden': activeTab !== 'preview' }">
        <MarkdownRenderer :content="localContent" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import MarkdownRenderer from './MarkdownRenderer.vue'
import { updatePage } from '../api/wiki'

const props = defineProps<{
  content: string
  slug: string
}>()

const emit = defineEmits<{
  saved: []
  cancel: []
}>()

const localContent = ref(props.content)
const saving = ref(false)
const dirty = ref(false)
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const activeTab = ref<'edit' | 'preview'>('edit')

// Track changes
watch(localContent, (val) => {
  dirty.value = val !== props.content
  autoResize()
})

// Reset if parent content changes (e.g. after reload)
watch(() => props.content, (val) => {
  localContent.value = val
  dirty.value = false
})

function autoResize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = el.scrollHeight + 'px'
}

onMounted(() => {
  nextTick(autoResize)
})

async function handleSave() {
  saving.value = true
  try {
    await updatePage(props.slug, localContent.value)
    ElMessage.success('已保存')
    dirty.value = false
    emit('saved')
  } catch (e: any) {
    ElMessage.error('保存失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

async function handleCancel() {
  if (dirty.value) {
    try {
      await ElMessageBox.confirm(
        '你有未保存的修改，确定要放弃吗？',
        '提示',
        { confirmButtonText: '放弃修改', cancelButtonText: '继续编辑', type: 'warning' }
      )
    } catch {
      // User clicked "继续编辑"
      return
    }
  }
  emit('cancel')
}
</script>

<style scoped>
.wiki-editor {
  display: flex;
  flex-direction: column;
  gap: 0;
  min-height: 400px;
}

.editor-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
  margin-bottom: 12px;
}

.toolbar-title {
  font-size: 1.1em;
  font-weight: 600;
  color: var(--text-primary);
}

.toolbar-actions {
  display: flex;
  gap: 8px;
}

.editor-tabs-mobile {
  display: none;
  margin-bottom: 12px;
}

.editor-body {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.editor-pane,
.preview-pane {
  flex: 1;
  min-width: 0;
  overflow: auto;
}

.editor-pane {
  display: flex;
  flex-direction: column;
}

.preview-pane {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  background: var(--bg-card);
  overflow-y: auto;
  max-height: 70vh;
}

.editor-textarea {
  width: 100%;
  min-height: 300px;
  padding: 12px 16px;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', 'Menlo', monospace;
  font-size: 14px;
  line-height: 1.6;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-input);
  color: var(--text-primary);
  resize: none;
  outline: none;
  overflow: hidden;
  transition: border-color var(--transition), box-shadow var(--transition);
}

.editor-textarea:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-soft);
}

.editor-textarea::placeholder {
  color: var(--text-muted);
}

/* Mobile: show tab switcher, hide inactive pane */
@media (max-width: 768px) {
  .editor-tabs-mobile {
    display: flex;
    justify-content: center;
  }

  .editor-body {
    flex-direction: column;
  }

  .mobile-hidden {
    display: none;
  }

  .preview-pane {
    max-height: 50vh;
  }
}
</style>
