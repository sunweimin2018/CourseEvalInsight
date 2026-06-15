<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useExcelStore } from '@/store/excel'
import { ElMessage } from 'element-plus'
import type { UploadFile, UploadRawFile } from 'element-plus'

const router = useRouter()
const store = useExcelStore()
const fileList = ref<UploadFile[]>([])
const uploading = ref(false)
const summary = ref<{ total_files: number; total_rows: number; sheets_parsed: string[] } | null>(null)

function beforeUpload(file: UploadRawFile) {
  const ext = file.name.split('.').pop()?.toLowerCase()
  if (ext !== 'xlsx' && ext !== 'xls') {
    ElMessage.error('Only .xlsx and .xls files are allowed')
    return false
  }
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.error('File size must be less than 10MB')
    return false
  }
  return true
}

async function handleUpload() {
  if (fileList.value.length === 0) {
    ElMessage.warning('Please select files first')
    return
  }
  uploading.value = true
  try {
    const formData = new FormData()
    fileList.value.forEach((f) => {
      if (f.raw) formData.append('files', f.raw)
    })
    const data = await store.upload(formData)
    summary.value = data
    ElMessage.success('Upload successful')
  } catch {
    // error handled by interceptor
  } finally {
    uploading.value = false
  }
}

function goPreview() {
  router.push('/excel/preview')
}
</script>

<template>
  <div>
    <h2 style="margin-bottom: 20px">Excel Upload</h2>
    <el-card>
      <el-upload
        v-model:file-list="fileList"
        drag
        multiple
        :limit="10"
        :auto-upload="false"
        :before-upload="beforeUpload"
        accept=".xlsx,.xls"
      >
        <el-icon style="font-size: 48px; color: #c0c4cc"><UploadFilled /></el-icon>
        <div style="margin-top: 10px; color: #606266">
          Drag files here or <em>click to upload</em>
        </div>
        <template #tip>
          <div style="margin-top: 8px; color: #909399; font-size: 13px">
            Supports .xlsx / .xls, max 10 files, each up to 10MB
          </div>
        </template>
      </el-upload>
      <div style="margin-top: 20px">
        <el-button type="primary" :loading="uploading" @click="handleUpload">
          Upload & Parse
        </el-button>
      </div>
    </el-card>

    <el-card v-if="summary" style="margin-top: 20px">
      <template #header>Upload Summary</template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="Files">{{ summary.total_files }}</el-descriptions-item>
        <el-descriptions-item label="Total Rows">{{ summary.total_rows }}</el-descriptions-item>
        <el-descriptions-item label="Sheets">{{ summary.sheets_parsed.join(', ') }}</el-descriptions-item>
      </el-descriptions>
      <div style="margin-top: 16px">
        <el-button type="success" @click="goPreview">View Data</el-button>
      </div>
    </el-card>
  </div>
</template>
