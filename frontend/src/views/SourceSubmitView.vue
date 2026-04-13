<template>
  <AppLayout>
    <div class="submit-page">
      <h2>提交新源</h2>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="粘贴文本" name="text">
          <el-form label-position="top">
            <el-form-item label="标题">
              <el-input v-model="textForm.title" placeholder="源材料标题" />
            </el-form-item>
            <el-form-item label="内容">
              <el-input v-model="textForm.text" type="textarea" :rows="12" placeholder="粘贴文本内容..." />
            </el-form-item>
            <el-form-item label="提交者">
              <el-input v-model="textForm.submittedBy" placeholder="你的名字" />
            </el-form-item>
            <el-button type="primary" @click="doSubmitText" :loading="submitting">提交</el-button>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="输入 URL" name="url">
          <el-form label-position="top">
            <el-form-item label="URL">
              <el-input v-model="urlForm.url" placeholder="https://..." />
            </el-form-item>
            <el-form-item label="提交者">
              <el-input v-model="urlForm.submittedBy" placeholder="你的名字" />
            </el-form-item>
            <el-button type="primary" @click="doSubmitUrl" :loading="submitting">提交</el-button>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="上传文件" name="file">
          <el-form label-position="top">
            <el-form-item label="文件">
              <el-upload
                :auto-upload="false"
                :on-change="handleFileChange"
                :on-remove="handleFileRemove"
                multiple
                accept=".pdf,.docx,.doc,.xlsx,.xls,.pptx,.ppt,.md,.txt,.html,.csv"
              >
                <el-button>选择文件</el-button>
                <template #tip>
                  <div class="el-upload__tip">支持多选。PDF、Word、Excel、PPT、Markdown、TXT 格式</div>
                </template>
              </el-upload>
            </el-form-item>
            <el-form-item v-if="uploadProgress > 0" label="上传进度">
              <el-progress :percentage="uploadProgress" :stroke-width="12" />
              <div style="font-size:12px;color:#888;margin-top:4px">{{ uploadingFileName }}</div>
            </el-form-item>
            <el-form-item label="提交者">
              <el-input v-model="fileForm.submittedBy" placeholder="你的名字" />
            </el-form-item>
            <el-button type="primary" @click="doUploadFile" :loading="submitting">{{ submitting && uploadProgress > 0 ? `上传中 ${uploadProgress}%` : '上传并提交' }}</el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <el-divider />

      <h3>最近提交</h3>
      <el-table :data="sources" v-loading="loadingSources">
        <el-table-column prop="filename" label="文件名" />
        <el-table-column prop="submitted_by" label="提交者" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button v-if="row.file_path" link type="primary" size="small" @click="downloadFile(row.id)">下载</el-button>
            <el-button link type="warning" size="small" @click="doReingest(row.id)">重新处理</el-button>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="提交时间" width="180">
          <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
        </el-table-column>
      </el-table>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import AppLayout from '../components/AppLayout.vue'
import { submitText, submitUrl, uploadFile, listSources, reingestSource } from '../api/sources'

const activeTab = ref('text')
const submitting = ref(false)
const loadingSources = ref(false)
const sources = ref<any[]>([])
const uploadProgress = ref(0)
const uploadingFileName = ref('')

const textForm = reactive({ title: '', text: '', submittedBy: '' })
const urlForm = reactive({ url: '', submittedBy: '' })
const fileForm = reactive({ files: [] as File[], submittedBy: '' })

function statusType(status: string) {
  return { pending: 'info', processing: 'warning', done: 'success', failed: 'danger' }[status] || 'info'
}

function handleFileChange(uploadFile: any) {
  fileForm.files.push(uploadFile.raw)
}

function handleFileRemove(uploadFile: any) {
  const idx = fileForm.files.indexOf(uploadFile.raw)
  if (idx > -1) fileForm.files.splice(idx, 1)
}

async function doSubmitText() {
  if (!textForm.text) return ElMessage.warning('请输入内容')
  submitting.value = true
  try {
    await submitText(textForm.text, textForm.title, textForm.submittedBy)
    ElMessage.success('提交成功，正在处理...')
    textForm.title = ''; textForm.text = ''
    await loadSourcesList()
  } catch { ElMessage.error('提交失败') }
  submitting.value = false
}

async function doSubmitUrl() {
  if (!urlForm.url) return ElMessage.warning('请输入 URL')
  submitting.value = true
  try {
    await submitUrl(urlForm.url, urlForm.submittedBy)
    ElMessage.success('提交成功，正在处理...')
    urlForm.url = ''
    await loadSourcesList()
  } catch { ElMessage.error('提交失败') }
  submitting.value = false
}

async function doUploadFile() {
  if (!fileForm.files.length) return ElMessage.warning('请选择文件')
  submitting.value = true
  uploadProgress.value = 0
  let success = 0
  let processed = 0
  for (const f of fileForm.files) {
    uploadingFileName.value = f.name
    try {
      await uploadFile(f, fileForm.submittedBy, (pct) => { uploadProgress.value = pct })
      success++
    } catch { /* continue with next file */ }
    processed++
    uploadProgress.value = Math.round((processed / fileForm.files.length) * 100)
  }
  uploadingFileName.value = ''
  uploadProgress.value = 0
  if (success > 0) {
    ElMessage.success(`${success} 个文件上传成功，正在处理...`)
    fileForm.files = []
    await loadSourcesList()
  } else {
    ElMessage.error('上传失败')
  }
  submitting.value = false
}

let pollTimer: ReturnType<typeof setInterval> | null = null

function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(async () => {
    const hasPending = sources.value.some(s => s.status === 'pending' || s.status === 'processing')
    if (!hasPending) {
      stopPolling()
      return
    }
    try { sources.value = await listSources() } catch {}
  }, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function loadSourcesList() {
  loadingSources.value = true
  try { sources.value = await listSources() } catch {}
  loadingSources.value = false
  // Start polling if any source is still processing
  const hasProcessing = sources.value.some(s => s.status === 'pending' || s.status === 'processing')
  if (hasProcessing) startPolling()
}

function downloadFile(id: string) {
  const token = localStorage.getItem('token')
  const url = `/api/sources/${id}/file`
  const a = document.createElement('a')
  // Use fetch with auth header to download
  fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    .then(r => r.blob())
    .then(blob => {
      a.href = URL.createObjectURL(blob)
      a.download = ''
      a.click()
      URL.revokeObjectURL(a.href)
    })
}

async function doReingest(id: string) {
  try {
    await reingestSource(id)
    ElMessage.success('已重新加入处理队列')
    await loadSourcesList()
  } catch { ElMessage.error('操作失败') }
}

onMounted(loadSourcesList)
onUnmounted(stopPolling)
</script>
