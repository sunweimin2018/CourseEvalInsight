<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { Edit } from '@element-plus/icons-vue'

const props = defineProps<{
  modelValue: string | null
  status: string
  loading: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  regenerate: []
  save: []
  confirm: []
  export: []
}>()

const text = ref('')

watch(() => props.modelValue, (v) => {
  text.value = v ?? ''
}, { immediate: true })

function onInput() {
  emit('update:modelValue', text.value)
}

const readonly = computed(() => props.status === 'confirmed')
</script>

<template>
  <div v-loading.fullscreen.lock="loading" element-loading-text="生成中...">
    <el-input
      :model-value="text"
      type="textarea"
      :rows="10"
      :disabled="readonly"
      placeholder="课程目标内容..."
      @input="(v: string) => { text = v; onInput() }"
    />
    <div style="margin-top: 12px; display: flex; gap: 8px">
      <el-button :loading="loading" @click="emit('regenerate')">
        <el-icon><Edit /></el-icon> 重新生成
      </el-button>
      <el-button type="primary" :loading="loading" :disabled="status === 'confirmed'" @click="emit('save')">保存草稿</el-button>
      <el-button type="success" :loading="loading" :disabled="status === 'confirmed'" @click="emit('confirm')">确认</el-button>
      <el-button :loading="loading" @click="emit('export')">导出Word</el-button>
    </div>
  </div>
</template>
