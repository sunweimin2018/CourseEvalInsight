import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  uploadFiles, getRawData, cleanData, getCleanedData,
  getCourses, createCourse,
  getClasses, createClass,
  getSemesters, createSemester,
  uploadCourseFile, getCourseFiles, deleteCourseFile,
  getWordContent, openExcelForEdit, getWorkingData,
  addRow, updateCell, deleteDataRow, saveWorkingCopy, resetWorkingCopy,
  type SimpleItem, type CourseFileRecord, type WordContent, type WorkingData,
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

  // Course files (scoped by the course/class/semester passed into each action)
  const courseFiles = ref<CourseFileRecord[]>([])

  // Data Preview – Word
  const wordContent = ref<WordContent | null>(null)

  // Data Preview – Excel editing
  const workingData = ref<WorkingData | null>(null)
  const hasUnsavedChanges = ref(false)
  const editingFileId = ref<number | null>(null)
  const dirtyCells = ref<Set<string>>(new Set())

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

  async function fetchCourseFiles(courseId: number, classId: number, semesterName: string) {
    const data = await getCourseFiles(courseId, classId, semesterName) as unknown as CourseFileRecord[]
    courseFiles.value = data
    return data
  }

  async function uploadOneCourseFile(courseId: number, classId: number, semesterName: string, fileType: string, file: File) {
    await uploadCourseFile(courseId, classId, semesterName, fileType, file)
    await fetchCourseFiles(courseId, classId, semesterName)
  }

  async function removeCourseFile(id: number, courseId: number, classId: number, semesterName: string) {
    await deleteCourseFile(id)
    await fetchCourseFiles(courseId, classId, semesterName)
  }

  // ── Data Preview – Word ─────────────────────────────────────────────────

  async function fetchWordContent(fileId: number) {
    const data = await getWordContent(fileId) as unknown as WordContent
    wordContent.value = data
    return data
  }

  function clearWordContent() {
    wordContent.value = null
  }

  // ── Data Preview – Excel editing ─────────────────────────────────────────

  async function openExcel(fileId: number) {
    const data = await openExcelForEdit(fileId) as unknown as WorkingData
    workingData.value = data
    editingFileId.value = fileId
    hasUnsavedChanges.value = false
    dirtyCells.value = new Set()
    return data
  }

  async function fetchWorkingData(fileId: number, page: number, size: number) {
    const data = await getWorkingData(fileId, page, size) as unknown as WorkingData
    workingData.value = data
    return data
  }

  function markDirty(rowIdx: number, colName: string) {
    dirtyCells.value = new Set([...dirtyCells.value, `${rowIdx}:${colName}`])
    hasUnsavedChanges.value = true
  }

  async function addDataRow(fileId: number, rowData: Record<string, unknown>) {
    await addRow(fileId, rowData)
    hasUnsavedChanges.value = true
  }

  async function updateDataCell(fileId: number, rowIdx: number, colName: string, value: unknown) {
    await updateCell(fileId, rowIdx, colName, value)
    markDirty(rowIdx, colName)
  }

  async function deleteDataRowAction(fileId: number, rowIdx: number) {
    await deleteDataRow(fileId, rowIdx)
    hasUnsavedChanges.value = true
  }

  async function saveChanges(fileId: number) {
    await saveWorkingCopy(fileId)
    hasUnsavedChanges.value = false
    dirtyCells.value = new Set()
  }

  async function resetChanges(fileId: number) {
    const data = await resetWorkingCopy(fileId) as unknown as WorkingData
    workingData.value = data
    hasUnsavedChanges.value = false
    dirtyCells.value = new Set()
    return data
  }

  function clearWorkingData() {
    workingData.value = null
    editingFileId.value = null
    hasUnsavedChanges.value = false
    dirtyCells.value = new Set()
  }

  function clearAll() {
    uploadedFiles.value = []
    uploadSummary.value = null
    rawData.value = null
    cleanedData.value = null
    cleaningSummary.value = null
    courseFiles.value = []
    wordContent.value = null
    clearWorkingData()
  }

  return {
    uploadedFiles, uploadSummary, rawData, cleanedData, cleaningSummary,
    upload, fetchRawData, runClean, fetchCleanedData,
    courses, classes, semesters,
    courseFiles,
    fetchCourses, addCourse,
    fetchClasses, addClass,
    fetchSemesters, addSemester,
    fetchCourseFiles, uploadOneCourseFile, removeCourseFile,
    // Data Preview
    wordContent,
    workingData, hasUnsavedChanges, editingFileId, dirtyCells,
    fetchWordContent, clearWordContent,
    openExcel, fetchWorkingData,
    addDataRow, updateDataCell, deleteDataRowAction,
    saveChanges, resetChanges, clearWorkingData, clearAll,
  }
})
