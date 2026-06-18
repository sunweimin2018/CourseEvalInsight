<script setup lang="ts">
import type { WordContent } from '@/api/excel'

defineProps<{
  content: WordContent | null
  loading: boolean
}>()
</script>

<template>
  <el-card>
    <template #header>
      <span style="font-weight: 600">课程大纲 - {{ content?.file_name || '' }}</span>
    </template>

    <div v-if="loading" style="text-align: center; padding: 60px 0">
      <el-icon style="font-size: 32px; color: #909399">
        <svg viewBox="0 0 1024 1024" width="1em" height="1em" fill="currentColor">
          <path d="M512 64a448 448 0 1 0 0 896 448 448 0 0 0 0-896zm0 832a384 384 0 1 1 0-768 384 384 0 0 1 0 768z"/>
          <path d="M512 256a32 32 0 0 1 32 32v256a32 32 0 0 1-64 0V288a32 32 0 0 1 32-32z"/>
          <path d="M512 640a48 48 0 1 1 0 96 48 48 0 0 1 0-96z"/>
        </svg>
      </el-icon>
      <p style="color: #909399; margin-top: 12px">加载中...</p>
    </div>

    <el-empty v-else-if="!content" description="请先选择课程大纲文件" />

    <div v-else class="docx-content">
      <!-- Paragraphs -->
      <div v-if="content.paragraphs.length > 0" class="paragraphs-section">
        <p
          v-for="p in content.paragraphs"
          :key="p.index"
          :class="{
            'is-heading': p.style.includes('Heading'),
            'heading-1': p.style === 'Heading 1' || p.style === 'heading 1',
            'heading-2': p.style === 'Heading 2' || p.style === 'heading 2',
            'heading-3': p.style === 'Heading 3' || p.style === 'heading 3',
          }"
        >
          {{ p.text }}
        </p>
      </div>

      <!-- Tables -->
      <div v-for="t in content.tables" :key="t.index" class="table-section">
        <el-table :data="t.rows.map((row, i) => ({ _idx: i, ...Object.fromEntries(t.headers.map((h, j) => [h, row[j] || ''])) }))" border stripe size="small">
          <el-table-column
            v-for="h in t.headers"
            :key="h"
            :prop="h"
            :label="h"
            min-width="120"
            show-overflow-tooltip
          />
        </el-table>
      </div>

      <el-empty v-if="!content.paragraphs.length && !content.tables.length" description="文档内容为空" />
    </div>
  </el-card>
</template>

<style scoped>
.docx-content {
  max-height: 70vh;
  overflow-y: auto;
  padding: 16px 0;
}

.paragraphs-section p {
  margin: 0 0 12px;
  line-height: 1.8;
  font-size: 14px;
  color: #303133;
}

.paragraphs-section p.is-heading {
  font-weight: 700;
  color: #1d1d1d;
}

.paragraphs-section p.heading-1 {
  font-size: 22px;
  margin: 24px 0 16px;
  border-bottom: 2px solid #409eff;
  padding-bottom: 8px;
}

.paragraphs-section p.heading-2 {
  font-size: 18px;
  margin: 20px 0 12px;
}

.paragraphs-section p.heading-3 {
  font-size: 16px;
  margin: 16px 0 10px;
}

.table-section {
  margin: 20px 0;
}
</style>
