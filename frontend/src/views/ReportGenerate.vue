<script setup lang="ts">
import { ref, watch } from 'vue'
import { useExcelStore } from '@/store/excel'
import { ElMessage } from 'element-plus'
import { Refresh, Download, View, Edit } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, TitleComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'
import CourseSelectors from '@/components/CourseSelectors.vue'
import type { SelectionModel } from '@/components/CourseSelectors.vue'
import { generateReport, getReportPreview, downloadReport, getReports } from '@/api/report'
import type { ReportPreview, ReportData, ReportRecord } from '@/api/report'

use([BarChart, PieChart, GridComponent, TooltipComponent, TitleComponent, LegendComponent, CanvasRenderer])

interface GradeStats {
  count: number
  missing: number
  max: number
  min: number
  avg: number
  median: number
  stdev: number
  pass_rate: number
  distribution: Record<string, { label: string; count: number }>
}

interface EvalBlock {
  type: string
  text?: string
  num_cols?: number
  grid?: Array<Array<{ text: string; colspan: number; rowspan: number } | null>>
}

const store = useExcelStore()

const selection = ref<SelectionModel>({
  courseId: null, classId: null, semesterName: null,
})

const generating = ref(false)
const loadingPreview = ref(false)
const report = ref<ReportRecord | null>(null)
const reportData = ref<ReportData | null>(null)
const existingReportId = ref<number | null>(null)

const availableTypes = ref<string[]>([])

watch(selection, async (s) => {
  report.value = null
  reportData.value = null
  existingReportId.value = null
  if (s.courseId && s.classId && s.semesterName) {
    await store.fetchCourseFiles(s.courseId, s.classId, s.semesterName)
    availableTypes.value = store.courseFiles.map((f) => f.file_type)
    try {
      const reports = await getReports(s.courseId, s.classId, s.semesterName) as unknown as ReportRecord[]
      if (reports.length > 0) {
        existingReportId.value = reports[0].id
      }
    } catch {
      // no existing report
    }
  } else {
    store.courseFiles = []
    availableTypes.value = []
  }
}, { deep: true })

async function handleGenerate() {
  const s = selection.value
  if (!s.courseId || !s.classId || !s.semesterName) return

  generating.value = true
  try {
    const generated = await generateReport(s.courseId, s.classId, s.semesterName) as unknown as ReportRecord
    report.value = generated
    reportData.value = null
    existingReportId.value = generated.id
    ElMessage.success('报告生成成功')
    await loadPreview(generated.id)
  } catch {
    ElMessage.error('报告生成失败')
  } finally {
    generating.value = false
  }
}

async function loadPreview(id: number) {
  loadingPreview.value = true
  try {
    const preview = await getReportPreview(id) as unknown as ReportPreview
    report.value = preview
    reportData.value = preview.report_data
  } catch {
    ElMessage.error('加载报告预览失败')
  } finally {
    loadingPreview.value = false
  }
}

async function loadExistingReport() {
  if (!existingReportId.value) return
  await loadPreview(existingReportId.value)
}

async function handleExport(format: 'docx' | 'pdf' = 'docx') {
  if (!existingReportId.value || !report.value) return
  try {
    await downloadReport(existingReportId.value, report.value.report_name, format)
    ElMessage.success('导出成功')
  } catch (err: unknown) {
    let message = '导出失败'
    const axiosErr = err as { response?: { status: number; data: Blob }; message?: string }
    if (axiosErr.response?.data instanceof Blob && axiosErr.response.data.type.includes('json')) {
      try {
        const text = await axiosErr.response.data.text()
        const parsed = JSON.parse(text)
        message = parsed.msg || message
      } catch { /* use default message */ }
    } else if (axiosErr.message) {
      message = axiosErr.message
    }
    ElMessage.error(message)
  }
}

function isBlocksList(val: unknown): val is Array<{ type: string; [key: string]: unknown }> {
  return Array.isArray(val)
}

function distributionChartData(stats: GradeStats): EChartsOption | undefined {
  const dist = stats.distribution
  if (!dist) return undefined
  const labels = Object.values(dist).map((d) => d.label)
  const values = Object.values(dist).map((d) => d.count)
  return {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: labels, axisLabel: { rotate: 15 } },
    yAxis: { type: 'value' },
    series: [{ data: values, type: 'bar', itemStyle: { color: '#409eff' } }],
  }
}

function passRatePieData(stats: GradeStats): EChartsOption | undefined {
  const passRate = stats.pass_rate
  const count = stats.count
  if (!count) return undefined
  const passCount = Math.round(passRate / 100 * count)
  const failCount = count - passCount
  return {
    tooltip: { trigger: 'item' },
    legend: { bottom: '0%' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      data: [
        { value: passCount, name: '及格', itemStyle: { color: '#67c23a' } },
        { value: failCount, name: '不及格', itemStyle: { color: '#f56c6c' } },
      ],
    }],
  }
}

const fileStatusText: Record<string, string> = {
  syllabus: '课程大纲',
  student_info: '学生基本信息表',
  grades: '学生成绩表',
}
</script>

<template>
  <div>
    <h2 style="margin-bottom: 20px">Report Generation</h2>

    <CourseSelectors v-model="selection" />

    <!-- File status panel -->
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
      <div style="margin-top: 16px; display: flex; gap: 12px">
        <el-button
          type="primary"
          :loading="generating"
          :disabled="availableTypes.length < 3"
          @click="handleGenerate"
        >
          <el-icon style="margin-right: 6px"><Refresh /></el-icon>
          生成报告
        </el-button>
        <el-button
          v-if="existingReportId"
          type="success"
          @click="loadExistingReport"
        >
          <el-icon style="margin-right: 6px"><View /></el-icon>
          预览已有报告
        </el-button>
        <el-button
          v-if="existingReportId"
          type="warning"
          @click="handleExport('docx')"
        >
          <el-icon style="margin-right: 6px"><Download /></el-icon>
          导出Word
        </el-button>
        <el-button
          v-if="existingReportId"
          type="danger"
          @click="handleExport('pdf')"
        >
          <el-icon style="margin-right: 6px"><Download /></el-icon>
          导出PDF
        </el-button>
        <router-link v-if="availableTypes.length > 0" to="/excel/preview">
          <el-button>
            <el-icon style="margin-right: 6px"><Edit /></el-icon>
            编辑数据
          </el-button>
        </router-link>
      </div>
    </el-card>

    <el-empty v-if="!selection.courseId || !selection.classId || !selection.semesterName" description="请先选择课程、班级和学期" />

    <!-- Loading -->
    <el-card v-if="loadingPreview" style="margin-top: 20px">
      <el-skeleton :rows="10" animated />
    </el-card>

    <!-- Report Preview -->
    <div v-if="reportData && !loadingPreview">
      <!-- Module 1: Course Basic Info Table -->
      <el-card style="margin-bottom: 20px">
        <template #header>
          <span style="font-weight: 700">一、课程基本信息表</span>
        </template>
        <el-descriptions :column="4" border>
          <el-descriptions-item label="课程名称" :span="1">
            {{ reportData.module_1_course_info.course_name }}
          </el-descriptions-item>
          <el-descriptions-item label="修课人数" :span="1">
            {{ reportData.module_1_course_info.student_count }}
          </el-descriptions-item>
          <el-descriptions-item label="课程编号" :span="1">
            {{ reportData.module_1_course_info.course_code }}
          </el-descriptions-item>
          <el-descriptions-item label="课序号" :span="1">
            {{ reportData.module_1_course_info.course_seq }}
          </el-descriptions-item>
          <el-descriptions-item label="授课班级" :span="1">
            {{ reportData.module_1_course_info.teaching_class }}
          </el-descriptions-item>
          <el-descriptions-item label="学时数" :span="1">
            {{ reportData.module_1_course_info.total_hours }}
          </el-descriptions-item>
          <el-descriptions-item label="选用教材" :span="3">
            {{ reportData.module_1_course_info.textbook }}
          </el-descriptions-item>
          <el-descriptions-item label="学分" :span="1">
            {{ reportData.module_1_course_info.credits }}
          </el-descriptions-item>
          <el-descriptions-item label="开课院系" :span="1">
            {{ reportData.module_1_course_info.department }}
          </el-descriptions-item>
          <el-descriptions-item label="授课教师" :span="1">
            {{ reportData.module_1_course_info.teacher }}
          </el-descriptions-item>
          <el-descriptions-item label="课程性质" :span="1">
            {{ reportData.module_1_course_info.course_nature }}
          </el-descriptions-item>
          <el-descriptions-item label="课程类型" :span="1">
            {{ reportData.module_1_course_info.course_type }}
          </el-descriptions-item>
        </el-descriptions>
        <div v-if="reportData.module_1_course_info.male_count !== undefined" style="margin-top: 12px; color: #606266; font-size: 14px">
          学生概况：共 {{ reportData.module_1_course_info.student_count }} 人
          (男 {{ reportData.module_1_course_info.male_count }}，女 {{ reportData.module_1_course_info.female_count }})
        </div>
      </el-card>

      <!-- Module 2: Course Objectives -->
      <el-card style="margin-bottom: 20px">
        <template #header>
          <span style="font-weight: 700">二、课程目标</span>
        </template>
        <div style="white-space: pre-wrap; line-height: 1.8">{{ reportData.module_2_objectives }}</div>
      </el-card>

      <!-- Module 3: Evaluation Standards -->
      <el-card style="margin-bottom: 20px">
        <template #header>
          <span style="font-weight: 700">三、课程评价标准</span>
        </template>
        <template v-if="isBlocksList(reportData.module_3_evaluation_standards)">
          <div v-for="(block, bi) in (reportData.module_3_evaluation_standards as EvalBlock[])" :key="bi" style="margin-bottom: 12px">
            <div v-if="block.type === 'paragraph'" style="white-space: pre-wrap; line-height: 1.8">
              {{ block.text }}
            </div>
            <el-table
              v-else-if="block.type === 'table'"
              :data="block.grid"
              border size="small"
            >
              <el-table-column
                v-for="(_, colIdx) in block.num_cols"
                :key="colIdx"
                :label="''"
              >
                <template #default="{ row, $index: rowIdx }">
                  <template v-if="row[colIdx]">
                    <span :style="{ fontWeight: rowIdx === 0 ? 'bold' : 'normal' }">
                      {{ row[colIdx].text }}
                    </span>
                  </template>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </template>
        <div v-else style="white-space: pre-wrap; line-height: 1.8">{{ reportData.module_3_evaluation_standards }}</div>
      </el-card>

      <!-- Module 4: Evaluation Results -->
      <el-card style="margin-bottom: 20px">
        <template #header>
          <span style="font-weight: 700">四、课程评价结果</span>
        </template>
        <div v-if="!reportData.module_4_evaluation_results.generated">
          <el-empty description="暂无成绩数据" />
        </div>
        <div v-else>
          <div v-for="(stats, colName) in reportData.module_4_evaluation_results.grade_analysis" :key="colName" style="margin-bottom: 32px">
            <h3>{{ colName }}</h3>
            <el-row :gutter="16" style="margin-bottom: 16px">
              <el-col :span="3" v-for="item in [
                { label: '参考人数', value: stats.count },
                { label: '缺考人数', value: stats.missing },
                { label: '最高分', value: stats.max },
                { label: '最低分', value: stats.min },
                { label: '平均分', value: stats.avg },
                { label: '中位数', value: stats.median },
                { label: '标准差', value: stats.stdev },
                { label: '及格率', value: stats.pass_rate + '%' },
              ]" :key="item.label">
                <el-statistic :title="item.label" :value="item.value" />
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="12">
                <v-chart
                  v-if="distributionChartData(stats)"
                  :option="distributionChartData(stats)"
                  style="height: 300px"
                />
              </el-col>
              <el-col :span="12">
                <v-chart
                  v-if="passRatePieData(stats)"
                  :option="passRatePieData(stats)"
                  style="height: 300px"
                />
              </el-col>
            </el-row>
          </div>
        </div>
      </el-card>

      <!-- Module 5: Improvement Plan -->
      <el-card style="margin-bottom: 20px">
        <template #header>
          <span style="font-weight: 700">五、课程持续改进方案及措施</span>
        </template>
        <div style="white-space: pre-wrap; line-height: 1.8">{{ reportData.module_5_improvement_plan }}</div>
      </el-card>
    </div>
  </div>
</template>
