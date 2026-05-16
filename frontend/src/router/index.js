import { createRouter, createWebHistory } from 'vue-router'
import { useApi } from '../composables/useApi'

const routes = [
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue'), meta: { guest: true } },
  { path: '/', name: 'dashboard', component: () => import('../views/DashboardView.vue'), meta: { auth: true } },
  { path: '/products', name: 'products', component: () => import('../views/ProductsView.vue'), meta: { auth: true } },
  { path: '/quotes', name: 'quotes', component: () => import('../views/QuotesView.vue'), meta: { auth: true } },
  { path: '/new-quote', name: 'newquote', component: () => import('../views/NewQuoteView.vue'), meta: { auth: true } },
  { path: '/import', name: 'import', component: () => import('../views/ImportView.vue'), meta: { auth: true, admin: true } },
  { path: '/admin', name: 'admin', component: () => import('../views/AdminView.vue'), meta: { auth: true, admin: true } },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

router.beforeEach((to, from, next) => {
  const { isLoggedIn, isAdmin } = useApi()

  // Auth-required pages → redirect to login if not logged in
  if (to.meta.auth && !isLoggedIn()) {
    return next({ name: 'login' })
  }

  // Admin-only pages
  if (to.meta.admin && !isAdmin()) {
    return next({ name: 'dashboard' })
  }

  // Guest pages (login) → redirect to dashboard if already logged in
  if (to.meta.guest && isLoggedIn()) {
    return next({ name: 'dashboard' })
  }

  next()
})

export default router
