import request from '@/utils/request'

// ── Generic upload ──────────────────────────────────────────────────────────

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

// ── Course / Class / Semester ──────────────────────────────────────────────

export interface SimpleItem {
  id: number
  name: string
  create_time: string
}

export function getCourses(params?: { class_id?: number; semester_name?: string }) {
  return request.get('/excel/courses/', { params })
}

export function createCourse(name: string) {
  return request.post('/excel/courses/', { name })
}

export function getClasses(params?: { course_id?: number; semester_name?: string }) {
  return request.get('/excel/classes/', { params })
}

export function createClass(name: string) {
  return request.post('/excel/classes/', { name })
}

export function getSemesters(params?: { course_id?: number; class_id?: number }) {
  return request.get('/excel/semesters/', { params })
}

export function createSemester(name: string) {
  return request.post('/excel/semesters/', { name })
}

// ── Course files ────────────────────────────────────────────────────────────

export interface CourseFileRecord {
  id: number
  course: number
  class_group: number
  semester: number
  course_name: string
  class_name: string
  semester_name: string
  file_type: 'syllabus' | 'student_info' | 'grades'
  file_type_display: string
  file_name: string
  file_size: number
  upload_time: string
}

export function uploadCourseFile(courseId: number, classId: number, semesterName: string, fileType: string, file: File) {
  const formData = new FormData()
  formData.append('course_id', String(courseId))
  formData.append('class_id', String(classId))
  formData.append('semester_name', semesterName)
  formData.append('file_type', fileType)
  formData.append('file', file)
  return request.post('/excel/course-files/upload/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getCourseFiles(courseId: number, classId: number, semesterName: string) {
  return request.get('/excel/course-files/', {
    params: { course_id: courseId, class_id: classId, semester_name: semesterName },
  })
}

export function deleteCourseFile(id: number) {
  return request.delete(`/excel/course-files/${id}/`)
}

// ── Data Preview – Word ──────────────────────────────────────────────────────

export interface WordBodyElement {
  type: 'paragraph' | 'table'
  text?: string
  style?: string
  table_index?: number
}

export interface WordContent {
  file_name: string
  paragraphs: { index: number; text: string; style: string }[]
  tables: { index: number; headers: string[]; rows: string[][] }[]
  body_elements: WordBodyElement[]
}

export function getWordContent(fileId: number) {
  return request.get(`/excel/course-files/${fileId}/word-content/`)
}

// ── Data Preview – Excel editing ─────────────────────────────────────────────

export interface WorkingData {
  sheet_name: string
  headers: string[]
  rows: Record<string, unknown>[]
  total: number
  page: number
  page_size: number
}

export function openExcelForEdit(fileId: number) {
  return request.post(`/excel/course-files/${fileId}/data/open/`)
}

export function getWorkingData(fileId: number, page: number, size: number) {
  return request.get(`/excel/course-files/${fileId}/data/`, { params: { page, size } })
}

export function addRow(fileId: number, rowData: Record<string, unknown>) {
  return request.post(`/excel/course-files/${fileId}/data/add-row/`, rowData)
}

export function updateCell(fileId: number, rowIdx: number, colName: string, value: unknown) {
  return request.put(`/excel/course-files/${fileId}/data/update-cell/`, {
    row_idx: rowIdx,
    col_name: colName,
    value,
  })
}

export function deleteDataRow(fileId: number, rowIdx: number) {
  return request.delete(`/excel/course-files/${fileId}/data/delete-row/`, {
    data: { row_idx: rowIdx },
  })
}

export function saveWorkingCopy(fileId: number) {
  return request.post(`/excel/course-files/${fileId}/data/save/`)
}

export function resetWorkingCopy(fileId: number) {
  return request.post(`/excel/course-files/${fileId}/data/reset/`)
}

// ── Upload validation ────────────────────────────────────────────────────────

export interface ValidationComparison {
  expected: string
  current: string | null
  match: boolean
}

export interface GradeValidationResult {
  student_count: {
    match: boolean
    student_info_count: number
    grades_count: number
  }
  header_validation: {
    match: boolean
    expected_items: string[]
    grade_columns: string[]
    comparisons: ValidationComparison[]
    error?: string
  } | null
}

export function validateGradesUpload(courseId: number, classId: number, semesterName: string) {
  return request.post('/excel/course-files/validate-grades/', {
    course_id: courseId,
    class_id: classId,
    semester_name: semesterName,
  })
}

export function resolveCountMismatch(
  courseId: number,
  classId: number,
  semesterName: string,
  userChoice: 'student_info_wrong' | 'grades_wrong',
) {
  return request.post('/excel/course-files/resolve-mismatch/', {
    course_id: courseId,
    class_id: classId,
    semester_name: semesterName,
    user_choice: userChoice,
  })
}

export function fixHeaders(fileId: number, mapping: Record<string, string>) {
  return request.post(`/excel/course-files/${fileId}/fix-headers/`, { mapping })
}
