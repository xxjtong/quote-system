<script setup>
import { ref, inject, computed, onMounted } from 'vue'
import { useApi } from '../composables/useApi'
import { useAdvancedApi } from '../composables/useAdvancedApi'

const toast = inject('toast')
const { api, apiRaw, isAdmin } = useApi()
const { dicts, categories } = useAdvancedApi()

const uploading = ref(false)
const previewing = ref(false)
const exporting = ref(false)
const categoryList = ref([])
const typeList = ref([])
const manufacturerList = ref([])

onMounted(async () => {
  try {
    const [cats, types, mfrs] = await Promise.all([
      categories.list(), dicts.productTypes(), dicts.manufacturers(),
    ])
    categoryList.value = cats?.items || []
    typeList.value = types?.items || []
    manufacturerList.value = mfrs?.items || []
  } catch {}
})
const importing = ref(false)
const result = ref(null)
const previewData = ref(null)  // { products: [...], total, sheet_count }
const selectedAll = ref(false)
const fileInput = ref(null)

const exportLabel = computed(() => isAdmin.value ? '导出全部产品' : '导出我的产品')

const selectedCount = computed(() => {
  if (!previewData.value?.products) return 0
  return previewData.value.products.filter(p => p._selected).length
})

async function handleFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  uploading.value = true
  result.value = null
  previewData.value = null
  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('preview', '1')  // preview mode
    const r = await api('/api/products/import-preview', 'POST', formData)
    if (r.error) { toast(r.error, 'danger'); return }
    previewData.value = r
    previewing.value = true
  } catch (err) {
    toast('解析失败', 'danger')
  } finally {
    uploading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

function toggleAll() {
  selectedAll.value = !selectedAll.value
  previewData.value.products.forEach(p => { p._selected = selectedAll.value })
}

function cancelPreview() {
  previewing.value = false
  previewData.value = null
}

async function confirmImport() {
  const selected = previewData.value.products.filter(p => p._selected)
  if (!selected.length) { toast('请选择要导入的产品', 'warning'); return }
  importing.value = true
  try {
    const r = await api('/api/products/import-confirm', 'POST', { products: selected })
    if (r.error) { toast(r.error, 'danger'); return }
    toast(r.message || `成功导入 ${r.imported} 个产品`)
    previewing.value = false
    previewData.value = null
  } catch (err) {
    toast('导入失败', 'danger')
  } finally {
    importing.value = false
  }
}

async function exportTemplate() {
  try {
    const r = await apiRaw('/api/products/export-template')
    if (!r) return
    const blob = await r.blob()
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = '产品导入模板.xlsx'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(a.href)
  } catch (err) {
    toast('下载模板失败', 'danger')
  }
}

async function exportAll() {
  exporting.value = true
  try {
    const r = await apiRaw('/api/products/export-all')
    if (!r || !r.ok) { toast('导出失败', 'danger'); return }
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
          <div class="spinner-border spinner-border-sm me-2" role="status"></div>正在解析文件，请稍候...
        </div>
      </div>
    </div>

    <!-- Preview Table -->
    <div v-if="previewing && previewData" class="card-modern mt-3">
      <div class="d-flex justify-content-between align-items-center p-3 border-bottom">
        <div>
          <h6 class="mb-0"><i class="bi bi-table me-2"></i>预览导入数据</h6>
          <small class="text-muted">共 {{ previewData.total }} 条，已选 {{ selectedCount }} 条</small>
        </div>
        <div class="d-flex gap-2">
          <button class="btn btn-outline-secondary btn-sm" @click="toggleAll">
            {{ selectedAll ? '取消全选' : '全选' }}
          </button>
          <button class="btn btn-outline-danger btn-sm" @click="cancelPreview">取消</button>
          <button class="btn btn-primary btn-sm" @click="confirmImport" :disabled="importing || selectedCount === 0">
            <span v-if="importing" class="spinner-border spinner-border-sm me-1"></span>
            <span v-else><i class="bi bi-check-lg me-1"></i>导入选中 ({{ selectedCount }})</span>
          </button>
        </div>
      </div>
      <div class="table-responsive" style="max-height:60vh;overflow-y:auto">
        <table class="table table-modern table-sm mb-0">
          <thead style="position:sticky;top:0;z-index:2">
            <tr>
              <th style="width:36px">
                <input type="checkbox" class="form-check-input" :checked="selectedAll" @change="toggleAll">
              </th>
              <th>产品名称</th>
              <th>型号</th>
              <th>品类</th>
              <th>类型</th>
              <th>厂商</th>
              <th>单价</th>
              <th>描述</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(p, idx) in previewData.products" :key="idx"
              :style="p._selected ? 'background:#fff3cd' : 'background:#fff'"
              :class="{ 'opacity-50': !p.name }">
              <td>
                <input type="checkbox" class="form-check-input" v-model="p._selected"
                  @change="selectedAll = false">
              </td>
              <td>
                <span v-if="p.name" class="fw-medium">{{ p.name }}</span>
                <span v-else class="text-danger small">必填</span>
              </td>
              <td class="text-muted small" style="font-family:monospace">{{ p.model || p.sku || '—' }}</td>
              <td>
                <select v-if="categoryList.length" v-model="p.category" class="form-select form-select-sm" style="width:100px;font-size:.75rem">
                  <option value="">—</option>
                  <option v-for="c in categoryList" :key="c.id" :value="c.name">{{ c.name }}</option>
                  <option value="__custom__">✏️ 手动输入…</option>
                </select>
                <input v-if="p.category === '__custom__' || !categoryList.length" v-model="p.category" class="form-control form-control-sm" style="width:100px;font-size:.75rem" placeholder="输入品类" />
              </td>
              <td style="position:relative">
                <input v-model="p.product_type" class="form-control form-control-sm" style="width:80px;font-size:.75rem"
                  list="type-list" :class="{ 'border-primary fw-medium': typeList.some(t => t.name === p.product_type) }" placeholder="类型" />
              </td>
              <td style="position:relative">
                <input v-model="p.manufacturer" class="form-control form-control-sm" style="width:90px;font-size:.75rem"
                  list="mfr-list" :class="{ 'border-primary fw-medium': manufacturerList.some(m => m.name === p.manufacturer) }" />
              </td>
              <td class="text-end">{{ p.price ? '¥' + Number(p.price).toFixed(2) : '—' }}</td>
              <td class="text-muted small text-truncate" style="max-width:150px">{{ p.function_desc || '—' }}</td>
              <td>
                <span v-if="p._status === 'exists'" class="badge bg-warning text-dark">已存在</span>
                <span v-else class="badge bg-success">新</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <datalist id="cat-list"><option v-for="c in categoryList" :key="c.id" :value="c.name" /></datalist>
      <datalist id="type-list"><option v-for="t in typeList" :key="t.id" :value="t.name" /></datalist>
      <datalist id="mfr-list"><option v-for="m in manufacturerList" :key="m.id" :value="m.name" /></datalist>
    </div>

    <div v-if="result" class="alert alert-success mt-3">
      <i class="bi bi-check-circle me-2"></i>
      成功导入 {{ result.imported }} 个产品
    </div>
  </div>
</template>
