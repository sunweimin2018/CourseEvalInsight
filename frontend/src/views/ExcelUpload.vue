<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useExcelStore } from '@/store/excel'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Delete } from '@element-plus/icons-vue'
import type { UploadFile, UploadRawFile } from 'element-plus'

const store = useExcelStore()

// ── Dropdown options ────────────────────────────────────────────────────────
const courseOptions = ref<{ id: number; name: string }[]>([])
const classOptions = ref<{ id: number; name: string }[]>([])
const semesterOptions = ref<{ id: number; name: string }[]>([])

const selectedCourse = ref<number | null>(null)
const selectedClass = ref<number | null>(null)
const selectedSemester = ref<number | null>(null)

// ── Add-new dialog ──────────────────────────────────────────────────────────
const dialogVisible = ref(false)
const dialogTitle = ref('')
const dialogInput = ref('')
const dialogType = ref<'course' | 'class' | 'semester'>('course')
const dialogLoading = ref(false)

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

// ── Data loading ────────────────────────────────────────────────────────────
async function loadOptions() {
  const [courses, classes, semesters] = await Promise.all([
    store.fetchCourses(),
    store.fetchClasses(),
    store.fetchSemesters(),
  ])
  courseOptions.value = courses
  classOptions.value = classes
  semesterOptions.value = semesters
}

// ── Three-selector linkage ──────────────────────────────────────────────────
watch([selectedCourse, selectedClass, selectedSemester], async ([c, cl, s]) => {
  if (c && cl && s) {
    store.selectedCourseId = c
    store.selectedClassId = cl
    store.selectedSemesterId = s
    await store.fetchCourseFiles()
  } else {
    store.courseFiles = []
  }
})

// ── Add-new flow ────────────────────────────────────────────────────────────
function openAddDialog(type: 'course' | 'class' | 'semester') {
  dialogType.value = type
  dialogInput.value = ''
  const labels: Record<string, string> = { course: '课程名称', class: '班级', semester: '学期' }
  dialogTitle.value = '添加新' + labels[type]
  dialogVisible.value = true
}

function handleSelectChange(type: 'course' | 'class' | 'semester', value: unknown) {
  if (value === '__add__') {
    if (type === 'course') selectedCourse.value = null
    else if (type === 'class') selectedClass.value = null
    else selectedSemester.value = null
    openAddDialog(type)
  }
}

function onCourseChange(v: unknown) { handleSelectChange('course', v) }
function onClassChange(v: unknown) { handleSelectChange('class', v) }
function onSemesterChange(v: unknown) { handleSelectChange('semester', v) }

async function confirmAdd() {
  const name = dialogInput.value.trim()
  if (!name) {
    ElMessage.warning('名称不能为空')
    return
  }
  dialogLoading.value = true
  try {
    let item: { id: number; name: string } | null = null
    if (dialogType.value === 'course') {
      item = await store.addCourse(name)
      courseOptions.value = store.courses
      selectedCourse.value = item.id
    } else if (dialogType.value === 'class') {
      item = await store.addClass(name)
      classOptions.value = store.classes
      selectedClass.value = item.id
    } else {
      item = await store.addSemester(name)
      semesterOptions.value = store.semesters
      selectedSemester.value = item.id
    }
    dialogVisible.value = false
    ElMessage.success('添加成功')
  } catch {
    // error handled by interceptor
  } finally {
    dialogLoading.value = false
  }
}

// ── File upload ─────────────────────────────────────────────────────────────
async function handleUpload(fileType: string) {
  const files = fileList.value[fileType]
  if (!files || files.length === 0) {
    ElMessage.warning('请先选择文件')
    return
  }
  if (!selectedCourse.value || !selectedClass.value || !selectedSemester.value) {
    ElMessage.warning('请先选择课程、班级和学期')
    return
  }
  uploading.value[fileType] = true
  try {
    const file = files[0].raw!
    await store.uploadOneCourseFile(fileType, file)
    fileList.value[fileType] = []
    ElMessage.success('上传成功')
  } catch {
    // error handled by interceptor
  } finally {
    uploading.value[fileType] = false
  }
}

// ── Delete file ─────────────────────────────────────────────────────────────
async function handleDelete(fileId: number) {
  try {
    await ElMessageBox.confirm('确定要删除该文件吗？', '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await store.removeCourseFile(fileId)
    ElMessage.success('删除成功')
  } catch {
    // cancelled or error
  }
}

onMounted(() => {
  loadOptions()
})
</script>

<template>
  <div>
    <h2 style="margin-bottom: 20px">文件上传</h2>

    <!-- Selectors -->
    <el-card style="margin-bottom: 20px">
      <el-row :gutter="16">
        <el-col :span="8">
          <div style="margin-bottom: 4px; font-weight: 500">课程名称</div>
          <el-select
            v-model="selectedCourse"
            placeholder="选择课程"
            style="width: 100%"
            clearable
            filterable
            @change="onCourseChange"
          >
            <el-option
              v-for="c in courseOptions"
              :key="c.id"
              :label="c.name"
              :value="c.id"
            >
              {{ c.name }}
            </el-option>
            <el-option value="__add__" style="color: #409eff; font-weight: 500">
              + 添加新课程
            </el-option>
          </el-select>
        </el-col>
        <el-col :span="8">
          <div style="margin-bottom: 4px; font-weight: 500">班级</div>
          <el-select
            v-model="selectedClass"
            placeholder="选择班级"
            style="width: 100%"
            clearable
            filterable
            @change="onClassChange"
          >
            <el-option
              v-for="c in classOptions"
              :key="c.id"
              :label="c.name"
              :value="c.id"
            >
              {{ c.name }}
            </el-option>
            <el-option value="__add__" style="color: #409eff; font-weight: 500">
              + 添加新班级
            </el-option>
          </el-select>
        </el-col>
        <el-col :span="8">
          <div style="margin-bottom: 4px; font-weight: 500">学期</div>
          <el-select
            v-model="selectedSemester"
            placeholder="选择学期"
            style="width: 100%"
            clearable
            filterable
            @change="onSemesterChange"
          >
            <el-option
              v-for="s in semesterOptions"
              :key="s.id"
              :label="s.name"
              :value="s.id"
            >
              {{ s.name }}
            </el-option>
            <el-option value="__add__" style="color: #409eff; font-weight: 500">
              + 添加新学期
            </el-option>
          </el-select>
        </el-col>
      </el-row>
    </el-card>

    <!-- Upload cards -->
    <el-row v-if="selectedCourse && selectedClass && selectedSemester" :gutter="16" style="margin-bottom: 20px">
      <el-col v-for="ft in FILE_TYPES" :key="ft.key" :span="8">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-weight: 600">{{ ft.label }}</span>
              <el-tag v-if="getFileByType(ft.key)" type="success" size="small">已上传</el-tag>
              <el-tag v-else type="info" size="small">未上传</el-tag>
            </div>
          </template>
          <div style="color: #909399; font-size: 13px; margin-bottom: 12px">{{ ft.tips }}</div>
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
            :disabled="fileList[ft.key]?.length === 0"
            @click="handleUpload(ft.key)"
          >
            上传
          </el-button>
        </el-card>
      </el-col>
    </el-row>
    <el-empty v-else description="请先在上方选择课程、班级和学期" />

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
        <el-table-column label="操作" width="100">
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

    <!-- Add dialog -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="400px" :close-on-click-modal="false">
      <el-input
        v-model="dialogInput"
        :placeholder="'请输入' + dialogTitle.replace('添加新', '')"
        maxlength="100"
        @keyup.enter="confirmAdd"
      />
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="dialogLoading" @click="confirmAdd">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>
