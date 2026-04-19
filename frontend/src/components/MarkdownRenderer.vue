<template>
  <div class="wiki-content" ref="rootEl" v-html="rendered" @click="handleClick"></div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import { useRouter } from 'vue-router'
import mermaid from 'mermaid'
import hljs from 'highlight.js/lib/core'
// Register only the languages we actually expect in wiki/chat output.
import javascript from 'highlight.js/lib/languages/javascript'
import typescript from 'highlight.js/lib/languages/typescript'
import python from 'highlight.js/lib/languages/python'
import bash from 'highlight.js/lib/languages/bash'
import json from 'highlight.js/lib/languages/json'
import yaml from 'highlight.js/lib/languages/yaml'
import sql from 'highlight.js/lib/languages/sql'
import xml from 'highlight.js/lib/languages/xml'
import css from 'highlight.js/lib/languages/css'
import go from 'highlight.js/lib/languages/go'
import rust from 'highlight.js/lib/languages/rust'
import markdown from 'highlight.js/lib/languages/markdown'

hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('js', javascript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('ts', typescript)
hljs.registerLanguage('python', python)
hljs.registerLanguage('py', python)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('sh', bash)
hljs.registerLanguage('shell', bash)
hljs.registerLanguage('json', json)
hljs.registerLanguage('yaml', yaml)
hljs.registerLanguage('yml', yaml)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('css', css)
hljs.registerLanguage('go', go)
hljs.registerLanguage('rust', rust)
hljs.registerLanguage('rs', rust)
hljs.registerLanguage('markdown', markdown)
hljs.registerLanguage('md', markdown)

const props = withDefaults(
  defineProps<{ content: string; newTab?: boolean }>(),
  { newTab: false }
)
const router = useRouter()
const rootEl = ref<HTMLDivElement | null>(null)

// Tag mermaid fences with a sentinel class instead of rendering as <code>
const md = new MarkdownIt({
  html: false,
  linkify: true,
  highlight(code: string, lang: string) {
    if (lang === 'mermaid') {
      const escaped = code
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
      return `<pre class="mermaid-source" data-code="${encodeURIComponent(code)}">${escaped}</pre>`
    }
    const validLang = lang && hljs.getLanguage(lang) ? lang : 'plaintext'
    const highlighted = hljs.highlight(code, { language: validLang }).value
    return `<pre class="code-block" data-code="${encodeURIComponent(code)}"><code class="hljs language-${validLang}">${highlighted}</code><button class="code-copy-btn" data-code="${encodeURIComponent(code)}">复制</button></pre>`
  },
})

mermaid.initialize({ startOnLoad: false, theme: 'default', securityLevel: 'strict' })

/** Escape a string for safe insertion into HTML attributes and text. */
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

const rendered = computed(() => {
  let html = md.render(props.content)
  // Replace [[slug]] wikilinks with safe anchor tags (XSS-safe: slug is escaped)
  html = html.replace(/\[\[([^\]]+)\]\]/g, (_match: string, slug: string) => {
    const safe = escapeHtml(slug)
    return `<a class="wikilink" data-slug="${safe}">${safe}</a>`
  })
  // Replace [1][2] numbered citations with clickable sup badges (digits only → always safe)
  html = html.replace(/\[(\d{1,2})\]/g, (_match: string, num: string) => {
    return `<sup class="citation" data-src-idx="${num}">[${num}]</sup>`
  })
  return html
})

async function renderMermaid() {
  await nextTick()
  const root = rootEl.value
  if (!root) return
  const nodes = root.querySelectorAll<HTMLElement>('pre.mermaid-source')
  let idx = 0
  for (const node of Array.from(nodes)) {
    const raw = node.getAttribute('data-code')
    if (!raw) continue
    const code = decodeURIComponent(raw)
    const containerId = `mermaid-svg-${Date.now()}-${idx++}`
    try {
      const { svg } = await mermaid.render(containerId, code)
      const wrapper = document.createElement('div')
      wrapper.className = 'mermaid-rendered'
      wrapper.innerHTML = svg
      node.replaceWith(wrapper)
    } catch (err) {
      const errBox = document.createElement('pre')
      errBox.className = 'mermaid-error'
      errBox.textContent = `Mermaid 渲染失败: ${(err as Error).message}\n\n${code}`
      node.replaceWith(errBox)
    }
  }
}

watch(() => props.content, () => renderMermaid())
onMounted(() => renderMermaid())

function handleClick(e: MouseEvent) {
  const target = e.target as HTMLElement

  // Handle code copy button
  if (target.classList.contains('code-copy-btn')) {
    const code = decodeURIComponent(target.getAttribute('data-code') || '')
    navigator.clipboard.writeText(code)
    target.textContent = '已复制'
    setTimeout(() => { target.textContent = '复制' }, 2000)
    return
  }

  if (!target.classList.contains('wikilink')) return
  const slug = target.getAttribute('data-slug')
  if (!slug) return
  e.preventDefault()
  const href = router.resolve(`/wiki/${slug}`).href
  // Middle-click / Ctrl/Cmd-click → browser handles new tab naturally via target=_blank on the rendered anchor.
  // For left-click, honor `newTab` prop.
  if (props.newTab || e.ctrlKey || e.metaKey || e.button === 1) {
    window.open(href, '_blank', 'noopener')
  } else {
    router.push(`/wiki/${slug}`)
  }
}
</script>

<style scoped>
.wiki-content :deep(.mermaid-rendered) {
  display: flex;
  justify-content: center;
  margin: 16px 0;
  padding: 12px;
  background: #fafafa;
  border-radius: 6px;
  overflow-x: auto;
}
.wiki-content :deep(.mermaid-rendered svg) { max-width: 100%; height: auto; }
.wiki-content :deep(.mermaid-error) {
  background: #fef0f0;
  color: #b94a48;
  padding: 12px;
  border-radius: 6px;
  font-size: 13px;
  white-space: pre-wrap;
}
.wiki-content :deep(.code-block) {
  position: relative;
}
.wiki-content :deep(.code-copy-btn) {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 4px 8px;
  font-size: 12px;
  background: var(--bg-hover, #f3f4f6);
  border: 1px solid var(--line, #e5e7eb);
  border-radius: 4px;
  cursor: pointer;
  color: var(--text-secondary, #6b7280);
}
.wiki-content :deep(.code-copy-btn:hover) {
  background: var(--bg-secondary, #f9fafb);
  color: var(--text-primary, #111827);
}
.wiki-content :deep(.hljs) {
  background: transparent;
  padding: 0;
}
</style>
