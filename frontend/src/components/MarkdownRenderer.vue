<template>
  <div class="wiki-content" ref="rootEl" v-html="rendered" @click="handleClick"></div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import { useRouter } from 'vue-router'
import mermaid from 'mermaid'

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
    return ''
  },
})

mermaid.initialize({ startOnLoad: false, theme: 'default', securityLevel: 'strict' })

const rendered = computed(() => {
  let html = md.render(props.content)
  html = html.replace(/\[\[([^\]]+)\]\]/g, '<a class="wikilink" data-slug="$1">$1</a>')
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
</style>
