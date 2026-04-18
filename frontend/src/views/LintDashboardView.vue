<template>
  <AppLayout>
    <div class="lint-shell">
      <!-- Header strip -->
      <div class="header-strip">
        <span class="strip-crumb">健康检查</span>
        <span v-if="lastRunTime" class="strip-meta">· 上次 {{ formatTime(lastRunTime) }}</span>
        <div style="flex:1"></div>
        <el-button
          size="small"
          :icon="Refresh"
          :loading="triggering"
          @click="runLint"
        >重新检查</el-button>
      </div>

      <div class="lint-scroll">
        <div class="lint-content">
          <!-- Hero: health score -->
          <div class="kicker">SYSTEM CHECK</div>
          <h1 class="display-title">
            知识库<span class="display-accent">健康度</span>
          </h1>

          <template v-if="!loading && report">
            <div class="health-hero">
              <div class="score-block">
                <div class="score-value" :data-grade="grade.key">{{ healthScore }}</div>
                <div class="score-label">{{ grade.label }}</div>
              </div>
              <div class="score-bar">
                <div class="bar-track">
                  <div class="bar-fill" :data-grade="grade.key" :style="{ width: healthScore + '%' }"></div>
                </div>
                <div class="bar-meta">
                  <span>共 {{ totalIssues }} 处问题 · {{ totalPages }} 个页面</span>
                  <span>评分基于严重程度加权</span>
                </div>
              </div>
            </div>

            <!-- 4-color severity cards -->
            <div class="severity-grid">
              <div
                v-for="sev in severityCards"
                :key="sev.key"
                class="sev-card"
                :data-tone="sev.key"
              >
                <div class="sev-top">
                  <span class="sev-dot"></span>
                  <span class="sev-label">{{ sev.label }}</span>
                </div>
                <div class="sev-value">{{ sev.count }}</div>
                <div class="sev-desc">{{ sev.desc }}</div>
              </div>
            </div>
          </template>

          <!-- Loading -->
          <template v-if="loading">
            <div class="severity-grid">
              <div v-for="i in 4" :key="i" class="sev-card skeleton">
                <el-skeleton animated :rows="2" />
              </div>
            </div>
          </template>

          <!-- Empty -->
          <template v-else-if="!report">
            <div class="empty-hero">
              <el-empty
                :image-size="120"
                description="尚未运行健康检查"
              >
                <el-button type="primary" @click="runLint" :loading="triggering">立即检查</el-button>
              </el-empty>
            </div>
          </template>

          <!-- Issue sections -->
          <template v-else>
            <!-- Orphan -->
            <section class="issue-section">
              <div class="sec-head">
                <h2 class="sec-h">孤儿页面</h2>
                <span class="sec-count" :class="{ has: orphanCount > 0 }">{{ orphanCount }}</span>
                <div style="flex:1"></div>
                <span class="sec-desc">无任何页面引用</span>
              </div>
              <div v-if="orphanIssues.length" class="rows">
                <a
                  v-for="issue in orphanIssues"
                  :key="issue.affected_pages[0]"
                  :href="`/wiki/${issue.affected_pages[0]}`"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="row-card"
                >
                  <span class="row-icon"><el-icon><Document /></el-icon></span>
                  <span class="row-text">
                    <span class="row-title">{{ issue.affected_pages[0] }}</span>
                    <span v-if="issue.description" class="row-sub">{{ issue.description }}</span>
                  </span>
                  <button class="fix-btn" @click.prevent="openFix(issue)">修复</button>
                </a>
              </div>
              <div v-else class="row-empty">没有孤儿页面 ✓</div>
            </section>

            <!-- Broken Links -->
            <section class="issue-section">
              <div class="sec-head">
                <h2 class="sec-h">断链</h2>
                <span class="sec-count" :class="{ has: brokenCount > 0 }">{{ brokenCount }}</span>
                <div style="flex:1"></div>
                <span class="sec-desc">引用了不存在的页面</span>
              </div>
              <div v-if="brokenLinkIssues.length" class="rows">
                <div
                  v-for="issue in brokenLinkIssues"
                  :key="issue.affected_pages[0]"
                  class="row-card vert"
                >
                  <div class="broken-line">
                    <template v-if="issue.from_pages?.length">
                      <a
                        v-for="fromSlug in issue.from_pages"
                        :key="fromSlug"
                        :href="`/wiki/${fromSlug}`"
                        class="slug-link"
                        target="_blank"
                        rel="noopener noreferrer"
                      >{{ fromSlug }}</a>
                    </template>
                    <span class="arrow">→</span>
                    <span class="bad-slug">{{ issue.affected_pages[0] }}</span>
                    <span class="bad-tag">缺失</span>
                    <button class="fix-btn small" @click.prevent="openFix(issue)">修复</button>
                  </div>
                  <p v-if="issue.suggested_fix" class="row-fix">{{ issue.suggested_fix }}</p>
                </div>
              </div>
              <div v-else class="row-empty">没有断链 ✓</div>
            </section>

            <!-- Content Issues -->
            <section class="issue-section">
              <div class="sec-head">
                <h2 class="sec-h">内容问题</h2>
                <span class="sec-count" :class="{ has: contentCount > 0 }">{{ contentCount }}</span>
                <div style="flex:1"></div>
                <span class="sec-desc">AI 检测的质量问题</span>
              </div>
              <div v-if="contentIssues.length" class="rows">
                <div
                  v-for="issue in contentIssues"
                  :key="`${issue.type}-${issue.affected_pages.join(',')}`"
                  class="issue-block"
                  :data-tone="issue.severity"
                >
                  <div class="issue-head">
                    <span class="severity-pill" :data-tone="issue.severity">{{ severityLabel(issue.severity) }}</span>
                    <span class="type-pill">{{ issue.type }}</span>
                    <div style="flex:1"></div>
                    <button class="fix-btn small" @click="openFix(issue)">修复</button>
                  </div>
                  <p class="issue-desc">{{ issue.description }}</p>
                  <div v-if="issue.affected_pages?.length" class="issue-pages">
                    <a
                      v-for="slug in issue.affected_pages"
                      :key="slug"
                      :href="`/wiki/${slug}`"
                      class="page-pill"
                      target="_blank"
                      rel="noopener noreferrer"
                    >{{ slug }}</a>
                  </div>
                  <details v-if="issue.suggested_fix" class="fix-details">
                    <summary>建议修复</summary>
                    <p class="row-fix">{{ issue.suggested_fix }}</p>
                  </details>
                </div>
              </div>
              <div v-else class="row-empty">没有内容问题 ✓</div>
            </section>

            <div class="report-meta" v-if="report.auto_fixed > 0 || report.pending_review > 0">
              <span v-if="report.auto_fixed > 0" class="meta-pill ok">已自动修复 {{ report.auto_fixed }}</span>
              <span v-if="report.pending_review > 0" class="meta-pill warn">待人工审核 {{ report.pending_review }}</span>
            </div>
          </template>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Document } from '@element-plus/icons-vue'
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
const totalIssues = computed(() => allIssues.value.length)
const totalPages = computed(() => (report.value as any)?.total_pages || 0)

const lastRunTime = computed(() => report.value?.created_at ?? '')

// Severity buckets
const severityCards = computed(() => {
  const sev = (k: string) => allIssues.value.filter(i => i.severity === k).length
  return [
    { key: 'critical', label: '严重', count: sev('high'), desc: '需立即处理' },
    { key: 'high',     label: '高',   count: brokenCount.value, desc: '影响阅读体验' },
    { key: 'medium',   label: '中',   count: sev('medium'), desc: '建议优化' },
    { key: 'low',      label: '低',   count: orphanCount.value + sev('low'), desc: '可后续处理' },
  ]
})

// Health score: 100 - weighted issues, clamped 0..100
const healthScore = computed(() => {
  const sev = (k: string) => allIssues.value.filter(i => i.severity === k).length
  const penalty = sev('high') * 8 + sev('medium') * 3 + sev('low') * 1 + brokenCount.value * 4 + orphanCount.value * 1
  const denom = Math.max(totalPages.value, 10)
  const score = Math.round(100 - (penalty * 100) / (denom * 5))
  return Math.max(0, Math.min(100, score))
})

const grade = computed(() => {
  const s = healthScore.value
  if (s >= 90) return { key: 'excellent', label: '优秀' }
  if (s >= 75) return { key: 'good',      label: '良好' }
  if (s >= 60) return { key: 'fair',      label: '一般' }
  return { key: 'poor', label: '需关注' }
})

function formatTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function severityLabel(severity: string): string {
  return ({ high: '严重', medium: '中等', low: '低' } as Record<string, string>)[severity] || severity
}

async function loadReports() {
  loading.value = true
  try {
    const reports = await getReports()
    if (reports.length > 0) report.value = reports[0]
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
    if (totalIssues.value === 0) ElMessage.success('知识库很健康！')
    else ElMessage.warning(`发现 ${totalIssues.value} 个问题`)
  } catch (e: any) {
    ElMessage.error('运行检查失败: ' + (e?.response?.data?.detail ?? e.message))
  } finally {
    triggering.value = false
  }
}

function openFix(issue: LintIssue) {
  ElMessageBox.alert(
    issue.suggested_fix || '暂无具体修复建议，请前往受影响页面手动处理。',
    `修复建议 · ${issue.type}`,
    { confirmButtonText: '前往页面', distinguishCancelAndClose: true },
  ).then(() => {
    if (issue.affected_pages[0]) window.open(`/wiki/${issue.affected_pages[0]}`, '_blank')
  }).catch(() => {})
}

onMounted(() => loadReports())
</script>

<style scoped>
.lint-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--paper);
}

/* Header strip — matches HomeView */
.header-strip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 20px;
  border-bottom: 1px solid var(--line);
  background: color-mix(in oklch, var(--paper) 82%, transparent);
  backdrop-filter: blur(8px);
  flex-shrink: 0;
}
.strip-crumb { color: var(--ink); font-weight: 500; font-size: 12.5px; }
.strip-meta { font-family: var(--font-mono); font-size: 11.5px; color: var(--ink-4); }

.lint-scroll { flex: 1; overflow-y: auto; }
.lint-content { max-width: 960px; margin: 0 auto; padding: 40px 36px 60px; }

/* Hero */
.kicker {
  font-size: 10.5px;
  font-family: var(--font-mono);
  color: var(--ink-4);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.display-title {
  font-family: var(--font-display);
  font-weight: 400;
  font-size: clamp(34px, 4vw, 48px);
  line-height: 1.05;
  letter-spacing: -0.015em;
  margin: 0 0 28px;
  color: var(--ink);
}
.display-accent { font-style: italic; color: var(--accent-ink); }

/* Health hero */
.health-hero {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 28px;
  align-items: center;
  padding: 24px 28px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 14px;
  margin-bottom: 24px;
}
.score-block {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}
.score-value {
  font-family: var(--font-display);
  font-size: 96px;
  line-height: 0.95;
  font-weight: 400;
  color: var(--ink);
}
.score-value[data-grade="excellent"] { color: oklch(0.5 0.13 150); }
.score-value[data-grade="good"]      { color: oklch(0.5 0.13 200); }
.score-value[data-grade="fair"]      { color: oklch(0.5 0.13 80); }
.score-value[data-grade="poor"]      { color: oklch(0.5 0.16 25); }
.score-label {
  font-family: var(--font-display);
  font-style: italic;
  font-size: 22px;
  color: var(--ink-3);
  margin-top: 4px;
}

.score-bar { display: flex; flex-direction: column; gap: 12px; }
.bar-track {
  height: 8px;
  background: var(--paper-3);
  border-radius: 999px;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.5s cubic-bezier(0.2, 0.8, 0.2, 1);
}
.bar-fill[data-grade="excellent"] { background: oklch(0.6 0.13 150); }
.bar-fill[data-grade="good"]      { background: oklch(0.6 0.13 200); }
.bar-fill[data-grade="fair"]      { background: oklch(0.65 0.13 80); }
.bar-fill[data-grade="poor"]      { background: oklch(0.6 0.16 25); }
.bar-meta {
  display: flex;
  justify-content: space-between;
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--ink-4);
}

/* 4-color severity cards */
.severity-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 36px;
}
@media (max-width: 720px) { .severity-grid { grid-template-columns: repeat(2, 1fr); } }
.sev-card {
  padding: 16px 18px;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  position: relative;
}
.sev-card.skeleton { background: var(--paper-2); }
.sev-top { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.sev-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.sev-card[data-tone="critical"] .sev-dot { background: oklch(0.55 0.18 25); }
.sev-card[data-tone="high"]     .sev-dot { background: oklch(0.65 0.16 50); }
.sev-card[data-tone="medium"]   .sev-dot { background: oklch(0.7 0.14 80); }
.sev-card[data-tone="low"]      .sev-dot { background: var(--ink-4); }
.sev-card[data-tone="critical"] { border-color: oklch(0.85 0.08 25); background: oklch(0.97 0.02 25); }
.sev-card[data-tone="high"]     { border-color: oklch(0.85 0.07 50); background: oklch(0.97 0.02 50); }
.sev-card[data-tone="medium"]   { border-color: oklch(0.86 0.06 80); background: oklch(0.97 0.02 80); }

.sev-label {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--ink-3);
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.sev-value {
  font-family: var(--font-display);
  font-size: 36px;
  line-height: 1;
  color: var(--ink);
  margin-bottom: 4px;
}
.sev-desc { font-size: 12px; color: var(--ink-3); }

/* Issue sections */
.issue-section {
  margin-bottom: 28px;
}
.sec-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 14px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line);
}
.sec-h {
  font-family: var(--font-display);
  font-weight: 400;
  font-size: 22px;
  color: var(--ink);
  margin: 0;
}
.sec-count {
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--ink-4);
  background: var(--paper-2);
  padding: 2px 8px;
  border-radius: 999px;
}
.sec-count.has { color: oklch(0.42 0.14 30); background: oklch(0.95 0.04 30); }
.sec-desc { font-family: var(--font-mono); font-size: 11px; color: var(--ink-4); }

.rows { display: flex; flex-direction: column; gap: 6px; }
.row-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 8px;
  text-decoration: none;
  color: var(--ink);
  transition: all var(--transition);
}
.row-card:hover {
  background: var(--paper-3);
  border-color: var(--line-2);
  text-decoration: none;
}
.row-card.vert { flex-direction: column; align-items: stretch; }
.row-icon { color: var(--ink-4); display: grid; place-items: center; }
.row-text { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.row-title {
  font-size: 13.5px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row-sub { font-size: 12px; color: var(--ink-3); }
.row-empty { font-size: 13px; color: var(--ink-4); padding: 16px 4px; font-style: italic; }
.row-fix { margin: 6px 0 0; font-size: 12.5px; color: var(--ink-3); line-height: 1.6; }

/* Fix button */
.fix-btn {
  padding: 5px 12px;
  font-size: 12px;
  font-family: var(--font-ui);
  font-weight: 500;
  background: var(--ink);
  color: var(--paper);
  border: none;
  border-radius: 6px;
  cursor: pointer;
  flex-shrink: 0;
  transition: background var(--transition);
}
.fix-btn:hover { background: var(--ink-2); }
.fix-btn.small { padding: 3px 10px; font-size: 11.5px; }

/* Broken lines */
.broken-line { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
.slug-link { color: var(--accent-ink); text-decoration: none; font-weight: 500; font-size: 13px; }
.slug-link:hover { text-decoration: underline; }
.arrow { color: var(--ink-4); font-family: var(--font-mono); }
.bad-slug { color: oklch(0.45 0.15 25); font-weight: 500; font-size: 13px; }
.bad-tag {
  font-family: var(--font-mono);
  font-size: 10px;
  color: oklch(0.45 0.15 25);
  background: oklch(0.95 0.05 25);
  padding: 1px 6px;
  border-radius: 4px;
}

/* Issue blocks */
.issue-block {
  padding: 14px 16px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-left-width: 3px;
  border-radius: 8px;
}
.issue-block[data-tone="high"]   { border-left-color: oklch(0.55 0.18 25); }
.issue-block[data-tone="medium"] { border-left-color: oklch(0.65 0.16 50); }
.issue-block[data-tone="low"]    { border-left-color: var(--ink-4); }

.issue-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.severity-pill {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--paper-3);
  color: var(--ink-2);
}
.severity-pill[data-tone="high"]   { background: oklch(0.93 0.06 25); color: oklch(0.4 0.14 25); }
.severity-pill[data-tone="medium"] { background: oklch(0.94 0.05 50); color: oklch(0.42 0.13 50); }
.severity-pill[data-tone="low"]    { background: var(--paper-3); color: var(--ink-3); }
.type-pill {
  font-family: var(--font-mono);
  font-size: 10px;
  padding: 2px 7px;
  border: 1px solid var(--line);
  border-radius: 4px;
  color: var(--ink-3);
}
.issue-desc { margin: 0 0 10px; font-size: 13.5px; color: var(--ink-2); line-height: 1.6; }

.issue-pages { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.page-pill {
  font-family: var(--font-mono);
  font-size: 11px;
  padding: 2px 8px;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--ink-3);
  text-decoration: none;
  transition: all var(--transition);
}
.page-pill:hover { color: var(--accent-ink); border-color: var(--accent); text-decoration: none; }

.fix-details summary {
  font-size: 12px;
  color: var(--accent-ink);
  cursor: pointer;
  margin-top: 4px;
}

/* Empty hero */
.empty-hero {
  padding: 40px 0;
  background: var(--paper-2);
  border: 1px dashed var(--line);
  border-radius: 12px;
}

.report-meta { display: flex; gap: 8px; margin-top: 12px; }
.meta-pill {
  font-family: var(--font-mono);
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 999px;
}
.meta-pill.ok   { background: oklch(0.94 0.04 150); color: oklch(0.4 0.1 150); }
.meta-pill.warn { background: oklch(0.94 0.05 80);  color: oklch(0.42 0.12 60); }

@media (max-width: 720px) {
  .health-hero { grid-template-columns: 1fr; }
  .lint-content { padding: 28px 18px 40px; }
}
</style>
