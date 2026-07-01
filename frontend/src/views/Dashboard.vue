<script setup lang="ts">
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
</script>

<template>
  <div>
    <h2 class="page-title">{{ $t('dashboard.welcome', { name: auth.userInfo?.username || 'User' }) }}</h2>
    <el-row :gutter="20">
      <el-col :span="8">
        <el-card shadow="hover" style="border-top: 3px solid #5470e6">
          <template #header>
            <span style="font-weight: 700; color: #5470e6">{{ $t('dashboard.uploadCard') }}</span>
          </template>
          <p style="color: #555; line-height: 1.8; margin-bottom: 16px">{{ $t('dashboard.uploadDesc') }}</p>
          <el-button type="primary" @click="$router.push('/excel/upload')">{{ $t('dashboard.uploadBtn') }}</el-button>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" style="border-top: 3px solid #67c23a">
          <template #header>
            <span style="font-weight: 700; color: #67c23a">{{ $t('dashboard.previewCard') }}</span>
          </template>
          <p style="color: #555; line-height: 1.8; margin-bottom: 16px">{{ $t('dashboard.previewDesc') }}</p>
          <el-button type="primary" @click="$router.push('/excel/preview')">{{ $t('dashboard.previewBtn') }}</el-button>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" style="border-top: 3px solid #9b59b6">
          <template #header>
            <span style="font-weight: 700; color: #9b59b6">{{ $t('dashboard.reportCard') }}</span>
          </template>
          <p style="color: #555; line-height: 1.8; margin-bottom: 16px">{{ $t('dashboard.reportDesc') }}</p>
          <el-button type="primary" @click="$router.push('/report/builder')">{{ $t('dashboard.reportBtn') }}</el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>
