<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, TitleComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'

use([BarChart, PieChart, GridComponent, TooltipComponent, TitleComponent, LegendComponent, CanvasRenderer])

interface Distribution {
  [key: string]: { label: string; count: number }
}

interface GradeStats {
  count: number
  missing: number
  max: number
  min: number
  avg: number
  median: number
  stdev: number
  pass_rate: number
  distribution: Distribution
}

interface Module4Data {
  grade_analysis: Record<string, GradeStats>
  score_columns: string[]
  generated: boolean
}

const props = defineProps<{
  modelValue: Module4Data | null
  status: string
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: Module4Data): void
  (e: 'regenerate'): void
  (e: 'save'): void
  (e: 'confirm'): void
  (e: 'export'): void
}>()

const localData = ref<Module4Data | null>(null)

watch(() => props.modelValue, (val) => {
  localData.value = val ? JSON.parse(JSON.stringify(val)) : null
}, { immediate: true })

function emitUpdate() {
  if (localData.value) {
    emit('update:modelValue', JSON.parse(JSON.stringify(localData.value)))
  }
}

function onStatChange(colName: string, field: string, value: string) {
  if (!localData.value) return
  const num = parseFloat(value)
  if (!isNaN(num) && localData.value.grade_analysis[colName]) {
    ;(localData.value.grade_analysis[colName] as Record<string, unknown>)[field] = num
    emitUpdate()
  }
}

function onDistCountChange(colName: string, key: string, value: string) {
  if (!localData.value) return
  const num = parseInt(value, 10)
  if (!isNaN(num) && localData.value.grade_analysis[colName]?.distribution[key]) {
    localData.value.grade_analysis[colName].distribution[key].count = num
    emitUpdate()
  }
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

const statFields = [
  { key: 'count', label: '参考人数' },
  { key: 'missing', label: '缺考人数' },
  { key: 'max', label: '最高分' },
  { key: 'min', label: '最低分' },
  { key: 'avg', label: '平均分' },
  { key: 'median', label: '中位数' },
  { key: 'stdev', label: '标准差' },
]
</script>

<template>
  <div v-loading="loading">
    <el-alert
      v-if="!modelValue || !modelValue.generated"
      title="尚未生成数据，请点击"生成模块"按钮"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 16px"
    />

    <template v-if="localData && localData.generated">
      <div v-for="(stats, colName) in localData.grade_analysis" :key="colName" style="margin-bottom: 32px">
        <h3>{{ colName }}</h3>

        <!-- Stat fields -->
        <el-row :gutter="12" style="margin-bottom: 16px">
          <el-col v-for="sf in statFields" :key="sf.key" :span="3">
            <div style="font-size: 12px; color: #909399; margin-bottom: 4px">{{ sf.label }}</div>
            <el-input
              :model-value="String((stats as Record<string, unknown>)[sf.key])"
              @update:model-value="(v: string) => onStatChange(colName as string, sf.key, v)"
              size="small"
            />
          </el-col>
          <el-col :span="3">
            <div style="font-size: 12px; color: #909399; margin-bottom: 4px">及格率(%)</div>
            <el-input
              :model-value="String(stats.pass_rate)"
              @update:model-value="(v: string) => onStatChange(colName as string, 'pass_rate', v)"
              size="small"
            />
          </el-col>
        </el-row>

        <!-- Distribution table -->
        <el-table :data="Object.entries(stats.distribution).map(([k, d]) => ({ key: k, ...d }))" border size="small" style="margin-bottom: 16px; max-width: 400px">
          <el-table-column prop="label" label="分数段" width="160" />
          <el-table-column label="人数" width="120">
            <template #default="{ row }">
              <el-input
                :model-value="String(row.count)"
                @update:model-value="(v: string) => onDistCountChange(colName as string, row.key, v)"
                size="small"
              />
            </template>
          </el-table-column>
          <el-table-column label="占比" width="100">
            <template #default="{ row }">
              {{ stats.count ? Math.round(row.count / stats.count * 1000) / 10 : 0 }}%
            </template>
          </el-table-column>
        </el-table>

        <!-- Charts -->
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
    </template>

    <div style="margin-top: 20px; display: flex; gap: 8px">
      <el-button type="primary" :loading="loading" @click="emit('regenerate')">
        {{ localData?.generated ? '重新生成' : '生成模块' }}
      </el-button>
      <el-button v-if="localData?.generated" @click="emit('save')">保存草稿</el-button>
      <el-button v-if="localData?.generated" type="success" @click="emit('confirm')">
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
