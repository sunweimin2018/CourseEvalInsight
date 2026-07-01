import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN'
import en from './locales/en'
// @ts-ignore element-plus locale types are provided at runtime
import zhCnEl from 'element-plus/es/locale/lang/zh-cn'
// @ts-ignore
import enEl from 'element-plus/es/locale/lang/en'

export const LOCALE_KEY = 'app-locale'
export const DEFAULT_LOCALE = 'zh-CN'

export function getSavedLocale(): string {
  return localStorage.getItem(LOCALE_KEY) || DEFAULT_LOCALE
}

export function saveLocale(locale: string) {
  localStorage.setItem(LOCALE_KEY, locale)
}

export const i18n = createI18n({
  legacy: false,
  locale: getSavedLocale(),
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': zhCN,
    en,
  },
})

const elLocaleMap: Record<string, unknown> = {
  'zh-CN': zhCnEl,
  en: enEl,
}

export function getElLocale(locale: string): unknown {
  return elLocaleMap[locale] || zhCnEl
}
