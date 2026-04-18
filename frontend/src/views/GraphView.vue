<template>
  <AppLayout>
    <div class="graph-shell">
      <div class="header-strip">
        <span class="strip-crumb">关系图谱</span>
        <span class="strip-meta">· {{ stats.total || 0 }} 节点</span>
        <div style="flex:1"></div>
        <span class="strip-badge">Beta · 开发中</span>
      </div>

      <div class="graph-scroll">
        <div class="graph-content">
          <div class="hero">
            <div class="kicker">RELATIONSHIP GRAPH</div>
            <h1 class="display-title">
              知识的<span class="display-accent">连接图</span>
            </h1>
            <p class="display-sub">
              以力导向图的方式展示信息源、实体、概念与分析之间的引用与关联关系，点击节点可跳转到对应页面。
            </p>
          </div>

          <div class="legend">
            <span class="legend-item" data-type="concept"><span class="legend-dot" data-type="concept"></span>概念</span>
            <span class="legend-item" data-type="entity"><span class="legend-dot" data-type="entity"></span>实体</span>
            <span class="legend-item" data-type="source"><span class="legend-dot" data-type="source"></span>信息源</span>
            <span class="legend-item" data-type="analysis"><span class="legend-dot" data-type="analysis"></span>分析</span>
          </div>

          <div class="placeholder-card">
            <div class="placeholder-icon">
              <svg viewBox="0 0 100 100" width="80" height="80" aria-hidden="true">
                <circle cx="50" cy="50" r="10" fill="oklch(0.80 0.10 30)" />
                <circle cx="20" cy="25" r="6" fill="oklch(0.80 0.10 250)" />
                <circle cx="80" cy="25" r="6" fill="oklch(0.80 0.10 150)" />
                <circle cx="20" cy="80" r="6" fill="oklch(0.80 0.10 320)" />
                <circle cx="80" cy="80" r="6" fill="oklch(0.80 0.10 150)" />
                <line x1="50" y1="50" x2="20" y2="25" stroke="var(--line)" stroke-width="1" />
                <line x1="50" y1="50" x2="80" y2="25" stroke="var(--line)" stroke-width="1" />
                <line x1="50" y1="50" x2="20" y2="80" stroke="var(--line)" stroke-width="1" />
                <line x1="50" y1="50" x2="80" y2="80" stroke="var(--line)" stroke-width="1" />
              </svg>
            </div>
            <div class="placeholder-title">交互式关系图谱即将上线</div>
            <div class="placeholder-desc">
              下一版将接入力导向图引擎，支持拖拽、聚焦、按类型过滤与节点详情预览。
            </div>
            <div class="placeholder-actions">
              <router-link to="/wiki" class="ghost-btn">先去浏览知识库</router-link>
            </div>
          </div>

          <div v-if="stats.total" class="stats-strip">
            <div class="stat-cell">
              <div class="stat-row"><span class="stat-num">{{ stats.sources }}</span><span class="type-pill" data-type="source">信息源</span></div>
            </div>
            <div class="stat-cell">
              <div class="stat-row"><span class="stat-num">{{ stats.entities }}</span><span class="type-pill" data-type="entity">实体</span></div>
            </div>
            <div class="stat-cell">
              <div class="stat-row"><span class="stat-num">{{ stats.concepts }}</span><span class="type-pill" data-type="concept">概念</span></div>
            </div>
            <div class="stat-cell">
              <div class="stat-row"><span class="stat-num">{{ stats.analyses }}</span><span class="type-pill" data-type="analysis">分析</span></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import AppLayout from '../components/AppLayout.vue'
import { getStats } from '../api/wiki'

const stats = ref<{ sources: number; entities: number; concepts: number; analyses: number; total: number }>({
  sources: 0, entities: 0, concepts: 0, analyses: 0, total: 0,
})

onMounted(async () => {
  try { stats.value = await getStats() } catch {}
})
</script>

<style scoped>
.graph-shell { display: flex; flex-direction: column; height: 100%; background: var(--paper); }

.header-strip {
  position: sticky; top: 0; z-index: 10;
  display: flex; align-items: center; gap: 10px;
  padding: 11px 20px;
  background: color-mix(in srgb, var(--paper) 82%, transparent);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--line);
  font-size: 13px;
}
.strip-crumb { color: var(--ink); font-weight: 500; }
.strip-meta { color: var(--ink-4); font-family: var(--font-mono); font-size: 12px; }
.strip-badge {
  font-family: var(--font-mono); font-size: 11px;
  letter-spacing: 0.06em; padding: 3px 10px;
  background: oklch(0.97 0.02 60); color: oklch(0.50 0.12 60);
  border: 1px solid oklch(0.85 0.08 60); border-radius: 999px;
}

.graph-scroll { flex: 1; overflow-y: auto; }
.graph-content { max-width: 880px; margin: 0 auto; padding: 40px 36px 80px; }

.hero { margin-bottom: 28px; }
.kicker {
  font-family: var(--font-mono); font-size: 11px;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--ink-4); margin-bottom: 10px;
}
.display-title {
  font-family: var(--font-display);
  font-size: clamp(32px, 4vw, 46px);
  font-weight: 400; line-height: 1.08; letter-spacing: -0.015em;
  color: var(--ink); margin: 0 0 12px;
}
.display-accent { font-style: italic; color: var(--accent-ink, var(--ink)); }
.display-sub { font-size: 15px; color: var(--ink-3); line-height: 1.65; margin: 0; max-width: 620px; }

.legend {
  display: flex; flex-wrap: wrap; gap: 14px;
  padding: 12px 0; margin-bottom: 20px;
  border-bottom: 1px solid var(--line);
}
.legend-item { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--ink-3); font-family: var(--font-mono); }
.legend-dot { width: 10px; height: 10px; border-radius: 999px; display: inline-block; }
.legend-dot[data-type="concept"] { background: oklch(0.80 0.10 250); }
.legend-dot[data-type="entity"] { background: oklch(0.80 0.10 30); }
.legend-dot[data-type="source"] { background: oklch(0.80 0.10 150); }
.legend-dot[data-type="analysis"] { background: oklch(0.80 0.10 320); }

.placeholder-card {
  padding: 48px 28px; text-align: center;
  background: var(--paper-2);
  border: 1px dashed var(--line);
  border-radius: 16px;
  margin-bottom: 28px;
}
.placeholder-icon { margin-bottom: 18px; display: flex; justify-content: center; }
.placeholder-title {
  font-family: var(--font-display); font-size: 22px;
  color: var(--ink); margin-bottom: 8px;
}
.placeholder-desc { font-size: 13.5px; color: var(--ink-3); line-height: 1.65; max-width: 460px; margin: 0 auto 18px; }
.placeholder-actions { display: flex; gap: 8px; justify-content: center; }
.ghost-btn {
  display: inline-block; padding: 8px 18px;
  background: var(--paper); border: 1px solid var(--line);
  border-radius: 999px; font-size: 13px; color: var(--ink);
  text-decoration: none; transition: all .15s;
}
.ghost-btn:hover { background: var(--ink); color: var(--paper); border-color: var(--ink); }

.stats-strip {
  display: grid; grid-template-columns: repeat(4, 1fr);
  border: 1px solid var(--line); border-radius: 12px; overflow: hidden;
}
.stat-cell {
  padding: 18px 20px; border-right: 1px solid var(--line);
  background: var(--paper-2);
}
.stat-cell:last-child { border-right: none; }
.stat-row { display: flex; align-items: baseline; gap: 10px; }
.stat-num { font-family: var(--font-display); font-size: 28px; color: var(--ink); }

.type-pill {
  display: inline-flex; align-items: center;
  padding: 2px 10px;
  font-family: var(--font-mono); font-size: 11px;
  border: 1px solid var(--line); border-radius: 999px;
  background: var(--paper);
}
.type-pill[data-type="concept"] { border-color: oklch(0.85 0.08 250); color: oklch(0.45 0.15 250); background: oklch(0.97 0.02 250); }
.type-pill[data-type="entity"] { border-color: oklch(0.85 0.08 30); color: oklch(0.50 0.15 30); background: oklch(0.97 0.02 30); }
.type-pill[data-type="source"] { border-color: oklch(0.85 0.08 150); color: oklch(0.45 0.15 150); background: oklch(0.97 0.02 150); }
.type-pill[data-type="analysis"] { border-color: oklch(0.85 0.08 320); color: oklch(0.45 0.15 320); background: oklch(0.97 0.02 320); }

@media (max-width: 720px) {
  .graph-content { padding: 24px 18px 60px; }
  .stats-strip { grid-template-columns: repeat(2, 1fr); }
  .stat-cell:nth-child(2) { border-right: none; }
  .stat-cell:nth-child(1), .stat-cell:nth-child(2) { border-bottom: 1px solid var(--line); }
}
</style>
