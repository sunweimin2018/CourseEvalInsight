<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { ElMessage } from 'element-plus'
import { checkUsername } from '@/api/user'

const router = useRouter()
const auth = useAuthStore()
const form = ref({ username: '', password: '', confirmPassword: '', phone: '', email: '' })
const loading = ref(false)
const usernameError = ref('')
let checkTimer: ReturnType<typeof setTimeout> | null = null

function validateUsernameFormat(val: string): string {
  if (!val) return ''
  if (val.length < 3) return ''
  if (val[0] >= '0' && val[0] <= '9') return '用户名不能以数字开头'
  if (!/^[a-zA-Z0-9]+$/.test(val)) return '用户名只能由字母和数字组成'
  return ''
}

watch(
  () => form.value.username,
  (val) => {
    if (checkTimer) clearTimeout(checkTimer)
    usernameError.value = validateUsernameFormat(val)
    if (usernameError.value) return
    if (!val || val.length < 3) return
    checkTimer = setTimeout(async () => {
      try {
        const data = await checkUsername(val) as unknown as { exists: boolean }
        if (data.exists) {
          usernameError.value = '该用户已存在，请输入其他用户名'
        }
      } catch {
        // ignore network errors during typing
      }
    }, 500)
  },
)

async function handleRegister() {
  if (!form.value.username) {
    ElMessage.warning('Please enter a username')
    return
  }
  const formatErr = validateUsernameFormat(form.value.username)
  if (formatErr) {
    ElMessage.warning(formatErr)
    return
  }
  if (usernameError.value) {
    ElMessage.warning('Please use a different username')
    return
  }
  if (!form.value.password) {
    ElMessage.warning('Please enter a password')
    return
  }
  if (form.value.password.length < 6) {
    ElMessage.warning('Password must be at least 6 characters')
    return
  }
  if (form.value.password !== form.value.confirmPassword) {
    ElMessage.warning('Passwords do not match')
    return
  }
  loading.value = true
  try {
    await auth.register(form.value.username, form.value.password, form.value.phone || undefined, form.value.email || undefined)
    router.push('/dashboard')
  } catch {
    // error message already shown by Axios interceptor
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-container">
    <div class="login-card" style="padding: 50px 40px 40px">
      <h2 class="login-title">Create Account</h2>
      <el-form label-width="100px" @submit.prevent="handleRegister">
        <el-form-item :error="usernameError" label="Username" required>
          <el-input v-model="form.username" placeholder="Letters + digits, start with letter" size="large" clearable />
        </el-form-item>
        <el-form-item label="Password" required>
          <el-input
            v-model="form.password"
            type="password"
            placeholder="Min 6 characters"
            size="large"
            show-password
          />
        </el-form-item>
        <el-form-item label="Confirm" required>
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="Re-enter password"
            size="large"
            show-password
            @keyup.enter="handleRegister"
          />
        </el-form-item>
        <el-form-item label="Phone">
          <el-input v-model="form.phone" placeholder="Optional" size="large" clearable />
        </el-form-item>
        <el-form-item label="Email">
          <el-input v-model="form.email" placeholder="Optional" size="large" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="handleRegister">
            Register
          </el-button>
        </el-form-item>
      </el-form>
      <div style="text-align: center">
        Already have an account?
        <router-link to="/login">Login</router-link>
      </div>
    </div>
  </div>
</template>
