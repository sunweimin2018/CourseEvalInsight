<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import ModuleActionBar from './ModuleActionBar.vue'

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
    <ModuleActionBar
      :loading="loading"
      :regenerate-disabled="readonly"
      :save-disabled="readonly"
      :confirm-disabled="readonly"
      @regenerate="emit('regenerate')"
      @save="emit('save')"
      @confirm="emit('confirm')"
      @export="emit('export')"
    />
  </div>
</template>
