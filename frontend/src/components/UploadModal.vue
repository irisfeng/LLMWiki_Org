<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" class="modal-mask" @click.self="tryClose">
        <div class="modal-box" role="dialog" aria-modal="true">
          <!-- Header -->
          <div class="modal-header">
            <div class="header-icon">
              <el-icon :size="18"><UploadFilled /></el-icon>
            </div>
            <div class="header-text">
              <div class="header-title">上传到知识库</div>
              <div class="header-sub">PDF · Word · PPT · Excel · Markdown · TXT · HTML · URL · 文本</div>
            </div>
            <button class="icon-btn" @click="tryClose" title="关闭">
              <el-icon :size="16"><Close /></el-icon>
            </button>
          </div>

          <!-- Mode tabs -->
          <div class="mode-tabs">
            <button
              v-for="m in modes"
              :key="m.k"
              class="mode-tab"
              :class="{ active: mode === m.k }"
              @click="mode = m.k"
            >
              <el-icon><component :is="m.icon" /></el-icon>
              {{ m.label }}
            </button>
          </div>

          <div class="modal-body">
            <!-- File mode -->
            <div v-if="mode === 'file'" class="pane">
              <div
                class="dropzone"
                :class="{ 'is-dragging': isDragging, 'has-files': files.length > 0 }"
                @dragover.prevent="isDragging = true"
                @dragleave.prevent="isDragging = false"
                @drop.prevent="onDrop"
              >
                <input
                  type="file"
                  multiple
                  class="file-input"
                  :accept="ACCEPT"
                  @change="onFilePick"
                />
                <div v-if="!files.length" class="dropzone-empty">
                  <el-icon :size="28" class="dropzone-icon"><UploadFilled /></el-icon>
                  <div class="dropzone-title">拖拽文件到这里</div>
                  <div class="dropzone-hint">或 <span class="link-accent">点击选择</span> · 支持多选</div>
                </div>
                <div v-else class="dropzone-filled">
                  <el-icon :size="20" class="dropzone-icon-small"><UploadFilled /></el-icon>
                  <span>继续拖入或点击添加</span>
                </div>
              </div>

              <!-- File list -->
              <ul v-if="files.length" class="file-list" @click.stop>
                <li v-for="(item, idx) in files" :key="item.uid" class="file-row" :data-status="item.status">
                  <span class="file-ext" :data-kind="kindOf(item.file.name)">{{ extOf(item.file.name) }}</span>
                  <div class="file-main">
                    <div class="file-name" :title="item.file.name">{{ item.file.name }}</div>
                    <div class="file-meta">
                      <span>{{ formatSize(item.file.size) }}</span>
                      <span v-if="item.status === 'queued'" class="status-txt">排队中</span>
                      <span v-else-if="item.status === 'uploading'" class="status-txt">上传中 {{ item.progress }}%</span>
                      <span v-else-if="item.status === 'processing'" class="status-txt">解析中…</span>
                      <span v-else-if="item.status === 'done'" class="status-txt done">
                        已入库<span v-if="item.pagesCount"> · 生成 {{ item.pagesCount }} 页</span>
                        <router-link
                          v-if="item.sourceId"
                          :to="`/source/${item.sourceId}`"
                          class="done-link"
                          @click="closeUploadModal"
                        >查看 →</router-link>
                      </span>
                      <span v-else-if="item.status === 'failed'" class="status-txt failed" :title="item.error">
                        失败：{{ item.error }}
                      </span>
                    </div>
                    <div v-if="item.status === 'uploading'" class="file-progress">
                      <div class="file-progress-fill" :style="{ width: item.progress + '%' }"></div>
                    </div>
                  </div>
                  <div class="file-actions">
                    <button
                      v-if="item.status === 'failed'"
                      class="row-btn"
                      @click="retryFile(idx)"
                      title="重试"
                    ><el-icon><Refresh /></el-icon></button>
                    <button
                      v-if="item.status === 'queued' || item.status === 'failed'"
                      class="row-btn danger"
                      @click="removeFile(idx)"
                      title="移除"
                    ><el-icon><Close /></el-icon></button>
                  </div>
                </li>
              </ul>
            </div>

            <!-- URL mode -->
            <div v-else-if="mode === 'url'" class="pane">
              <label class="field">
                <span class="field-label">URL</span>
                <input
                  v-model="urlForm.url"
                  class="field-input"
                  placeholder="https://..."
                  @keyup.enter="submitUrlForm"
                />
              </label>
            </div>

            <!-- Text mode -->
            <div v-else class="pane">
              <label class="field">
                <span class="field-label">标题</span>
                <input v-model="textForm.title" class="field-input" placeholder="源材料标题（可选）" />
              </label>
              <label class="field">
                <span class="field-label">内容</span>
                <textarea
                  v-model="textForm.text"
                  class="field-input field-textarea"
                  rows="10"
                  placeholder="粘贴文本内容..."
                />
              </label>
            </div>

            <!-- Common: submitter -->
            <label class="field">
              <span class="field-label">提交者</span>
              <input v-model="submittedBy" class="field-input" placeholder="你的名字（可选）" />
            </label>

            <!-- AI note -->
            <div class="ai-note">
              <el-icon class="ai-icon"><MagicStick /></el-icon>
              AI 会自动抽取标题、摘要、实体，链接到已有概念，并打上健康度标签。
            </div>
          </div>

          <!-- Footer -->
          <div class="modal-footer">
            <div class="summary">
              <template v-if="mode === 'file' && files.length">
                {{ files.length }} 个文件 · {{ formatSize(totalSize) }}
                <span v-if="counts.done" class="chip done">{{ counts.done }} 完成</span>
                <span v-if="counts.failed" class="chip failed">{{ counts.failed }} 失败</span>
                <span v-if="counts.active" class="chip active">{{ counts.active }} 处理中</span>
              </template>
            </div>
            <div class="actions">
              <button class="ghost-btn" @click="tryClose">{{ isUploading ? '关闭' : '取消' }}</button>
              <button
                v-if="mode === 'file'"
                class="primary-btn"
                :disabled="!files.length || isUploading"
                @click="startUploadAll"
              >{{ isUploading ? `上传中… ${counts.done}/${files.length}` : '上传并解析' }}</button>
              <button
                v-else-if="mode === 'url'"
                class="primary-btn"
                :disabled="!urlForm.url || isUploading"
                @click="submitUrlForm"
              >{{ isUploading ? '提交中…' : '提交 URL' }}</button>
              <button
                v-else
                class="primary-btn"
                :disabled="!textForm.text || isUploading"
                @click="submitTextForm"
              >{{ isUploading ? '提交中…' : '提交文本' }}</button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Close, Refresh, Document, Link, MagicStick } from '@element-plus/icons-vue'
import { uploadFile, submitUrl, submitText, getSource } from '../api/sources'
import { isUploadModalOpen, closeUploadModal, onUploadDone } from '../composables/useUploadModal'

const ACCEPT = '.pdf,.docx,.doc,.xlsx,.xls,.pptx,.ppt,.md,.txt,.html,.csv'
const MAX_FILE_MB = 100
const CONCURRENCY = 3

const modes = [
  { k: 'file' as const, label: '上传文件', icon: UploadFilled },
  { k: 'url' as const, label: '输入 URL', icon: Link },
  { k: 'text' as const, label: '粘贴文本', icon: Document },
]

const mode = ref<'file' | 'url' | 'text'>('file')
const submittedBy = ref(localStorage.getItem('userName') || '')

const textForm = reactive({ title: '', text: '' })
const urlForm = reactive({ url: '' })

interface FileItem {
  uid: number
  file: File
  status: 'queued' | 'uploading' | 'processing' | 'done' | 'failed'
  progress: number
  error?: string
  sourceId?: string
  pagesCount?: number
}
const files = ref<FileItem[]>([])
const isDragging = ref(false)
let uidSeq = 0

const open = computed(() => isUploadModalOpen.value)

const counts = computed(() => ({
  done: files.value.filter(f => f.status === 'done').length,
  failed: files.value.filter(f => f.status === 'failed').length,
  active: files.value.filter(f => f.status === 'uploading' || f.status === 'processing').length,
}))

const isUploading = computed(() => counts.value.active > 0)

const totalSize = computed(() => files.value.reduce((s, f) => s + f.file.size, 0))

function extOf(name: string) {
  const dot = name.lastIndexOf('.')
  return dot < 0 ? 'FILE' : name.slice(dot + 1).toUpperCase().slice(0, 4)
}
function kindOf(name: string) {
  const ext = extOf(name).toLowerCase()
  if (['pdf'].includes(ext)) return 'pdf'
  if (['md', 'txt'].includes(ext)) return 'text'
  if (['docx', 'doc'].includes(ext)) return 'word'
  if (['xlsx', 'xls', 'csv'].includes(ext)) return 'excel'
  if (['pptx', 'ppt'].includes(ext)) return 'ppt'
  if (['html', 'htm'].includes(ext)) return 'web'
  return 'other'
}
function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}

function onFilePick(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files) addFiles(Array.from(input.files))
  input.value = ''
}

function onDrop(e: DragEvent) {
  isDragging.value = false
  const list = e.dataTransfer?.files
  if (list) addFiles(Array.from(list))
}

function addFiles(list: File[]) {
  for (const f of list) {
    if (f.size > MAX_FILE_MB * 1024 * 1024) {
      ElMessage.warning(`${f.name} 超过 ${MAX_FILE_MB}MB，已跳过`)
      continue
    }
    files.value.push({ uid: ++uidSeq, file: f, status: 'queued', progress: 0 })
  }
}

function removeFile(idx: number) {
  files.value.splice(idx, 1)
}

async function retryFile(idx: number) {
  const item = files.value[idx]
  item.status = 'queued'
  item.progress = 0
  item.error = undefined
  runQueue()
}

async function uploadOne(item: FileItem) {
  item.status = 'uploading'
  item.progress = 0
  try {
    const resp = await uploadFile(item.file, submittedBy.value, (pct) => { item.progress = pct })
    item.sourceId = resp?.id
    item.progress = 100
    // If backend already marked failed (e.g. extraction failed synchronously)
    if (resp?.status === 'failed') {
      item.status = 'failed'
      item.error = resp.error_message || '解析失败'
      return
    }
    item.status = 'processing'
    pollIngestion(item)
  } catch (e: any) {
    item.status = 'failed'
    item.error = e?.response?.data?.detail || e?.message || '上传失败'
  }
}

async function pollIngestion(item: FileItem) {
  if (!item.sourceId) return
  const started = Date.now()
  const MAX_MS = 3 * 60 * 1000  // 3 min ceiling
  while (Date.now() - started < MAX_MS) {
    await new Promise(r => setTimeout(r, 2500))
    try {
      const s = await getSource(item.sourceId!)
      if (s.status === 'done') {
        item.status = 'done'
        item.pagesCount = s.generated_pages_count || 0
        onUploadDone()
        return
      }
      if (s.status === 'failed') {
        item.status = 'failed'
        item.error = s.error_message || '解析失败'
        onUploadDone()
        return
      }
      // still pending/processing — loop
    } catch { /* transient — keep polling */ }
  }
  // Timeout — don't mark failed, just surface to user
  item.error = '解析耗时较长，请稍后在知识库查看'
}

async function runQueue() {
  const queued = () => files.value.filter(f => f.status === 'queued')
  const running = () => files.value.filter(f => f.status === 'uploading' || f.status === 'processing').length
  while (queued().length > 0) {
    while (running() < CONCURRENCY && queued().length > 0) {
      const next = queued()[0]
      if (!next) break
      uploadOne(next)  // fire-and-forget; state transitions handled inside
      await new Promise(r => setTimeout(r, 20))  // yield
    }
    await new Promise(r => setTimeout(r, 200))
  }
}

async function startUploadAll() {
  if (submittedBy.value) localStorage.setItem('userName', submittedBy.value)
  await runQueue()
  // Don't auto-close — let user see processing/done states and click through
}

async function submitUrlForm() {
  try {
    await submitUrl(urlForm.url, submittedBy.value)
    ElMessage.success('URL 已提交，正在抓取解析')
    urlForm.url = ''
    onUploadDone()
    closeUploadModal()
  } catch (e: any) {
    ElMessage.error('提交失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  }
}

async function submitTextForm() {
  try {
    await submitText(textForm.text, textForm.title, submittedBy.value)
    ElMessage.success('文本已提交，正在解析')
    textForm.title = ''; textForm.text = ''
    onUploadDone()
    closeUploadModal()
  } catch (e: any) {
    ElMessage.error('提交失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  }
}

async function tryClose() {
  if (isUploading.value) {
    try {
      await ElMessageBox.confirm('还有文件正在上传，关闭将中断未完成的上传（已开始的不受影响）。', '确认关闭', {
        confirmButtonText: '仍然关闭',
        cancelButtonText: '继续上传',
        type: 'warning',
      })
    } catch { return }
  }
  closeUploadModal()
  // Reset on close if nothing in-flight
  if (!isUploading.value) {
    files.value = files.value.filter(f => f.status !== 'done')
  }
}

// Reset transient state when modal opens fresh
watch(open, (v) => {
  if (v) {
    mode.value = 'file'
    if (!submittedBy.value) submittedBy.value = localStorage.getItem('userName') || ''
  }
})
</script>

<style scoped>
.modal-mask {
  position: fixed; inset: 0; z-index: 2000;
  background: color-mix(in srgb, var(--ink) 40%, transparent);
  backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
}
.modal-box {
  width: 100%; max-width: 560px; max-height: 90vh;
  background: var(--paper);
  border-radius: 14px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.25);
  display: flex; flex-direction: column;
  overflow: hidden;
}
.modal-header {
  display: flex; align-items: center; gap: 12px;
  padding: 18px 22px 14px;
  border-bottom: 1px solid var(--line);
}
.header-icon {
  width: 36px; height: 36px;
  display: grid; place-items: center;
  background: oklch(0.95 0.04 150); color: oklch(0.50 0.12 150);
  border-radius: 10px;
}
.header-text { flex: 1; min-width: 0; }
.header-title { font-family: var(--font-display); font-size: 18px; color: var(--ink); line-height: 1.2; }
.header-sub { font-size: 12px; color: var(--ink-4); margin-top: 3px; font-family: var(--font-mono); }
.icon-btn {
  width: 28px; height: 28px; border-radius: 6px;
  background: transparent; border: none; color: var(--ink-3);
  cursor: pointer; display: grid; place-items: center;
  transition: background .15s;
}
.icon-btn:hover { background: var(--paper-2); color: var(--ink); }

.mode-tabs {
  display: flex; gap: 4px; padding: 10px 20px;
  border-bottom: 1px solid var(--line);
  background: var(--paper-2);
}
.mode-tab {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 6px 12px; border-radius: 6px;
  background: transparent; border: 1px solid transparent;
  font-size: 13px; color: var(--ink-3); cursor: pointer;
  transition: all .15s;
}
.mode-tab:hover { background: var(--paper); color: var(--ink); }
.mode-tab.active { background: var(--paper); color: var(--ink); border-color: var(--line); }

.modal-body { padding: 18px 22px; overflow-y: auto; flex: 1; }

.pane { display: flex; flex-direction: column; gap: 14px; margin-bottom: 14px; }

.dropzone {
  position: relative;
  border: 2px dashed var(--line);
  border-radius: 12px;
  padding: 32px 20px;
  background: var(--paper-2);
  text-align: center;
  cursor: pointer;
  transition: all .2s;
}
.dropzone:hover { border-color: var(--ink-3); background: var(--paper); }
.dropzone.is-dragging { border-color: oklch(0.50 0.12 150); background: oklch(0.97 0.03 150); }
.dropzone.has-files { padding: 14px; }
.file-input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.dropzone-icon { color: var(--ink-3); margin-bottom: 8px; }
.dropzone-title { font-size: 14px; color: var(--ink); margin-bottom: 4px; }
.dropzone-hint { font-size: 12.5px; color: var(--ink-4); }
.link-accent { color: oklch(0.50 0.12 150); font-weight: 500; }
.dropzone-filled { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--ink-3); }
.dropzone-icon-small { color: var(--ink-4); }

.file-list { list-style: none; padding: 0; margin: 10px 0 0; display: flex; flex-direction: column; gap: 4px; max-height: 220px; overflow-y: auto; }
.file-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 10px; align-items: center;
  padding: 8px 10px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 8px;
}
.file-row[data-status="done"] { border-color: oklch(0.85 0.08 150); background: oklch(0.97 0.02 150); }
.file-row[data-status="failed"] { border-color: oklch(0.85 0.10 25); background: oklch(0.98 0.02 25); }
.file-ext {
  min-width: 40px; padding: 3px 8px;
  font-family: var(--font-mono); font-size: 10.5px; font-weight: 600;
  text-align: center; border-radius: 4px;
  background: var(--paper); color: var(--ink-3);
  border: 1px solid var(--line);
}
.file-ext[data-kind="pdf"] { color: oklch(0.50 0.15 25); background: oklch(0.97 0.03 25); border-color: oklch(0.85 0.08 25); }
.file-ext[data-kind="word"] { color: oklch(0.50 0.15 250); background: oklch(0.97 0.03 250); border-color: oklch(0.85 0.08 250); }
.file-ext[data-kind="ppt"] { color: oklch(0.50 0.15 60); background: oklch(0.97 0.03 60); border-color: oklch(0.85 0.08 60); }
.file-ext[data-kind="excel"] { color: oklch(0.45 0.15 150); background: oklch(0.97 0.03 150); border-color: oklch(0.85 0.08 150); }
.file-ext[data-kind="text"] { color: var(--ink-3); }
.file-main { min-width: 0; }
.file-name { font-size: 13px; color: var(--ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-meta { font-size: 11.5px; color: var(--ink-4); font-family: var(--font-mono); display: flex; gap: 8px; margin-top: 2px; }
.status-txt.done { color: oklch(0.45 0.12 150); display: inline-flex; align-items: center; gap: 6px; }
.status-txt.failed { color: oklch(0.50 0.15 25); }
.done-link { color: oklch(0.45 0.12 150); text-decoration: none; font-weight: 500; }
.done-link:hover { text-decoration: underline; }
.file-progress { margin-top: 4px; height: 3px; background: var(--paper); border-radius: 2px; overflow: hidden; }
.file-progress-fill { height: 100%; background: var(--ink); transition: width .15s; }
.file-actions { display: flex; gap: 4px; }
.row-btn {
  width: 24px; height: 24px; display: grid; place-items: center;
  background: transparent; border: 1px solid var(--line); border-radius: 5px;
  color: var(--ink-3); cursor: pointer; transition: all .15s;
}
.row-btn:hover { background: var(--paper); color: var(--ink); }
.row-btn.danger:hover { color: oklch(0.50 0.15 25); border-color: oklch(0.80 0.10 25); }

.field { display: flex; flex-direction: column; gap: 5px; }
.field-label { font-family: var(--font-mono); font-size: 10.5px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-4); }
.field-input {
  width: 100%; padding: 9px 12px;
  background: var(--paper-2); border: 1px solid var(--line);
  border-radius: 8px; font-size: 13px; color: var(--ink); font-family: inherit;
}
.field-input:focus { outline: none; border-color: var(--ink-3); background: var(--paper); }
.field-textarea { resize: vertical; min-height: 140px; font-family: var(--font-mono); font-size: 12.5px; line-height: 1.6; }

.ai-note {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 10px 12px; margin-top: 4px;
  background: oklch(0.96 0.04 150); color: oklch(0.40 0.10 150);
  border: 1px solid oklch(0.88 0.06 150);
  border-radius: 8px; font-size: 12.5px; line-height: 1.5;
}
.ai-icon { margin-top: 2px; }

.modal-footer {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 22px;
  border-top: 1px solid var(--line);
  background: var(--paper-2);
}
.summary { flex: 1; font-size: 12.5px; color: var(--ink-4); display: flex; align-items: center; gap: 6px; }
.chip { padding: 2px 8px; border-radius: 999px; font-size: 11px; font-family: var(--font-mono); }
.chip.done { background: oklch(0.95 0.03 150); color: oklch(0.45 0.12 150); }
.chip.failed { background: oklch(0.96 0.03 25); color: oklch(0.50 0.15 25); }
.chip.active { background: oklch(0.95 0.03 60); color: oklch(0.50 0.12 60); }

.actions { display: flex; gap: 8px; }
.ghost-btn {
  padding: 8px 16px; background: transparent; border: 1px solid var(--line);
  border-radius: 999px; font-size: 13px; color: var(--ink-3);
  cursor: pointer; transition: all .15s;
}
.ghost-btn:hover { color: var(--ink); background: var(--paper); }
.primary-btn {
  padding: 8px 18px; background: var(--ink); color: var(--paper);
  border: none; border-radius: 999px; font-size: 13px; font-weight: 500;
  cursor: pointer; transition: opacity .15s;
}
.primary-btn:hover:not(:disabled) { opacity: 0.85; }
.primary-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.modal-enter-active, .modal-leave-active { transition: opacity .2s; }
.modal-enter-active .modal-box, .modal-leave-active .modal-box { transition: transform .2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-from .modal-box, .modal-leave-to .modal-box { transform: translateY(8px) scale(0.98); }

@media (max-width: 640px) {
  .modal-box { max-width: 100%; max-height: 100vh; border-radius: 0; }
}
</style>
