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

export interface SegmentEntry {
  label: string
  count: number
  pct: number
}

export interface GradeSectionBaseStats {
  count: number
  missing: number
  max: number
  min: number
  avg: number
  median: number
  stdev: number
  pass_rate: number
}

export interface GradeSection {
  col_name: string
  description_line_1: string
  description_line_2: string
  stats: GradeSectionBaseStats
  segments: SegmentEntry[]
  avg_score: number
  ai_summary?: string
  segment_source?: 'matched' | 'fallback' | 'default'
  weight_pct?: number
  is_weighted?: boolean
}

export interface Module4Data {
  sections: GradeSection[]
  segment_labels: string[]
  generated: boolean
  fallback: boolean
  grade_analysis: Record<string, GradeStats>
  score_columns: string[]
}

// ── Module 5: 课程目标达成度 ──────────────────────────────────────────────

export interface ObjectiveAchievementRow {
  objective: string
  item: string
  target_score: number | null
  avg_score: number | null
  weight_pct: string
  achievement_rate: string
}

export interface DistributionRow {
  label: string
  counts: number[]
  pcts: number[]
}

export interface DistributionTable {
  objectives: string[]
  avg: number[]
  rows: DistributionRow[]
}

export interface LowAchievementStudent {
  name: string
  achievements: Record<string, number>  // decimal values e.g. 0.46
}

export interface StudentAchievement {
  name: string
  avg_achievement: number
}

export interface RadarData {
  labels: string[]
  values: number[]
}

export interface PerObjectiveAnalysis {
  objective: string
  rate: number
  analysis: string
}

// ── Section 5.1: 课程目标达成情况 ──────────────────────────────────────────

export interface Section51Item {
  item: string
  target_score: number
  avg_score: number
  weight_pct: string
}

export interface Section51Objective {
  name: string
  items: Section51Item[]
  achievement_rate: string
}

export interface Section51Data {
  semester_name: string
  title: string
  objectives: Section51Objective[]
}

export interface Module5Data {
  report_title: string
  objectives: string[]
  achievement_table: ObjectiveAchievementRow[]
  distribution_table: DistributionTable | null
  per_objective_analysis: PerObjectiveAnalysis[]
  low_students: LowAchievementStudent[]
  radar_data: RadarData
  student_achievements?: StudentAchievement[]
  overall_avg_achievement?: number
  section_5_1: Section51Data | null
  generated: boolean
  excel_generated?: boolean
  excel_filename?: string
}

// ── Module 6: 持续改进方案 ──────────────────────────────────────────────────

export interface Module6Part2 {
  problems: string
  measures: string
  expected_effects: string
}

export interface Module6Data {
  part1: string
  part2: Module6Part2
  part3: string
}

export interface ReportData {
  module_1_course_info: Record<string, unknown>
  module_2_objectives: string
  module_3_evaluation_standards: string | Array<{ type: string; [key: string]: unknown }>
  module_4_evaluation_results: Module4Data
  module_5_objective_achievement: Module5Data
  module_6_improvement_plan: Module6Data | string
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
  return request.post(`/report/${reportId}/module/${moduleNum}/generate/`, {}, { timeout: 120000 })
}

const MODULE_DATA_KEYS: Record<number, string> = {
  1: 'module_1_course_info',
  2: 'module_2_objectives',
  3: 'module_3_evaluation_standards',
  4: 'module_4_evaluation_results',
  5: 'module_5_objective_achievement',
  6: 'module_6_improvement_plan',
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

// ── Module 5 Excel ──────────────────────────────────────────────────────────

export function generateAchievementExcel(reportId: number) {
  return request.post(`/report/${reportId}/module/5/generate-excel/`, {}, { timeout: 120000 })
}

export async function downloadAchievementExcel(reportId: number, filename: string) {
  const token = localStorage.getItem('access_token')
  const headers: Record<string, string> = {}
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  const resp = await axios.get(`/api/v1/report/${reportId}/module/5/download-excel/`, {
    responseType: 'blob',
    headers,
  })
  const url = URL.createObjectURL(resp.data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
