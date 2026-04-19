<template>
  <div class="source-preview" :data-mode="mode">
    <!-- PDF / HTML: iframe a blob URL (iframes can't carry Authorization headers) -->
    <iframe
      v-if="mode === 'iframe' && iframeSrc"
      :src="iframeSrc"
      class="preview-iframe"
      :title="filename"
    />

    <!-- Plain text: preformatted -->
    <pre v-else-if="mode === 'text'" class="preview-text">{{ textContent }}</pre>

    <!-- Markdown: render through MarkdownRenderer -->
    <div v-else-if="mode === 'md'" class="preview-md">
      <MarkdownRenderer :content="textContent" />
    </div>

    <!-- DOCX: mammoth-converted HTML -->
    <div
      v-else-if="mode === 'docx'"
      class="preview-docx"
      v-html="docxHtml"
    />

    <!-- XLSX: rendered spreadsheet -->
    <div v-else-if="mode === 'xlsx'" class="preview-xlsx">
      <div v-if="xlsxSheets.length > 1" class="xlsx-tabs">
        <button
          v-for="(s, i) in xlsxSheets"
          :key="s.name"
          class="xlsx-tab"
          :class="{ active: i === activeSheet }"
          @click="activeSheet = i"
        >{{ s.name }}</button>
      </div>
      <div
        class="xlsx-sheet"
        v-html="xlsxSheets[activeSheet]?.html || ''"
      />
    </div>

    <!-- Unsupported (pptx, zip, …) or failed: download CTA -->
    <div v-else-if="mode === 'fallback'" class="preview-fallback">
      <div class="fallback-icon">📄</div>
      <div class="fallback-title">{{ fallbackReason }}</div>
      <a :href="downloadUrl" class="fallback-btn">下载原文</a>
    </div>

    <div v-else-if="mode === 'loading'" class="preview-loading">
      解析中…
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onBeforeUnmount, onMounted, watch } from 'vue'
import MarkdownRenderer from './MarkdownRenderer.vue'
import { sourceRawUrl, sourceDownloadUrl } from '../api/wiki'

const props = defineProps<{
  sourceId: string
  filename: string
}>()

const downloadUrl = computed(() => sourceDownloadUrl(props.sourceId))
const iframeSrc = ref('')

const ext = computed(() => {
  const i = props.filename.lastIndexOf('.')
  return i < 0 ? '' : props.filename.slice(i + 1).toLowerCase()
})

type Mode = 'loading' | 'iframe' | 'text' | 'md' | 'docx' | 'xlsx' | 'fallback'
const mode = ref<Mode>('loading')
const textContent = ref('')
const docxHtml = ref('')
const xlsxSheets = ref<{ name: string; html: string }[]>([])
const activeSheet = ref(0)
const fallbackReason = ref('此格式暂不支持在线预览')

async function fetchRawWithAuth(): Promise<Response> {
  const token = localStorage.getItem('token')
  const r = await fetch(sourceRawUrl(props.sourceId), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!r.ok) {
    if (r.status === 401) {
      // Mirror axios interceptor behavior: clear token and redirect to login.
      localStorage.removeItem('token')
      window.location.href = '/login'
      throw new Error('登录已过期，请重新登录')
    }
    throw new Error(`HTTP ${r.status}`)
  }
  return r
}

async function fetchText() {
  const r = await fetchRawWithAuth()
  return await r.text()
}

async function fetchArrayBuffer() {
  const r = await fetchRawWithAuth()
  return await r.arrayBuffer()
}

async function loadIframeBlob() {
  const r = await fetchRawWithAuth()
  const blob = await r.blob()
  // Preserve server-declared content-type so the browser renders PDF/HTML correctly.
  const typed = blob.type ? blob : new Blob([blob], { type: guessMime(ext.value) })
  if (iframeSrc.value) URL.revokeObjectURL(iframeSrc.value)
  iframeSrc.value = URL.createObjectURL(typed)
}

function guessMime(e: string): string {
  if (e === 'pdf') return 'application/pdf'
  if (e === 'html' || e === 'htm') return 'text/html'
  return 'application/octet-stream'
}

async function loadDocx() {
  // Lazy-load mammoth only when needed — saves ~300 KB on pages that don't preview docx.
  const mammoth = await import('mammoth')
  const buf = await fetchArrayBuffer()
  const { value } = await mammoth.convertToHtml({ arrayBuffer: buf })
  docxHtml.value = value
}

async function loadXlsx() {
  const XLSX = await import('xlsx')
  const buf = await fetchArrayBuffer()
  const wb = XLSX.read(buf, { type: 'array' })
  xlsxSheets.value = wb.SheetNames.map((name) => ({
    name,
    html: XLSX.utils.sheet_to_html(wb.Sheets[name]),
  }))
}

async function run() {
  mode.value = 'loading'
  try {
    switch (ext.value) {
      case 'pdf':
      case 'html':
      case 'htm':
        await loadIframeBlob()
        mode.value = 'iframe'
        break
      case 'txt':
      case 'csv':
        textContent.value = await fetchText()
        mode.value = 'text'
        break
      case 'md':
      case 'markdown':
        textContent.value = await fetchText()
        mode.value = 'md'
        break
      case 'docx':
        await loadDocx()
        mode.value = 'docx'
        break
      case 'xlsx':
      case 'xls':
        await loadXlsx()
        mode.value = 'xlsx'
        break
      case 'doc':
        fallbackReason.value = '旧版 .doc 格式暂不支持预览，可下载后用 Word 打开'
        mode.value = 'fallback'
        break
      case 'pptx':
      case 'ppt':
        fallbackReason.value = '演示文稿暂不支持在线预览，可下载后用 PowerPoint 打开'
        mode.value = 'fallback'
        break
      default:
        fallbackReason.value = `.${ext.value || '?'} 格式暂不支持在线预览`
        mode.value = 'fallback'
    }
  } catch (e: any) {
    console.error('[SourcePreview] failed', e)
    fallbackReason.value = `预览失败：${e?.message || e}`
    mode.value = 'fallback'
  }
}

onMounted(run)
watch(() => props.sourceId, run)
onBeforeUnmount(() => {
  if (iframeSrc.value) URL.revokeObjectURL(iframeSrc.value)
})
</script>

<style scoped>
.source-preview {
  width: 100%;
}

.preview-iframe {
  width: 100%;
  min-height: 78vh;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--paper);
}

.preview-text {
  margin: 0;
  padding: 18px 20px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--paper);
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
  font-size: 13px;
  line-height: 1.6;
  color: var(--ink);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 78vh;
  overflow: auto;
}

.preview-md,
.preview-docx {
  padding: 24px 28px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--paper);
  max-height: 78vh;
  overflow: auto;
  font-size: 14.5px;
  line-height: 1.75;
  color: var(--ink);
}

.preview-docx :deep(p) {
  margin: 0 0 12px;
}
.preview-docx :deep(h1),
.preview-docx :deep(h2),
.preview-docx :deep(h3) {
  font-weight: 600;
  margin: 18px 0 8px;
  color: var(--ink);
}
.preview-docx :deep(table) {
  border-collapse: collapse;
  margin: 10px 0;
  font-size: 13px;
}
.preview-docx :deep(td),
.preview-docx :deep(th) {
  border: 1px solid var(--line);
  padding: 6px 10px;
}
.preview-docx :deep(img) {
  max-width: 100%;
  height: auto;
}

.preview-xlsx {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--paper);
  max-height: 78vh;
  overflow: auto;
}
.xlsx-tabs {
  display: flex;
  gap: 4px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--line);
  background: var(--paper-2, #f3efe5);
  position: sticky;
  top: 0;
  z-index: 1;
}
.xlsx-tab {
  border: 1px solid transparent;
  background: transparent;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12.5px;
  color: var(--ink-3);
  cursor: pointer;
}
.xlsx-tab.active {
  background: var(--paper);
  border-color: var(--line);
  color: var(--ink);
}
.xlsx-sheet {
  padding: 10px;
  overflow: auto;
}
.xlsx-sheet :deep(table) {
  border-collapse: collapse;
  font-size: 12.5px;
  font-family: var(--font-mono, ui-monospace, monospace);
}
.xlsx-sheet :deep(td),
.xlsx-sheet :deep(th) {
  border: 1px solid var(--line);
  padding: 3px 8px;
  white-space: nowrap;
}

.preview-fallback {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 48px 24px;
  border: 1px dashed var(--line-2, #d3cdb9);
  border-radius: 10px;
  background: repeating-linear-gradient(
    -45deg,
    transparent 0 10px,
    rgba(0, 0, 0, 0.015) 10px 20px
  );
}
.fallback-icon {
  font-size: 40px;
}
.fallback-title {
  font-size: 14px;
  color: var(--ink-3);
}
.fallback-btn {
  margin-top: 4px;
  padding: 8px 18px;
  border-radius: 6px;
  background: var(--ink);
  color: var(--paper);
  text-decoration: none;
  font-size: 13.5px;
}
.fallback-btn:hover {
  opacity: 0.9;
}

.preview-loading {
  padding: 40px;
  text-align: center;
  font-size: 13px;
  color: var(--ink-4);
}
</style>
