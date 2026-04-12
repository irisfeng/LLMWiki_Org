import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', component: () => import('../views/HomeView.vue') },
  { path: '/wiki', component: () => import('../views/WikiListView.vue') },
  { path: '/wiki/:slug(.*)', component: () => import('../views/WikiPageView.vue') },
  { path: '/submit', component: () => import('../views/SourceSubmitView.vue') },
  { path: '/chat', component: () => import('../views/ChatView.vue') },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
