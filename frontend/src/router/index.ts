import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Register.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/dashboard',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
      },
      {
        path: 'excel/upload',
        name: 'ExcelUpload',
        component: () => import('@/views/ExcelUpload.vue'),
      },
      {
        path: 'excel/preview',
        name: 'DataPreview',
        component: () => import('@/views/DataPreview.vue'),
      },
      {
        path: 'user/center',
        name: 'UserCenter',
        component: () => import('@/views/UserCenter.vue'),
      },
      {
        path: 'admin/users',
        name: 'AdminUsers',
        component: () => import('@/views/AdminUsers.vue'),
        meta: { requiresAdmin: true },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('access_token')
  const role = (() => {
    try {
      const raw = localStorage.getItem('userInfo')
      return raw ? JSON.parse(raw).role : null
    } catch {
      return null
    }
  })()

  if (to.meta.requiresAuth !== false && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/dashboard')
  } else if (to.meta.requiresAdmin && role !== 'admin') {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
