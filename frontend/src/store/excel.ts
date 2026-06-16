import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  uploadFiles, getRawData, cleanData, getCleanedData,
  getCourses, createCourse,
  getClasses, createClass,
  getSemesters, createSemester,
  uploadCourseFile, getCourseFiles, deleteCourseFile,
  type SimpleItem, type CourseFileRecord,
} from '@/api/excel'

export interface UploadSummary {
  total_files: number
  total_rows: number
  sheets_parsed: string[]
}

export const useExcelStore = defineStore('excel', () => {
  const uploadedFiles = ref<{ name: string; size: number; status: string }[]>([])
  const uploadSummary = ref<UploadSummary | null>(null)
  const rawData = ref<{ headers: string[]; rows: Record<string, unknown>[]; total: number } | null>(null)
  const cleanedData = ref<{ headers: string[]; rows: Record<string, unknown>[]; total: number } | null>(null)
  const cleaningSummary = ref<{
    total_rows_before: number
    total_rows_after: number
    removed_duplicates: number
    removed_outliers: number
  } | null>(null)

  // Course / Class / Semester
  const courses = ref<SimpleItem[]>([])
  const classes = ref<SimpleItem[]>([])
  const semesters = ref<SimpleItem[]>([])

  // Course files
  const selectedCourseId = ref<number | null>(null)
  const selectedClassId = ref<number | null>(null)
  const selectedSemesterId = ref<number | null>(null)
  const courseFiles = ref<CourseFileRecord[]>([])

  async function upload(formData: FormData) {
    const data = (await uploadFiles(formData)) as unknown as UploadSummary
    uploadSummary.value = data
    return data
  }

  async function fetchRawData(page: number, size: number) {
    const data = (await getRawData(page, size)) as unknown as {
      headers: string[]
      rows: Record<string, unknown>[]
      total: number
    }
    rawData.value = data
    return data
  }

  async function runClean() {
    const data = (await cleanData()) as unknown as {
      total_rows_before: number
      total_rows_after: number
      removed_duplicates: number
      removed_outliers: number
    }
    cleaningSummary.value = data
    return data
  }

  async function fetchCleanedData(page: number, size: number) {
    const data = (await getCleanedData(page, size)) as unknown as {
      headers: string[]
      rows: Record<string, unknown>[]
      total: number
    }
    cleanedData.value = data
    return data
  }

  // ── Course / Class / Semester ──────────────────────────────────────────

  async function fetchCourses() {
    const data = await getCourses() as unknown as SimpleItem[]
    courses.value = data
    return data
  }

  async function addCourse(name: string) {
    const item = await createCourse(name) as unknown as SimpleItem
    await fetchCourses()
    return item
  }

  async function fetchClasses() {
    const data = await getClasses() as unknown as SimpleItem[]
    classes.value = data
    return data
  }

  async function addClass(name: string) {
    const item = await createClass(name) as unknown as SimpleItem
    await fetchClasses()
    return item
  }

  async function fetchSemesters() {
    const data = await getSemesters() as unknown as SimpleItem[]
    semesters.value = data
    return data
  }

  async function addSemester(name: string) {
    const item = await createSemester(name) as unknown as SimpleItem
    await fetchSemesters()
    return item
  }

  // ── Course files ────────────────────────────────────────────────────────

  async function fetchCourseFiles() {
    if (!selectedCourseId.value || !selectedClassId.value || !selectedSemesterId.value) {
      courseFiles.value = []
      return []
    }
    const data = await getCourseFiles(
      selectedCourseId.value,
      selectedClassId.value,
      selectedSemesterId.value,
    ) as unknown as CourseFileRecord[]
    courseFiles.value = data
    return data
  }

  async function uploadOneCourseFile(fileType: string, file: File) {
    if (!selectedCourseId.value || !selectedClassId.value || !selectedSemesterId.value) {
      throw new Error('请先选择课程、班级和学期')
    }
    await uploadCourseFile(
      selectedCourseId.value,
      selectedClassId.value,
      selectedSemesterId.value,
      fileType,
      file,
    )
    await fetchCourseFiles()
  }

  async function removeCourseFile(id: number) {
    await deleteCourseFile(id)
    await fetchCourseFiles()
  }

  return {
    uploadedFiles, uploadSummary, rawData, cleanedData, cleaningSummary,
    upload, fetchRawData, runClean, fetchCleanedData,
    courses, classes, semesters,
    selectedCourseId, selectedClassId, selectedSemesterId,
    courseFiles,
    fetchCourses, addCourse,
    fetchClasses, addClass,
    fetchSemesters, addSemester,
    fetchCourseFiles, uploadOneCourseFile, removeCourseFile,
  }
})
