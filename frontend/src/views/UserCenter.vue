<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { UserFilled } from '@element-plus/icons-vue'
import { getProfile, updateProfile } from '@/api/user'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()

const profileForm = ref({ username: '', email: '', phone: '' })
const passwordForm = ref({ current_password: '', new_password: '', confirm_password: '' })
const profileLoading = ref(false)
const passwordLoading = ref(false)
const profileFormRef = ref()
const passwordFormRef = ref()

const profileRules = {
  username: [{ required: true, message: 'Username is required', trigger: 'blur' }],
}
const passwordRules = {
  current_password: [{ required: true, message: 'Current password is required', trigger: 'blur' }],
  new_password: [
    { required: true, message: 'New password is required', trigger: 'blur' },
    { min: 6, message: 'Min 6 characters', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: 'Please confirm new password', trigger: 'blur' },
    {
      validator: (_rule: unknown, value: string, callback: (err?: Error) => void) => {
        if (value !== passwordForm.value.new_password) {
          callback(new Error('Passwords do not match'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

async function fetchProfile() {
  try {
    const data = (await getProfile()) as unknown as {
      id: number
      username: string
      email: string
      phone: string
    }
    profileForm.value.username = data.username ?? ''
    profileForm.value.email = data.email ?? ''
    profileForm.value.phone = data.phone ?? ''
  } catch {
    // handled by interceptor
  }
}

async function handleProfileSave() {
  const valid = await profileFormRef.value?.validate().catch(() => false)
  if (!valid) return
  profileLoading.value = true
  try {
    await updateProfile({
      username: profileForm.value.username,
      email: profileForm.value.email,
      phone: profileForm.value.phone,
    })
    if (auth.userInfo) {
      auth.userInfo.username = profileForm.value.username
    }
    ElMessage.success('Profile updated')
  } catch {
    // handled by interceptor
  } finally {
    profileLoading.value = false
  }
}

async function handlePasswordChange() {
  const valid = await passwordFormRef.value?.validate().catch(() => false)
  if (!valid) return
  passwordLoading.value = true
  try {
    await updateProfile({
      current_password: passwordForm.value.current_password,
      new_password: passwordForm.value.new_password,
    })
    ElMessage.success('Password changed. Please login again.')
    passwordForm.value = { current_password: '', new_password: '', confirm_password: '' }
    setTimeout(() => auth.logout(), 1500)
  } catch {
    // handled by interceptor
  } finally {
    passwordLoading.value = false
  }
}

onMounted(() => {
  fetchProfile()
})
</script>

<template>
  <div style="max-width: 600px; margin: 0 auto">
    <h2 style="margin-bottom: 24px">User Center</h2>

    <el-card style="margin-bottom: 24px">
      <template #header>
        <span><el-icon><UserFilled /></el-icon> Profile Information</span>
      </template>
      <el-form ref="profileFormRef" :model="profileForm" :rules="profileRules" label-width="120px">
        <el-form-item label="Username" prop="username">
          <el-input v-model="profileForm.username" />
        </el-form-item>
        <el-form-item label="Email">
          <el-input v-model="profileForm.email" />
        </el-form-item>
        <el-form-item label="Phone">
          <el-input v-model="profileForm.phone" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="profileLoading" @click="handleProfileSave">Save Changes</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <template #header>
        <span>Change Password</span>
      </template>
      <el-form ref="passwordFormRef" :model="passwordForm" :rules="passwordRules" label-width="160px">
        <el-form-item label="Current Password" prop="current_password">
          <el-input v-model="passwordForm.current_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="New Password" prop="new_password">
          <el-input v-model="passwordForm.new_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="Confirm Password" prop="confirm_password">
          <el-input v-model="passwordForm.confirm_password" type="password" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="warning" :loading="passwordLoading" @click="handlePasswordChange">Change Password</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>
