<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { Plus, Delete } from '@element-plus/icons-vue'
import ModuleActionBar from './ModuleActionBar.vue'

interface EvalBlock {
  type: 'paragraph' | 'table'
  text?: string
  num_cols?: number
  grid?: Array<Array<{ text: string; colspan: number; rowspan: number } | null>>
}

const props = defineProps<{
  modelValue: unknown
  status: string
  loading: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: unknown]
  regenerate: []
  save: []
  confirm: []
  export: []
}>()

const readonly = computed(() => props.status === 'confirmed')

const isLegacy = ref(false)
const legacyText = ref('')
const blocks = ref<EvalBlock[]>([])

// ── Header cell detection & inline editing ──────────────────────────────────
const editingHeaders = ref<Set<string>>(new Set())

function headerKey(bi: number, ri: number, ci: number): string {
  return `${bi}-${ri}-${ci}`
}

function isHeaderCell(ri: number, _ci: number, cell: { colspan: number; rowspan: number }): boolean {
  return ri === 0 || cell.colspan > 1 || cell.rowspan > 1
}

function isEditingHeader(bi: number, ri: number, ci: number): boolean {
  return editingHeaders.value.has(headerKey(bi, ri, ci))
}

function startEditHeader(bi: number, ri: number, ci: number) {
  const next = new Set(editingHeaders.value)
  next.add(headerKey(bi, ri, ci))
  editingHeaders.value = next
}

function stopEditHeader(bi: number, ri: number, ci: number) {
  const next = new Set(editingHeaders.value)
  next.delete(headerKey(bi, ri, ci))
  editingHeaders.value = next
}

watch(() => props.modelValue, (v) => {
  if (!v) {
    blocks.value = []
    isLegacy.value = false
    legacyText.value = ''
    return
  }
  if (typeof v === 'string') {
    isLegacy.value = true
    legacyText.value = v
  } else if (Array.isArray(v)) {
    isLegacy.value = false
    blocks.value = JSON.parse(JSON.stringify(v))
  }
}, { immediate: true })

function emitBlocks() {
  emit('update:modelValue', JSON.parse(JSON.stringify(blocks.value)))
}

function updateParagraphText(idx: number, val: string) {
  if (blocks.value[idx] && blocks.value[idx].type === 'paragraph') {
    blocks.value[idx].text = val
    emitBlocks()
  }
}

function updateCellText(blockIdx: number, rowIdx: number, colIdx: number, val: string) {
  const block = blocks.value[blockIdx]
  if (!block || !block.grid) return
  const cell = block.grid[rowIdx][colIdx]
  if (cell) {
    cell.text = val
    emitBlocks()
  }
}

function addParagraph() {
  blocks.value.push({ type: 'paragraph', text: '' })
  emitBlocks()
}

function addTable() {
  blocks.value.push({ type: 'table', num_cols: 3, grid: [] })
  emitBlocks()
}

function addTableRow(blockIdx: number) {
  const block = blocks.value[blockIdx]
  if (!block || block.type !== 'table') return
  const cols = block.num_cols || 3
  const row: Array<{ text: string; colspan: number; rowspan: number }> = []
  for (let i = 0; i < cols; i++) {
    row.push({ text: '', colspan: 1, rowspan: 1 })
  }
  if (!block.grid) block.grid = []
  block.grid.push(row)
  emitBlocks()
}

function removeBlock(idx: number) {
  blocks.value.splice(idx, 1)
  emitBlocks()
}
</script>

<template>
  <div v-loading.fullscreen.lock="loading" element-loading-text="生成中...">
    <template v-if="isLegacy">
      <el-input
        :model-value="legacyText"
        type="textarea"
        :rows="8"
        :disabled="readonly"
        @input="(v: string) => { legacyText = v; emit('update:modelValue', v) }"
      />
    </template>
    <template v-else>
      <div v-for="(block, bi) in blocks" :key="bi" style="margin-bottom: 16px; border: 1px solid #ebeef5; border-radius: 4px; padding: 12px">
        <div style="display: flex; justify-content: space-between; margin-bottom: 8px">
          <el-tag size="small">{{ block.type === 'paragraph' ? '段落' : '表格' }}</el-tag>
          <el-button v-if="!readonly" size="small" type="danger" :icon="Delete" @click="removeBlock(bi)">删除</el-button>
        </div>
        <template v-if="block.type === 'paragraph'">
          <el-input
            :model-value="block.text"
            type="textarea"
            :rows="4"
            :disabled="readonly"
            @input="(v: string) => updateParagraphText(bi, v)"
          />
        </template>
        <template v-else-if="block.type === 'table'">
          <table style="border-collapse: collapse; margin-bottom: 8px">
            <tbody>
              <tr v-for="(row, ri) in block.grid" :key="ri">
                <template v-for="(cell, ci) in row" :key="ci">
                  <td
                    v-if="cell"
                    :colspan="cell.colspan"
                    :rowspan="cell.rowspan"
                    :style="{
                      border: '1px solid #909399',
                      padding: '6px 10px',
                      verticalAlign: 'middle',
                      textAlign: 'center',
                    }"
                  >
                    <!-- Readonly mode: plain text -->
                    <div v-if="readonly" style="min-height: 28px; line-height: 28px; text-align: center">{{ cell.text }}</div>
                    <!-- Header cell in edit mode: tag, double-click to edit -->
                    <template v-else-if="isHeaderCell(ri, ci, cell)">
                      <span
                        v-if="!isEditingHeader(bi, ri, ci)"
                        @dblclick="startEditHeader(bi, ri, ci)"
                        style="cursor: pointer; font-weight: 700; min-height: 28px; display: flex; align-items: center; justify-content: center"
                      >{{ cell.text || ' ' }}</span>
                      <el-input
                        v-else
                        :model-value="cell.text"
                        size="small"
                        input-style="text-align: center"
                        @blur="stopEditHeader(bi, ri, ci)"
                        @keyup.enter="stopEditHeader(bi, ri, ci)"
                        @input="(v: string) => updateCellText(bi, ri, ci, v)"
                      />
                    </template>
                    <!-- Regular cell: editable input -->
                    <el-input
                      v-else
                      :model-value="cell.text"
                      size="small"
                      input-style="text-align: center"
                      @input="(v: string) => updateCellText(bi, ri, ci, v)"
                    />
                  </td>
                </template>
              </tr>
            </tbody>
          </table>
          <el-button v-if="!readonly" size="small" style="margin-top: 8px" @click="addTableRow(bi)">+ 添加行</el-button>
        </template>
      </div>
      <div v-if="!readonly" style="margin-bottom: 12px; display: flex; gap: 8px">
        <el-button size="small" :icon="Plus" @click="addParagraph">添加段落</el-button>
        <el-button size="small" :icon="Plus" @click="addTable">添加表格</el-button>
      </div>
    </template>
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
