<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import ModuleActionBar from './ModuleActionBar.vue'

const props = defineProps<{
  modelValue: Record<string, unknown> | null
  status: string
  loading: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, unknown>]
  regenerate: []
  save: []
  confirm: []
  export: []
}>()

const fields = [
  { key: 'course_name', label: '课程名称' },
  { key: 'course_code', label: '课程编号' },
  { key: 'course_seq', label: '课序号' },
  { key: 'teaching_class', label: '授课班级' },
  { key: 'student_count', label: '修课人数' },
  { key: 'total_hours', label: '学时数' },
  { key: 'credits', label: '学分' },
  { key: 'textbook', label: '选用教材' },
  { key: 'department', label: '开课院系' },
  { key: 'teacher', label: '授课教师' },
  { key: 'course_nature', label: '课程性质' },
  { key: 'course_type', label: '课程类型' },
]

const form = ref<Record<string, string>>({})

watch(() => props.modelValue, (v) => {
  if (v) {
    const m: Record<string, string> = {}
    for (const f of fields) {
      m[f.key] = String(v[f.key] ?? '')
    }
    form.value = m
  }
}, { immediate: true })

function isUnfilled(key: string): boolean {
  return form.value[key] === '未填写'
}

function onInput() {
  emit('update:modelValue', { ...form.value })
}

const readonly = computed(() => props.status === 'confirmed')
</script>

<template>
  <div v-loading.fullscreen.lock="loading" element-loading-text="生成中...">
    <el-form :model="form" label-width="100px" :disabled="readonly">
      <el-row :gutter="16">
        <el-col v-for="f in fields" :key="f.key" :span="12">
          <el-form-item :label="f.label">
            <el-input
              :model-value="form[f.key]"
              :class="{ 'unfilled-input': isUnfilled(f.key) }"
              @input="(v: string) => { form[f.key] = v; onInput() }"
            />
          </el-form-item>
        </el-col>
      </el-row>
    </el-form>
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

<style scoped>
.unfilled-input :deep(.el-input__inner) {
  color: #e6a23c;
  font-weight: 700;
  border-color: #e6a23c;
}
</style>
