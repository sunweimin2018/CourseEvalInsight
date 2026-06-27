<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Check, Refresh, Download, Document,
} from '@element-plus/icons-vue'
import CourseSelectors from '@/components/CourseSelectors.vue'
import type { SelectionModel } from '@/components/CourseSelectors.vue'
import { useExcelStore } from '@/store/excel'
import {
  generateReport, getReportPreview, getReports,
  generateModule, updateModule, exportModuleDocx, mergeReport,
  generateAchievementExcel, downloadAchievementExcel,
} from '@/api/report'
import type { ReportRecord, ReportData } from '@/api/report'
import Module1Editor from '@/components/report/Module1Editor.vue'
import Module2Editor from '@/components/report/Module2Editor.vue'
import Module3Editor from '@/components/report/Module3Editor.vue'
import Module4Editor from '@/components/report/Module4Editor.vue'
import Module5Editor from '@/components/report/Module5Editor.vue'
import Module6Editor from '@/components/report/Module6Editor.vue'

const store = useExcelStore()

// ── Selection ──────────────────────────────────────────────────────────────
const selection = ref<SelectionModel>({ courseId: null, classId: null, semesterName: null })
const availableTypes = ref<string[]>([])

// ── Report state ────────────────────────────────────────────────────────────
const reportId = ref<number | null>(null)
const reportName = ref('')
const reportData = ref<ReportData | null>(null)
const moduleStatuses = ref<Record<number, string>>({
  1: 'pending', 2: 'pending', 3: 'pending', 4: 'pending', 5: 'pending', 6: 'pending',
})

// ── UI state ────────────────────────────────────────────────────────────────
const activeStep = ref(1)
const loading = ref(false)
const actionLoading = ref(false)

const steps = [
  { num: 1, title: '课程基本信息表', icon: '1' },
  { num: 2, title: '课程目标', icon: '2' },
  { num: 3, title: '课程评价标准', icon: '3' },
  { num: 4, title: '课程评价结果', icon: '4' },
  { num: 5, title: '课程目标达成度', icon: '5' },
  { num: 6, title: '持续改进方案', icon: '6' },
  { num: 7, title: '合并导出', icon: '✓' },
]

const fileStatusText: Record<string, string> = {
  syllabus: '课程大纲',
  student_info: '学生基本信息表',
  grades: '学生成绩表',
}

// ── Watch selection ─────────────────────────────────────────────────────────
watch(selection, async (s) => {
  reportId.value = null
  reportData.value = null
  moduleStatuses.value = { 1: 'pending', 2: 'pending', 3: 'pending', 4: 'pending', 5: 'pending', 6: 'pending' }

  if (s.courseId && s.classId && s.semesterName) {
    await store.fetchCourseFiles(s.courseId, s.classId, s.semesterName)
    availableTypes.value = store.courseFiles.map((f) => f.file_type)
    try {
      const reports = await getReports(s.courseId, s.classId, s.semesterName) as unknown as ReportRecord[]
      if (reports.length > 0) {
        const r = reports[0]
        reportId.value = r.id
        reportName.value = r.report_name
        const m = r as Record<string, unknown>
        for (let i = 1; i <= 6; i++) {
          moduleStatuses.value[i] = (m[`module_${i}_status`] as string) || 'pending'
        }
        // Load full report data so module editors display immediately
        try {
          const preview = await getReportPreview(r.id) as unknown as { report_data: ReportData }
          reportData.value = preview.report_data
        } catch { /* data load failed, user can regenerate */ }
      } else {
        // Auto-generate a new report when no existing one is found
        await ensureReport(true)
      }
    } catch {
      // no existing report — auto-generate silently
      try { await ensureReport(true) } catch { /* generation failed */ }
    }
  } else {
    store.courseFiles = []
    availableTypes.value = []
  }
}, { deep: true })

// ── Report data helpers ─────────────────────────────────────────────────────
const moduleKeys = ['', 'module_1_course_info', 'module_2_objectives', 'module_3_evaluation_standards', 'module_4_evaluation_results', 'module_5_objective_achievement', 'module_6_improvement_plan'] as const

function getModuleData(num: number) {
  if (!reportData.value) return null
  return (reportData.value as Record<string, unknown>)[moduleKeys[num]] ?? null
}

function setModuleData(num: number, data: unknown) {
  if (!reportData.value) return
  ;(reportData.value as Record<string, unknown>)[moduleKeys[num]] = data
}

const allConfirmed = computed(() => {
  for (let i = 1; i <= 6; i++) {
    if (moduleStatuses.value[i] !== 'confirmed') return false
  }
  return true
})

const confirmedCount = computed(() => {
  let count = 0
  for (let i = 1; i <= 6; i++) {
    if (moduleStatuses.value[i] === 'confirmed') count++
  }
  return count
})

function stepStatus(num: number): 'wait' | 'process' | 'finish' | 'error' {
  const s = moduleStatuses.value[num]
  if (s === 'confirmed') return 'finish'
  if (s === 'draft') return 'process'
  return 'wait'
}

// ── Actions ─────────────────────────────────────────────────────────────────

async function ensureReport(silent = false) {
  if (reportId.value) return true

  const s = selection.value
  if (!s.courseId || !s.classId || !s.semesterName) {
    if (!silent) ElMessage.warning('请先选择课程、班级和学期')
    return false
  }

  loading.value = true
  try {
    const generated = await generateReport(s.courseId, s.classId, s.semesterName) as unknown as ReportRecord
    reportId.value = generated.id
    reportName.value = generated.report_name
    const m = generated as Record<string, unknown>
    for (let i = 1; i <= 6; i++) {
      moduleStatuses.value[i] = (m[`module_${i}_status`] as string) || 'draft'
    }
    // Load the full preview
    const preview = await getReportPreview(generated.id) as unknown as { report_data: ReportData }
    reportData.value = preview.report_data
    for (let i = 1; i <= 6; i++) {
      if (moduleStatuses.value[i] === 'pending') {
        moduleStatuses.value[i] = 'draft'
      }
    }
    if (!silent) ElMessage.success('报告初始化成功')
    return true
  } catch {
    if (!silent) ElMessage.error('报告初始化失败')
    return false
  } finally {
    loading.value = false
  }
}

async function fetchReportData(): Promise<boolean> {
  if (!reportId.value) return false
  try {
    const preview = await getReportPreview(reportId.value) as unknown as { report_data: ReportData }
    reportData.value = preview.report_data
    const p = preview as unknown as Record<string, unknown>
    for (let i = 1; i <= 6; i++) {
      moduleStatuses.value[i] = (p[`module_${i}_status`] as string) || 'pending'
    }
    return true
  } catch {
    return false
  }
}

async function loadReport() {
  if (!reportId.value) return
  loading.value = true
  try {
    const ok = await fetchReportData()
    if (!ok) ElMessage.error('加载报告失败')
  } finally {
    loading.value = false
  }
}

async function handleRegenerate(num: number) {
  const ok = await ensureReport()
  if (!ok || !reportId.value) return

  if (!reportData.value && !(await fetchReportData())) {
    ElMessage.error('加载报告数据失败')
    return
  }

  actionLoading.value = true
  try {
    const result = await generateModule(reportId.value, num) as { module_data: unknown; module_status: string }
    setModuleData(num, result.module_data)
    moduleStatuses.value[num] = result.module_status
    ElMessage.success(`模块${num} 生成成功`)
  } catch {
    ElMessage.error(`模块${num} 生成失败`)
  } finally {
    actionLoading.value = false
  }
}

async function handleSave(num: number) {
  if (!reportId.value) return
  if (!reportData.value && !(await fetchReportData())) {
    ElMessage.error('加载报告数据失败')
    return
  }
  const data = getModuleData(num)
  actionLoading.value = true
  try {
    const result = await updateModule(reportId.value, num, data, false) as { module_status: string }
    moduleStatuses.value[num] = result.module_status
    ElMessage.success('草稿已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    actionLoading.value = false
  }
}

async function handleConfirm(num: number) {
  if (!reportId.value) return
  if (!reportData.value && !(await fetchReportData())) {
    ElMessage.error('加载报告数据失败')
    return
  }
  const data = getModuleData(num)
  actionLoading.value = true
  try {
    const result = await updateModule(reportId.value, num, data, true) as { module_status: string }
    moduleStatuses.value[num] = result.module_status
    ElMessage.success(`模块${num} 已确认`)

    // Auto-export after confirm
    try {
      await exportModuleDocx(reportId.value, num, `${reportName.value}_模块${num}`)
      ElMessage.success(`模块${num} Word已导出`)
    } catch {
      ElMessage.warning('Word导出失败，请稍后手动导出')
    }
  } catch {
    ElMessage.error('确认失败')
  } finally {
    actionLoading.value = false
  }
}

async function handleExportModule(num: number) {
  if (!reportId.value) return
  try {
    await exportModuleDocx(reportId.value, num, `${reportName.value}_模块${num}`)
    ElMessage.success(`模块${num} Word已导出`)
  } catch {
    ElMessage.error('导出失败')
  }
}

// ── Module 5 Excel ──────────────────────────────────────────────────────────

async function handleGenerateExcel() {
  if (!reportId.value) {
    const ok = await ensureReport()
    if (!ok) return
  }
  actionLoading.value = true
  try {
    const result = await generateAchievementExcel(reportId.value!) as { success: boolean; filename: string }
    if (result.success) {
      ElMessage.success('课程达成度计算Excel已生成')
      // Refresh report data to get updated excel_generated flag
      await fetchReportData()
    }
  } catch {
    ElMessage.error('Excel生成失败')
  } finally {
    actionLoading.value = false
  }
}

async function handleDownloadExcel() {
  if (!reportId.value) return
  const moduleData = getModuleData(5) as Record<string, unknown> | null
  const filename = (moduleData as any)?.excel_filename || '课程达成度计算.xlsx'
  try {
    await downloadAchievementExcel(reportId.value, filename as string)
    ElMessage.success('Excel下载成功')
  } catch {
    ElMessage.error('Excel下载失败')
  }
}

function handleStepClick(num: number) {
  if (num === 7 && !allConfirmed.value) {
    const unconfirmed: number[] = []
    for (let i = 1; i <= 6; i++) {
      if (moduleStatuses.value[i] !== 'confirmed') unconfirmed.push(i)
    }
    const names = unconfirmed.map(n => `"${steps[n - 1].title}"`).join('、')
    ElMessage.warning(`以下模块尚未确认，请确认${names}模块`)
    activeStep.value = unconfirmed[0] || 1
    return
  }
  activeStep.value = num
  if (num <= 6 && !reportData.value && reportId.value) {
    loadReport()
  }
}

async function handleMerge(format: 'docx' | 'pdf') {
  if (!reportId.value) return
  if (!allConfirmed.value) {
    ElMessage.warning('以下模块尚未确认，请先确认所有模块')
    return
  }
  try {
    await mergeReport(reportId.value, reportName.value, format)
    ElMessage.success(`合并${format === 'pdf' ? 'PDF' : 'Word'}导出成功`)
  } catch (err: unknown) {
    const message = (err as { message?: string }).message || '合并导出失败'
    ElMessage.error(message)
  }
}

// ── Module data update (from editors) ───────────────────────────────────────
function onModuleDataUpdate(num: number, data: unknown) {
  setModuleData(num, data)
  // Auto-mark as draft when user edits
  if (moduleStatuses.value[num] === 'confirmed') {
    moduleStatuses.value[num] = 'draft'
  }
}
</script>

<template>
  <div>
    <h2 style="margin-bottom: 20px">报告构建</h2>

    <!-- Course / File status -->
    <CourseSelectors v-model="selection" />

    <el-card
      v-if="selection.courseId && selection.classId && selection.semesterName"
      style="margin-bottom: 20px"
    >
      <template #header>文件状态</template>
      <el-row :gutter="16">
        <el-col v-for="(label, type) in fileStatusText" :key="type" :span="8">
          <el-card shadow="never">
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>{{ label }}</span>
              <el-tag v-if="availableTypes.includes(type)" type="success" size="small">已上传</el-tag>
              <el-tag v-else type="danger" size="small">未上传</el-tag>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>

    <el-empty v-if="!selection.courseId || !selection.classId || !selection.semesterName" description="请先选择课程、班级和学期" />

    <!-- Main builder area -->
    <div v-if="selection.courseId && selection.classId && selection.semesterName" style="display: flex; gap: 20px">
      <!-- Left: Steps -->
      <div style="width: 220px; flex-shrink: 0">
        <el-card>
          <template #header>
            <span style="font-weight: 700">报告步骤</span>
          </template>
          <el-steps direction="vertical" :active="activeStep - 1" finish-status="success">
            <el-step
              v-for="step in steps"
              :key="step.num"
              :status="step.num === 7 ? (allConfirmed ? 'finish' : 'wait') : stepStatus(step.num)"
              @click="handleStepClick(step.num)"
              style="cursor: pointer"
            >
              <template #title>
                <span :style="{
                  fontWeight: activeStep === step.num ? 'bold' : 'normal',
                  color: activeStep === step.num ? '#409eff' : '#303133'
                }">
                  {{ step.title }}
                </span>
              </template>
              <template #description>
                <span v-if="step.num <= 6" style="font-size: 12px">
                  <el-tag
                    v-if="moduleStatuses[step.num] === 'confirmed'"
                    type="success"
                    size="small"
                  >已确认</el-tag>
                  <el-tag
                    v-else-if="moduleStatuses[step.num] === 'draft'"
                    type="info"
                    size="small"
                  >草稿</el-tag>
                  <el-tag
                    v-else
                    type="warning"
                    size="small"
                  >待生成</el-tag>
                </span>
                <span v-else style="font-size: 12px">
                  <el-tag
                    v-if="allConfirmed"
                    type="success"
                    size="small"
                  >可以导出</el-tag>
                  <el-tag
                    v-else
                    type="info"
                    size="small"
                  >{{ confirmedCount }}/6 已确认</el-tag>
                </span>
              </template>
            </el-step>
          </el-steps>
        </el-card>
      </div>

      <!-- Right: Editor area -->
      <div style="flex: 1; min-width: 0">
        <!-- Step 1: Module 1 Editor -->
        <el-card v-if="activeStep === 1">
          <template #header>
            <span style="font-weight: 700">一、课程基本信息表</span>
          </template>
          <Module1Editor
            :model-value="getModuleData(1) as any"
            :status="moduleStatuses[1]"
            :loading="actionLoading"
            @update:model-value="(d: any) => onModuleDataUpdate(1, d)"
            @regenerate="handleRegenerate(1)"
            @save="handleSave(1)"
            @confirm="handleConfirm(1)"
            @export="handleExportModule(1)"
          />
        </el-card>

        <!-- Step 2: Module 2 Editor -->
        <el-card v-if="activeStep === 2">
          <template #header>
            <span style="font-weight: 700">二、课程目标</span>
          </template>
          <Module2Editor
            :model-value="getModuleData(2) as string | null"
            :status="moduleStatuses[2]"
            :loading="actionLoading"
            @update:model-value="(d: string) => onModuleDataUpdate(2, d)"
            @regenerate="handleRegenerate(2)"
            @save="handleSave(2)"
            @confirm="handleConfirm(2)"
            @export="handleExportModule(2)"
          />
        </el-card>

        <!-- Step 3: Module 3 Editor -->
        <el-card v-if="activeStep === 3">
          <template #header>
            <span style="font-weight: 700">三、课程评价标准</span>
          </template>
          <Module3Editor
            :model-value="getModuleData(3) as any"
            :status="moduleStatuses[3]"
            :loading="actionLoading"
            @update:model-value="(d: any) => onModuleDataUpdate(3, d)"
            @regenerate="handleRegenerate(3)"
            @save="handleSave(3)"
            @confirm="handleConfirm(3)"
            @export="handleExportModule(3)"
          />
        </el-card>

        <!-- Step 4: Module 4 Editor -->
        <el-card v-if="activeStep === 4">
          <template #header>
            <span style="font-weight: 700">四、课程评价结果</span>
          </template>
          <Module4Editor
            :model-value="getModuleData(4) as any"
            :status="moduleStatuses[4]"
            :loading="actionLoading"
            @update:model-value="(d: any) => onModuleDataUpdate(4, d)"
            @regenerate="handleRegenerate(4)"
            @save="handleSave(4)"
            @confirm="handleConfirm(4)"
            @export="handleExportModule(4)"
          />
        </el-card>

        <!-- Step 5: Module 5 Editor (课程目标达成度) -->
        <el-card v-if="activeStep === 5">
          <template #header>
            <span style="font-weight: 700">五、课程目标达成度</span>
          </template>
          <Module5Editor
            :model-value="getModuleData(5) as any"
            :status="moduleStatuses[5]"
            :loading="actionLoading"
            @update:model-value="(d: any) => onModuleDataUpdate(5, d)"
            @regenerate="handleRegenerate(5)"
            @save="handleSave(5)"
            @confirm="handleConfirm(5)"
            @export="handleExportModule(5)"
            @generate-excel="handleGenerateExcel"
            @download-excel="handleDownloadExcel"
          />
        </el-card>

        <!-- Step 6: Module 6 Editor (持续改进方案) -->
        <el-card v-if="activeStep === 6">
          <template #header>
            <span style="font-weight: 700">六、课程持续改进方案及措施</span>
          </template>
          <Module6Editor
            :model-value="getModuleData(6) as any"
            :status="moduleStatuses[6]"
            :loading="actionLoading"
            @update:model-value="(d: any) => onModuleDataUpdate(6, d)"
            @regenerate="handleRegenerate(6)"
            @save="handleSave(6)"
            @confirm="handleConfirm(6)"
            @export="handleExportModule(6)"
          />
        </el-card>

        <!-- Step 7: Merge Export -->
        <el-card v-if="activeStep === 7">
          <template #header>
            <span style="font-weight: 700">合并导出完整报告</span>
          </template>

          <el-alert
            v-if="!allConfirmed"
            :title="`还有 ${6 - confirmedCount} 个模块未确认`"
            type="warning"
            show-icon
            :closable="false"
            style="margin-bottom: 20px"
          >
            <template #default>
              <div v-for="i in 6" :key="i">
                <el-tag v-if="moduleStatuses[i] !== 'confirmed'" type="danger" size="small" style="margin-right: 8px">
                  模块{{ i }}: {{ moduleStatuses[i] === 'draft' ? '草稿' : '待生成' }}
                </el-tag>
              </div>
            </template>
          </el-alert>

          <el-result
            v-if="allConfirmed"
            icon="success"
            title="所有模块已确认"
            sub-title="可以导出完整的 Word 或 PDF 报告"
          >
            <template #extra>
              <el-button type="primary" size="large" @click="handleMerge('docx')">
                <el-icon style="margin-right: 6px"><Document /></el-icon>
                导出完整 Word 报告
              </el-button>
              <el-button type="danger" size="large" @click="handleMerge('pdf')">
                <el-icon style="margin-right: 6px"><Download /></el-icon>
                导出完整 PDF 报告
              </el-button>
            </template>
          </el-result>

          <div v-if="!allConfirmed" style="text-align: center; padding: 40px">
            <el-empty description="请先确认所有6个模块后再进行合并导出" />
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>
