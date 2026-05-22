<script setup>
import { ref, inject, computed } from 'vue'
import { useApi, BASE_URL } from '../composables/useApi'

const toast = inject('toast')
const { api, authToken, isAdmin } = useApi()

const uploading = ref(false)
const exporting = ref(false)
const result = ref(null)
const fileInput = ref(null)

const exportLabel = computed(() => isAdmin.value ? '导出全部产品' : '导出我的产品')

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
  const token = authToken.value
  const url = BASE_URL + '/api/products/export-template' + (token ? '?token=' + encodeURIComponent(token) : '')
  const a = document.createElement('a')
  a.href = url
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

async function exportAll() {
  exporting.value = true
  try {
    const token = authToken.value
    const r = await fetch(BASE_URL + '/api/products/export-all', {
      headers: { Authorization: 'Bearer ' + token }
    })
    if (!r.ok) { toast('导出失败 (' + r.status + ')', 'danger'); return }
    const blob = await r.blob()
    const cd = r.headers.get('Content-Disposition') || ''
    let fname = 'products_export.xlsx'
    const mStar = cd.match(/filename\*=UTF-8''(.+?)(?:;|$)/)
    if (mStar && mStar[1]) {
      fname = decodeURIComponent(mStar[1])
    } else {
      const m = cd.match(/filename="?([^";\n]+)"?/)
      if (m && m[1] && m[1] !== '.xlsx') fname = m[1].replace(/\\"/g, '')
    }
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = fname
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(a.href)
    toast('导出成功')
  } catch (err) {
    toast('导出失败', 'danger')
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h5><i class="bi bi-arrow-left-right"></i> 导入 / 导出产品</h5>
      <div style="display:flex;gap:8px">
        <button class="btn btn-outline-primary btn-modern" @click="exportTemplate">
          <i class="bi bi-download"></i> 下载模板
        </button>
        <button class="btn btn-success btn-modern" @click="exportAll" :disabled="exporting">
          <span v-if="exporting" class="spinner-border spinner-border-sm me-1"></span>
          <i v-else class="bi bi-box-arrow-down me-1"></i>{{ exportLabel }}
        </button>
      </div>
    </div>

    <div class="card-modern">
      <div class="text-center py-5">
        <i class="bi bi-file-earmark-excel text-success mb-3 d-block" style="font-size:4rem"></i>
        <h5>从 Excel 导入产品</h5>
        <p class="text-muted small mb-4">
          支持 .xlsx 格式，每个 Sheet 作为一个分类<br>
          表头需包含：名称、规格型号、功能描述、单价等字段<br>
          支持备注列嵌入图片（自动提取并压缩）
        </p>

        <div class="mb-3">
          <input ref="fileInput" type="file" accept=".xlsx" class="form-control mx-auto"
            style="max-width:350px" @change="handleFile" :disabled="uploading">
        </div>

        <div v-if="uploading" class="text-primary small">
          <div class="spinner-border spinner-border-sm me-2" role="status"></div>正在导入，请稍候...
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
