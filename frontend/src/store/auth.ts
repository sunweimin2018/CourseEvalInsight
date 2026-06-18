import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, register as registerApi, logout as logoutApi } from '@/api/user'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref(localStorage.getItem('access_token') || '')
  const userInfo = ref<{ id: number; username: string; role: string } | null>(
    (() => {
      try {
        const raw = localStorage.getItem('userInfo')
        return raw ? JSON.parse(raw) : null
      } catch {
        return null
      }
    })(),
  )

  const isLoggedIn = () => !!accessToken.value
  const isAdmin = computed(() => userInfo.value?.role === 'admin')

  async function login(username: string, password: string) {
    const data = (await loginApi(username, password)) as unknown as {
      access: string
      refresh: string
      user: { id: number; username: string; role: string }
    }
    accessToken.value = data.access
    userInfo.value = data.user
    localStorage.setItem('access_token', data.access)
    localStorage.setItem('refresh_token', data.refresh)
    localStorage.setItem('userInfo', JSON.stringify(data.user))
    // Clear excel store to prevent stale data from previous user
    import('@/store/excel').then((m) => m.useExcelStore().clearAll())
  }

  async function register(username: string, password: string, phone?: string, email?: string) {
    const data = (await registerApi(username, password, phone, email)) as unknown as {
      access: string
      refresh: string
      user: { id: number; username: string; role: string }
    }
    accessToken.value = data.access
    userInfo.value = data.user
    localStorage.setItem('access_token', data.access)
    localStorage.setItem('refresh_token', data.refresh)
    localStorage.setItem('userInfo', JSON.stringify(data.user))
  }

  async function logout() {
    try {
      const refresh = localStorage.getItem('refresh_token')
      await logoutApi(refresh || undefined)
    } finally {
      accessToken.value = ''
      userInfo.value = null
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('userInfo')
    }
  }

  return { accessToken, userInfo, isLoggedIn, isAdmin, login, register, logout }
})
