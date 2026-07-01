<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { useExcelStore } from '@/store/excel'
import { UserFilled, Monitor, Upload, View, SwitchButton, Setting, User, Document } from '@element-plus/icons-vue'
import LangSwitcher from '@/components/LangSwitcher.vue'

const router = useRouter()
const auth = useAuthStore()
const excelStore = useExcelStore()

async function handleLogout() {
  await auth.logout()
  excelStore.clearAll()
  router.push('/login')
}
</script>

<template>
  <el-container style="height: 100%; min-height: 100vh; overflow: hidden">
    <el-aside width="220px" style="background: #304156; overflow-y: auto; overflow-x: hidden">
      <div
        style="height: 60px; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 18px; font-weight: bold; flex-shrink: 0"
      >
        {{ $t('nav.appTitle') }}
      </div>
      <el-menu
        :default-active="router.currentRoute.value.path"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
        router
        style="border-right: none"
      >
        <el-menu-item index="/dashboard">
          <el-icon><Monitor /></el-icon>
          <span>{{ $t('nav.dashboard') }}</span>
        </el-menu-item>
        <el-menu-item index="/excel/upload">
          <el-icon><Upload /></el-icon>
          <span>{{ $t('nav.uploadFiles') }}</span>
        </el-menu-item>
        <el-menu-item index="/excel/preview">
          <el-icon><View /></el-icon>
          <span>{{ $t('nav.dataPreview') }}</span>
        </el-menu-item>
        <el-menu-item index="/report/builder">
          <el-icon><Document /></el-icon>
          <span>{{ $t('nav.reportBuilder') }}</span>
        </el-menu-item>
        <el-menu-item index="/report/generate">
          <el-icon><Document /></el-icon>
          <span>{{ $t('nav.reportPreview') }}</span>
        </el-menu-item>
        <el-menu-item index="/user/center">
          <el-icon><User /></el-icon>
          <span>{{ $t('nav.userCenter') }}</span>
        </el-menu-item>
        <el-menu-item v-if="auth.isAdmin" index="/admin/users">
          <el-icon><Setting /></el-icon>
          <span>{{ $t('nav.userManagement') }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container style="flex-direction: column; height: 100%">
      <el-header
        style="display: flex; align-items: center; justify-content: flex-end; background: #fff; border-bottom: 1px solid #e6e6e6; flex-shrink: 0; height: 60px"
      >
        <LangSwitcher style="margin-right: 16px" />
        <el-dropdown>
          <span style="cursor: pointer; display: flex; align-items: center; gap: 8px">
            <el-icon><UserFilled /></el-icon>
            {{ auth.userInfo?.username || 'User' }}
            <el-tag v-if="auth.isAdmin" type="danger" size="small">{{ $t('nav.admin') }}</el-tag>
          </span>
          <template #dropdown>
            <el-dropdown-item @click="router.push('/user/center')">
              <el-icon><User /></el-icon>
              {{ $t('nav.userCenter') }}
            </el-dropdown-item>
            <el-dropdown-item @click="handleLogout">
              <el-icon><SwitchButton /></el-icon>
              {{ $t('nav.logout') }}
            </el-dropdown-item>
          </template>
        </el-dropdown>
      </el-header>
      <el-main style="background: #f5f7fa; overflow-y: auto; flex: 1">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
