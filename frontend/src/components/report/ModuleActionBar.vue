<script setup lang="ts">
import { Edit } from '@element-plus/icons-vue'

defineProps<{
  loading: boolean
  regenerateDisabled?: boolean
  saveDisabled?: boolean
  confirmDisabled?: boolean
}>()

const emit = defineEmits<{
  regenerate: []
  save: []
  confirm: []
  export: []
}>()
</script>

<template>
  <div style="margin-top: 12px; display: flex; gap: 8px">
    <el-button :loading="loading" :disabled="regenerateDisabled" @click="emit('regenerate')">
      <el-icon><Edit /></el-icon> 重新生成
    </el-button>
    <el-button type="primary" :loading="loading" :disabled="saveDisabled" @click="emit('save')">保存草稿</el-button>
    <el-button type="success" :loading="loading" :disabled="confirmDisabled" @click="emit('confirm')">确认</el-button>
    <el-button :loading="loading" @click="emit('export')">导出Word</el-button>
  </div>
</template>
