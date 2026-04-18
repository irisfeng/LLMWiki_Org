<template>
  <AppLayout>
    <div class="lint-page">
      <el-breadcrumb separator="/" class="page-breadcrumb">
        <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
        <el-breadcrumb-item>健康检查</el-breadcrumb-item>
      </el-breadcrumb>

      <!-- Header -->
      <div class="page-header">
        <div class="header-text">
          <h2>知识库健康检查</h2>
          <p class="subtitle">检测孤儿页面、断链、内容矛盾等问题</p>
        </div>
        <div class="header-actions">
          <span v-if="lastRunTime" class="last-run">
            上次检查: {{ formatTime(lastRunTime) }}
          </span>
          <el-button
            type="primary"
            :icon="Refresh"
            :loading="triggering"
            @click="runLint"
          >
            运行检查
          </el-button>
        </div>
      </div>

      <!-- Loading skeleton -->
      <template v-if="loading">
        <div class="summary-row">
          <div v-for="i in 3" :key="i" class="summary-card">
            <el-skeleton animated :rows="0">
              <template #template>
                <el-skeleton-item variant="circle" style="width: 40px; height: 40px" />
                <el-skeleton-item variant="h1" style="width: 48px; height: 32px; margin-top: 10px" />
                <el-skeleton-item variant="text" style="width: 60px; margin-top: 6px" />
              </template>
            </el-skeleton>
          </div>
        </div>
        <div class="section-skeleton">
          <el-skeleton v-for="i in 3" :key="i" animated :rows="3" style="margin-bottom: 20px" />
        </div>
      </template>

      <!-- No reports yet -->
      <template v-else-if="!report">
        <div class="empty-state">
          <el-empty
            :image-size="140"
            description="还没有健康检查报告，点击上方按钮运行第一次检查"
          />
        </div>
      </template>

      <!-- Report content -->
      <template v-else>
        <!-- Summary cards -->
        <div class="summary-row">
          <div
            class="summary-card"
            :class="orphanCount > 0 ? 'card-warn' : 'card-ok'"
          >
            <div class="card-icon">
              <el-icon :size="28"><DocumentRemove /></el-icon>
            </div>
            <div class="card-value">{{ orphanCount }}</div>
            <div class="card-label">孤儿页面</div>
          </div>
          <div
            class="summary-card"
            :class="brokenCount > 0 ? 'card-warn' : 'card-ok'"
          >
            <div class="card-icon">
              <el-icon :size="28"><Link /></el-icon>
            </div>
            <div class="card-value">{{ brokenCount }}</div>
            <div class="card-label">断链</div>
          </div>
          <div
            class="summary-card"
            :class="contentCount > 0 ? 'card-warn' : 'card-ok'"
          >
            <div class="card-icon">
              <el-icon :size="28"><WarningFilled /></el-icon>
            </div>
            <div class="card-value">{{ contentCount }}</div>
            <div class="card-label">内容问题</div>
          </div>
        </div>

        <!-- Section: Orphan Pages -->
        <section class="issue-section">
          <h3 class="section-title">
            <el-icon><DocumentRemove /></el-icon>
            孤儿页面
            <el-tag size="small" :type="orphanCount > 0 ? 'danger' : 'success'" round>
              {{ orphanCount }}
            </el-tag>
          </h3>
          <p class="section-desc">没有任何页面链接到这些页面，可能需要补充关联或清理</p>
          <template v-if="orphanIssues.length">
            <div class="orphan-list">
              <a
                v-for="issue in orphanIssues"
                :key="issue.affected_pages[0]"
                :href="`/wiki/${issue.affected_pages[0]}`"
                target="_blank"
                rel="noopener noreferrer"
                class="orphan-item"
              >
                <el-icon><Document /></el-icon>
                <span class="orphan-title">{{ issue.affected_pages[0] }}</span>
                <span class="orphan-desc" v-if="issue.description">{{ issue.description }}</span>
              </a>
            </div>
          </template>
          <el-empty v-else :image-size="60" description="没有孤儿页面" />
        </section>

        <!-- Section: Broken Links -->
        <section class="issue-section">
          <h3 class="section-title">
            <el-icon><Link /></el-icon>
            断链
            <el-tag size="small" :type="brokenCount > 0 ? 'danger' : 'success'" round>
              {{ brokenCount }}
            </el-tag>
          </h3>
          <p class="section-desc">这些页面中引用了不存在的 wiki 链接</p>
          <template v-if="brokenLinkIssues.length">
            <div class="broken-list">
              <div
                v-for="issue in brokenLinkIssues"
                :key="issue.affected_pages[0]"
                class="broken-item"
              >
                <div class="broken-row">
                  <template v-if="issue.from_pages?.length">
                    <span
                      v-for="fromSlug in issue.from_pages"
                      :key="fromSlug"
                      class="broken-from"
                    >
                      <a
                        :href="`/wiki/${fromSlug}`"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="slug-link"
                      >{{ fromSlug }}</a>
                    </span>
                  </template>
                  <span class="arrow-icon">&#8594;</span>
                  <span class="broken-slug">{{ issue.affected_pages[0] }}</span>
                  <span class="broken-label">（不存在）</span>
                </div>
                <p v-if="issue.suggested_fix" class="broken-fix">{{ issue.suggested_fix }}</p>
              </div>
            </div>
          </template>
          <el-empty v-else :image-size="60" description="没有断链" />
        </section>

        <!-- Section: Content Issues -->
        <section class="issue-section">
          <h3 class="section-title">
            <el-icon><WarningFilled /></el-icon>
            内容问题
            <el-tag size="small" :type="contentCount > 0 ? 'danger' : 'success'" round>
              {{ contentCount }}
            </el-tag>
          </h3>
          <p class="section-desc">通过 AI 分析检测到的内容质量问题</p>
          <template v-if="contentIssues.length">
            <div class="content-issues">
              <div
                v-for="issue in contentIssues"
                :key="`${issue.type}-${issue.affected_pages.join(',')}`"
                class="issue-card"
              >
                <div class="issue-header">
                  <el-tag
                    :type="severityType(issue.severity)"
                    size="small"
                    effect="dark"
                  >
                    {{ severityLabel(issue.severity) }}
                  </el-tag>
                  <el-tag size="small" effect="plain">{{ issue.type }}</el-tag>
                </div>
                <p class="issue-desc">{{ issue.description }}</p>
                <div v-if="issue.affected_pages?.length" class="issue-pages">
                  <span class="pages-label">涉及页面:</span>
                  <a
                    v-for="slug in issue.affected_pages"
                    :key="slug"
                    :href="`/wiki/${slug}`"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="page-pill"
                  >
                    {{ slug }}
                  </a>
                </div>
                <el-collapse class="fix-collapse">
                  <el-collapse-item title="建议修复" name="fix">
                    <p class="fix-text">{{ issue.suggested_fix }}</p>
                  </el-collapse-item>
                </el-collapse>
              </div>
            </div>
          </template>
          <el-empty v-else :image-size="60" description="没有内容问题" />
        </section>

        <!-- Auto-fixed / Pending review stats -->
        <div class="report-meta" v-if="report.auto_fixed > 0 || report.pending_review > 0">
          <el-tag v-if="report.auto_fixed > 0" type="success" effect="plain">
            已自动修复: {{ report.auto_fixed }}
          </el-tag>
          <el-tag v-if="report.pending_review > 0" type="warning" effect="plain">
            待人工审核: {{ report.pending_review }}
          </el-tag>
        </div>
      </template>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Refresh,
  DocumentRemove,
  Document,
  Link,
  WarningFilled,
} from '@element-plus/icons-vue'
import AppLayout from '../components/AppLayout.vue'
import { getReports, triggerLint, getIssueList } from '../api/lint'
import type { LintReport, LintIssue } from '../api/lint'

const loading = ref(false)
const triggering = ref(false)
const report = ref<LintReport | null>(null)

const allIssues = computed(() => report.value ? getIssueList(report.value) : [])
const orphanIssues = computed(() => allIssues.value.filter(i => i.type === 'orphan'))
const brokenLinkIssues = computed(() => allIssues.value.filter(i => i.type === 'missing_page'))
const contentIssues = computed(() => allIssues.value.filter(i => !['orphan', 'missing_page'].includes(i.type)))

const orphanCount = computed(() => orphanIssues.value.length)
const brokenCount = computed(() => brokenLinkIssues.value.length)
const contentCount = computed(() => contentIssues.value.length)

const lastRunTime = computed(() => report.value?.created_at ?? '')

function formatTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function severityType(severity: string): 'danger' | 'warning' | 'info' {
  if (severity === 'high') return 'danger'
  if (severity === 'medium') return 'warning'
  return 'info'
}

function severityLabel(severity: string): string {
  if (severity === 'high') return '严重'
  if (severity === 'medium') return '中等'
  return '低'
}

async function loadReports() {
  loading.value = true
  try {
    const reports = await getReports()
    // Use the most recent report
    if (reports.length > 0) {
      report.value = reports[0]
    }
  } catch (e: any) {
    ElMessage.error('获取报告失败: ' + (e?.response?.data?.detail ?? e.message))
  } finally {
    loading.value = false
  }
}

async function runLint() {
  triggering.value = true
  try {
    const newReport = await triggerLint()
    report.value = newReport
    const total = orphanCount.value + brokenCount.value + contentCount.value
    if (total === 0) {
      ElMessage.success('检查完成，知识库很健康!')
    } else {
      ElMessage.warning(`检查完成，发现 ${total} 个问题`)
    }
  } catch (e: any) {
    ElMessage.error('运行检查失败: ' + (e?.response?.data?.detail ?? e.message))
  } finally {
    triggering.value = false
  }
}

onMounted(() => {
  loadReports()
})
</script>

<style scoped>
.lint-page {
  max-width: 960px;
  margin: 0 auto;
}

.page-breadcrumb {
  margin-bottom: 16px;
}

/* ---- Header ---- */
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 24px;
  gap: 16px;
  flex-wrap: wrap;
}

.page-header h2 {
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
}

.subtitle {
  margin: 0;
  font-size: 14px;
  color: var(--text-secondary, #888);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.last-run {
  font-size: 13px;
  color: var(--text-secondary, #888);
  white-space: nowrap;
}

/* ---- Summary cards ---- */
.summary-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 28px;
}

.summary-card {
  background: var(--bg-card, var(--bg-secondary, #fff));
  border: 1px solid var(--border, #e4e7ed);
  border-radius: 10px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  box-shadow: var(--shadow-sm, 0 1px 3px rgba(0, 0, 0, 0.06));
  transition: border-color 0.2s, box-shadow 0.2s;
}

.summary-card:hover {
  box-shadow: var(--shadow-md, 0 2px 8px rgba(0, 0, 0, 0.1));
}

.card-icon {
  margin-bottom: 8px;
}

.card-warn .card-icon {
  color: var(--el-color-danger, #f56c6c);
}

.card-ok .card-icon {
  color: var(--el-color-success, #67c23a);
}

.card-warn {
  border-color: var(--el-color-danger-light-5, #fab6b6);
}

.card-ok {
  border-color: var(--el-color-success-light-5, #b3e19d);
}

.card-value {
  font-size: 32px;
  font-weight: 700;
  line-height: 1.1;
  color: var(--text-primary);
}

.card-warn .card-value {
  color: var(--el-color-danger, #f56c6c);
}

.card-ok .card-value {
  color: var(--el-color-success, #67c23a);
}

.card-label {
  font-size: 13px;
  color: var(--text-secondary, #888);
  margin-top: 4px;
}

/* ---- Issue sections ---- */
.issue-section {
  background: var(--bg-card, var(--bg-secondary, #fff));
  border: 1px solid var(--border, #e4e7ed);
  border-radius: 10px;
  padding: 20px 24px;
  margin-bottom: 20px;
  box-shadow: var(--shadow-sm, 0 1px 3px rgba(0, 0, 0, 0.06));
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 6px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.section-desc {
  font-size: 13px;
  color: var(--text-secondary, #888);
  margin: 0 0 16px;
}

/* ---- Orphan pages list ---- */
.orphan-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.orphan-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  background: var(--bg-primary, #fafafa);
  border: 1px solid var(--border, #e4e7ed);
  text-decoration: none;
  color: var(--text-primary);
  transition: background 0.15s, border-color 0.15s;
}

.orphan-item:hover {
  background: var(--el-color-primary-light-9, #ecf5ff);
  border-color: var(--el-color-primary-light-5, #a0cfff);
}

.orphan-title {
  font-weight: 500;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.orphan-desc {
  font-size: 12px;
  color: var(--text-secondary, #888);
  flex-shrink: 0;
}

/* ---- Broken links list ---- */
.broken-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.broken-item {
  padding: 10px 14px;
  border-radius: 6px;
  background: var(--bg-primary, #fafafa);
  border: 1px solid var(--border, #e4e7ed);
}

.broken-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.broken-from + .broken-from::before {
  content: ', ';
}

.slug-link {
  color: var(--el-color-primary, #409eff);
  text-decoration: none;
  font-weight: 500;
}

.slug-link:hover {
  text-decoration: underline;
}

.broken-slug {
  color: var(--el-color-danger, #f56c6c);
  font-weight: 500;
}

.broken-label {
  font-size: 12px;
  color: var(--text-secondary, #888);
}

.broken-fix {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--text-secondary, #888);
  line-height: 1.5;
}

.arrow-icon {
  color: var(--text-secondary, #888);
  font-size: 16px;
}

/* ---- Content issues ---- */
.content-issues {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.issue-card {
  padding: 14px 16px;
  border-radius: 8px;
  background: var(--bg-primary, #fafafa);
  border: 1px solid var(--border, #e4e7ed);
}

.issue-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.issue-desc {
  margin: 0 0 10px;
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.6;
}

.issue-pages {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.pages-label {
  font-size: 12px;
  color: var(--text-secondary, #888);
}

.page-pill {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 12px;
  background: var(--el-color-primary-light-9, #ecf5ff);
  color: var(--el-color-primary, #409eff);
  font-size: 12px;
  text-decoration: none;
  transition: background 0.15s;
}

.page-pill:hover {
  background: var(--el-color-primary-light-7, #c6e2ff);
}

.fix-collapse {
  border: none;
}

.fix-collapse :deep(.el-collapse-item__header) {
  font-size: 13px;
  height: 32px;
  line-height: 32px;
  background: transparent;
  border: none;
  color: var(--el-color-primary, #409eff);
}

.fix-collapse :deep(.el-collapse-item__wrap) {
  border: none;
  background: transparent;
}

.fix-text {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary, #888);
  line-height: 1.6;
}

/* ---- Report meta ---- */
.report-meta {
  display: flex;
  gap: 10px;
  margin-top: 8px;
  margin-bottom: 16px;
}

/* ---- Empty state ---- */
.empty-state {
  padding: 60px 0;
  text-align: center;
}

/* ---- Skeleton ---- */
.section-skeleton {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ---- Responsive ---- */
@media (max-width: 768px) {
  .lint-page {
    padding: 0 4px;
  }

  .summary-row {
    grid-template-columns: 1fr;
  }

  .page-header {
    flex-direction: column;
    align-items: stretch;
  }

  .header-actions {
    justify-content: space-between;
  }

  .issue-section {
    padding: 16px;
  }

  .orphan-item {
    flex-wrap: wrap;
  }

  .orphan-desc {
    width: 100%;
    margin-left: 28px;
  }
}
</style>
