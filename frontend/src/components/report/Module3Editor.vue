<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

interface TableCell {
  text: string
  colspan: number
  rowspan: number
}

interface EvalBlock {
  type: 'paragraph' | 'table'
  text?: string
  num_cols?: number
  grid?: (TableCell | null)[][]
}

const props = defineProps<{
  modelValue: EvalBlock[] | string | null
  status: string
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: EvalBlock[] | string): void
  (e: 'regenerate'): void
  (e: 'save'): void
  (e: 'confirm'): void
  (e: 'export'): void
}>()

const editingBlocks = ref<EvalBlock[]>([])
const isLegacyText = ref(false)
const legacyText = ref('')

watch(() => props.modelValue, (val) => {
  if (Array.isArray(val)) {
    editingBlocks.value = JSON.parse(JSON.stringify(val))
    isLegacyText.value = false
  } else if (typeof val === 'string' && val !== null) {
    legacyText.value = val
    isLegacyText.value = true
  } else {
    editingBlocks.value = []
    isLegacyText.value = false
  }
}, { immediate: true })

function onParagraphChange(index: number, text: string) {
  editingBlocks.value[index] = { ...editingBlocks.value[index], text }
  emitUpdate()
}

function onTableCellChange(blockIdx: number, rowIdx: number, colIdx: number, text: string) {
  const block = editingBlocks.value[blockIdx]
  if (block.type === 'table' && block.grid) {
    const cell = block.grid[rowIdx][colIdx]
    if (cell) {
      cell.text = text
    }
  }
  emitUpdate()
}

function onLegacyTextChange(text: string) {
  legacyText.value = text
  emit('update:modelValue', text)
}

function emitUpdate() {
  emit('update:modelValue', JSON.parse(JSON.stringify(editingBlocks.value)))
}

function hasContent(): boolean {
  if (isLegacyText.value) return legacyText.value !== null
  return editingBlocks.value.length > 0
}
</script>

<template>
  <div v-loading="loading">
    <el-alert
      v-if="!hasContent() && modelValue === null"
      title="尚未生成数据，请点击"生成模块"按钮"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 16px"
    />

    <!-- Legacy text mode -->
    <template v-if="isLegacyText && modelValue !== null">
      <el-input
        type="textarea"
        :model-value="legacyText"
        @update:model-value="onLegacyTextChange"
        :rows="12"
        placeholder="请输入课程评价标准..."
      />
    </template>

    <!-- Block-based editor -->
    <template v-else-if="!isLegacyText && editingBlocks.length > 0">
      <div v-for="(block, bi) in editingBlocks" :key="bi" style="margin-bottom: 16px">
        <!-- Paragraph block -->
        <template v-if="block.type === 'paragraph'">
          <el-input
            type="textarea"
            :model-value="block.text"
            @update:model-value="(v: string) => onParagraphChange(bi, v)"
            :rows="4"
          />
        </template>

        <!-- Table block -->
        <template v-else-if="block.type === 'table' && block.grid && block.num_cols">
          <el-table :data="block.grid" border size="small" style="width: 100%">
            <el-table-column
              v-for="(_, colIdx) in block.num_cols"
              :key="colIdx"
              :label="colIdx === 0 ? '列' + (colIdx + 1) : ''"
            >
              <template #default="{ row, $index: rowIdx }">
                <template v-if="row[colIdx]">
                  <el-input
                    :model-value="row[colIdx].text"
                    @update:model-value="(v: string) => onTableCellChange(bi, rowIdx, colIdx, v)"
                    size="small"
                    :style="{ fontWeight: rowIdx === 0 ? 'bold' : 'normal' }"
                  />
                </template>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </div>
    </template>

    <div style="margin-top: 20px; display: flex; gap: 8px">
      <el-button type="primary" :loading="loading" @click="emit('regenerate')">
        {{ hasContent() ? '重新生成' : '生成模块' }}
      </el-button>
      <el-button v-if="hasContent()" @click="emit('save')">保存草稿</el-button>
      <el-button v-if="hasContent()" type="success" @click="emit('confirm')">
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
