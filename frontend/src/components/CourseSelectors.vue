<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useExcelStore } from '@/store/excel'
import { ElMessage } from 'element-plus'
import type { SimpleItem } from '@/api/excel'

export interface SelectionModel {
  courseId: number | null
  classId: number | null
  semesterName: string | null
}

const props = defineProps<{
  modelValue: SelectionModel
  cascade?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: SelectionModel]
}>()

const store = useExcelStore()

const courseOptions = ref<{ id: number; name: string }[]>([])
const classOptions = ref<{ id: number; name: string }[]>([])

function generateSemesterOptions() {
  const options: { value: string; label: string }[] = []
  for (let y = 2025; y < 2025 + 10; y++) {
    options.push({ value: `${y}-${y + 1}年第一学期`, label: `${y}-${y + 1}年第一学期` })
    options.push({ value: `${y}-${y + 1}年第二学期`, label: `${y}-${y + 1}年第二学期` })
  }
  return options
}

const generatedSemesters = generateSemesterOptions()

function mergeSemesters(dbItems: SimpleItem[]) {
  const map = new Map<string, { value: string; label: string }>()
  for (const s of generatedSemesters) {
    map.set(s.value, s)
  }
  for (const s of dbItems) {
    if (!map.has(s.name)) {
      map.set(s.name, { value: s.name, label: s.name })
    }
  }
  return Array.from(map.values())
}

const semesterOptions = ref<{ value: string; label: string }[]>([...generatedSemesters])

const selectedCourse = ref<number | null>(props.modelValue.courseId)
const selectedClass = ref<number | null>(props.modelValue.classId)
const selectedSemester = ref<string | null>(props.modelValue.semesterName)

// Guard to prevent cascading reload loops
let reloading = false

const dialogVisible = ref(false)
const dialogTitle = ref('')
const dialogInput = ref('')
const dialogType = ref<'course' | 'class' | 'semester'>('course')
const dialogLoading = ref(false)

function emitSelection() {
  emit('update:modelValue', {
    courseId: selectedCourse.value,
    classId: selectedClass.value,
    semesterName: selectedSemester.value,
  })
}

async function loadAllOptions() {
  await Promise.all([
    store.fetchCourses(),
    store.fetchClasses(),
    store.fetchSemesters(),
  ])
  courseOptions.value = store.courses
  classOptions.value = store.classes
  semesterOptions.value = mergeSemesters(store.semesters)
}

async function reloadFiltered(by: 'course' | 'class' | 'semester') {
  reloading = true
  const cid = selectedCourse.value
  const clid = selectedClass.value
  const sname = selectedSemester.value
  let needEmit = false

  if (by !== 'course') {
    const courses = await store.fetchCourses({
      class_id: clid ?? undefined,
      semester_name: sname ?? undefined,
    })
    courseOptions.value = courses
    if (selectedCourse.value && !courses.find((c) => c.id === selectedCourse.value)) {
      selectedCourse.value = null
      needEmit = true
    }
  }

  if (by !== 'class') {
    const classes = await store.fetchClasses({
      course_id: cid ?? undefined,
      semester_name: sname ?? undefined,
    })
    classOptions.value = classes
    if (selectedClass.value && !classes.find((c) => c.id === selectedClass.value)) {
      selectedClass.value = null
      needEmit = true
    }
  }

  if (by !== 'semester') {
    const semesters = await store.fetchSemesters({
      course_id: cid ?? undefined,
      class_id: clid ?? undefined,
    })
    semesterOptions.value = mergeSemesters(semesters)
    if (selectedSemester.value && !semesterOptions.value.find((s) => s.value === selectedSemester.value)) {
      selectedSemester.value = null
      needEmit = true
    }
  }

  reloading = false
  if (needEmit) emitSelection()
}

function openAddDialog(type: 'course' | 'class' | 'semester') {
  dialogType.value = type
  dialogInput.value = ''
  const labels: Record<string, string> = { course: '课程名称', class: '班级', semester: '学期' }
  dialogTitle.value = '添加新' + labels[type]
  dialogVisible.value = true
}

function handleSelectChange(type: 'course' | 'class' | 'semester', value: unknown) {
  if (value === '__add__') {
    if (type === 'course') selectedCourse.value = null
    else if (type === 'class') selectedClass.value = null
    else if (type === 'semester') selectedSemester.value = null
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
    if (dialogType.value === 'course') {
      const item = await store.addCourse(name)
      courseOptions.value = store.courses
      selectedCourse.value = item.id
    } else if (dialogType.value === 'class') {
      const item = await store.addClass(name)
      classOptions.value = store.classes
      selectedClass.value = item.id
    } else {
      const item = await store.addSemester(name)
      semesterOptions.value = mergeSemesters(store.semesters)
      selectedSemester.value = item.name
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
watch(
  () => props.modelValue,
  (v) => {
    if (v.courseId !== selectedCourse.value) selectedCourse.value = v.courseId
    if (v.classId !== selectedClass.value) selectedClass.value = v.classId
    if (v.semesterName !== selectedSemester.value) selectedSemester.value = v.semesterName
  },
  { deep: true },
)

watch(selectedCourse, () => {
  if (reloading) return
  emitSelection()
  if (props.cascade !== false) reloadFiltered('course')
})

watch(selectedClass, () => {
  if (reloading) return
  emitSelection()
  if (props.cascade !== false) reloadFiltered('class')
})

watch(selectedSemester, () => {
  if (reloading) return
  emitSelection()
  if (props.cascade !== false) reloadFiltered('semester')
})

onMounted(() => {
  loadAllOptions()
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
          @change="(v: unknown) => handleSelectChange('semester', v)"
        >
          <el-option
            v-for="s in semesterOptions"
            :key="s.value"
            :label="s.label"
            :value="s.value"
          />
          <el-option value="__add__" style="color: #409eff; font-weight: 500">
            + 添加新学期
          </el-option>
        </el-select>
      </el-col>
    </el-row>

    <!-- Add dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="400px"
      :close-on-click-modal="false"
    >
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
