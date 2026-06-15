<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, Edit, Delete } from '@element-plus/icons-vue'
import { getUsers, createUser, updateUser, deleteUser } from '@/api/user'

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
const dialogTitle = ref('Add User')
const formMode = ref<'create' | 'edit'>('create')
const form = ref({ id: 0, username: '', email: '', password: '', role: 'user' })
const formRules = {
  username: [{ required: true, message: 'Username is required', trigger: 'blur' }],
  password: [
    { required: true, message: 'Password is required', trigger: 'blur' },
    { min: 6, message: 'Min 6 characters', trigger: 'blur' },
  ],
}
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
  dialogTitle.value = 'Add User'
  resetForm()
  dialogVisible.value = true
}

function showEditDialog(row: UserItem) {
  formMode.value = 'edit'
  dialogTitle.value = 'Edit User'
  form.value = { id: row.id, username: row.username, email: row.email, password: '', role: row.role }
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  try {
    if (formMode.value === 'create') {
      await createUser({ username: form.value.username, email: form.value.email, password: form.value.password, role: form.value.role })
      ElMessage.success('User created')
    } else {
      const payload: Record<string, unknown> = { username: form.value.username, email: form.value.email, role: form.value.role }
      if (form.value.password) payload.password = form.value.password
      await updateUser(form.value.id, payload)
      ElMessage.success('User updated')
    }
    dialogVisible.value = false
    fetchUsers()
  } catch {
    // error handled by interceptor
  }
}

async function handleDelete(row: UserItem) {
  try {
    await ElMessageBox.confirm(`Delete user "${row.username}"?`, 'Confirm', { type: 'warning' })
    await deleteUser(row.id)
    ElMessage.success('User deleted')
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
    <h2 style="margin-bottom: 16px">User Management</h2>
    <div style="display: flex; justify-content: space-between; margin-bottom: 16px">
      <div style="display: flex; gap: 8px">
        <el-input
          v-model="search"
          placeholder="Search username..."
          clearable
          style="width: 240px"
          @clear="handleSearch"
          @keyup.enter="handleSearch"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" @click="handleSearch">Search</el-button>
      </div>
      <el-button type="primary" :icon="Plus" @click="showCreateDialog">Add User</el-button>
    </div>

    <el-table :data="users" v-loading="loading" stripe border style="width: 100%">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="username" label="Username" />
      <el-table-column prop="email" label="Email" />
      <el-table-column prop="role" label="Role" width="100">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">{{ row.role }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="create_time" label="Created" width="180" />
      <el-table-column label="Actions" width="180" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" :icon="Edit" @click="showEditDialog(row)">Edit</el-button>
          <el-button type="danger" size="small" :icon="Delete" @click="handleDelete(row)">Delete</el-button>
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
        <el-form-item label="Username" prop="username">
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="Email">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="Password" :prop="formMode === 'create' ? 'password' : undefined">
          <el-input v-model="form.password" type="password" show-password :placeholder="formMode === 'edit' ? 'Leave blank to keep current' : ''" />
        </el-form-item>
        <el-form-item label="Role">
          <el-select v-model="form.role">
            <el-option label="Regular User" value="user" />
            <el-option label="Admin" value="admin" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">Cancel</el-button>
        <el-button type="primary" @click="handleSubmit">Save</el-button>
      </template>
    </el-dialog>
  </div>
</template>
