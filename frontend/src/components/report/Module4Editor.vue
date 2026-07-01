<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import ModuleActionBar from './ModuleActionBar.vue'
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
    series: [{ data: segs.map((s) => s.count), type: 'bar', barMaxWidth: 36, itemStyle: { color: '#409eff' } }],
  }
}
</script>

<template>
  <div v-loading.fullscreen.lock="loading" element-loading-text="生成中...">
    <div v-if="!data || !data.generated">
      <el-result icon="warning" title="暂无成绩数据" sub-title="请点击下方「重新生成」按钮生成数据" />
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
          <h3>
            {{ section.col_name }}
            <el-tag v-if="section.weight_pct" size="small" type="success" style="margin-left: 8px">占总评{{ section.weight_pct }}%</el-tag>
            <el-tag v-if="section.is_weighted" size="small" type="warning" style="margin-left: 8px">已归一化至百分制</el-tag>
            <el-tag v-if="section.segment_source === 'fallback'" size="small" type="info" style="margin-left: 8px">使用默认分数段</el-tag>
            <el-tag v-if="section.segment_source === 'default'" size="small" type="warning" style="margin-left: 8px">使用系统默认分数段</el-tag>
          </h3>
          <p>{{ section.description_line_1 }}</p>
          <p>{{ section.description_line_2 }}</p>

          <el-table
            :data="buildTableRows(section)"
            border
            style="margin-bottom: 20px"
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
</style>
