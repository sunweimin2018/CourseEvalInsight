import request from '@/utils/request'

export function login(username: string, password: string) {
  return request.post('/user/login/', { username, password })
}

export function register(username: string, password: string, phone?: string, email?: string) {
  return request.post('/user/register/', { username, password, phone, email })
}

export function logout(refresh?: string) {
  return request.post('/user/logout/', { refresh })
}

export function refreshToken(refresh: string) {
  return request.post('/user/token/refresh/', { refresh })
}

export function getProfile() {
  return request.get('/user/profile/')
}

export function updateProfile(data: Record<string, unknown>) {
  return request.put('/user/profile/', data)
}

export function getUsers(params?: { page?: number; page_size?: number; search?: string }) {
  return request.get('/user/admin/users/', { params })
}

export function createUser(data: Record<string, unknown>) {
  return request.post('/user/admin/users/', data)
}

export function updateUser(id: number, data: Record<string, unknown>) {
  return request.put(`/user/admin/users/${id}/`, data)
}

export function deleteUser(id: number) {
  return request.delete(`/user/admin/users/${id}/`)
}

export function checkUsername(username: string) {
  return request.get('/user/check-username/', { params: { username } })
}
