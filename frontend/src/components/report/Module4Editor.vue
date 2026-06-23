<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { Edit } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, TitleComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'

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
  'update:modelValue': [value: Module4Data]
  regenerate: []
  save: []
  confirm: []
  export: []
}>()

const data = ref<Module4Data | null>(null)

watch(() => props.modelValue, (v) => {
  data.value = v ? JSON.parse(JSON.stringify(v)) : null
}, { immediate: true })

const readonly = computed(() => props.status === 'confirmed')

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
  const count = stats.count
  if (!count) return undefined
  const passCount = Math.round(stats.pass_rate / 100 * count)
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
</script>

<template>
  <div v-loading="loading" element-loading-text="生成中...">
    <div v-if="!data || !data.generated">
      <el-empty description="暂无成绩数据，请重新生成" />
    </div>
    <div v-else>
      <div v-for="(stats, colName) in data.grade_analysis" :key="colName" style="margin-bottom: 32px">
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
    <div style="margin-top: 12px; display: flex; gap: 8px">
      <el-button :loading="loading" @click="emit('regenerate')">
        <el-icon><Edit /></el-icon> 重新生成
      </el-button>
      <el-button type="primary" :loading="loading" :disabled="status === 'confirmed'" @click="emit('save')">保存草稿</el-button>
      <el-button type="success" :loading="loading" :disabled="status === 'confirmed'" @click="emit('confirm')">确认</el-button>
      <el-button :loading="loading" @click="emit('export')">导出Word</el-button>
    </div>
  </div>
</template>
