<script setup>
import { ref, reactive, computed, onMounted, inject } from 'vue'
import { useApi } from '../composables/useApi'
import { formatMoney, escHtml } from '../composables/useUtils'

const BASE_URL = import.meta.env.BASE_URL === '/' ? '' : import.meta.env.BASE_URL.replace(/\/$/, '')

const toast = inject('toast')
const { api, isAdmin } = useApi()

// ─── State ───
const products = ref([])
const categories = ref([])
const suppliers = ref([])
const totalProducts = ref(0)
const currentPage = ref(1)
const perPage = ref(20)
const totalPages = computed(() => Math.max(1, Math.ceil(totalProducts.value / perPage.value)))

const searchTerm = ref('')
const categoryFilter = ref('')
const supplierFilter = ref('')
const selectedIds = reactive(new Set())
const sortBy = ref('id')
const sortOrder = ref('desc')
const loading = ref(false)

let cacheVersion = null

// ─── IME composition ───
const isComposing = ref(false)
function onCompositionStart() { isComposing.value = true }
function onCompositionEnd(e) {
  isComposing.value = false
  debouncedSearch(e.target.value)
}

// ─── Debounced search ───
let searchTimer = null
function debouncedSearch(val) {
  if (isComposing.value) return
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    searchTerm.value = val
    currentPage.value = 1
    fetchProducts()
  }, 500)
}
function clearSearch() {
  searchTerm.value = ''
  currentPage.value = 1
  fetchProducts()
}

// ─── Fetch products ───
async function fetchProducts() {
  loading.value = true
  try {
    const params = new URLSearchParams({
      page: currentPage.value,
      per_page: perPage.value,
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
    })
    if (searchTerm.value) params.set('search', searchTerm.value)
    if (categoryFilter.value) params.set('category', categoryFilter.value)
    if (supplierFilter.value) params.set('supplier', supplierFilter.value)

    const data = await api(`/api/products?${params}`)
    if (!data.error) {
      products.value = data.products || []
      totalProducts.value = data.total || 0
      categories.value = data.categories || []
      suppliers.value = data.suppliers || []
      cacheVersion = data.version
    }
  } catch (e) {
    toast('加载产品失败', 'danger')
  } finally {
    loading.value = false
  }
}

// ─── Tooltip ───
function productTooltip(p) {
  const parts = [p.name]
  if (p.function_desc) parts.push('功能: ' + p.function_desc)
  if (p.spec) parts.push('规格: ' + p.spec)
  if (p.supplier) parts.push('厂商: ' + p.supplier)
  if (p.remark) parts.push('备注: ' + p.remark)
  if (p.cost_price) parts.push('成本: ¥' + p.cost_price)
  return parts.join('\n')
}

function imageSrc(p) {
  if (!p.image_url) return ''
  return p.image_url.startsWith('http') ? p.image_url : BASE_URL + p.image_url
}

// ─── Select all / single (admin only) ───
const allSelected = computed(() =>
  products.value.length > 0 && products.value.every(p => selectedIds.has(p.id))
)

function toggleAll() {
  if (allSelected.value) {
    products.value.forEach(p => selectedIds.delete(p.id))
  } else {
    products.value.forEach(p => selectedIds.add(p.id))
  }
}

function toggleSelect(id) {
  if (selectedIds.has(id)) selectedIds.delete(id)
  else selectedIds.add(id)
}

// ─── Batch delete ───
async function batchDelete() {
  if (selectedIds.size === 0) return
  if (!confirm(`确定删除选中的 ${selectedIds.size} 个产品吗？`)) return
  const r = await api('/api/products/batch-delete', 'POST', {
    ids: Array.from(selectedIds)
  })
  if (r.error) { toast(r.error, 'danger'); return }
  selectedIds.clear()
  toast(r.message)
  fetchProducts()
}

// ─── Delete single ───
async function deleteProduct(id) {
  if (!confirm('确定删除该产品吗？')) return
  const r = await api(`/api/products/${id}`, 'DELETE')
  if (r.error) { toast(r.error, 'danger'); return }
  selectedIds.delete(id)
  toast('已删除')
  fetchProducts()
}

// ─── Toggle active (admin) ───
async function toggleActive(id) {
  const r = await api(`/api/products/${id}/toggle-active`, 'PUT')
  if (r.error) { toast(r.error, 'danger'); return }
  toast(r.is_active ? '已恢复' : '已停用')
  fetchProducts()
}

// ─── Export template ───
function exportTemplate() {
  window.open(BASE_URL + '/api/products/export-template')
}

// ─── Image preview modal ───
const previewImage = ref('')

// ─── Product detail modal ───
const detailProduct = ref(null)
function showDetail(p) {
  detailProduct.value = p
}

function detailImageSrc(p) {
  if (!p || !p.image_url) return ''
  return p.image_url.startsWith('http') ? p.image_url : BASE_URL + p.image_url
}

// ─── Product Form Modal ───
const showForm = ref(false)
const formTitle = ref('')
const editingId = ref(null)
const formData = reactive({
  name: '', category: '', spec: '', unit: '', price: '',
  cost_price: '', supplier: '', function_desc: '', remark: '', image_url: ''
})
const existingImageUrl = ref('')  // 编辑时保留已有图片URL（不填入输入框）
const formSaving = ref(false)
const imageDownloading = ref(false)

function showAddProduct() {
  editingId.value = null
  formTitle.value = '新增产品'
  formData.name = ''; formData.category = ''; formData.spec = ''; formData.unit = ''
  formData.price = ''; formData.cost_price = ''; formData.supplier = ''
  formData.function_desc = ''; formData.remark = ''; formData.image_url = ''
  existingImageUrl.value = ''
  smartResult.value = null
  smartError.value = ''
  imageDownloading.value = false
  smartRecognizing.value = false
  showForm.value = true
}

function showEditProduct(p) {
  editingId.value = p.id
  formTitle.value = '编辑产品'
  formData.name = p.name || ''
  formData.category = p.category || ''
  formData.spec = p.spec || ''
  formData.unit = p.unit || ''
  formData.price = p.price || ''
  formData.cost_price = p.cost_price || ''
  formData.supplier = p.supplier || ''
  formData.function_desc = p.function_desc || ''
  formData.remark = p.remark || ''
  formData.image_url = ''  // 不预填已有URL，保留在预览区
  existingImageUrl.value = p.image_url || ''
  smartResult.value = null
  smartError.value = ''
  smartRecognizing.value = false
  showForm.value = true
}

// ─── Auto-download image on blur/enter ───
async function onImageUrlBlur() {
  const url = formData.image_url.trim()
  if (!url || !url.startsWith('http')) return
  // 如果已经是本地路径则跳过
  if (url.startsWith('/uploads/')) return
  imageDownloading.value = true
  try {
    const r = await api('/api/download-image', 'POST', { url })
    if (r.url) {
      formData.image_url = r.url
      toast('图片已保存到本地')
    } else {
      toast(r.error || '下载失败', 'warning')
    }
  } catch (e) {
    toast('下载失败', 'warning')
  } finally {
    imageDownloading.value = false
  }
}

function onImageUrlKeydown(e) {
  if (e.key === 'Enter') {
    e.preventDefault()
    onImageUrlBlur()
  }
}

// ─── Smart Paste Handler ───
const smartRecognizing = ref(false)
const smartResult = ref(null)
const smartError = ref('')

async function onSmartPaste(e) {
  const items = e.clipboardData?.items
  if (!items) return

  for (const item of items) {
    // 模式1: 图片粘贴
    if (item.type.startsWith('image/')) {
      e.preventDefault()
      const blob = item.getAsFile()
      if (!blob) continue
      smartRecognizing.value = true
      smartError.value = ''
      smartResult.value = null
      try {
        const form = new FormData()
        form.append('file', blob, 'smart.' + (item.type.split('/')[1] || 'png'))
        const r = await api('/api/products/recognize', 'POST', form)
        if (r.products && r.products.length > 0) {
          smartResult.value = r.products[0]
        } else {
          smartError.value = r.error || '未能识别出产品信息'
        }
      } catch (err) {
        smartError.value = '识别失败，请重试'
      } finally {
        smartRecognizing.value = false
      }
      return
    }

    // 模式2: 文字粘贴
    if (item.type === 'text/plain' || item.type === 'text/html') {
      e.preventDefault()
      item.getAsString(async (str) => {
        const text = str.trim()
        if (!text || text.length < 3) return
        smartRecognizing.value = true
        smartError.value = ''
        smartResult.value = null
        try {
          const r = await api('/api/products/recognize', 'POST', { text })
          if (r.products && r.products.length > 0) {
            smartResult.value = r.products[0]
          } else {
            smartError.value = r.error || '未能识别出产品信息'
          }
        } catch (err) {
          smartError.value = '识别失败，请重试'
        } finally {
          smartRecognizing.value = false
        }
      })
      return
    }
  }
}

function fillFromSmartResult() {
  if (!smartResult.value) return
  const s = smartResult.value
  if (s.name) formData.name = s.name
  if (s.spec) formData.spec = s.spec
  if (s.supplier) formData.supplier = s.supplier
  if (s.price) formData.price = s.price
  if (s.cost_price) formData.cost_price = s.cost_price
  if (s.function_desc) formData.function_desc = s.function_desc
  if (s.remark) formData.remark = s.remark
  if (s.unit) formData.unit = s.unit
  if (s.category) formData.category = s.category
  smartResult.value = null
  toast('已填入识别结果')
}

function clearSmartResult() {
  smartResult.value = null
  smartError.value = ''
}
// ─── Image paste handler (图片URL区域)
const imageUploading = ref(false)
async function onImagePaste(e) {
  const items = e.clipboardData?.items
  if (!items) return
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      e.preventDefault()
      const blob = item.getAsFile()
      if (!blob) continue
      imageUploading.value = true
      try {
        const form = new FormData()
        form.append('file', blob, 'paste.' + (item.type.split('/')[1] || 'png'))
        const r = await api('/api/upload/image', 'POST', form)
        if (r.url) {
          formData.image_url = r.url
          toast('图片已上传')
        } else {
          toast(r.error || '上传失败', 'warning')
        }
      } catch (err) {
        toast('上传失败', 'warning')
      } finally {
        imageUploading.value = false
      }
      return
    }
  }
}

// ─── Preview image (for saved local images) ───
function currentImagePreview() {
  const url = existingImageUrl.value || formData.image_url.trim()
  if (!url) return ''
  return url.startsWith('http') ? url : BASE_URL + url
}

function deleteImage() {
  existingImageUrl.value = ''
  formData.image_url = ''
}

function closeForm() {
  showForm.value = false
  smartResult.value = null
  smartError.value = ''
  smartRecognizing.value = false
  imageDownloading.value = false
}

async function saveProduct() {
  if (!formData.name.trim()) {
    toast('请输入产品名称', 'warning')
    return
  }
  formSaving.value = true
  try {
    const body = {
      name: formData.name.trim(),
      category: formData.category.trim(),
      spec: formData.spec.trim(),
      unit: formData.unit.trim(),
      price: parseFloat(formData.price) || 0,
      cost_price: parseFloat(formData.cost_price) || 0,
      supplier: formData.supplier.trim(),
      function_desc: formData.function_desc.trim(),
      remark: formData.remark.trim(),
      image_url: formData.image_url.trim() || existingImageUrl.value,
    }
    const url = editingId.value ? `/api/products/${editingId.value}` : '/api/products'
    const method = editingId.value ? 'PUT' : 'POST'
    const r = await api(url, method, body)
    if (r.error) { toast(r.error, 'danger'); return }
    toast(editingId.value ? '已更新' : '已添加')
    showForm.value = false
    fetchProducts()
  } catch (e) {
    toast('保存失败', 'danger')
  } finally {
    formSaving.value = false
  }
}

// ─── Page navigation ───
function goPage(p) {
  currentPage.value = p
  fetchProducts()
}

// ─── Pagination display ───
const pageNumbers = computed(() => {
  if (totalPages.value <= 1) return []
  let start = Math.max(1, Math.min(currentPage.value - 3, totalPages.value - 6))
  let end = Math.min(totalPages.value, start + 6)
  if (end - start < 6) start = Math.max(1, end - 6)
  const pages = []
  for (let p = start; p <= end; p++) pages.push(p)
  return pages
})

// ─── Init ───
onMounted(fetchProducts)
</script>

<template>
  <div>
    <!-- Header -->
    <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
      <h5 class="fw-bold mb-0">产品管理</h5>
      <div class="d-flex gap-2">
        <button v-if="isAdmin()" class="btn btn-outline-primary btn-modern" @click="exportTemplate">
          <i class="bi bi-download"></i> 下载模板
        </button>
        <button v-if="isAdmin()" class="btn btn-primary btn-modern" @click="showAddProduct">
          <i class="bi bi-plus-lg"></i> 新增产品
        </button>
      </div>
    </div>

    <div class="card-modern">
      <!-- Filters -->
      <div class="row g-2 mb-3 align-items-center">
        <div class="col-md-5">
          <div style="position:relative">
            <i class="bi bi-search text-muted" style="position:absolute;left:12px;top:50%;transform:translateY(-50%);z-index:10"></i>
            <input class="form-control search-box ps-5 pe-5"
              placeholder="搜索名称/规格/型号/功能/厂家...（支持拼音/缩写）"
              :value="searchTerm"
              @input="debouncedSearch($event.target.value)"
              @compositionstart="onCompositionStart"
              @compositionend="onCompositionEnd"
              @keydown.enter="searchTerm = $event.target.value.trim(); currentPage = 1; fetchProducts()">
            <span v-if="searchTerm" @click="clearSearch"
              style="position:absolute;right:8px;top:50%;transform:translateY(-50%);width:24px;height:24px;border-radius:50%;background:var(--gray-300);display:flex;align-items:center;justify-content:center;cursor:pointer;z-index:10">✕</span>
          </div>
        </div>
        <div class="col-md-2">
          <select class="form-select form-select-sm" style="border-radius:8px"
            v-model="categoryFilter" @change="currentPage = 1; fetchProducts()">
            <option value="">全部分类</option>
            <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <div class="col-md-2">
          <select class="form-select form-select-sm" style="border-radius:8px"
            v-model="supplierFilter" @change="currentPage = 1; fetchProducts()">
            <option value="">全部厂商</option>
            <option v-for="s in suppliers" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
        <div class="col-md-3 d-flex justify-content-md-end align-items-center gap-2" style="flex-wrap:wrap">
          <span class="text-muted" style="font-size:.82rem">共 {{ totalProducts }} 个产品</span>
          <select class="per-page-select" v-model.number="perPage" @change="currentPage = 1; fetchProducts()">
            <option :value="10">10条/页</option>
            <option :value="20">20条/页</option>
            <option :value="50">50条/页</option>
            <option :value="100">100条/页</option>
            <option :value="500">全部</option>
          </select>
          <button v-if="isAdmin() && selectedIds.size > 0" class="btn btn-sm btn-modern btn-outline-danger" @click="batchDelete">
            <i class="bi bi-trash"></i> 删除({{ selectedIds.size }})
          </button>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="text-center py-5">
        <div class="spinner-border text-primary mb-2" role="status"></div>
        <p class="text-muted small">加载产品数据...</p>
      </div>

      <!-- Table -->
      <div v-else class="table-responsive">
        <table class="table table-modern">
          <thead>
            <tr>
              <th v-if="isAdmin()" style="width:36px">
                <input type="checkbox" class="form-check-input"
                  :checked="allSelected"
                  @change="toggleAll">
              </th>
              <th>产品信息</th>
              <th>规格型号</th>
              <th>图片</th>
              <th>分类</th>
              <th>厂商</th>
              <th>销售单价</th>
              <th v-if="isAdmin()">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="products.length === 0">
              <td :colspan="isAdmin() ? 8 : 7">
                <div class="empty-state">
                  <i class="bi bi-inbox"></i>
                  <p>暂无产品</p>
                  <button v-if="isAdmin()" class="btn btn-primary btn-modern mt-2" @click="showAddProduct">新增第一个产品</button>
                </div>
              </td>
            </tr>
            <tr v-for="p in products" :key="p.id" :class="{ 'opacity-50': !p.is_active }">
              <td v-if="isAdmin()">
                <input type="checkbox" class="form-check-input product-check"
                  :checked="selectedIds.has(p.id)"
                  @change="toggleSelect(p.id)">
              </td>
              <td style="cursor:pointer" @click="showDetail(p)">
                <div class="td-name" style="font-weight:500;color:var(--gray-800)">{{ p.name }}</div>
                <div v-if="p.function_desc" class="small text-muted td-name">{{ p.function_desc }}</div>
              </td>
              <td class="td-name" style="max-width:120px">{{ p.spec || '—' }}</td>
              <td>
                <div class="img-cell" style="position:relative;display:inline-block">
                  <img v-if="p.image_url" :src="imageSrc(p)" style="width:40px;height:40px;object-fit:cover;border-radius:4px;cursor:pointer"
                    class="img-thumb"
                    @click="previewImage = imageSrc(p)">
                  <span v-else class="text-muted" style="font-size:.7rem">—</span>
                </div>
              </td>
              <td>
                <span v-for="(tag, i) in (p.category || '').split(',').filter(Boolean)" :key="i"
                  class="badge bg-light text-dark me-1" style="font-weight:400">{{ tag.trim() }}</span>
                <span v-if="!p.category" class="text-muted">—</span>
              </td>
              <td class="td-name" style="max-width:100px">{{ p.supplier || '—' }}</td>
              <td class="text-end fw-medium">{{ formatMoney(p.price) }}</td>
              <td v-if="isAdmin()">
                <div class="d-flex gap-1">
                  <button class="btn btn-sm btn-outline-primary btn-sm-icon" @click="showEditProduct(p)" title="编辑">
                    <i class="bi bi-pencil"></i>
                  </button>
                  <button class="btn btn-sm btn-outline-warning btn-sm-icon"
                    @click="toggleActive(p.id)" :title="p.is_active ? '停用' : '恢复'">
                    <i :class="p.is_active ? 'bi bi-eye-slash' : 'bi bi-eye'"></i>
                  </button>
                  <button class="btn btn-sm btn-outline-danger btn-sm-icon" @click="deleteProduct(p.id)" title="删除">
                    <i class="bi bi-trash"></i>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <nav v-if="totalPages > 1" class="mt-3">
        <ul class="pagination pagination-modern justify-content-center mb-0">
          <li class="page-item" :class="{ disabled: currentPage <= 1 }">
            <a class="page-link" @click="goPage(1)" title="首页"><i class="bi bi-chevron-double-left"></i></a>
          </li>
          <li class="page-item" :class="{ disabled: currentPage <= 1 }">
            <a class="page-link" @click="goPage(currentPage - 1)">上一页</a>
          </li>
          <li v-for="p in pageNumbers" :key="p" class="page-item" :class="{ active: p === currentPage }">
            <a class="page-link" @click="goPage(p)">{{ p }}</a>
          </li>
          <li class="page-item" :class="{ disabled: currentPage >= totalPages }">
            <a class="page-link" @click="goPage(currentPage + 1)">下一页</a>
          </li>
          <li class="page-item" :class="{ disabled: currentPage >= totalPages }">
            <a class="page-link" @click="goPage(totalPages)" title="末页"><i class="bi bi-chevron-double-right"></i></a>
          </li>
        </ul>
      </nav>
    </div>

    <!-- Product Form Modal -->
    <Teleport to="body">
      <div v-if="showForm" class="modal-backdrop show" @click="closeForm"></div>
      <div v-if="showForm" class="modal d-block modern-modal" tabindex="-1">
        <div class="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title fw-semibold">{{ formTitle }}</h5>
              <button type="button" class="btn-close" @click="closeForm"></button>
            </div>
            <div class="modal-body">
              <div class="row g-2">
                <div class="col-md-6">
                  <label class="form-label-modern">产品名称 <span class="text-danger">*</span></label>
                  <input class="form-control" v-model="formData.name" maxlength="200" placeholder="产品名称">
                </div>
                <div class="col-md-6">
                  <label class="form-label-modern">分类</label>
                  <input class="form-control" v-model="formData.category" list="catList" placeholder="选择或输入分类">
                  <datalist id="catList">
                    <option v-for="c in categories" :key="c" :value="c"></option>
                  </datalist>
                </div>
                <div class="col-md-6">
                  <label class="form-label-modern">厂商</label>
                  <input class="form-control" v-model="formData.supplier" list="supList" placeholder="选择或输入厂商">
                  <datalist id="supList">
                    <option v-for="s in suppliers" :key="s" :value="s"></option>
                  </datalist>
                </div>
                <div class="col-md-6">
                  <label class="form-label-modern">规格型号</label>
                  <input class="form-control" v-model="formData.spec" placeholder="规格型号">
                </div>
                <div class="col-md-3">
                  <label class="form-label-modern">单位</label>
                  <input class="form-control" v-model="formData.unit" placeholder="台/个/套">
                </div>
                <div class="col-md-3">
                  <label class="form-label-modern">销售单价</label>
                  <input class="form-control" v-model="formData.price" type="number" step="0.01" min="0" placeholder="0.00">
                </div>
                <div v-if="isAdmin()" class="col-md-3">
                  <label class="form-label-modern">成本价</label>
                  <input class="form-control" v-model="formData.cost_price" type="number" step="0.01" min="0" placeholder="0.00">
                </div>
                <div class="col-12">
                  <label class="form-label-modern">功能描述</label>
                  <textarea class="form-control" v-model="formData.function_desc" placeholder="功能描述" rows="2"></textarea>
                </div>
                <div class="col-12">
                  <label class="form-label-modern">备注</label>
                  <textarea class="form-control" v-model="formData.remark" placeholder="备注" rows="2"></textarea>
                </div>
                <div class="col-12" @paste="onImagePaste">
                  <label class="form-label-modern">
                    图片URL
                    <span v-if="imageUploading" class="spinner-border spinner-border-sm ms-2" style="width:.75rem;height:.75rem"></span>
                    <small class="text-muted ms-2">（可直接粘贴剪贴板图片）</small>
                  </label>
                  <!-- 当前图片预览 -->
                  <div v-if="existingImageUrl || formData.image_url" class="mb-2" style="display:flex;align-items:center;gap:.5rem">
                    <img :src="currentImagePreview()" style="width:80px;height:80px;object-fit:cover;border-radius:6px;border:1px solid var(--gray-200)">
                    <button class="btn btn-sm btn-outline-danger py-0 px-1" @click="deleteImage" title="删除图片" style="font-size:.7rem">
                      <i class="bi bi-trash"></i>
                    </button>
                  </div>
                  <div class="input-group">
                    <input class="form-control" v-model="formData.image_url" placeholder="https://... 或粘贴网络图片链接"
                      @blur="onImageUrlBlur" @keydown="onImageUrlKeydown">
                    <button class="btn btn-outline-secondary" @click="onImageUrlBlur" :disabled="imageDownloading"
                      title="下载并保存为本地图片">
                      <span v-if="imageDownloading" class="spinner-border spinner-border-sm"></span>
                      <i v-else class="bi bi-cloud-download"></i>
                    </button>
                  </div>
                </div>
                <!-- 智能识别区域 -->
                <div class="col-12 mt-3" @paste="onSmartPaste">
                  <div class="p-3 rounded-3" style="background:var(--gray-50);border:2px dashed var(--gray-300)">
                    <label class="form-label-modern mb-1" style="font-size:.82rem">
                      <i class="bi bi-magic"></i> 智能识别
                      <span v-if="smartRecognizing" class="spinner-border spinner-border-sm ms-2" style="width:.75rem;height:.75rem"></span>
                      <small class="text-muted ms-2">Ctrl+V 粘贴产品文字或截图，自动提取信息</small>
                    </label>
                    <div v-if="!smartResult && !smartError && !smartRecognizing"
                      class="text-center py-2 text-muted" style="font-size:.8rem">
                      在此区域粘贴 或 点击后 Ctrl+V
                    </div>
                    <div v-if="smartError" class="alert alert-warning py-1 px-2 mb-0 small" style="font-size:.8rem">
                      {{ smartError }}
                    </div>
                    <!-- 识别结果预览 -->
                    <div v-if="smartResult" class="mt-2 p-2 rounded-2" style="background:white;border:1px solid var(--gray-200);font-size:.82rem">
                      <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="fw-semibold text-primary"><i class="bi bi-check-circle"></i> 识别结果</span>
                        <button class="btn btn-sm btn-outline-secondary py-0 px-2" @click="clearSmartResult" style="font-size:.7rem">✕</button>
                      </div>
                      <table class="table table-sm table-borderless mb-2" style="font-size:.78rem">
                        <tbody>
                          <tr v-if="smartResult.name"><td class="text-muted pe-2" style="width:70px">产品名称</td><td class="fw-medium">{{ smartResult.name }}</td></tr>
                          <tr v-if="smartResult.spec"><td class="text-muted pe-2">规格型号</td><td>{{ smartResult.spec }}</td></tr>
                          <tr v-if="smartResult.supplier"><td class="text-muted pe-2">厂商</td><td>{{ smartResult.supplier }}</td></tr>
                          <tr v-if="smartResult.price"><td class="text-muted pe-2">销售单价</td><td class="text-primary fw-medium">¥{{ smartResult.price }}</td></tr>
                          <tr v-if="smartResult.cost_price"><td class="text-muted pe-2">成本价</td><td>¥{{ smartResult.cost_price }}</td></tr>
                          <tr v-if="smartResult.unit"><td class="text-muted pe-2">单位</td><td>{{ smartResult.unit }}</td></tr>
                          <tr v-if="smartResult.category"><td class="text-muted pe-2">分类</td><td>{{ smartResult.category }}</td></tr>
                          <tr v-if="smartResult.remark"><td class="text-muted pe-2">备注</td><td>{{ smartResult.remark }}</td></tr>
                        </tbody>
                      </table>
                      <button class="btn btn-sm btn-primary w-100" @click="fillFromSmartResult">
                        <i class="bi bi-arrow-up"></i> 确认填入上方表单
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div class="modal-footer">
              <button class="btn btn-primary btn-modern" @click="saveProduct" :disabled="formSaving">
                <span v-if="formSaving" class="spinner-border spinner-border-sm me-1"></span>
                {{ editingId ? '保存' : '新增' }}
              </button>
              <button class="btn btn-secondary btn-modern" @click="closeForm">取消</button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Image Preview Modal -->
    <Teleport to="body">
      <div v-if="previewImage" class="modal-backdrop show" style="z-index:2000" @click="previewImage = ''"></div>
      <div v-if="previewImage" class="modal d-block" tabindex="-1" style="z-index:2001;display:flex!important;align-items:center;justify-content:center" @click="previewImage = ''">
        <div class="bg-white p-3 rounded-3" style="box-shadow:0 8px 32px rgba(0,0,0,.3)" @click.stop>
          <img :src="previewImage" style="max-width:400px;max-height:400px;border-radius:6px;cursor:zoom-out">
        </div>
      </div>
    </Teleport>

    <!-- Product Detail Modal -->
    <Teleport to="body">
      <div v-if="detailProduct" class="modal-backdrop show" @click="detailProduct = null"></div>
      <div v-if="detailProduct" class="modal d-block modern-modal" tabindex="-1">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title fw-semibold">{{ detailProduct.name }}</h5>
              <button type="button" class="btn-close" @click="detailProduct = null"></button>
            </div>
            <div class="modal-body">
              <div class="text-center mb-3">
                <img v-if="detailProduct.image_url" :src="detailImageSrc(detailProduct)"
                  style="max-width:400px;max-height:300px;object-fit:contain;border-radius:8px;border:1px solid var(--gray-200)">
                <div v-else class="text-muted py-3"><i class="bi bi-image" style="font-size:2rem"></i><p class="small mt-1">暂无图片</p></div>
              </div>
              <table class="table table-sm" style="font-size:.85rem">
                <tbody>
                  <tr><td class="text-muted" style="width:80px">分类</td><td class="fw-medium">{{ detailProduct.category || '—' }}</td></tr>
                  <tr><td class="text-muted">规格型号</td><td>{{ detailProduct.spec || '—' }}</td></tr>
                  <tr><td class="text-muted">单位</td><td>{{ detailProduct.unit || '—' }}</td></tr>
                  <tr><td class="text-muted">厂商</td><td>{{ detailProduct.supplier || '—' }}</td></tr>
                  <tr><td class="text-muted">销售单价</td><td class="fw-medium text-primary">{{ formatMoney(detailProduct.price) }}</td></tr>
                  <tr v-if="isAdmin() && detailProduct.cost_price"><td class="text-muted">成本价</td><td>¥{{ detailProduct.cost_price }}</td></tr>
                  <tr v-if="detailProduct.function_desc"><td class="text-muted">功能描述</td><td>{{ detailProduct.function_desc }}</td></tr>
                  <tr v-if="detailProduct.remark"><td class="text-muted">备注</td><td>{{ detailProduct.remark }}</td></tr>
                </tbody>
              </table>
            </div>
            <div class="modal-footer">
              <button v-if="isAdmin()" class="btn btn-outline-primary btn-modern btn-sm" @click="showEditProduct(detailProduct); detailProduct = null">
                <i class="bi bi-pencil"></i> 编辑
              </button>
              <button class="btn btn-secondary btn-modern btn-sm" @click="detailProduct = null">关闭</button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
