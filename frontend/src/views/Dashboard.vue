<script setup lang="ts">
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
</script>

<template>
  <div>
    <h2 style="margin-bottom: 20px">Welcome, {{ auth.userInfo?.username || 'User' }}</h2>
    <el-row :gutter="20">
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>Upload Excel</template>
          <p style="color: #606266">Upload and parse multiple Excel files for analysis.</p>
          <el-button type="primary" @click="$router.push('/excel/upload')">Go Upload</el-button>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>Data Preview</template>
          <p style="color: #606266">Preview raw and cleaned data before analysis.</p>
          <el-button type="primary" @click="$router.push('/excel/preview')">Go Preview</el-button>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>Reports</template>
          <p style="color: #606266">Generate and download analysis reports.</p>
          <el-button disabled>Coming Soon</el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>
