<template>
  <div class="wiki-content" v-html="rendered" @click="handleClick"></div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import { useRouter } from 'vue-router'

const props = defineProps<{ content: string }>()
const router = useRouter()
const md = new MarkdownIt({ html: false, linkify: true })

const rendered = computed(() => {
  let html = md.render(props.content)
  html = html.replace(/\[\[([^\]]+)\]\]/g, '<a class="wikilink" data-slug="$1">$1</a>')
  return html
})

function handleClick(e: Event) {
  const target = e.target as HTMLElement
  if (target.classList.contains('wikilink')) {
    const slug = target.getAttribute('data-slug')
    if (slug) {
      router.push(`/wiki/${slug}`)
    }
  }
}
</script>
