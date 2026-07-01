<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'

const router = useRouter()
const auth = useAuthStore()
const form = ref({ username: '', password: '' })
const loading = ref(false)

async function handleLogin() {
  if (!form.value.username || !form.value.password) return
  loading.value = true
  try {
    await auth.login(form.value.username, form.value.password)
    router.push('/dashboard')
  } catch {
    // Error already shown by interceptor
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-container">
    <div class="login-card" style="padding: 50px 40px 40px">
      <h2 class="login-title">{{ $t('auth.loginTitle') }}</h2>
      <el-form @submit.prevent="handleLogin">
        <el-form-item>
          <el-input v-model="form.username" :placeholder="$t('auth.usernamePlaceholder')" size="large" clearable />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="form.password"
            type="password"
            :placeholder="$t('auth.passwordPlaceholder')"
            size="large"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="handleLogin">
            {{ $t('auth.loginBtn') }}
          </el-button>
        </el-form-item>
      </el-form>
      <div style="text-align: center">
        {{ $t('auth.noAccount') }}
        <router-link to="/register">{{ $t('auth.register') }}</router-link>
      </div>
    </div>
  </div>
</template>
