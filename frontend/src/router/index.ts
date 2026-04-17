import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
  { path: '/', component: () => import('../views/HomeView.vue') },
  { path: '/wiki', component: () => import('../views/WikiListView.vue') },
  { path: '/wiki/:slug(.*)', component: () => import('../views/WikiPageView.vue') },
  { path: '/submit', component: () => import('../views/SourceSubmitView.vue') },
  { path: '/sources', component: () => import('../views/SourceLibraryView.vue') },
  { path: '/chat', component: () => import('../views/ChatView.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (!to.meta?.public && !token) {
    return '/login'
  }
})

export default router
