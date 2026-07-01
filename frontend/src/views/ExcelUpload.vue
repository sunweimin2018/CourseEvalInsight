<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useExcelStore } from '@/store/excel'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Delete, Check, DataBoard, Edit, Download } from '@element-plus/icons-vue'
import type { UploadFile, UploadRawFile } from 'element-plus'
import CourseSelectors from '@/components/CourseSelectors.vue'
import { analyzeExamStatus, type GradeValidationResult, type ExamStatusResult, downloadGradesTemplate } from '@/api/excel'

const { t } = useI18n()

const store = useExcelStore()
const { selection, validationStatus } = storeToRefs(store)

// ── Validation phase ──────────────────────────────────────────────────────
const validationPhase = ref<'upload' | 'validating' | 'failed' | 'passed'>('upload')
const currentStep = computed(() => {
  if (validationPhase.value === 'passed') return 3
  if (validationPhase.value === 'validating') return 1
  if (validationPhase.value === 'failed') {
    return 2  // Always a header issue; student_info was confirmed during exam status phase
  }
  if (examConfirmed.value) return 1  // student info validated via exam status
  return 0
})

const step1Status = computed(() => {
  if (validationPhase.value === 'passed') return 'success'
  if (validationPhase.value === 'validating') return 'process'
  if (validationPhase.value === 'failed' && validationResult.value) {
    return 'success'  // Student info validated independently via exam confirmation
  }
  if (examConfirmed.value) return 'success'
  return ''
})

const step2Status = computed(() => {
  if (validationPhase.value === 'passed') return 'success'
  if (validationPhase.value === 'failed' && validationResult.value) {
    const hv = validationResult.value.header_validation
    if (hv && hv.match) return 'success'
    if (hv && !hv.match && !hv.error) return 'error'
  }
  if (validationPhase.value === 'validating') return 'wait'
  return ''
})

// Sync phase from backend status on load / file refresh
watch(validationStatus, (status) => {
  if (status === 'passed') {
    validationPhase.value = 'passed'
  } else if (status === 'failed' && validationPhase.value !== 'validating') {
    validationPhase.value = 'failed'
  } else if (status === 'pending') {
    validationPhase.value = 'upload'
  }
})

// ── File upload state ───────────────────────────────────────────────────────
const fileList = ref<Record<string, UploadFile[]>>({
  syllabus: [],
  student_info: [],
  grades: [],
})
const uploading = ref<Record<string, boolean>>({
  syllabus: false,
  student_info: false,
  grades: false,
})
const headerWarnings = ref<Record<string, string[]>>({})

const FILE_TYPES = computed(() => [
  { key: 'syllabus', label: t('excel.upload.syllabus'), tips: t('excel.upload.syllabusTip') },
  { key: 'student_info', label: t('excel.upload.studentInfo'), tips: t('excel.upload.studentInfoTip') },
  { key: 'grades', label: t('excel.upload.grades'), tips: t('excel.upload.gradesTip') },
])

function getFileByType(type: string) {
  return store.courseFiles.find((f) => f.file_type === type) || null
}

function getEffectiveStatus(fileType: string): 'passed' | 'pending' | 'failed' {
  const file = getFileByType(fileType)
  if (!file) return 'pending'
  if (file.validation_status === 'passed' || file.validation_status === 'failed') {
    return file.validation_status
  }
  if (fileType === 'student_info' && examConfirmed.value) {
    return 'passed'
  }
  return 'pending'
}

// ── Sequential upload enforcement ──────────────────────────────────────────

const prereqMessages = computed<Record<string, string>>(() => ({
  student_info: t('excel.upload.prereqSyllabus'),
  grades: t('excel.upload.prereqStudentInfo'),
}))

function canUpload(fileType: string): boolean {
  if (fileType === 'syllabus') return true
  if (fileType === 'student_info') return getFileByType('syllabus') !== null
  if (fileType === 'grades') {
    if (!getFileByType('student_info')) return false
    // Gate: must confirm exam status before uploading grades (when analysis columns exist)
    if (examStatus.value && !examStatus.value.skipped && !examConfirmed.value) return false
    return true
  }
  return false
}

async function fetchExamStatus() {
  const s = selection.value
  if (!s.courseId || !s.classId || !s.semesterName) return
  examStatusLoading.value = true
  try {
    const result = await analyzeExamStatus(s.courseId, s.classId, s.semesterName) as unknown as ExamStatusResult
    examStatus.value = result
    if (result.skipped) {
      examConfirmed.value = true // No exam columns — auto-confirm
    } else {
      examConfirmed.value = false
      examDialogVisible.value = true // Show modal
    }
  } catch {
    examStatus.value = null
    examConfirmed.value = true // Allow proceed on error
  } finally {
    examStatusLoading.value = false
  }
}

function confirmExamStatus() {
  examConfirmed.value = true
  examDialogVisible.value = false
  ElMessage.success('考试状态确认成功，请继续上传学生成绩表')
}

async function rejectExamStatus() {
  const s = selection.value
  const file = getFileByType('student_info')
  if (file && s.courseId && s.classId && s.semesterName) {
    await store.removeCourseFile(file.id, s.courseId, s.classId, s.semesterName)
  }
  examConfirmed.value = false
  examStatus.value = null
  examDialogVisible.value = false
  ElMessage.warning('已删除学生基本信息表，请修改后重新上传')
}

async function handleDownloadTemplate() {
  const s = selection.value
  if (!s.courseId || !s.classId || !s.semesterName) return
  try {
    const blob = await downloadGradesTemplate(s.courseId, s.classId, s.semesterName) as Blob
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '学生成绩表模板.xlsx'
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('模板下载成功')
  } catch {
    ElMessage.error('模板下载失败')
  }
}

function uploadDisabled(fileType: string): boolean {
  if (!canUpload(fileType)) return true
  return (fileList.value[fileType]?.length ?? 0) === 0
}

// ── Validation ──────────────────────────────────────────────────────────────

function beforeUpload(file: UploadRawFile, fileType: string) {
  const ext = file.name.split('.').pop()?.toLowerCase()
  if (fileType === 'syllabus') {
    if (ext !== 'docx' && ext !== 'doc') {
      ElMessage.error('仅支持 .docx 和 .doc 格式文件')
      return false
    }
  } else {
    if (ext !== 'xlsx' && ext !== 'xls') {
      ElMessage.error('仅支持 .xlsx 和 .xls 格式文件')
      return false
    }
  }
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 10MB')
    return false
  }
  return true
}

// ── Three-selector linkage ──────────────────────────────────────────────────

watch(selection, async (s) => {
  examStatus.value = null
  examConfirmed.value = false
  examDialogVisible.value = false
  validationPhase.value = 'upload'
  validationResult.value = null
  headerWarnings.value = {}
  if (s.courseId && s.classId && s.semesterName) {
    await store.fetchCourseFiles(s.courseId, s.classId, s.semesterName)
    // Restore confirmed state: if files already exist, the user has
    // previously uploaded and confirmed — skip re-confirmation.
    const siFile = store.courseFiles.find(f => f.file_type === 'student_info')
    const sylFile = store.courseFiles.find(f => f.file_type === 'syllabus')
    if (siFile && sylFile) {
      examConfirmed.value = true
    }
    if (validationStatus.value === 'passed') {
      validationPhase.value = 'passed'
    } else if (validationStatus.value === 'failed') {
      validationPhase.value = 'failed'
    }
  } else {
    store.courseFiles = []
  }
}, { deep: true })

// ── File upload ─────────────────────────────────────────────────────────────

function buildFileName(fileType: string, ext: string): string {
  const s = selection.value
  const courseName = store.courses.find((c) => c.id === s.courseId)?.name || '未命名课程'
  const className = store.classes.find((c) => c.id === s.classId)?.name || '未命名班级'
  const semesterName = s.semesterName || '未命名学期'
  switch (fileType) {
    case 'syllabus':
      return `${courseName}课程大纲.${ext}`
    case 'student_info':
      return `${className}学生基本信息表.${ext}`
    case 'grades':
      return `${courseName}${className}${semesterName}学生成绩分布表.${ext}`
    default:
      return `file.${ext}`
  }
}

async function handleUpload(fileType: string) {
  if (!canUpload(fileType)) {
    ElMessage.warning(prereqMessages.value[fileType] || 'N/A')
    return
  }
  const files = fileList.value[fileType]
  if (!files || files.length === 0) {
    ElMessage.warning('请先选择文件')
    return
  }
  const s = selection.value
  if (!s.courseId || !s.classId || !s.semesterName) {
    ElMessage.warning('请先选择课程、班级和学期')
    return
  }
  uploading.value[fileType] = true
  try {
    const rawFile = files[0].raw!
    const ext = rawFile.name.split('.').pop() || 'xlsx'
    const newName = buildFileName(fileType, ext)
    const renamedFile = new File([rawFile], newName, { type: rawFile.type })
    const record = await store.uploadOneCourseFile(s.courseId, s.classId, s.semesterName, fileType, renamedFile)
    fileList.value[fileType] = []
    ElMessage.success('上传成功')
    if (record?.header_warnings?.length) {
      headerWarnings.value[fileType] = record.header_warnings
    } else {
      delete headerWarnings.value[fileType]
    }
    if (fileType === 'student_info') {
      await fetchExamStatus()
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    if (msg) ElMessage.error(msg)
  } finally {
    uploading.value[fileType] = false
  }
}

// ── Delete file ─────────────────────────────────────────────────────────────

async function handleDelete(fileId: number) {
  try {
    await ElMessageBox.confirm(
      '确定要删除该文件吗？删除课程大纲将同时删除已上传的学生信息表和成绩表；删除学生信息表将同时删除已上传的成绩表。',
      '确认删除',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    const s = selection.value
    await store.removeCourseFile(fileId, s.courseId!, s.classId!, s.semesterName!)
    validationResult.value = null
    ElMessage.success('删除成功')
  } catch (e: unknown) {
    if (e instanceof Error && e.message !== 'cancel') {
      ElMessage.error('删除失败，请刷新页面后重试')
    }
  }
}

// ── Validation flow after grades upload ─────────────────────────────────────

const validationResult = ref<GradeValidationResult | null>(null)
const validationDialogVisible = ref(false)
const validationPromptVisible = ref(false)

const headerDialogVisible = ref(false)
const editedHeaders = ref<Record<string, string>>({})
const validating = ref(false)

// ── Exam status analysis (after student_info upload) ──────────────────────
const examStatus = ref<ExamStatusResult | null>(null)
const examStatusLoading = ref(false)
const examConfirmed = ref(false)
const examDialogVisible = ref(false)

interface FlatExamStudent {
  _idx: number
  status: string
  name: string
  student_id: string
  class_name: string
  score?: number
  _sep?: boolean
}

const flatExamStudents = computed(() => {
  const rows: FlatExamStudent[] = []
  let idx = 0
  for (const s of (examStatus.value?.normal?.students ?? [])) {
    idx++
    rows.push({ _idx: idx, status: '正常', name: s.name, student_id: s.student_id, class_name: s.class_name, score: s.score })
  }
  for (const s of (examStatus.value?.deferred?.students ?? [])) {
    idx++
    rows.push({ _idx: idx, status: '缓考', name: s.name, student_id: s.student_id, class_name: s.class_name })
  }
  for (const s of (examStatus.value?.absent?.students ?? [])) {
    idx++
    rows.push({ _idx: idx, status: '缺考', name: s.name, student_id: s.student_id, class_name: s.class_name })
  }
  if (rows.length > 12) {
    return [
      ...rows.slice(0, 5),
      { _idx: 0, status: '', name: '', student_id: '', class_name: '', _sep: true } as FlatExamStudent,
      ...rows.slice(-4),
    ]
  }
  return rows
})

const courseInfoExamRows = computed(() => {
  const ci = examStatus.value?.course_info
  if (!ci?.comparisons) return []
  return [
    { field: '课程编号', studentInfoValue: ci.comparisons.course_code.grades_value, syllabusValue: ci.comparisons.course_code.syllabus_value, match: ci.comparisons.course_code.match },
    { field: '课程名称', studentInfoValue: ci.comparisons.course_name.grades_value, syllabusValue: ci.comparisons.course_name.syllabus_value, match: ci.comparisons.course_name.match },
  ]
})

// Hide student_info and grades from the uploaded files table when validation is pending or failed
const displayedCourseFiles = computed(() => {
  return store.courseFiles.filter((f) => {
    if (f.file_type === 'student_info') {
      if (examConfirmed.value) return true
      if (examStatus.value?.skipped ?? false) return true
      return false
    }
    if (f.file_type === 'grades') {
      if (f.validation_status === 'pending' || f.validation_status === 'failed') return false
    }
    return true
  })
})

const allThreeUploaded = computed(() =>
  !!getFileByType('syllabus') && !!getFileByType('student_info') && !!getFileByType('grades'),
)

// Force validation prompt modal when all 3 files are uploaded
watch([allThreeUploaded, validationPhase], ([uploaded, phase]) => {
  if (uploaded && phase !== 'passed') {
    validationPromptVisible.value = true
  } else {
    validationPromptVisible.value = false
  }
})

const headerComparisonRows = computed(() => {
  if (!validationResult.value?.header_validation) return []
  return validationResult.value.header_validation.comparisons
})

const headerEditRows = computed(() => {
  return headerComparisonRows.value.filter((row) => row.expected)
})


async function validateStudentInfo() {
  await fetchExamStatus()
}

async function startValidation() {
  validationPhase.value = 'validating'
  await triggerValidation()
}

async function triggerValidation() {
  if (!allThreeUploaded.value) {
    ElMessage.warning(t('excel.validation.needThree'))
    validationPhase.value = 'upload'
    return
  }
  validating.value = true
  try {
    await runValidation()
  } finally {
    validating.value = false
  }
}

async function runValidation() {
  const s = selection.value
  if (!s.courseId || !s.classId || !s.semesterName) return
  try {
    const result = await store.validateGrades(s.courseId, s.classId, s.semesterName)
    validationResult.value = result

    try {
      await store.fetchCourseFiles(s.courseId, s.classId, s.semesterName)
    } catch {
      // ignore fetch failure; validation result is authoritative
    }

    validationPhase.value = 'failed'
    validationDialogVisible.value = true
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    if (msg) ElMessage.error(msg)
  }
}

function confirmValidationPass() {
  validationDialogVisible.value = false
  ElMessage.success('学生成绩表验证通过')
}

async function rejectGradesValidation() {
  validationDialogVisible.value = false
  await doResolveMismatch('grades_wrong')
}

async function forcePassValidation() {
  const s = selection.value
  if (!s.courseId || !s.classId || !s.semesterName) return
  try {
    await store.forcePassAndRefresh(s.courseId, s.classId, s.semesterName)
    validationPhase.value = 'passed'
    validationDialogVisible.value = false
    ElMessage.success('学生成绩表验证通过')
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    if (msg) ElMessage.error(msg)
  }
}

async function doResolveMismatch(choice: 'student_info_wrong' | 'grades_wrong') {
  const s = selection.value
  if (!s.courseId || !s.classId || !s.semesterName) return
  try {
    await store.resolveMismatch(s.courseId, s.classId, s.semesterName, choice)
    validationPhase.value = 'upload'
    ElMessage.warning('已删除学生成绩表，请修改后重新上传')
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    if (msg) ElMessage.error(msg)
  }
}

// ── Open header edit dialog from validation results ──────────────────────

function openHeaderEditDialog() {
  validationDialogVisible.value = false
  if (!validationResult.value?.header_validation?.comparisons) return
  editedHeaders.value = {}
  for (const comp of validationResult.value.header_validation.comparisons) {
    if (comp.expected) {
      editedHeaders.value[comp.expected] = comp.current || ''
    }
  }
  headerDialogVisible.value = true
}

async function confirmHeaderEdits() {
  const s = selection.value
  const gradesFile = getFileByType('grades')
  if (!gradesFile || !s.courseId || !s.classId || !s.semesterName) return

  const mapping: Record<string, string> = {}
  for (const [expected, newName] of Object.entries(editedHeaders.value)) {
    const comp = validationResult.value?.header_validation?.comparisons.find(
      (c) => c.expected === expected,
    )
    if (comp && comp.current && comp.current !== newName.trim()) {
      mapping[comp.current] = newName.trim()
    }
  }

  if (Object.keys(mapping).length === 0) {
    headerDialogVisible.value = false
    return
  }

  try {
    await store.repairHeaders(gradesFile.id, mapping)
    headerDialogVisible.value = false
    validationPhase.value = 'upload'
    ElMessage.success('表头修改成功，请重新进行数据验证')
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    if (msg) ElMessage.error(msg)
  }
}
</script>

<template>
  <div>
    <h2 class="page-title">{{ $t('excel.upload.title') }}</h2>

    <!-- Selectors -->
    <CourseSelectors v-model="selection" :cascade="false" />

    <!-- Step indicator -->
    <el-steps
      v-if="selection.courseId && selection.classId && selection.semesterName"
      :active="currentStep"
      finish-status="success"
      style="margin-bottom: 24px"
    >
      <el-step :title="$t('excel.steps.upload')" :description="$t('excel.steps.uploadDesc')" />
      <el-step :title="$t('excel.steps.studentCheck')" :description="$t('excel.steps.studentCheckDesc')" :status="step1Status" />
      <el-step :title="$t('excel.steps.headerCheck')" :description="$t('excel.steps.headerCheckDesc')" :status="step2Status" />
      <el-step :title="$t('excel.steps.passed')" :description="$t('excel.steps.passedDesc')" />
    </el-steps>

    <!-- Upload cards -->
    <el-row
      v-if="selection.courseId && selection.classId && selection.semesterName"
      :gutter="16"
      style="margin-bottom: 20px"
    >
      <el-col v-for="ft in FILE_TYPES" :key="ft.key" :span="8">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-weight: 600">{{ ft.label }}</span>
              <div style="display: flex; gap: 6px; align-items: center">
                <el-tag v-if="getFileByType(ft.key)" type="success" size="small">
                  {{ $t('excel.upload.uploaded') }}
                </el-tag>
                <el-tag v-else type="info" size="small">
                  {{ $t('excel.upload.notUploaded') }}
                </el-tag>
                <template v-if="ft.key !== 'syllabus' && getFileByType(ft.key)">
                  <el-tag
                    v-if="getEffectiveStatus(ft.key) === 'passed'"
                    type="success"
                    size="small"
                  >
                    {{ $t('excel.upload.validated') }}
                  </el-tag>
                  <el-tag
                    v-else-if="getEffectiveStatus(ft.key) === 'pending'"
                    size="small"
                    style="cursor: pointer"
                    @click.stop="ft.key === 'student_info' ? validateStudentInfo() : startValidation()"
                  >
                    {{ $t('excel.upload.pendingValidation') }}
                  </el-tag>
                  <el-tag
                    v-else
                    type="danger"
                    size="small"
                    style="cursor: pointer"
                    @click.stop="ft.key === 'student_info' ? validateStudentInfo() : startValidation()"
                  >
                    {{ $t('excel.upload.validationFailed') }}
                  </el-tag>
                </template>
              </div>
            </div>
          </template>

          <!-- File already uploaded -->
          <template v-if="getFileByType(ft.key)">
            <div style="text-align: center; padding: 24px 12px; background: #f0f9eb; border-radius: 8px">
              <el-icon style="font-size: 28px; color: #67c23a"><Check /></el-icon>
              <div style="margin-top: 8px; color: #67c23a; font-weight: 500">文件已上传</div>
              <div style="font-size: 12px; color: #909399; margin-top: 4px">
                如需更换请先在下方「已上传文件」中删除
              </div>
            </div>
          </template>

          <!-- No file yet, can upload -->
          <template v-else-if="canUpload(ft.key)">
            <div style="color: #909399; font-size: 13px; margin-bottom: 12px">
              {{ ft.tips }}
            </div>
            <el-upload
              v-model:file-list="fileList[ft.key]"
              drag
              :limit="1"
              :auto-upload="false"
              :before-upload="(file: UploadRawFile) => beforeUpload(file, ft.key)"
              :accept="ft.key === 'syllabus' ? '.docx,.doc' : '.xlsx,.xls'"
            >
              <el-icon style="font-size: 32px; color: #c0c4cc"><UploadFilled /></el-icon>
              <div style="margin-top: 6px; color: #606266; font-size: 13px">
                拖拽文件或<em>点击上传</em>
              </div>
            </el-upload>
            <el-button
              type="primary"
              style="width: 100%; margin-top: 12px"
              :loading="uploading[ft.key]"
              :disabled="uploadDisabled(ft.key)"
              @click="handleUpload(ft.key)"
            >
              上传
            </el-button>
            <el-alert
              v-if="headerWarnings[ft.key]?.length"
              :title="$t('excel.upload.headerWarning')"
              type="warning"
              :closable="false"
              show-icon
              style="margin-top: 12px"
            >
              <template #default>
                <ul style="margin: 4px 0; padding-left: 20px">
                  <li v-for="w in headerWarnings[ft.key]" :key="w">{{ w }}</li>
                </ul>
              </template>
            </el-alert>
          </template>

          <!-- Cannot upload yet (missing prerequisite) -->
          <div v-else style="text-align: center; padding: 24px 0">
            <el-alert
              :title="prereqMessages[ft.key]"
              type="warning"
              :closable="false"
              show-icon
              style="display: inline-flex; text-align: left"
            />
          </div>
        </el-card>
      </el-col>
    </el-row>
    <el-result v-else icon="info" title="请先在上方选择课程、班级和学期" />

    <!-- Grades template download (after student_info confirmed, before grades upload) -->
    <div
      v-if="examConfirmed && getFileByType('student_info') && !getFileByType('grades')"
      style="margin-bottom: 20px"
    >
      <el-card style="border: 2px dashed #409eff; background: #ecf5ff; text-align: center">
        <p style="color: #409eff; font-weight: 600; margin-bottom: 12px; font-size: 15px">
          学生基本信息已确认，可下载学生成绩表模板
        </p>
        <el-button type="primary" size="large" :icon="Download" @click="handleDownloadTemplate">
          模板下载
        </el-button>
      </el-card>
    </div>

    <!-- Exam status analysis modal (after student_info upload, before grades) -->
    <el-dialog
      v-model="examDialogVisible"
      title="考试状态分析"
      width="820px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
    >
      <template v-if="examStatus">
        <div v-loading="examStatusLoading">
          <p style="color: #606266; font-size: 14px; margin-bottom: 16px">
            学生基本信息表已上传，请核对以下考试状态信息后确认：
          </p>

          <!-- Merged student table -->
          <el-table
            :data="flatExamStudents"
            border size="small" max-height="360" style="width: 100%; margin-bottom: 12px"
            :row-class-name="({ row }: any) => row._sep ? 'sep-row' : ''"
          >
            <el-table-column width="70">
              <template #header><span>状态</span></template>
              <template #default="{ row }">
                <span v-if="row._sep" style="color: #909399">…</span>
                <el-tag v-else-if="row.status === '正常'" type="success" size="small">正常</el-tag>
                <el-tag v-else-if="row.status === '缓考'" type="warning" size="small">缓考</el-tag>
                <el-tag v-else type="danger" size="small">缺考</el-tag>
              </template>
            </el-table-column>
            <el-table-column min-width="80">
              <template #header><span>姓名</span></template>
              <template #default="{ row }">
                <span v-if="row._sep" style="color: #909399">…</span>
                <span v-else>{{ row.name }}</span>
              </template>
            </el-table-column>
            <el-table-column min-width="110">
              <template #header><span>学号</span></template>
              <template #default="{ row }">
                <span v-if="row._sep" style="color: #909399">…</span>
                <span v-else>{{ row.student_id }}</span>
              </template>
            </el-table-column>
            <el-table-column min-width="100">
              <template #header><span>班级</span></template>
              <template #default="{ row }">
                <span v-if="row._sep" style="color: #909399">…</span>
                <span v-else>{{ row.class_name }}</span>
              </template>
            </el-table-column>
            <el-table-column v-if="examStatus.has_score_col" width="70">
              <template #header><span>成绩</span></template>
              <template #default="{ row }">
                <span v-if="row._sep" style="color: #909399">…</span>
                <span v-else>{{ row.score }}</span>
              </template>
            </el-table-column>
          </el-table>

          <p style="color: #909399; font-size: 13px; margin-bottom: 14px">
            共 {{ examStatus.total }} 人：正常 {{ examStatus.normal.count }} 人<template v-if="examStatus.deferred.count > 0">，缓考 {{ examStatus.deferred.count }} 人</template><template v-if="examStatus.absent.count > 0">，缺考 {{ examStatus.absent.count }} 人</template>
          </p>

          <!-- Course info comparison -->
          <div v-if="examStatus.course_info?.student_info_has_metadata" style="background: #f5f7fa; border-radius: 8px; padding: 12px 16px; margin-bottom: 12px">
            <div style="font-weight: 600; margin-bottom: 8px; color: #303133">
              <el-tag :type="examStatus.course_info.match ? 'success' : 'warning'" size="small">
                {{ examStatus.course_info.match ? '课程信息一致' : '课程信息不一致' }}
              </el-tag>
              &nbsp;学生信息表与教学大纲字段比对
            </div>
            <el-table :data="courseInfoExamRows" border size="small" style="width: 100%">
              <el-table-column prop="field" label="字段" width="100" />
              <el-table-column label="学生信息表">
                <template #default="{ row }">
                  <span>{{ row.studentInfoValue || '(无)' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="教学大纲">
                <template #default="{ row }">
                  <span>{{ row.syllabusValue || '(无)' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="比对结果" width="100">
                <template #default="{ row }">
                  <el-tag :type="row.match ? 'success' : 'danger'" size="small">
                    {{ row.match ? '一致' : '不一致' }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
            <p v-if="!examStatus.course_info.match" style="color: #e6a23c; font-size: 12px; margin: 8px 0 0">
              课程信息不一致，请检查文件是否正确。如确认无误可继续操作。
            </p>
          </div>
        </div>
      </template>

      <template #footer>
        <span class="dialog-footer">
          <p style="color: #606266; font-size: 14px; font-weight: 600; margin-bottom: 12px">
            以上考试状态信息是否正确？
          </p>
          <el-button
            type="success"
            size="large"
            :icon="Check"
            @click="confirmExamStatus"
          >
            信息正确，继续上传学生成绩表
          </el-button>
          <el-button
            type="danger"
            size="large"
            :icon="Delete"
            style="margin-left: 12px"
            @click="rejectExamStatus"
          >
            信息不正确，重新上传学生基本信息表
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- Validation prompt modal (forced for upload, closeable for failed) -->
    <el-dialog
      v-model="validationPromptVisible"
      width="520px"
      :close-on-click-modal="false"
      :close-on-press-escape="validationPhase === 'failed'"
      :show-close="validationPhase === 'failed'"
      :title="validationPhase === 'failed' ? $t('excel.validation.failedTitle') : undefined"
    >
      <!-- Upload phase: prompt to start validation -->
      <template v-if="validationPhase === 'upload'">
        <el-result
          icon="warning"
          :title="$t('excel.validation.trigger')"
          :sub-title="$t('excel.validation.triggerDesc')"
        >
          <template #extra>
            <el-button
              type="warning"
              size="large"
              :loading="validating"
              @click="startValidation"
            >
              {{ $t('excel.validation.startBtn') }}
            </el-button>
          </template>
        </el-result>
      </template>

      <!-- Failed phase: retry or view details -->
      <template v-else-if="validationPhase === 'failed'">
        <el-result
          icon="error"
          :title="$t('excel.validation.failedTitle')"
          :sub-title="$t('excel.validation.failedDesc')"
        >
          <template #extra>
            <el-button type="primary" @click="validationDialogVisible = true">
              查看验证结果
            </el-button>
            <el-button
              type="danger"
              :loading="validating"
              @click="startValidation"
            >
              {{ $t('excel.validation.retryBtn') }}
            </el-button>
          </template>
        </el-result>
      </template>

      <!-- Validating: loading state -->
      <template v-else-if="validationPhase === 'validating'">
        <div style="text-align: center; padding: 40px">
          <el-icon style="font-size: 48px; color: #409eff">
            <svg viewBox="0 0 1024 1024" width="1em" height="1em" fill="currentColor">
              <path d="M512 64a448 448 0 1 0 0 896 448 448 0 0 0 0-896zm0 832a384 384 0 1 1 0-768 384 384 0 0 1 0 768z"/>
              <path d="M512 256a32 32 0 0 1 32 32v256a32 32 0 0 1-64 0V288a32 32 0 0 1 32-32z"/>
              <path d="M512 640a48 48 0 1 1 0 96 48 48 0 0 1 0-96z"/>
            </svg>
          </el-icon>
          <p style="color: #409eff; margin-top: 16px; font-size: 16px; font-weight: 600">正在验证数据...</p>
        </div>
      </template>
    </el-dialog>

    <!-- Phase 3: Passed -->
    <div v-if="validationPhase === 'passed'" style="margin-bottom: 20px">
      <el-card style="border: 2px solid #67c23a; background: #f0f9eb">
        <el-result icon="success" title="数据验证通过" sub-title="您可以进入以下模块继续操作">
          <template #extra>
            <router-link to="/excel/preview">
              <el-button type="primary" size="large">
                <el-icon style="margin-right: 6px"><DataBoard /></el-icon>
                预览/编辑数据
              </el-button>
            </router-link>
            <router-link to="/report/builder" style="margin-left: 12px">
              <el-button type="success" size="large">
                <el-icon style="margin-right: 6px"><Edit /></el-icon>
                生成报告
              </el-button>
            </router-link>
          </template>
        </el-result>
      </el-card>
    </div>

    <!-- Uploaded files table -->
    <el-card v-if="displayedCourseFiles.length > 0">
      <template #header>已上传文件</template>
      <el-table :data="displayedCourseFiles" stripe>
        <el-table-column prop="file_type_display" label="文件类型" width="160" />
        <el-table-column prop="file_name" label="文件名称" min-width="200" />
        <el-table-column label="文件大小" width="120">
          <template #default="{ row }">
            {{ (row.file_size / 1024).toFixed(1) }} KB
          </template>
        </el-table-column>
        <el-table-column prop="upload_time" label="上传时间" width="180" />
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button
              type="danger"
              size="small"
              :icon="Delete"
              @click="handleDelete(row.id)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Validation result dialog -->
    <el-dialog
      v-model="validationDialogVisible"
      :title="validationPhase === 'passed' ? '学生成绩表验证通过' : '学生成绩表验证结果'"
      width="850px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
    >
      <template v-if="validationResult">
        <!-- Student count comparison -->
        <div style="margin-bottom: 20px">
          <h4 style="margin-bottom: 10px">
            <el-tag :type="validationResult.student_count.student_id_match ? 'success' : 'danger'" size="default">
              {{ validationResult.student_count.student_id_match ? '学号一致' : '学号不一致' }}
            </el-tag>
            &nbsp;学生信息表
            <strong>{{ validationResult.student_count.student_info_count }}</strong> 人，
            学生成绩表
            <strong>{{ validationResult.student_count.grades_count }}</strong> 人
          </h4>

          <!-- Mismatch detail -->
          <template v-if="!validationResult.student_count.student_id_match && validationResult.student_count.comparison">
            <div v-if="validationResult.student_count.comparison.only_in_student_info.length" style="margin-bottom: 12px">
              <el-tag type="danger" size="small" style="margin-bottom: 6px">
                仅在「学生基本信息表」中存在（{{ validationResult.student_count.comparison.only_in_student_info.length }} 人），成绩表中缺失：
              </el-tag>
              <el-table
                :data="validationResult.student_count.comparison.only_in_student_info"
                border size="small" max-height="200"
              >
                <el-table-column type="index" label="序号" width="60" />
                <el-table-column prop="name" label="姓名" min-width="100" />
                <el-table-column prop="student_id" label="学号" min-width="120" />
                <el-table-column prop="class_name" label="班级" min-width="100" />
                <el-table-column label="来源" width="100">
                  <template #default>
                    <el-tag type="primary" size="small">学生信息表</el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            <div v-if="validationResult.student_count.comparison.only_in_grades.length" style="margin-bottom: 12px">
              <el-tag type="danger" size="small" style="margin-bottom: 6px">
                仅在「学生成绩表」中存在（{{ validationResult.student_count.comparison.only_in_grades.length }} 人），学生信息表中缺失：
              </el-tag>
              <el-table
                :data="validationResult.student_count.comparison.only_in_grades"
                border size="small" max-height="200"
              >
                <el-table-column type="index" label="序号" width="60" />
                <el-table-column prop="name" label="姓名" min-width="100" />
                <el-table-column prop="student_id" label="学号" min-width="120" />
                <el-table-column prop="class_name" label="班级" min-width="100" />
                <el-table-column label="来源" width="100">
                  <template #default>
                    <el-tag type="success" size="small">学生成绩表</el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            <p v-if="validationResult.student_count.comparison.matching_count > 0" style="color: #67c23a; font-size: 13px">
              两表共同包含 {{ validationResult.student_count.comparison.matching_count }} 名学生
            </p>
          </template>
        </div>

        <!-- Header validation -->
        <div v-if="validationResult.header_validation" style="margin-bottom: 20px">
          <h4 style="margin-bottom: 8px">
            <el-tag :type="validationResult.header_validation.match ? 'success' : 'danger'" size="default">
              {{ validationResult.header_validation.match ? '表头匹配' : '表头不匹配' }}
            </el-tag>
            &nbsp;成绩表列名与教学大纲评价项目对比
          </h4>

          <el-table
            v-if="!validationResult.header_validation.error && validationResult.header_validation.comparisons.length > 0"
            :data="validationResult.header_validation.comparisons"
            border
            size="small"
          >
            <el-table-column label="大纲评价项目" width="280">
              <template #default="{ row }">
                <template v-if="row.expected">
                  {{ row.expected }}<template v-if="row.percentage">&nbsp;({{ row.percentage }})</template>
                </template>
                <span v-else style="color: #909399; font-style: italic">(无对应大纲项)</span>
              </template>
            </el-table-column>
            <el-table-column label="成绩表列名" width="240">
              <template #default="{ row }">
                <span :style="{
                  color: row.match ? '#67c23a' :
                         row.similarity != null ? '#e6a23c' :
                         '#f56c6c'
                }">
                  {{ row.current || '(未匹配)' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.match" type="success" size="small">匹配</el-tag>
                <el-tag v-else-if="row.similarity != null" type="warning" size="small">
                  相似 {{ (row.similarity * 100).toFixed(0) }}%
                </el-tag>
                <el-tag v-else-if="!row.expected" type="warning" size="small">多余列</el-tag>
                <el-tag v-else type="danger" size="small">不匹配</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- Passed summary -->
        <el-result
          v-if="validationPhase === 'passed'"
          icon="success"
          title="验证通过"
          sub-title="学生成绩表验证全部通过，可以继续后续操作"
        />
      </template>

      <template #footer>
        <span class="dialog-footer">
          <template v-if="validationPhase === 'passed'">
            <el-button type="primary" @click="confirmValidationPass">确 定</el-button>
          </template>
          <template v-else>
            <div
              v-if="validationResult?.header_validation && !validationResult.header_validation.match"
              style="text-align: left; margin-bottom: 16px; padding: 12px; background: #fdf6ec; border-radius: 6px; color: #303133; font-weight: 700; font-size: 13px"
            >
              您上传的学生成绩表成绩组成与本课程教学大纲要求的考核要求不一样（见上表），可
              <el-link type="primary" :underline="true" @click="handleDownloadTemplate">
                下载学生成绩表模板
              </el-link>
              ，以模板的格式重新上传学生成绩表。
            </div>
            <el-button type="danger" @click="rejectGradesValidation">
              删除成绩表，重新上传
            </el-button>
            <el-button
              v-if="validationResult?.header_validation && validationResult.header_validation.match"
              type="success"
              @click="forcePassValidation"
            >
              表头无误，确认通过
            </el-button>
          </template>
        </span>
      </template>
    </el-dialog>

    <!-- Header edit dialog -->
    <el-dialog
      v-model="headerDialogVisible"
      title="成绩表表头不匹配"
      width="750px"
      :close-on-click-modal="false"
    >
      <p style="margin-bottom: 16px; color: #909399">
        成绩表中的列名与教学大纲中的评价项目不匹配，请修改成绩列表头使其与大纲评价项目一致：
      </p>
      <el-table :data="headerEditRows" stripe>
        <el-table-column label="教学大纲评价项目" width="220">
          <template #default="{ row }">
            <template v-if="row.expected">
              {{ row.expected }}<template v-if="row.percentage">&nbsp;({{ row.percentage }})</template>
            </template>
            <span v-else style="color: #909399; font-style: italic">(无对应大纲项)</span>
          </template>
        </el-table-column>
        <el-table-column label="成绩表当前列名" width="200">
          <template #default="{ row }">
            <span :style="{
              color: row.match ? '#67c23a' :
                     row.similarity != null ? '#e6a23c' :
                     '#f56c6c'
            }">
              {{ row.current || '(未匹配)' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="修改为">
          <template #default="{ row }">
            <el-input v-model="editedHeaders[row.expected]" placeholder="输入正确列名" />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.match" type="success" size="small">匹配</el-tag>
            <el-tag v-else-if="row.similarity != null" type="warning" size="small">
              相似 {{ (row.similarity * 100).toFixed(0) }}%
            </el-tag>
            <el-tag v-else type="danger" size="small">不匹配</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="headerDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmHeaderEdits">确认修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>
