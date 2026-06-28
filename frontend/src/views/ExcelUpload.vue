<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useExcelStore } from '@/store/excel'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Delete, Check } from '@element-plus/icons-vue'
import type { UploadFile, UploadRawFile } from 'element-plus'
import CourseSelectors from '@/components/CourseSelectors.vue'
import type { GradeValidationResult } from '@/api/excel'

const store = useExcelStore()
const { selection } = storeToRefs(store)

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

const FILE_TYPES: { key: string; label: string; tips: string }[] = [
  { key: 'syllabus', label: '课程大纲', tips: '上传课程教学大纲文件' },
  { key: 'student_info', label: '学生基本信息表', tips: '上传包含学生基本信息的Excel文件' },
  { key: 'grades', label: '学生成绩表', tips: '上传包含学生成绩的Excel文件' },
]

function getFileByType(type: string) {
  return store.courseFiles.find((f) => f.file_type === type) || null
}

// ── Sequential upload enforcement ──────────────────────────────────────────

const prereqMessages: Record<string, string> = {
  student_info: '请先上传课程大纲',
  grades: '请先上传学生基本信息表',
}

function canUpload(fileType: string): boolean {
  if (fileType === 'syllabus') return true
  if (fileType === 'student_info') return getFileByType('syllabus') !== null
  if (fileType === 'grades') return getFileByType('student_info') !== null
  return false
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
  if (s.courseId && s.classId && s.semesterName) {
    await store.fetchCourseFiles(s.courseId, s.classId, s.semesterName)
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
    ElMessage.warning(prereqMessages[fileType] || '无法上传此文件类型')
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
    await store.uploadOneCourseFile(s.courseId, s.classId, s.semesterName, fileType, renamedFile)
    fileList.value[fileType] = []
    ElMessage.success('上传成功')
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
    ElMessage.success('删除成功')
  } catch (e: unknown) {
    if (e instanceof Error && e.message !== 'cancel') {
      ElMessage.error('删除失败，请刷新页面后重试')
    }
  }
}

// ── Validation flow after grades upload ─────────────────────────────────────

const validationResult = ref<GradeValidationResult | null>(null)
const headerDialogVisible = ref(false)
const editedHeaders = ref<Record<string, string>>({})
const validating = ref(false)

const allThreeUploaded = computed(() =>
  !!getFileByType('syllabus') && !!getFileByType('student_info') && !!getFileByType('grades'),
)

const headerComparisonRows = computed(() => {
  if (!validationResult.value?.header_validation) return []
  return validationResult.value.header_validation.comparisons
})

async function triggerValidation() {
  if (!allThreeUploaded.value) {
    ElMessage.warning('请先上传课程大纲、学生基本信息表和学生成绩表')
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

    // Step 1: Check count mismatch
    if (!result.student_count.match) {
      await handleCountMismatch(result)
      return
    }

    // Step 2: Check header validation
    if (result.header_validation) {
      const hv = result.header_validation

      if (hv.error) {
        ElMessage.warning(hv.error)
        return
      }

      if (!hv.match) {
        await handleHeaderMismatch(result)
        return
      }
    }

    ElMessage.success('文件验证通过')
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    if (msg) ElMessage.error(msg)
  }
}

async function handleCountMismatch(result: GradeValidationResult) {
  const sc = result.student_count
  try {
    await ElMessageBox.confirm(
      `学生信息表和学生成绩表中学生人数不一致，请选择哪个数据表可能有误：\n学生信息表：${sc.student_info_count} 人，学生成绩表：${sc.grades_count} 人`,
      '学生人数不一致',
      {
        confirmButtonText: '学生信息表有误',
        cancelButtonText: '学生成绩表有误',
        distinguishCancelAndClose: true,
        type: 'warning',
      },
    )
    // confirm → student_info_wrong
    await doResolveMismatch('student_info_wrong')
  } catch (e) {
    if (e === 'cancel') {
      // cancel → grades_wrong
      await doResolveMismatch('grades_wrong')
    }
    // close → do nothing
  }
}

async function doResolveMismatch(choice: 'student_info_wrong' | 'grades_wrong') {
  const s = selection.value
  if (!s.courseId || !s.classId || !s.semesterName) return
  try {
    await store.resolveMismatch(s.courseId, s.classId, s.semesterName, choice)
    if (choice === 'student_info_wrong') {
      ElMessage.warning('已删除学生基本信息表和学生成绩表，请重新上传学生基本信息表后再上传学生成绩表')
    } else {
      ElMessage.warning('已删除学生成绩表，请修改后重新上传')
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    if (msg) ElMessage.error(msg)
  }
}

// ── Header mismatch → confirm syllabus correctness ────────────────────────

async function handleHeaderMismatch(result: GradeValidationResult) {
  try {
    await ElMessageBox.confirm(
      '学生成绩表表头与教学大纲评价项目不匹配。\n\n请确认：您上传的课程大纲是否正确？',
      '表头验证不匹配',
      {
        confirmButtonText: '大纲正确，修改成绩表表头',
        cancelButtonText: '大纲不正确，重新上传',
        distinguishCancelAndClose: true,
        type: 'warning',
      },
    )
    // confirm → syllabus is correct, show header edit dialog
    editedHeaders.value = {}
    for (const comp of result.header_validation!.comparisons) {
      editedHeaders.value[comp.expected] = comp.current || ''
    }
    headerDialogVisible.value = true
  } catch (e) {
    if (e === 'cancel') {
      // cancel → syllabus is wrong, delete syllabus (cascades to student_info + grades)
      await deleteSyllabusAndRestart()
    }
    // close → do nothing
  }
}

async function deleteSyllabusAndRestart() {
  const s = selection.value
  const syllabusFile = getFileByType('syllabus')
  if (!syllabusFile || !s.courseId || !s.classId || !s.semesterName) return
  try {
    await store.removeCourseFile(syllabusFile.id, s.courseId, s.classId, s.semesterName)
    ElMessage.warning('已删除课程大纲、学生基本信息表和学生成绩表，请从课程大纲开始重新上传')
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    if (msg) ElMessage.error(msg)
  }
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
    ElMessage.success('表头修改成功，验证通过')
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    if (msg) ElMessage.error(msg)
  }
}
</script>

<template>
  <div>
    <h2 style="margin-bottom: 20px">文件上传</h2>

    <!-- Selectors -->
    <CourseSelectors v-model="selection" :cascade="false" />

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
              <el-tag v-if="getFileByType(ft.key)" type="success" size="small">已上传</el-tag>
              <el-tag v-else type="info" size="small">未上传</el-tag>
            </div>
          </template>

          <template v-if="canUpload(ft.key)">
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
          </template>
          <div v-else style="text-align: center; padding: 40px 0; color: #909399">
            <p>{{ prereqMessages[ft.key] }}</p>
          </div>
        </el-card>
      </el-col>
    </el-row>
    <el-empty v-else description="请先在上方选择课程、班级和学期" />

    <!-- Validation button -->
    <div v-if="allThreeUploaded" style="margin-bottom: 16px">
      <el-button
        type="warning"
        :loading="validating"
        :icon="Check"
        @click="triggerValidation"
      >
        数据验证
      </el-button>
      <span style="margin-left: 12px; color: #909399; font-size: 13px">
        验证学生人数一致性和成绩表表头与大纲评价项的匹配
      </span>
    </div>

    <!-- Uploaded files table -->
    <el-card v-if="store.courseFiles.length > 0">
      <template #header>已上传文件</template>
      <el-table :data="store.courseFiles" stripe>
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
      <el-table :data="headerComparisonRows" stripe>
        <el-table-column prop="expected" label="教学大纲评价项目" width="200" />
        <el-table-column label="成绩表当前列名" width="200">
          <template #default="{ row }">
            <span :style="{ color: row.match ? '#67c23a' : '#f56c6c' }">
              {{ row.current || '(未匹配)' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="修改为">
          <template #default="{ row }">
            <el-input v-model="editedHeaders[row.expected]" placeholder="输入正确列名" />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.match" type="success" size="small">匹配</el-tag>
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
