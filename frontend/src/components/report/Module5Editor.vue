<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { Edit } from '@element-plus/icons-vue'
import ModuleActionBar from './ModuleActionBar.vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, ScatterChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, TitleComponent, MarkLineComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'
import type { Module5Data } from '@/api/report'

use([BarChart, ScatterChart, GridComponent, TooltipComponent, TitleComponent, MarkLineComponent, CanvasRenderer])

const props = defineProps<{
  modelValue: Module5Data | null
  status: string
  loading: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: Module5Data]
  regenerate: []
  save: []
  confirm: []
  export: []
  'generate-excel': []
  'download-excel': []
}>()

const defVal: Module5Data = {
  report_title: '',
  objectives: [],
  achievement_table: [],
  distribution_table: null,
  per_objective_analysis: [],
  low_students: [],
  radar_data: { labels: [], values: [] },
  student_achievements: [],
  overall_avg_achievement: 0,
  section_5_1: null,
  generated: false,
}

const data = ref<Module5Data>(JSON.parse(JSON.stringify(defVal)))

function normalize(v: unknown): Module5Data {
  if (!v || typeof v !== 'object') return JSON.parse(JSON.stringify(defVal))
  const raw = JSON.parse(JSON.stringify(v)) as any
  if (!('achievement_table' in raw)) return JSON.parse(JSON.stringify(defVal))
  // Migrate old data keys to new structure
  if (!raw.per_objective_analysis) {
    if (raw.ai_analysis && raw.objectives?.length) {
      raw.per_objective_analysis = raw.objectives.map((obj: string) => ({
        objective: obj, rate: 0, analysis: raw.ai_analysis,
      }))
    } else {
      raw.per_objective_analysis = []
    }
    delete raw.ai_analysis
  }
  if (!raw.distribution_table && raw.distribution) {
    raw.distribution_table = {
      objectives: raw.distribution.objectives || [],
      avg: raw.distribution.avg || [],
      rows: raw.distribution.distributions || raw.distribution.rows || [],
    }
    delete raw.distribution
  }
  if (!raw.distribution_table) raw.distribution_table = null
  if (!raw.report_title) raw.report_title = ''
  if (!raw.low_students) raw.low_students = []
  if (!raw.objectives) raw.objectives = []
  if (!raw.radar_data) raw.radar_data = { labels: [], values: [] }
  if (!raw.student_achievements) raw.student_achievements = []
  if (raw.overall_avg_achievement == null) raw.overall_avg_achievement = 0
  if (!raw.section_5_1) raw.section_5_1 = null
  // Normalize achievement_table rows: achievement → achievement_rate
  if (Array.isArray(raw.achievement_table)) {
    raw.achievement_table = raw.achievement_table.map((r: any) => ({
      ...r,
      achievement_rate: r.achievement_rate ?? (r.achievement != null ? String(r.achievement) + '%' : ''),
    }))
  } else {
    raw.achievement_table = []
  }
  return raw as Module5Data
}

watch(() => props.modelValue, (v) => {
  data.value = normalize(v)
}, { immediate: true })

const readonly = computed(() => props.status === 'confirmed')

// Split a value by comma into trimmed parts; returns [val] if no comma present
function splitByComma(val: string | number): string[] {
  const s = String(val ?? '')
  if (!s.includes(',')) return [s]
  return s.split(',').map(p => p.trim()).filter(Boolean)
}

// Flatten section 5.1 objectives into table rows with span info.
// Supports comma-separated item names / weight_pct so each fragment
// gets its own row, with 课程目标 and 课程目标达成情况 merged.
const flattened51Rows = computed(() => {
  const section = data.value.section_5_1
  if (!section) return []
  const rows: any[] = []
  for (const obj of section.objectives) {
    const objRows: any[] = []
    for (const item of obj.items || []) {
      const itemParts = splitByComma(item.item)
      const weightParts = splitByComma(item.weight_pct)
      // Pair each item fragment with the corresponding weight fragment
      const maxLen = Math.max(itemParts.length, weightParts.length)
      for (let k = 0; k < maxLen; k++) {
        objRows.push({
          objective: obj.name,
          item: itemParts[k] ?? itemParts[itemParts.length - 1] ?? '',
          target_score: item.target_score,
          avg_score: item.avg_score,
          weight_pct: weightParts[k] ?? weightParts[weightParts.length - 1] ?? '0%',
          achievement_rate: obj.achievement_rate,
          _rowspan_obj: 0,
          _rowspan_ach: 0,
        })
      }
    }
    // Mark first row of this objective group with the total row count for merging
    if (objRows.length > 0) {
      objRows[0]._rowspan_obj = objRows.length
      objRows[0]._rowspan_ach = objRows.length
    }
    rows.push(...objRows)
  }
  return rows
})

function spanMethod51({ row, columnIndex }: { row: any; columnIndex: number }) {
  if (columnIndex === 0) {
    if (row._rowspan_obj > 0) return { rowspan: row._rowspan_obj, colspan: 1 }
    if (row._rowspan_obj === 0) return { rowspan: 0, colspan: 0 }
  }
  if (columnIndex === 5) {
    if (row._rowspan_ach > 0) return { rowspan: row._rowspan_ach, colspan: 1 }
    if (row._rowspan_ach === 0) return { rowspan: 0, colspan: 0 }
  }
  return { rowspan: 1, colspan: 1 }
}

// Pre-compute Table 6 row counts per objective for achievement_rate column merge
const table6RowCounts = computed(() => {
  const counts: Record<string, number> = {}
  for (const r of data.value.achievement_table) {
    const obj = (r as any).objective || ''
    counts[obj] = (counts[obj] || 0) + 1
  }
  return counts
})

function spanMethodTable6(objName: string) {
  return ({ row, columnIndex }: { row: any; columnIndex: number }) => {
    if (columnIndex === 4) {
      const total = table6RowCounts.value[objName] || 0
      // Find the row index within the filtered group
      const group = data.value.achievement_table.filter((r: any) => r.objective === objName)
      const rowIdx = group.indexOf(row)
      if (rowIdx === 0 && total > 1) return { rowspan: total, colspan: 1 }
      if (rowIdx > 0) return { rowspan: 0, colspan: 0 }
    }
    return { rowspan: 1, colspan: 1 }
  }
}

function parseRate(s: string): number {
  return parseFloat(String(s).replace('%', '').trim()) || 0
}

const chart1Option = computed<EChartsOption | undefined>(() => {
  const sec = data.value.section_5_1
  if (!sec || !sec.objectives.length) return undefined
  const names = sec.objectives.map((o) => o.name)
  const rates = sec.objectives.map((o) => parseRate(o.achievement_rate))
  return {
    title: { text: '课程目标达成情况', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis', valueFormatter: (v: unknown) => (v as number).toFixed(2) + '%' },
    xAxis: { type: 'category', data: names, axisLabel: { rotate: 15 } },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
    series: [{ data: rates, type: 'bar', barMaxWidth: 48, itemStyle: { color: '#409eff' } }],
  }
})

const distChartOptions = computed<EChartsOption[]>(() => {
  const dt = data.value.distribution_table
  if (!dt || !dt.objectives.length || !dt.rows.length) return []
  return dt.objectives.map((objName, oi) => ({
    title: { text: `${objName}达成度分布`, left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis', valueFormatter: (v: unknown) => (v as number).toFixed(1) + '%' },
    xAxis: { type: 'category', data: dt.rows.map((r) => r.label), axisLabel: { rotate: 15 } },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
    series: [{
      data: dt.rows.map((r) => r.pcts[oi]),
      type: 'bar',
      barMaxWidth: 36,
      itemStyle: { color: ['#67c23a', '#e6a23c', '#f56c6c', '#909399'][oi] || '#409eff' },
    }],
  }))
})

const scatterOption = computed<EChartsOption | undefined>(() => {
  const students = data.value.student_achievements
  const overall = data.value.overall_avg_achievement
  if (!students || !students.length) return undefined
  const values = students.map((s, i) => [i + 1, s.avg_achievement])
  return {
    title: { text: '学生个体课程目标达成度分布', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: {
      trigger: 'item',
      formatter: (p: any) => `${students[p.dataIndex]?.name ?? ''}<br/>序号: ${p.value[0]}<br/>平均达成度: ${p.value[1]}%`,
    },
    xAxis: { type: 'value', name: '学生序号' },
    yAxis: { type: 'value', name: '平均达成度(%)' },
    series: [{
      data: values,
      type: 'scatter',
      symbolSize: 8,
      itemStyle: { color: '#409eff' },
      markLine: {
        silent: true,
        symbol: 'none',
        label: { formatter: '平均: {c}%' },
        lineStyle: { color: 'red', type: 'solid' },
        data: [{ yAxis: overall, name: '总平均达成度' }],
      },
    }],
  }
})

function emitUpdate() {
  emit('update:modelValue', JSON.parse(JSON.stringify(data.value)))
}

function handleGenerateExcel() {
  emit('generate-excel')
}

function handleDownloadExcel() {
  emit('download-excel')
}

const excelGenerated = computed(() => data.value.excel_generated === true)
</script>

<template>
  <div v-loading="loading" element-loading-text="生成中...">
    <!-- ── Excel generation section (always visible) ── -->
    <div style="margin-bottom: 20px; padding: 16px; background: #f0f9eb; border-radius: 8px; border: 1px solid #e1f3d8">
      <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap">
        <div style="font-weight: 600; color: #67c23a">课程达成度计算Excel</div>
        <el-button
          type="warning"
          :loading="loading"
          :disabled="loading"
          @click="handleGenerateExcel"
        >
          <el-icon><Edit /></el-icon> {{ excelGenerated ? '重新生成Excel' : '生成课程达成度计算Excel' }}
        </el-button>
        <el-button
          v-if="excelGenerated"
          type="success"
          @click="handleDownloadExcel"
        >
          下载 {{ data.excel_filename || 'Excel' }}
        </el-button>
      </div>
      <div v-if="!excelGenerated" style="margin-top: 8px; color: #e6a23c; font-size: 13px">
        请先生成课程达成度计算Excel，然后才能生成下方的课程目标达成度内容。
      </div>
    </div>

    <!-- Empty / not-generated state -->
    <div v-if="!excelGenerated">
      <el-result icon="warning" title="请先生成课程达成度计算Excel">
        <template #extra>
          <el-alert
            type="warning"
            :closable="false"
            show-icon
            style="margin: 0 auto; max-width: 460px; text-align: left"
          >
            <template #title>
              请点击上方「生成课程达成度计算Excel」按钮，生成Excel后方可继续生成课程目标达成度内容。
            </template>
          </el-alert>
        </template>
      </el-result>
    </div>

    <!-- Not-generated state (Excel ready but content not generated) -->
    <div v-else-if="!data.generated">
      <el-result icon="info" title="暂无课程目标达成度数据">
        <template #extra>
          <el-alert
            type="info"
            :closable="false"
            show-icon
            style="margin: 0 auto; max-width: 460px; text-align: left"
          >
            <template #title>
              该模块尚未生成。请点击下方「重新生成」按钮。
            </template>
          </el-alert>
        </template>
      </el-result>
    </div>

    <!-- Generated content -->
    <div v-else>
      <!-- Section 5.1: 课程目标达成情况 -->
      <template v-if="data.section_5_1 && data.section_5_1.objectives.length">
        <h3 style="margin-top: 0">5.1 课程目标达成情况</h3>
        <p>课程目标达成情况计算见下表。</p>
        <p style="text-align: center; font-weight: bold">
          {{ data.section_5_1.title }}
        </p>

        <el-table :data="flattened51Rows" border size="small"
          :span-method="spanMethod51"
          style="width: auto; margin: 0 auto"
        >
          <el-table-column prop="objective" label="课程目标" width="100" />
          <el-table-column prop="item" label="评价内容" width="100" />
          <el-table-column prop="target_score" label="目标分值" width="90" align="center" />
          <el-table-column prop="avg_score" label="平均得分" width="90" align="center" />
          <el-table-column prop="weight_pct" label="权重系数" width="90" align="center" />
          <el-table-column prop="achievement_rate" label="课程目标达成情况" width="130" align="center" />
        </el-table>
      </template>

      <p style="margin-top: 0">课程目标达成情况计算见表6。</p>

      <!-- (1) 统计分析 -->
      <h3 style="margin-top: 20px">(1) 统计分析</h3>

      <!-- Table 6 -->
      <p v-if="data.report_title" style="font-weight: bold">
        表6 {{ data.report_title }}
      </p>

      <div v-for="objName in data.objectives" :key="objName" style="margin-bottom: 20px">
        <h4>{{ objName }}</h4>
        <el-table
          :data="data.achievement_table.filter((r: any) => r.objective === objName)"
          :span-method="spanMethodTable6(objName)"
          border
          size="small"
          style="width: auto; margin: 0 auto"
        >
          <el-table-column prop="item" label="评价内容" width="100" />
          <el-table-column prop="target_score" label="目标分值" width="90" align="center" />
          <el-table-column prop="avg_score" label="平均得分" width="90" align="center" />
          <el-table-column prop="weight_pct" label="权重系数" width="90" align="center" />
          <el-table-column prop="achievement_rate" label="课程目标达成情况" width="130" align="center" />
        </el-table>
      </div>

      <!-- Table 7: Distribution -->
      <template v-if="data.distribution_table && data.distribution_table.objectives.length">
        <p style="font-weight: bold">表7 各课程目标的达成情况和分布表</p>

        <el-table
          :data="data.distribution_table.rows"
          border
          size="small"
          style="margin-top: 0; width: auto; margin-left: auto; margin-right: auto"
        >
          <el-table-column prop="label" label="达成度分布" width="110" fixed />
          <template v-for="(objName, oi) in data.distribution_table.objectives" :key="objName">
            <el-table-column :label="objName + '（人数）'" align="center" width="100">
              <template #default="{ row }">{{ (row as any).counts[oi] }}</template>
            </el-table-column>
            <el-table-column :label="objName + '（比例）'" align="center" width="100">
              <template #default="{ row }">{{ (row as any).pcts[oi] }}%</template>
            </el-table-column>
          </template>
        </el-table>
      </template>

      <!-- (2) 图形分析 -->
      <h3 style="margin-top: 24px">(2) 图形分析</h3>

      <div v-if="chart1Option" style="margin-bottom: 24px">
        <v-chart :option="chart1Option" style="height: 320px" />
        <p style="text-align: center; margin-top: 4px">图：课程目标达成情况</p>
      </div>

      <template v-if="distChartOptions.length">
        <div v-for="(opt, di) in distChartOptions" :key="di" style="margin-bottom: 24px">
          <v-chart :option="opt" style="height: 320px" />
          <p style="text-align: center; margin-top: 4px">图：{{ data.distribution_table!.objectives[di] }}达成度分布</p>
        </div>
      </template>

      <p v-if="!chart1Option && !distChartOptions.length" style="color: #909399; font-size: 13px">
        暂无图表数据，请先生成课程目标达成度内容。
      </p>

      <!-- (3) 教学班整体课程目标达成情况分析 -->
      <template v-if="data.per_objective_analysis.length">
        <h3 style="margin-top: 24px">(3) 教学班整体课程目标达成情况分析</h3>
        <div
          v-for="(poa, idx) in data.per_objective_analysis"
          :key="idx"
          style="margin-bottom: 16px"
        >
          <h4>{{ ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧'][idx] || `(${idx + 1})` }}{{ poa.objective }}的达成情况分析</h4>
          <div v-if="readonly" style="white-space: pre-wrap; padding: 8px 12px; background: #f5f7fa; border-radius: 4px; line-height: 1.8">
            {{ poa.analysis }}
          </div>
          <el-input
            v-else
            :model-value="poa.analysis"
            type="textarea"
            :rows="3"
            @input="(v: string) => { data.per_objective_analysis[idx].analysis = v; emitUpdate() }"
          />
        </div>
      </template>

      <!-- (4) 学生个体课程目标达成情况分析 -->
      <template v-if="data.low_students.length">
        <h3 style="margin-top: 24px">(4) 学生个体课程目标达成情况分析</h3>
        <h4>需要关注及跟踪的学生</h4>
        <p style="font-weight: bold">表8 未达成课程目标学生汇总表</p>

        <el-table :data="data.low_students" border size="small" style="width: auto; margin: 0 auto">
          <el-table-column prop="name" label="姓名" width="100" fixed />
          <el-table-column
            v-for="objName in data.objectives"
            :key="objName"
            :label="objName + '达成度'"
            align="center"
            width="130"
          >
            <template #default="{ row }">
              <el-tag v-if="(row.achievements[objName] || 0) < 0.6" type="danger" size="small">
                {{ row.achievements[objName] }}
              </el-tag>
              <span v-else>{{ row.achievements[objName] }}</span>
            </template>
          </el-table-column>
        </el-table>

        <p style="margin-top: 12px; color: #909399; font-size: 13px">
          以上几位学生在课程目标的达成度上较低，需要重点关注与跟踪。
        </p>
      </template>

      <!-- Student scatter chart -->
      <div v-if="scatterOption" style="margin-top: 24px">
        <v-chart :option="scatterOption" style="height: 350px" />
        <p style="text-align: center; margin-top: 4px">图：学生个体课程目标达成度分布</p>
      </div>
    </div>

    <ModuleActionBar
      :loading="loading"
      :regenerate-disabled="!excelGenerated"
      :save-disabled="status === 'confirmed' || !excelGenerated"
      :confirm-disabled="status === 'confirmed' || !excelGenerated"
      @regenerate="emit('regenerate')"
      @save="emit('save')"
      @confirm="emit('confirm')"
      @export="emit('export')"
    />
  </div>
</template>
