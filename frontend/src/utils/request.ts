import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

let isRefreshing = false
let pendingRequests: Array<{ resolve: (value: unknown) => void; reject: (err: unknown) => void }> = []

function getAccessToken() {
  return localStorage.getItem('access_token') || ''
}

function getRefreshToken() {
  return localStorage.getItem('refresh_token') || ''
}

request.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  (response) => {
    const { code, msg, data } = response.data
    if (code === 200) {
      return data
    }
    ElMessage.error(msg || 'Request failed')
    return Promise.reject(new Error(msg))
  },
  async (error) => {
    const originalRequest = error.config

    // Login failures: show server message and reject — never try token refresh
    if (originalRequest.url?.includes('/user/login/')) {
      const msg = error.response?.data?.msg || 'Login failed'
      ElMessage.error(msg)
      return Promise.reject(new Error(msg))
    }

    if (error.response?.status === 401 && !originalRequest._retry) {
      const refresh = getRefreshToken()
      if (!refresh) {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        localStorage.removeItem('userInfo')
        router.push('/login')
        return Promise.reject(error)
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          pendingRequests.push({ resolve, reject })
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const data = (await axios.post('/api/v1/user/token/refresh/', { refresh })) as unknown as {
          data: { access: string; refresh: string }
        }
        const { access, refresh: newRefresh } = data.data
        localStorage.setItem('access_token', access)
        localStorage.setItem('refresh_token', newRefresh)

        pendingRequests.forEach(({ resolve }) => resolve(access))
        pendingRequests = []

        originalRequest.headers.Authorization = `Bearer ${access}`
        return request(originalRequest)
      } catch {
        pendingRequests.forEach(({ reject }) => reject(error))
        pendingRequests = []
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        localStorage.removeItem('userInfo')
        router.push('/login')
        return Promise.reject(error)
      } finally {
        isRefreshing = false
      }
    }

    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('userInfo')
      router.push('/login')
    }

    const msg = error.response?.data?.msg || error.message || 'Network error'
    ElMessage.error(msg)
    return Promise.reject(new Error(msg))
  },
)

export default request
