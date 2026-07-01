import axios from 'axios'

export async function downloadBlob(url: string, filename: string, params?: Record<string, string>) {
  const token = localStorage.getItem('access_token')
  const headers: Record<string, string> = {}
  if (token) headers.Authorization = `Bearer ${token}`

  const resp = await axios.get(url, { responseType: 'blob', headers, params })

  if (resp.data instanceof Blob && resp.data.type.includes('json')) {
    const text = await resp.data.text()
    const parsed = JSON.parse(text)
    throw new Error(parsed.msg || '请求失败')
  }

  const objectUrl = URL.createObjectURL(resp.data)
  const a = document.createElement('a')
  a.href = objectUrl
  a.download = filename
  a.click()
  URL.revokeObjectURL(objectUrl)
}
