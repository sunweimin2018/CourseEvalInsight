<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useExcelStore } from '@/store/excel'
import { ElMessage } from 'element-plus'

export interface SelectionModel {
  courseId: number | null
  classId: number | null
  semesterName: string | null
}

const props = defineProps<{
  modelValue: SelectionModel
}>()

const emit = defineEmits<{
  'update:modelValue': [value: SelectionModel]
}>()

const store = useExcelStore()

const courseOptions = ref<{ id: number; name: string }[]>([])
const classOptions = ref<{ id: number; name: string }[]>([])

// Fixed semester list: 2020-2021 ~ 2035-2036, each year has 第一学期 and 第二学期
function generateSemesterOptions() {
  const options: { value: string; label: string }[] = []
  for (let y = 2020; y <= 2035; y++) {
    options.push({ value: `${y}-${y + 1}年第一学期`, label: `${y}-${y + 1}年第一学期` })
    options.push({ value: `${y}-${y + 1}年第二学期`, label: `${y}-${y + 1}年第二学期` })
  }
  return options
}
const semesterOptions = generateSemesterOptions()

const selectedCourse = ref<number | null>(props.modelValue.courseId)
const selectedClass = ref<number | null>(props.modelValue.classId)
const selectedSemester = ref<string | null>(props.modelValue.semesterName)

const dialogVisible = ref(false)
const dialogTitle = ref('')
const dialogInput = ref('')
const dialogType = ref<'course' | 'class'>('course')
const dialogLoading = ref(false)

function emitSelection() {
  emit('update:modelValue', {
    courseId: selectedCourse.value,
    classId: selectedClass.value,
    semesterName: selectedSemester.value,
  })
}

async function loadOptions() {
  const [courses, classes] = await Promise.all([
    store.fetchCourses(),
    store.fetchClasses(),
  ])
  courseOptions.value = courses
  classOptions.value = classes
}

function openAddDialog(type: 'course' | 'class') {
  dialogType.value = type
  dialogInput.value = ''
  const labels: Record<string, string> = { course: '课程名称', class: '班级' }
  dialogTitle.value = '添加新' + labels[type]
  dialogVisible.value = true
}

function handleSelectChange(type: 'course' | 'class', value: unknown) {
  if (value === '__add__') {
    if (type === 'course') selectedCourse.value = null
    else selectedClass.value = null
    openAddDialog(type)
  }
}

async function confirmAdd() {
  const name = dialogInput.value.trim()
  if (!name) {
    ElMessage.warning('名称不能为空')
    return
  }
  dialogLoading.value = true
  try {
    let item: { id: number; name: string } | null = null
    if (dialogType.value === 'course') {
      item = await store.addCourse(name)
      courseOptions.value = store.courses
      selectedCourse.value = item.id
    } else {
      item = await store.addClass(name)
      classOptions.value = store.classes
      selectedClass.value = item.id
    }
    dialogVisible.value = false
    ElMessage.success('添加成功')
  } catch {
    // error handled by interceptor
  } finally {
    dialogLoading.value = false
  }
}

// Sync from parent
watch(() => props.modelValue, (v) => {
  if (v.courseId !== selectedCourse.value) selectedCourse.value = v.courseId
  if (v.classId !== selectedClass.value) selectedClass.value = v.classId
  if (v.semesterName !== selectedSemester.value) selectedSemester.value = v.semesterName
}, { deep: true })

// Sync to parent
watch([selectedCourse, selectedClass, selectedSemester], () => {
  emitSelection()
})

onMounted(() => {
  loadOptions()
})
</script>

<template>
  <el-card style="margin-bottom: 20px">
    <el-row :gutter="16">
      <el-col :span="8">
        <div style="margin-bottom: 4px; font-weight: 500">课程名称</div>
        <el-select
          v-model="selectedCourse"
          placeholder="选择课程"
          style="width: 100%"
          clearable
          filterable
          @change="(v: unknown) => handleSelectChange('course', v)"
        >
          <el-option v-for="c in courseOptions" :key="c.id" :label="c.name" :value="c.id" />
          <el-option value="__add__" style="color: #409eff; font-weight: 500">
            + 添加新课程
          </el-option>
        </el-select>
      </el-col>
      <el-col :span="8">
        <div style="margin-bottom: 4px; font-weight: 500">班级</div>
        <el-select
          v-model="selectedClass"
          placeholder="选择班级"
          style="width: 100%"
          clearable
          filterable
          @change="(v: unknown) => handleSelectChange('class', v)"
        >
          <el-option v-for="c in classOptions" :key="c.id" :label="c.name" :value="c.id" />
          <el-option value="__add__" style="color: #409eff; font-weight: 500">
            + 添加新班级
          </el-option>
        </el-select>
      </el-col>
      <el-col :span="8">
        <div style="margin-bottom: 4px; font-weight: 500">学期</div>
        <el-select
          v-model="selectedSemester"
          placeholder="选择学期"
          style="width: 100%"
          clearable
          filterable
        >
          <el-option v-for="s in semesterOptions" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
      </el-col>
    </el-row>

    <!-- Add dialog -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="400px" :close-on-click-modal="false">
      <el-input
        v-model="dialogInput"
        :placeholder="'请输入' + dialogTitle.replace('添加新', '')"
        maxlength="100"
        @keyup.enter="confirmAdd"
      />
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="dialogLoading" @click="confirmAdd">确定</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>
