<script setup>
import { ref, inject, onMounted } from 'vue'
import { useApi } from '../composables/useApi'

const BASE_URL = import.meta.env.BASE_URL === '/' ? '' : import.meta.env.BASE_URL.replace(/\/$/, '')

const toast = inject('toast')
const { api } = useApi()

const uploading = ref(false)
const result = ref(null)
const fileInput = ref(null)

async function handleFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  uploading.value = true
  result.value = null
  try {
    const formData = new FormData()
    formData.append('file', file)
    const r = await api('/api/products/import', 'POST', formData)
    if (r.error) { toast(r.error, 'danger'); return }
    result.value = r
    toast(r.message)
  } catch (err) {
    toast('导入失败', 'danger')
  } finally {
    uploading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

function exportTemplate() {
  window.open(BASE_URL + '/api/products/export-template')
}
</script>

<template>
  <div>
    <div class="page-header">
      <h5><i class="bi bi-upload"></i>导入产品</h5>
      <button class="btn btn-outline-primary btn-modern" @click="exportTemplate">
        <i class="bi bi-download"></i> 下载模板
      </button>
    </div>

    <div class="card-modern">
      <div class="text-center py-5">
        <i class="bi bi-file-earmark-excel text-success mb-3 d-block" style="font-size:4rem"></i>
        <h5>从 Excel 导入产品</h5>
        <p class="text-muted small mb-4">
          支持 .xlsx 格式，每个 Sheet 作为一个分类<br>
          表头需包含：名称、规格型号、单价、厂商等字段
        </p>

        <div class="mb-3">
          <input ref="fileInput" type="file" accept=".xlsx" class="form-control mx-auto"
            style="max-width:350px" @change="handleFile" :disabled="uploading">
        </div>

        <div v-if="uploading" class="text-primary small">
          <div class="spinner-border spinner-border-sm me-2" role="status"></div>
          正在导入...
        </div>

        <div v-if="result" class="mt-3">
          <div class="alert alert-success mx-auto" style="max-width:400px">
            <i class="bi bi-check-circle me-2"></i>
            成功导入 {{ result.imported }} 个产品
          </div>
          <div v-if="result.errors?.length" class="alert alert-warning mx-auto small" style="max-width:400px">
            <div v-for="(err, i) in result.errors.slice(0, 5)" :key="i">{{ err }}</div>
            <div v-if="result.errors.length > 5" class="mt-1">...还有 {{ result.errors.length - 5 }} 个错误</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
