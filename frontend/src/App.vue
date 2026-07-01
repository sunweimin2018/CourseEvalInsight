<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElConfigProvider } from 'element-plus'
import { getElLocale } from '@/i18n'

const { locale } = useI18n()
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const elLocale = computed(() => getElLocale(locale.value) as any)
</script>

<template>
  <el-config-provider :locale="elLocale">
    <router-view />
  </el-config-provider>
</template>
