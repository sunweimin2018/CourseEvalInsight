import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { i18n } from '@/i18n'

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
    // Pass through blob responses (file downloads) without JSON parsing
    if (response.config.responseType === 'blob') {
      return response.data
    }
    const { code, msg, data } = response.data
    if (code === 200) {
      return data
    }
    ElMessage.error(msg || i18n.global.t('request.failed'))
    return Promise.reject(new Error(msg))
  },
  async (error) => {
    const originalRequest = error.config

    // For blob responses, extract error msg from the blob body
    let responseData = error.response?.data
    if (originalRequest.responseType === 'blob' && responseData instanceof Blob) {
      try {
        const text = await responseData.text()
        responseData = JSON.parse(text)
      } catch {
        // If parsing fails, keep original blob
      }
    }

    // Login failures: show server message and reject — never try token refresh
    if (originalRequest.url?.includes('/user/login/')) {
      const msg = error.response?.data?.msg || i18n.global.t('request.loginFailed')
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

    const msg = responseData?.msg || error.message || i18n.global.t('request.networkError')
    ElMessage.error(msg)
    return Promise.reject(new Error(msg))
  },
)

export default request
