import axios from 'axios'
import request from '@/utils/request'

export interface ReportRecord {
  id: number
  course: number
  class_group: number
  semester: number
  course_name: string
  class_name: string
  semester_name: string
  report_name: string
  status: 'draft' | 'completed' | 'exported'
  status_display: string
  report_file_path: string
  created_time: string
  updated_time: string
}

export interface GradeStats {
  count: number
  missing: number
  max: number
  min: number
  avg: number
  median: number
  stdev: number
  pass_rate: number
  distribution: Record<string, { label: string; count: number }>
}

export interface ReportData {
  module_1_course_info: Record<string, unknown>
  module_2_objectives: string
  module_3_evaluation_standards: string | Array<{ type: string; [key: string]: unknown }>
  module_4_evaluation_results: {
    grade_analysis: Record<string, GradeStats>
    score_columns: string[]
    generated: boolean
  }
  module_5_improvement_plan: string
}

export interface ReportPreview extends ReportRecord {
  report_data: ReportData
}

export function generateReport(courseId: number, classId: number, semesterName: string) {
  return request.post('/report/generate/', {
    course_id: courseId,
    class_id: classId,
    semester_name: semesterName,
  })
}

export function getReportPreview(id: number) {
  return request.get(`/report/preview/${id}/`)
}

export async function downloadReport(id: number, filename: string, format: 'docx' | 'pdf' = 'docx') {
  const token = localStorage.getItem('access_token')
  const ext = format === 'pdf' ? '.pdf' : '.docx'
  const headers: Record<string, string> = {}
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  const resp = await axios.get(`/api/v1/report/export/${id}/`, {
    params: { export_format: format },
    responseType: 'blob',
    headers,
  })
  const url = URL.createObjectURL(resp.data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename.replace(/\.\w+$/, '') + ext
  a.click()
  URL.revokeObjectURL(url)
}

export function getReports(courseId?: number, classId?: number, semesterName?: string) {
  return request.get('/report/', {
    params: { course_id: courseId, class_id: classId, semester_name: semesterName },
  })
}

// ── Per-module API functions ───────────────────────────────────────────────

export function generateModule(reportId: number, moduleNum: number) {
  return request.post(`/report/${reportId}/module/${moduleNum}/generate/`)
}

const MODULE_DATA_KEYS: Record<number, string> = {
  1: 'module_1_course_info',
  2: 'module_2_objectives',
  3: 'module_3_evaluation_standards',
  4: 'module_4_evaluation_results',
  5: 'module_5_improvement_plan',
}

export function updateModule(reportId: number, moduleNum: number, data: unknown, confirmed = false) {
  return request.put(`/report/${reportId}/module/${moduleNum}/update/`, {
    module_key: MODULE_DATA_KEYS[moduleNum],
    data,
    confirmed,
  })
}

export async function exportModuleDocx(reportId: number, moduleNum: number, filename: string) {
  const token = localStorage.getItem('access_token')
  const headers: Record<string, string> = {}
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  const resp = await axios.get(`/api/v1/report/${reportId}/module/${moduleNum}/export-docx/`, {
    responseType: 'blob',
    headers,
  })
  const url = URL.createObjectURL(resp.data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename.replace(/\.\w+$/, '') + '.docx'
  a.click()
  URL.revokeObjectURL(url)
}

export async function mergeReport(reportId: number, filename: string, format: 'docx' | 'pdf' = 'docx') {
  const token = localStorage.getItem('access_token')
  const ext = format === 'pdf' ? '.pdf' : '.docx'
  const headers: Record<string, string> = {}
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  const resp = await axios.get(`/api/v1/report/${reportId}/merge/`, {
    params: { export_format: format },
    responseType: 'blob',
    headers,
  })
  // Check for error response
  if (resp.data instanceof Blob && resp.data.type.includes('json')) {
    const text = await resp.data.text()
    const parsed = JSON.parse(text)
    throw new Error(parsed.msg || '合并导出失败')
  }
  const url = URL.createObjectURL(resp.data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename.replace(/\.\w+$/, '') + ext
  a.click()
  URL.revokeObjectURL(url)
}
