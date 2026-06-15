<script setup lang="ts">
import { ref } from 'vue'
import { useExcelStore } from '@/store/excel'
import { ElMessage } from 'element-plus'

const store = useExcelStore()
const activeTab = ref('raw')
const rawPage = ref(1)
const cleanPage = ref(1)
const pageSize = 20
const rawTotal = ref(0)
const cleanTotal = ref(0)
const loading = ref(false)

async function loadRawData() {
  loading.value = true
  try {
    const data = await store.fetchRawData(rawPage.value, pageSize) as unknown as {
      headers: string[]
      rows: Record<string, unknown>[]
      total: number
    }
    rawTotal.value = data.total
  } finally {
    loading.value = false
  }
}

async function loadCleanedData() {
  loading.value = true
  try {
    const data = await store.fetchCleanedData(cleanPage.value, pageSize) as unknown as {
      headers: string[]
      rows: Record<string, unknown>[]
      total: number
    }
    cleanTotal.value = data.total
  } finally {
    loading.value = false
  }
}

async function handleClean() {
  loading.value = true
  try {
    await store.runClean()
    ElMessage.success('Data cleaning complete')
    cleanPage.value = 1
    await loadCleanedData()
    activeTab.value = 'clean'
  } finally {
    loading.value = false
  }
}

function onRawPageChange(page: number) {
  rawPage.value = page
  loadRawData()
}

function onCleanPageChange(page: number) {
  cleanPage.value = page
  loadCleanedData()
}

loadRawData()
</script>

<template>
  <div>
    <h2 style="margin-bottom: 20px">Data Preview</h2>

    <el-card v-if="store.cleaningSummary" style="margin-bottom: 20px">
      <template #header>Cleaning Summary</template>
      <el-row :gutter="20">
        <el-col :span="6">
          <el-statistic title="Before" :value="store.cleaningSummary.total_rows_before" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="After" :value="store.cleaningSummary.total_rows_after" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="Duplicates Removed" :value="store.cleaningSummary.removed_duplicates" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="Outliers Removed" :value="store.cleaningSummary.removed_outliers" />
        </el-col>
      </el-row>
    </el-card>

    <el-card>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
        <el-tabs v-model="activeTab" @tab-change="(t: string) => { if (t === 'raw') loadRawData(); else loadCleanedData() }">
          <el-tab-pane label="Raw Data" name="raw" />
          <el-tab-pane label="Cleaned Data" name="clean" />
        </el-tabs>
        <el-button type="warning" :loading="loading" @click="handleClean">Clean Data</el-button>
      </div>

      <div v-if="activeTab === 'raw' && store.rawData">
        <el-table :data="store.rawData.rows" border stripe v-loading="loading" max-height="500">
          <el-table-column
            v-for="h in store.rawData.headers"
            :key="h"
            :prop="h"
            :label="h"
            min-width="120"
            show-overflow-tooltip
          />
        </el-table>
        <el-pagination
          v-if="rawTotal > pageSize"
          style="margin-top: 16px; justify-content: center"
          :current-page="rawPage"
          :page-size="pageSize"
          :total="rawTotal"
          layout="prev, pager, next"
          @current-change="onRawPageChange"
        />
      </div>

      <div v-if="activeTab === 'clean' && store.cleanedData">
        <el-table :data="store.cleanedData.rows" border stripe v-loading="loading" max-height="500">
          <el-table-column
            v-for="h in store.cleanedData.headers"
            :key="h"
            :prop="h"
            :label="h"
            min-width="120"
            show-overflow-tooltip
          />
        </el-table>
        <el-pagination
          v-if="cleanTotal > pageSize"
          style="margin-top: 16px; justify-content: center"
          :current-page="cleanPage"
          :page-size="pageSize"
          :total="cleanTotal"
          layout="prev, pager, next"
          @current-change="onCleanPageChange"
        />
      </div>

      <el-empty
        v-if="activeTab === 'clean' && !store.cleanedData"
        description="No cleaned data yet. Click 'Clean Data' to start."
      />
    </el-card>
  </div>
</template>
