<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { Edit } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, TitleComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'
import type { Module4Data, GradeSection } from '@/api/report'

use([BarChart, GridComponent, TooltipComponent, TitleComponent, CanvasRenderer])

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

function buildTableRows(section: GradeSection) {
  const segs = section.segments
  const row1: Record<string, string> = { label: '人数', avg_col: String(section.avg_score) }
  const row2: Record<string, string> = { label: '比例%', avg_col: '100' }
  for (const seg of segs) {
    row1[seg.label] = String(seg.count)
    row2[seg.label] = seg.pct + '%'
  }
  return [row1, row2]
}

function sectionBarChartOption(section: GradeSection): EChartsOption | undefined {
  const segs = section.segments
  if (!segs.length) return undefined
  return {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: segs.map((s) => s.label), axisLabel: { rotate: 15 } },
    yAxis: { type: 'value' },
    series: [{ data: segs.map((s) => s.count), type: 'bar', itemStyle: { color: '#409eff' } }],
  }
}
</script>

<template>
  <div v-loading="loading" element-loading-text="生成中...">
    <div v-if="!data || !data.generated">
      <el-empty description="暂无成绩数据，请重新生成" />
    </div>
    <div v-else>
      <!-- Fallback warning -->
      <el-alert
        v-if="data.fallback"
        title="未从课程大纲中提取到考核评价标准分数段定义，已使用默认分数段（优秀/良好/中等/及格/不及格）"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 20px"
      />

      <!-- New format: sections -->
      <template v-if="data.sections && data.sections.length > 0">
        <div v-for="section in data.sections" :key="section.col_name" class="grade-section">
          <h3>{{ section.col_name }}</h3>
          <p>{{ section.description_line_1 }}</p>
          <p>{{ section.description_line_2 }}</p>

          <el-table
            :data="buildTableRows(section)"
            border
            style="margin-bottom: 20px; width: 100%"
          >
            <el-table-column prop="label" label="类别" width="100" fixed />
            <el-table-column
              v-for="seg in section.segments"
              :key="seg.label"
              :label="seg.label"
              align="center"
            >
              <template #default="{ row }">
                {{ row[seg.label] }}
              </template>
            </el-table-column>
            <el-table-column label="平均分" align="center" width="100">
              <template #default="{ row }">
                {{ row['avg_col'] }}
              </template>
            </el-table-column>
          </el-table>

          <!-- Chart -->
          <v-chart
            v-if="sectionBarChartOption(section)"
            :option="sectionBarChartOption(section)"
            style="height: 300px; margin-bottom: 4px"
          />
          <p class="chart-caption">图：学生{{ section.col_name }}成绩分布图</p>

          <!-- AI Summary textarea -->
          <div v-if="section.ai_summary !== undefined && section.ai_summary !== ''" style="margin-top: 20px">
            <label class="summary-label">AI分析描述（可编辑）</label>
            <el-input
              type="textarea"
              :rows="6"
              :model-value="section.ai_summary"
              :disabled="readonly"
              @input="(v: string) => { section.ai_summary = v; emit('update:modelValue', data!) }"
            />
          </div>

          <el-descriptions :column="4" border size="small" style="margin-top: 20px">
            <el-descriptions-item label="参考人数">{{ section.stats.count }}</el-descriptions-item>
            <el-descriptions-item label="缺考人数">{{ section.stats.missing }}</el-descriptions-item>
            <el-descriptions-item label="最高分">{{ section.stats.max }}</el-descriptions-item>
            <el-descriptions-item label="最低分">{{ section.stats.min }}</el-descriptions-item>
            <el-descriptions-item label="平均分">{{ section.stats.avg }}</el-descriptions-item>
            <el-descriptions-item label="中位数">{{ section.stats.median }}</el-descriptions-item>
            <el-descriptions-item label="标准差">{{ section.stats.stdev }}</el-descriptions-item>
            <el-descriptions-item label="及格率">{{ section.stats.pass_rate }}%</el-descriptions-item>
          </el-descriptions>
        </div>
      </template>

      <!-- Legacy format: grade_analysis -->
      <template v-else-if="data.grade_analysis">
        <div v-for="(stats, colName) in data.grade_analysis" :key="colName" class="grade-section">
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
        </div>
      </template>
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

<style scoped>
.grade-section {
  margin-bottom: 40px;
  border-bottom: 1px solid #ebeef5;
  padding-bottom: 24px;
}
.grade-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
}
.chart-caption {
  text-align: center;
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}
:deep(.el-table th) {
  font-weight: 700;
}
:deep(.el-table .cell) {
  font-weight: inherit;
}
.summary-label {
  display: block;
  font-weight: 700;
  font-size: 14px;
  color: #303133;
  margin-bottom: 8px;
}
</style>
