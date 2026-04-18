import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
  { path: '/', component: () => import('../views/HomeView.vue') },
  { path: '/wiki', component: () => import('../views/WikiListView.vue') },
  { path: '/wiki/:slug(.*)', component: () => import('../views/WikiPageView.vue') },
  { path: '/source/:id', component: () => import('../views/SourceDetailView.vue') },
  { path: '/graph', component: () => import('../views/GraphView.vue') },
  { path: '/lint', component: () => import('../views/LintDashboardView.vue') },
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
