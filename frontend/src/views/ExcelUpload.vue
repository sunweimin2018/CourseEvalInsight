<script setup lang="ts">
import { ref, watch } from 'vue'
import { useExcelStore } from '@/store/excel'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Delete } from '@element-plus/icons-vue'
import type { UploadFile, UploadRawFile } from 'element-plus'
import CourseSelectors from '@/components/CourseSelectors.vue'
import type { SelectionModel } from '@/components/CourseSelectors.vue'

const store = useExcelStore()

const selection = ref<SelectionModel>({
  courseId: null, classId: null, semesterName: null,
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

// ── Three-selector linkage ──────────────────────────────────────────────────
watch(selection, async (s) => {
  if (s.courseId && s.classId && s.semesterName) {
    await store.fetchCourseFiles(s.courseId, s.classId, s.semesterName)
  } else {
    store.courseFiles = []
  }
}, { deep: true })

// ── File upload ─────────────────────────────────────────────────────────────
async function handleUpload(fileType: string) {
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
    const file = files[0].raw!
    await store.uploadOneCourseFile(s.courseId, s.classId, s.semesterName, fileType, file)
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
    const s = selection.value
    await store.removeCourseFile(fileId, s.courseId!, s.classId!, s.semesterName!)
    ElMessage.success('删除成功')
  } catch (e: unknown) {
    if (e instanceof Error && e.message !== 'cancel') {
      ElMessage.error('删除失败，请刷新页面后重试')
    }
  }
}
</script>

<template>
  <div>
    <h2 style="margin-bottom: 20px">文件上传</h2>

    <!-- Selectors -->
    <CourseSelectors v-model="selection" />

    <!-- Upload cards -->
    <el-row v-if="selection.courseId && selection.classId && selection.semesterName" :gutter="16" style="margin-bottom: 20px">
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
  </div>
</template>
