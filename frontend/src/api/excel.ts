import request from '@/utils/request'

export function uploadFiles(formData: FormData) {
  return request.post('/excel/upload/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getRawData(page: number, size: number) {
  return request.get('/excel/raw-data/', { params: { page, size } })
}

export function cleanData() {
  return request.post('/excel/clean/')
}

export function getCleanedData(page: number, size: number) {
  return request.get('/excel/cleaned-data/', { params: { page, size } })
}
