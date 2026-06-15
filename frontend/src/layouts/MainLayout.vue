<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { UserFilled, Monitor, Upload, View, SwitchButton, Setting, User } from '@element-plus/icons-vue'

const router = useRouter()
const auth = useAuthStore()

async function handleLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <el-container style="height: 100vh">
    <el-aside width="220px" style="background: #304156">
      <div
        style="height: 60px; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 18px; font-weight: bold"
      >
        CourseEvalInsight
      </div>
      <el-menu
        :default-active="router.currentRoute.value.path"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
        router
      >
        <el-menu-item index="/dashboard">
          <el-icon><Monitor /></el-icon>
          <span>Dashboard</span>
        </el-menu-item>
        <el-menu-item index="/excel/upload">
          <el-icon><Upload /></el-icon>
          <span>Upload Excel</span>
        </el-menu-item>
        <el-menu-item index="/excel/preview">
          <el-icon><View /></el-icon>
          <span>Data Preview</span>
        </el-menu-item>
        <el-menu-item index="/user/center">
          <el-icon><User /></el-icon>
          <span>User Center</span>
        </el-menu-item>
        <el-menu-item v-if="auth.isAdmin" index="/admin/users">
          <el-icon><Setting /></el-icon>
          <span>User Management</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header
        style="display: flex; align-items: center; justify-content: flex-end; background: #fff; border-bottom: 1px solid #e6e6e6"
      >
        <el-dropdown>
          <span style="cursor: pointer; display: flex; align-items: center; gap: 8px">
            <el-icon><UserFilled /></el-icon>
            {{ auth.userInfo?.username || 'User' }}
            <el-tag v-if="auth.isAdmin" type="danger" size="small">Admin</el-tag>
          </span>
          <template #dropdown>
            <el-dropdown-item @click="router.push('/user/center')">
              <el-icon><User /></el-icon>
              User Center
            </el-dropdown-item>
            <el-dropdown-item @click="handleLogout">
              <el-icon><SwitchButton /></el-icon>
              Logout
            </el-dropdown-item>
          </template>
        </el-dropdown>
      </el-header>
      <el-main style="background: #f5f7fa">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
