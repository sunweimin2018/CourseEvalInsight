<script setup lang="ts">
import { ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { Delete, Refresh, Upload } from '@element-plus/icons-vue'
import type { WorkingData } from '@/api/excel'

const props = defineProps<{
  data: WorkingData | null
  fileId: number
  loading: boolean
  hasUnsavedChanges: boolean
  page: number
  pageSize: number
}>()

const emit = defineEmits<{
  'refresh': [page: number]
  'cell-update': [fileId: number, rowIdx: number, colName: string, value: unknown]
  'row-add': [fileId: number, rowData: Record<string, string>]
  'row-delete': [fileId: number, rowIdx: number]
  'save': [fileId: number]
  'reset': [fileId: number]
  'page-change': [page: number]
}>()

const editingCell = ref<{ absRowIdx: number; colName: string } | null>(null)
const editValue = ref('')
const dialogVisible = ref(false)
const newRowData = ref<Record<string, string>>({})
const editingPageIdx = ref(-1)

function toAbsolute(pageIdx: number) {
  return (props.page - 1) * props.pageSize + pageIdx
}

function startEdit(pageIdx: number, colName: string, currentValue: unknown) {
  editingCell.value = { absRowIdx: toAbsolute(pageIdx), colName }
  editingPageIdx.value = pageIdx
  editValue.value = String(currentValue ?? '')
}

async function commitEdit() {
  const cell = editingCell.value
  if (!cell) return
  emit('cell-update', props.fileId, cell.absRowIdx, cell.colName, editValue.value)
  editingCell.value = null
}

function cancelEdit() {
  editingCell.value = null
  editingPageIdx.value = -1
  editValue.value = ''
}

function onEditKeyup(e: KeyboardEvent) {
  if (e.key === 'Enter') commitEdit()
  else if (e.key === 'Escape') cancelEdit()
}

function confirmDelete(pageIdx: number) {
  const absIdx = toAbsolute(pageIdx)
  ElMessageBox.confirm('确定要删除该行数据吗？此操作不可撤销。', '确认删除', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  }).then(() => {
    emit('row-delete', props.fileId, absIdx)
  }).catch(() => {})
}

function showAddDialog() {
  if (!props.data) return
  newRowData.value = Object.fromEntries(props.data.headers.map(h => [h, '']))
  dialogVisible.value = true
}

function confirmAddRow() {
  emit('row-add', props.fileId, { ...newRowData.value })
  dialogVisible.value = false
}

async function handleSave() {
  emit('save', props.fileId)
}

function handleReset() {
  ElMessageBox.confirm('重置将丢弃所有未保存的修改，恢复为原始文件数据。是否继续？', '确认重置', {
    type: 'warning',
    confirmButtonText: '确认重置',
    cancelButtonText: '取消',
  }).then(() => {
    emit('reset', props.fileId)
  }).catch(() => {})
}

function onPageChange(page: number) {
  emit('refresh', page)
  emit('page-change', page)
}

function cellValue(row: Record<string, unknown>, col: string): string {
  return String(row[col] ?? '')
}
</script>

<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span style="font-weight: 600">{{ data?.sheet_name || 'Sheet1' }}</span>
        <div style="display: flex; gap: 8px">
          <el-button
            type="primary"
            size="small"
            :icon="Upload"
            :disabled="!hasUnsavedChanges"
            @click="handleSave"
          >
            保存
          </el-button>
          <el-button
            size="small"
            :icon="Refresh"
            @click="handleReset"
          >
            重置
          </el-button>
        </div>
      </div>
    </template>

    <!-- Toolbar -->
    <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center">
      <div style="display: flex; gap: 8px; align-items: center">
        <el-button type="success" size="small" @click="showAddDialog">新增行</el-button>
        <el-tag v-if="hasUnsavedChanges" type="warning" size="small">有未保存的修改</el-tag>
        <el-tag v-else type="info" size="small">已保存</el-tag>
      </div>
      <span style="color: #909399; font-size: 13px">共 {{ data?.total || 0 }} 条</span>
    </div>

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

    <el-empty v-else-if="!data" description="请先选择 Excel 文件" />

    <template v-else>
      <el-table :data="data.rows" border stripe v-loading="loading" max-height="500" size="small">
        <el-table-column type="index" width="60" label="#" />
        <el-table-column
          v-for="h in data.headers"
          :key="h"
          :prop="h"
          :label="h"
          min-width="140"
        >
          <template #default="{ row, $index }">
            <div v-if="editingPageIdx === $index && editingCell?.colName === h" style="display: flex; gap: 4px">
              <el-input
                :model-value="editValue"
                size="small"
                @update:model-value="(v: string) => editValue = v"
                @keyup="onEditKeyup"
                @blur="commitEdit"
              />
            </div>
            <div
              v-else
              style="cursor: pointer; min-height: 20px; padding: 2px 4px; border-radius: 2px"
              class="cell-hover"
              @dblclick="startEdit($index, h, row[h])"
            >
              {{ cellValue(row, h) }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ $index }">
            <el-button
              type="danger"
              size="small"
              :icon="Delete"
              text
              @click="confirmDelete($index)"
            />
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="data.total > pageSize"
        style="margin-top: 16px; justify-content: center"
        :current-page="page"
        :page-size="pageSize"
        :total="data.total"
        layout="prev, pager, next"
        @current-change="onPageChange"
      />
    </template>

    <!-- Add row dialog -->
    <el-dialog v-model="dialogVisible" title="新增行" width="500px" :close-on-click-modal="false">
      <el-form label-width="120px">
        <el-form-item
          v-for="h in data?.headers || []"
          :key="h"
          :label="h"
        >
          <el-input v-model="newRowData[h]" :placeholder="'请输入 ' + h" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmAddRow">确定新增</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<style scoped>
.cell-hover:hover {
  background: #ecf5ff;
}
</style>
