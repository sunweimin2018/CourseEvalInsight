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

export function getCourses() {
  return request.get('/excel/courses/')
}

export function createCourse(name: string) {
  return request.post('/excel/courses/', { name })
}

export function getClasses() {
  return request.get('/excel/classes/')
}

export function createClass(name: string) {
  return request.post('/excel/classes/', { name })
}

export function getSemesters() {
  return request.get('/excel/semesters/')
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

export function uploadCourseFile(courseId: number, classId: number, semesterId: number, fileType: string, file: File) {
  const formData = new FormData()
  formData.append('course_id', String(courseId))
  formData.append('class_id', String(classId))
  formData.append('semester_id', String(semesterId))
  formData.append('file_type', fileType)
  formData.append('file', file)
  return request.post('/excel/course-files/upload/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getCourseFiles(courseId: number, classId: number, semesterId: number) {
  return request.get('/excel/course-files/', {
    params: { course_id: courseId, class_id: classId, semester_id: semesterId },
  })
}

export function deleteCourseFile(id: number) {
  return request.delete(`/excel/course-files/${id}/`)
}
