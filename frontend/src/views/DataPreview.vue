<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useExcelStore } from '@/store/excel'
import { ElMessage } from 'element-plus'
import { Document, DataBoard, Edit } from '@element-plus/icons-vue'
import CourseSelectors from '@/components/CourseSelectors.vue'
import WordDocViewer from '@/components/WordDocViewer.vue'
import ExcelDataEditor from '@/components/ExcelDataEditor.vue'
import type { CourseFileRecord } from '@/api/excel'

const { t } = useI18n()

const store = useExcelStore()
const { selection, validationStatus } = storeToRefs(store)

const selectedFileType = ref<'syllabus' | 'student_info' | 'grades' | null>(null)
const loading = ref(false)
const wordLoading = ref(false)
const excelLoading = ref(false)

const editorPage = ref(1)
const pageSize = 20

const currentFile = computed<CourseFileRecord | null>(() => {
  if (!selectedFileType.value) return null
  return store.courseFiles.find(f => f.file_type === selectedFileType.value) || null
})

const availableTypes = computed(() => {
  return store.courseFiles.map(f => f.file_type)
})

async function onSelectionChange() {
  const s = selection.value
  if (s.courseId && s.classId && s.semesterName) {
    loading.value = true
    try {
      await store.fetchCourseFiles(s.courseId, s.classId, s.semesterName)
    } finally {
      loading.value = false
    }
    selectedFileType.value = null
    store.clearWordContent()
    store.clearWorkingData()
  } else {
    store.courseFiles = []
    selectedFileType.value = null
    store.clearWordContent()
    store.clearWorkingData()
  }
}

watch(selection, onSelectionChange, { deep: true })

async function selectFileType(type: 'syllabus' | 'student_info' | 'grades') {
  selectedFileType.value = type
  const file = currentFile.value
  if (!file) return

  if (type === 'syllabus') {
    wordLoading.value = true
    store.clearWordContent()
    try {
      await store.fetchWordContent(file.id)
    } catch {
      ElMessage.error(t('common.error'))
    } finally {
      wordLoading.value = false
    }
  } else {
    excelLoading.value = true
    store.clearWorkingData()
    try {
      await store.openExcel(file.id)
      editorPage.value = 1
    } catch {
      ElMessage.error(t('common.error'))
    } finally {
      excelLoading.value = false
    }
  }
}

async function handleCellUpdate(fileId: number, absRowIdx: number, colName: string, value: unknown) {
  try {
    await store.updateDataCell(fileId, absRowIdx, colName, value)
    await refreshExcelData(fileId)
  } catch {
    ElMessage.error(t('common.error'))
  }
}

async function handleRowAdd(fileId: number, rowData: Record<string, string>) {
  try {
    await store.addDataRow(fileId, rowData)
    await refreshExcelData(fileId)
    ElMessage.success(t('editor.addRowSuccess'))
  } catch {
    ElMessage.error(t('common.error'))
  }
}

async function handleRowDelete(fileId: number, absRowIdx: number) {
  try {
    await store.deleteDataRowAction(fileId, absRowIdx)
    await refreshExcelData(fileId)
    ElMessage.success(t('editor.deleteSuccess'))
  } catch {
    ElMessage.error(t('common.error'))
  }
}

async function handleSave(fileId: number) {
  try {
    await store.saveChanges(fileId)
    ElMessage.success(t('editor.saveSuccess'))
  } catch {
    ElMessage.error(t('common.error'))
  }
}

async function handleReset(fileId: number) {
  try {
    await store.resetChanges(fileId)
    editorPage.value = 1
    ElMessage.success(t('editor.resetSuccess'))
  } catch {
    ElMessage.error(t('common.error'))
  }
}

async function refreshExcelData(fileId: number) {
  excelLoading.value = true
  try {
    await store.fetchWorkingData(fileId, editorPage.value, pageSize)
  } finally {
    excelLoading.value = false
  }
}

async function onEditorPageChange(page: number) {
  editorPage.value = page
  const file = currentFile.value
  if (file) {
    await refreshExcelData(file.id)
  }
}
</script>

<template>
  <div>
    <h2 style="margin-bottom: 20px">{{ $t('preview.title') }}</h2>

    <!-- Selectors -->
    <CourseSelectors v-model="selection" />

    <!-- Validation gate warning -->
    <el-alert
      v-if="selection.courseId && selection.classId && selection.semesterName && validationStatus !== 'passed'"
      type="warning"
      show-icon
      :closable="false"
      style="margin-bottom: 20px"
    >
      <template #title>
        <span style="font-weight: 700">{{ $t('preview.notValidated') }}</span>
      </template>
    </el-alert>

    <!-- File type selection bar -->
    <div
      v-if="selection.courseId && selection.classId && selection.semesterName"
      style="margin-bottom: 20px"
    >
      <el-card v-if="store.courseFiles.length === 0 && !loading">
        <el-result icon="warning" :title="$t('preview.noFiles')" />
      </el-card>

      <div v-if="store.courseFiles.length > 0" style="display: flex; gap: 12px; align-items: center">
        <el-button
          v-for="type in (['syllabus', 'student_info', 'grades'] as const)"
          :key="type"
          :type="selectedFileType === type ? 'primary' : 'default'"
          :disabled="!availableTypes.includes(type)"
          @click="selectFileType(type)"
        >
          <el-icon style="margin-right: 6px">
            <Document v-if="type === 'syllabus'" />
            <DataBoard v-else />
          </el-icon>
          {{ type === 'syllabus' ? $t('preview.fileSyllabus') : type === 'student_info' ? $t('preview.fileStudentInfo') : $t('preview.fileGrades') }}
          <el-tag
            v-if="availableTypes.includes(type)"
            size="small"
            :type="selectedFileType === type ? '' : 'info'"
            style="margin-left: 8px"
            effect="plain"
          >
            {{ $t('excel.upload.uploaded') }}
          </el-tag>
        </el-button>
        <router-link
          v-if="availableTypes.length === 3"
          to="/report/generate"
          style="margin-left: auto"
        >
          <el-button type="success">
            <el-icon style="margin-right: 6px"><Edit /></el-icon>
            {{ $t('preview.generateReport') }}
          </el-button>
        </router-link>
      </div>
    </div>

    <el-result
      v-if="!selection.courseId || !selection.classId || !selection.semesterName"
      icon="info"
      :title="$t('excel.upload.selectFirst')"
    />

    <!-- Word Document Viewer -->
    <WordDocViewer
      v-if="selectedFileType === 'syllabus' && currentFile"
      :content="store.wordContent"
      :loading="wordLoading"
    />

    <!-- Excel Data Editor -->
    <ExcelDataEditor
      v-if="selectedFileType && selectedFileType !== 'syllabus' && currentFile"
      :key="currentFile.id"
      :data="store.workingData"
      :file-id="currentFile.id"
      :loading="excelLoading"
      :has-unsaved-changes="store.hasUnsavedChanges"
      :page="editorPage"
      :page-size="pageSize"
      @cell-update="handleCellUpdate"
      @row-add="handleRowAdd"
      @row-delete="handleRowDelete"
      @save="handleSave"
      @reset="handleReset"
      @refresh="() => refreshExcelData(currentFile!.id)"
      @page-change="onEditorPageChange"
    />
  </div>
</template>
