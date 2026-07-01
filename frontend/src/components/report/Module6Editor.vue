<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import ModuleActionBar from './ModuleActionBar.vue'
import type { Module6Data } from '@/api/report'

const props = defineProps<{
  modelValue: Module6Data | string | null
  status: string
  loading: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: Module6Data]
  regenerate: []
  save: []
  confirm: []
  export: []
}>()

const data = ref<Module6Data>({
  part1: '',
  part2: { problems: '', measures: '', expected_effects: '' },
  part3: '',
})

watch(() => props.modelValue, (v) => {
  if (v && typeof v === 'object' && 'part1' in v) {
    data.value = JSON.parse(JSON.stringify(v))
  } else if (typeof v === 'string' && v) {
    // Legacy string — place in part2 problems for migration
    data.value = {
      part1: '',
      part2: { problems: v, measures: '', expected_effects: '' },
      part3: '',
    }
  }
}, { immediate: true })

const readonly = computed(() => props.status === 'confirmed')

function emitUpdate() {
  emit('update:modelValue', JSON.parse(JSON.stringify(data.value)))
}
</script>

<template>
  <div v-loading.fullscreen.lock="loading" element-loading-text="生成中...">
    <!-- 6.1 -->
    <h3 style="margin-top: 0">6.1 连续两年课程评价结果系统地纳入课程持续改进的措施及其效果描述</h3>
    <el-input
      :model-value="data.part1"
      type="textarea"
      :rows="5"
      :disabled="readonly"
      placeholder="约200-300字..."
      @input="(v: string) => { data.part1 = v; emitUpdate() }"
    />

    <!-- 6.2 -->
    <h3 style="margin-top: 24px">6.2 本年度课程教学环节发现的问题、相应持续改进的措施以及描述预期将可能达到的效果</h3>

    <h4>(1) 存在的问题</h4>
    <el-input
      :model-value="data.part2.problems"
      type="textarea"
      :rows="6"
      :disabled="readonly"
      placeholder="分析当前教学中存在的3-5个具体问题..."
      @input="(v: string) => { data.part2.problems = v; emitUpdate() }"
    />

    <h4>(2) 持续改进措施</h4>
    <el-input
      :model-value="data.part2.measures"
      type="textarea"
      :rows="6"
      :disabled="readonly"
      placeholder="针对问题逐条提出改进措施..."
      @input="(v: string) => { data.part2.measures = v; emitUpdate() }"
    />

    <h4>(3) 预期效果</h4>
    <el-input
      :model-value="data.part2.expected_effects"
      type="textarea"
      :rows="5"
      :disabled="readonly"
      placeholder="描述预期可能达到的效果..."
      @input="(v: string) => { data.part2.expected_effects = v; emitUpdate() }"
    />

    <!-- 6.3 -->
    <h3 style="margin-top: 24px">6.3 其他可用的协助持续改进的资源</h3>
    <el-input
      :model-value="data.part3"
      type="textarea"
      :rows="3"
      :disabled="readonly"
      placeholder="约80-150字..."
      @input="(v: string) => { data.part3 = v; emitUpdate() }"
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
