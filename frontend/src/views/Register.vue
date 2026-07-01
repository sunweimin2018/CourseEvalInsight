<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/store/auth'
import { ElMessage } from 'element-plus'
import { checkUsername } from '@/api/user'

const router = useRouter()
const auth = useAuthStore()
const { t } = useI18n()
const form = ref({ username: '', password: '', confirmPassword: '', phone: '', email: '' })
const loading = ref(false)
const usernameError = ref('')
let checkTimer: ReturnType<typeof setTimeout> | null = null

function validateUsernameFormat(val: string): string {
  if (!val) return ''
  if (val.length < 3) return ''
  if (val[0] >= '0' && val[0] <= '9') return t('auth.usernameNoDigitStart')
  if (!/^[a-zA-Z0-9]+$/.test(val)) return t('auth.usernameAlphanumeric')
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
        const data = (await checkUsername(val)) as unknown as { exists: boolean }
        if (data.exists) {
          usernameError.value = t('auth.usernameExists')
        }
      } catch {
        // ignore network errors during typing
      }
    }, 500)
  },
)

async function handleRegister() {
  if (!form.value.username) {
    ElMessage.warning(t('auth.usernameRequired'))
    return
  }
  const formatErr = validateUsernameFormat(form.value.username)
  if (formatErr) {
    ElMessage.warning(formatErr)
    return
  }
  if (usernameError.value) {
    ElMessage.warning(t('auth.usernameExists'))
    return
  }
  if (!form.value.password) {
    ElMessage.warning(t('auth.passwordRequired'))
    return
  }
  if (form.value.password.length < 6) {
    ElMessage.warning(t('auth.passwordMinLength'))
    return
  }
  if (form.value.password !== form.value.confirmPassword) {
    ElMessage.warning(t('auth.passwordsMismatch'))
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
      <h2 class="login-title">{{ $t('auth.createAccount') }}</h2>
      <el-form label-width="100px" @submit.prevent="handleRegister">
        <el-form-item :error="usernameError" :label="$t('auth.username')" required>
          <el-input v-model="form.username" :placeholder="$t('auth.usernameHint')" size="large" clearable />
        </el-form-item>
        <el-form-item :label="$t('auth.password')" required>
          <el-input
            v-model="form.password"
            type="password"
            :placeholder="$t('auth.passwordHint')"
            size="large"
            show-password
          />
        </el-form-item>
        <el-form-item :label="$t('auth.confirmPassword')" required>
          <el-input
            v-model="form.confirmPassword"
            type="password"
            :placeholder="$t('auth.confirmPasswordPlaceholder')"
            size="large"
            show-password
            @keyup.enter="handleRegister"
          />
        </el-form-item>
        <el-form-item :label="$t('auth.phone')">
          <el-input v-model="form.phone" :placeholder="$t('auth.phonePlaceholder')" size="large" clearable />
        </el-form-item>
        <el-form-item :label="$t('auth.email')">
          <el-input v-model="form.email" :placeholder="$t('auth.emailPlaceholder')" size="large" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="handleRegister">
            {{ $t('auth.registerBtn') }}
          </el-button>
        </el-form-item>
      </el-form>
      <div style="text-align: center">
        {{ $t('auth.hasAccount') }}
        <router-link to="/login">{{ $t('auth.login') }}</router-link>
      </div>
    </div>
  </div>
</template>
