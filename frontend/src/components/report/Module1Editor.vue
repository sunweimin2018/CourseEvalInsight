<script setup lang="ts">
import { computed } from 'vue'

interface Module1Data {
  course_name: string
  course_code: string
  teaching_class: string
  student_count: string | number
  course_seq: string
  total_hours: string
  credits: string
  textbook: string
  department: string
  teacher: string
  course_nature: string
  course_type: string
  male_count?: number
  female_count?: number
  class_distribution?: string[]
}

const props = defineProps<{
  modelValue: Module1Data | null
  status: string
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: Module1Data): void
  (e: 'regenerate'): void
  (e: 'save'): void
  (e: 'confirm'): void
  (e: 'export'): void
}>()

const fields = computed(() => [
  { key: 'course_name', label: '课程名称', span: 1 },
  { key: 'student_count', label: '修课人数', span: 1 },
  { key: 'course_code', label: '课程编号', span: 1 },
  { key: 'course_seq', label: '课序号', span: 1 },
  { key: 'teaching_class', label: '授课班级', span: 1 },
  { key: 'total_hours', label: '学时数', span: 1 },
  { key: 'textbook', label: '选用教材', span: 3 },
  { key: 'credits', label: '学分', span: 1 },
  { key: 'department', label: '开课院系', span: 1 },
  { key: 'teacher', label: '授课教师', span: 1 },
  { key: 'course_nature', label: '课程性质', span: 1 },
  { key: 'course_type', label: '课程类型', span: 1 },
])

function onFieldChange(key: string, value: string) {
  if (!props.modelValue) return
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

const studentSummary = computed(() => {
  if (!props.modelValue) return ''
  const total = props.modelValue.student_count
  const male = props.modelValue.male_count ?? 0
  const female = props.modelValue.female_count ?? 0
  if (!total) return ''
  return `学生概况：共 ${total} 人 (男 ${male}，女 ${female})`
})
</script>

<template>
  <div v-loading="loading">
    <el-alert
      v-if="!modelValue"
      title="尚未生成数据，请点击"生成模块"按钮"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 16px"
    />

    <template v-if="modelValue">
      <el-form label-width="100px" label-position="left">
        <el-row :gutter="16">
          <el-col v-for="f in fields" :key="f.key" :span="f.span === 3 ? 18 : 6">
            <el-form-item :label="f.label">
              <el-input
                :model-value="String(modelValue[f.key as keyof Module1Data] ?? '')"
                @update:model-value="(v: string) => onFieldChange(f.key, v)"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <div v-if="studentSummary" style="margin-top: 12px; padding: 12px; background: #f5f7fa; border-radius: 4px; font-size: 14px; color: #606266">
        {{ studentSummary }}
      </div>
    </template>

    <div style="margin-top: 20px; display: flex; gap: 8px">
      <el-button type="primary" :loading="loading" @click="emit('regenerate')">
        {{ modelValue ? '重新生成' : '生成模块' }}
      </el-button>
      <el-button v-if="modelValue" @click="emit('save')">保存草稿</el-button>
      <el-button v-if="modelValue" type="success" @click="emit('confirm')">
        <el-icon style="margin-right: 4px"><component is="Check" /></el-icon>
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
