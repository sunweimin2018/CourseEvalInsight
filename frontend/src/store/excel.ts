import { defineStore } from 'pinia'
import { ref } from 'vue'
import { uploadFiles, getRawData, cleanData, getCleanedData } from '@/api/excel'

export interface UploadSummary {
  total_files: number
  total_rows: number
  sheets_parsed: string[]
}

export const useExcelStore = defineStore('excel', () => {
  const uploadedFiles = ref<{ name: string; size: number; status: string }[]>([])
  const uploadSummary = ref<UploadSummary | null>(null)
  const rawData = ref<{ headers: string[]; rows: Record<string, unknown>[]; total: number } | null>(null)
  const cleanedData = ref<{ headers: string[]; rows: Record<string, unknown>[]; total: number } | null>(null)
  const cleaningSummary = ref<{
    total_rows_before: number
    total_rows_after: number
    removed_duplicates: number
    removed_outliers: number
  } | null>(null)

  async function upload(formData: FormData) {
    const data = (await uploadFiles(formData)) as unknown as UploadSummary
    uploadSummary.value = data
    return data
  }

  async function fetchRawData(page: number, size: number) {
    const data = (await getRawData(page, size)) as unknown as {
      headers: string[]
      rows: Record<string, unknown>[]
      total: number
    }
    rawData.value = data
    return data
  }

  async function runClean() {
    const data = (await cleanData()) as unknown as {
      total_rows_before: number
      total_rows_after: number
      removed_duplicates: number
      removed_outliers: number
    }
    cleaningSummary.value = data
    return data
  }

  async function fetchCleanedData(page: number, size: number) {
    const data = (await getCleanedData(page, size)) as unknown as {
      headers: string[]
      rows: Record<string, unknown>[]
      total: number
    }
    cleanedData.value = data
    return data
  }

  return { uploadedFiles, uploadSummary, rawData, cleanedData, cleaningSummary, upload, fetchRawData, runClean, fetchCleanedData }
})
