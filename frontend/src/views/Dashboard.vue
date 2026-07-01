<script setup lang="ts">
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
</script>

<template>
  <div>
    <h2 style="margin-bottom: 20px">{{ $t('dashboard.welcome', { name: auth.userInfo?.username || 'User' }) }}</h2>
    <el-row :gutter="20">
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>{{ $t('dashboard.uploadCard') }}</template>
          <p style="color: #606266">{{ $t('dashboard.uploadDesc') }}</p>
          <el-button type="primary" @click="$router.push('/excel/upload')">{{ $t('dashboard.uploadBtn') }}</el-button>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>{{ $t('dashboard.previewCard') }}</template>
          <p style="color: #606266">{{ $t('dashboard.previewDesc') }}</p>
          <el-button type="primary" @click="$router.push('/excel/preview')">{{ $t('dashboard.previewBtn') }}</el-button>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>{{ $t('dashboard.reportCard') }}</template>
          <p style="color: #606266">{{ $t('dashboard.reportDesc') }}</p>
          <el-button type="primary" @click="$router.push('/report/builder')">{{ $t('dashboard.reportBtn') }}</el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>
