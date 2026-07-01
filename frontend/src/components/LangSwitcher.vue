<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { saveLocale } from '@/i18n'

const { locale } = useI18n()

function switchTo(loc: string) {
  locale.value = loc
  saveLocale(loc)
}
</script>

<template>
  <span class="lang-switcher">
    <el-button
      v-if="locale !== 'zh-CN'"
      text
      size="small"
      @click="switchTo('zh-CN')"
    >
      中文
    </el-button>
    <el-button
      v-if="locale !== 'en'"
      text
      size="small"
      @click="switchTo('en')"
    >
      English
    </el-button>
  </span>
</template>
