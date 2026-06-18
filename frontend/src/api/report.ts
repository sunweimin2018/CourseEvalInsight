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
  module_3_evaluation_standards: string
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

export async function downloadReport(id: number, filename: string) {
  const token = localStorage.getItem('access_token') || ''
  const resp = await axios.get(`/api/v1/report/export/${id}/`, {
    responseType: 'blob',
    headers: { Authorization: `Bearer ${token}` },
  })
  const url = URL.createObjectURL(resp.data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function getReports(courseId?: number, classId?: number, semesterName?: string) {
  return request.get('/report/', {
    params: { course_id: courseId, class_id: classId, semester_name: semesterName },
  })
}
