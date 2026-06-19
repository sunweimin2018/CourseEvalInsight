<script setup lang="ts">
const props = defineProps<{
  modelValue: string | null
  status: string
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'regenerate'): void
  (e: 'save'): void
  (e: 'confirm'): void
  (e: 'export'): void
}>()

function onInput(val: string) {
  emit('update:modelValue', val)
}
</script>

<template>
  <div v-loading="loading">
    <el-alert
      v-if="modelValue === null"
      title="尚未生成数据，请点击"生成模块"按钮"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 16px"
    />

    <el-alert
      v-if="modelValue !== null"
      title="请根据实际情况编辑以下改进方案模板，完成后确认"
      type="warning"
      show-icon
      :closable="false"
      style="margin-bottom: 16px"
    />

    <el-input
      v-if="modelValue !== null"
      type="textarea"
      :model-value="modelValue"
      @update:model-value="onInput"
      :rows="18"
      placeholder="请输入课程持续改进方案及措施..."
      style="font-size: 14px; line-height: 1.8"
    />

    <div style="margin-top: 20px; display: flex; gap: 8px">
      <el-button type="primary" :loading="loading" @click="emit('regenerate')">
        {{ modelValue !== null ? '重新生成' : '生成模块' }}
      </el-button>
      <el-button v-if="modelValue !== null" @click="emit('save')">保存草稿</el-button>
      <el-button v-if="modelValue !== null" type="success" @click="emit('confirm')">
        确认并导出Word
      </el-button>
      <el-tag v-if="status === 'confirmed'" type="success" size="large" style="margin-left: auto">
        已确认
      </el-tag>
      <el-tag v-else-if="status === 'draft'" type="info" size="large" style="margin-left: auto">
        草稿
      </el-tag>
    </div>
  </div>
</template>
