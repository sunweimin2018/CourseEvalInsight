<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, Edit, Delete } from '@element-plus/icons-vue'
import { getUsers, createUser, updateUser, deleteUser } from '@/api/user'

const { t } = useI18n()

interface UserItem {
  id: number
  username: string
  email: string
  role: string
  create_time: string
}

const users = ref<UserItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const search = ref('')
const loading = ref(false)

const dialogVisible = ref(false)
const dialogTitle = ref('')
const formMode = ref<'create' | 'edit'>('create')
const form = ref({ id: 0, username: '', email: '', password: '', role: 'user' })
const formRules = computed(() => ({
  username: [{ required: true, message: t('auth.usernameRequired'), trigger: 'blur' }],
  password: [
    { required: true, message: t('auth.passwordRequired'), trigger: 'blur' },
    { min: 6, message: t('auth.passwordMinLength'), trigger: 'blur' },
  ],
}))
const formRef = ref()

function resetForm() {
  form.value = { id: 0, username: '', email: '', password: '', role: 'user' }
}

async function fetchUsers() {
  loading.value = true
  try {
    const data = (await getUsers({ page: page.value, page_size: pageSize.value, search: search.value })) as unknown as {
      users: UserItem[]
      total: number
    }
    users.value = data.users ?? []
    total.value = data.total ?? 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  fetchUsers()
}

function showCreateDialog() {
  formMode.value = 'create'
  dialogTitle.value = t('admin.addUser')
  resetForm()
  dialogVisible.value = true
}

function showEditDialog(row: UserItem) {
  formMode.value = 'edit'
  dialogTitle.value = t('admin.editUser')
  form.value = { id: row.id, username: row.username, email: row.email, password: '', role: row.role }
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  try {
    if (formMode.value === 'create') {
      await createUser({ username: form.value.username, email: form.value.email, password: form.value.password, role: form.value.role })
      ElMessage.success(t('admin.userCreated'))
    } else {
      const payload: Record<string, unknown> = { username: form.value.username, email: form.value.email, role: form.value.role }
      if (form.value.password) payload.password = form.value.password
      await updateUser(form.value.id, payload)
      ElMessage.success(t('admin.userUpdated'))
    }
    dialogVisible.value = false
    fetchUsers()
  } catch {
    // error handled by interceptor
  }
}

async function handleDelete(row: UserItem) {
  try {
    await ElMessageBox.confirm(
      t('admin.deleteConfirm').replace('{user}', row.username),
      t('common.confirm'),
      { type: 'warning' },
    )
    await deleteUser(row.id)
    ElMessage.success(t('admin.userDeleted'))
    fetchUsers()
  } catch {
    // cancelled or error
  }
}

function handlePageChange(p: number) {
  page.value = p
  fetchUsers()
}

onMounted(() => {
  fetchUsers()
})
</script>

<template>
  <div>
    <h2 style="margin-bottom: 16px">{{ $t('admin.title') }}</h2>
    <div style="display: flex; justify-content: space-between; margin-bottom: 16px">
      <div style="display: flex; gap: 8px">
        <el-input
          v-model="search"
          :placeholder="$t('admin.searchPlaceholder')"
          clearable
          style="width: 240px"
          @clear="handleSearch"
          @keyup.enter="handleSearch"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" @click="handleSearch">{{ $t('common.search') }}</el-button>
      </div>
      <el-button type="primary" :icon="Plus" @click="showCreateDialog">{{ $t('admin.addUser') }}</el-button>
    </div>

    <el-table :data="users" v-loading="loading" stripe border style="width: 100%">
      <el-table-column prop="id" :label="$t('admin.id')" width="80" />
      <el-table-column prop="username" :label="$t('auth.username')" />
      <el-table-column prop="email" :label="$t('auth.email')" />
      <el-table-column prop="role" :label="$t('admin.role')" width="100">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">{{ row.role === 'admin' ? $t('nav.admin') : 'User' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="create_time" :label="$t('admin.created')" width="180" />
      <el-table-column :label="$t('common.actions')" width="180" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" :icon="Edit" @click="showEditDialog(row)">{{ $t('common.edit') }}</el-button>
          <el-button type="danger" size="small" :icon="Delete" @click="handleDelete(row)">{{ $t('common.delete') }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div style="display: flex; justify-content: center; margin-top: 16px">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px" @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px">
        <el-form-item :label="$t('auth.username')" prop="username">
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item :label="$t('auth.email')">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item :label="$t('auth.password')" :prop="formMode === 'create' ? 'password' : undefined">
          <el-input v-model="form.password" type="password" show-password :placeholder="formMode === 'edit' ? 'Leave blank to keep current' : ''" />
        </el-form-item>
        <el-form-item :label="$t('admin.role')">
          <el-select v-model="form.role">
            <el-option label="Regular User" value="user" />
            <el-option :label="$t('nav.admin')" value="admin" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleSubmit">{{ $t('common.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>
