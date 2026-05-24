<script setup>
import { ref, reactive, computed, onMounted, nextTick, inject } from 'vue'
import { useApi, BASE_URL } from '../composables/useApi'
import { formatMoney } from '../composables/useUtils'
import { usePagination } from '../composables/usePagination'

const emit = defineEmits(['edit', 'view', 'delete', 'toggle-active', 'export-template'])

const toast = inject('toast')
const { api, authToken, isAdmin, currentUser } = useApi()

// ─── State ───
const products = ref([])
const categories = ref([])
const suppliers = ref([])
const { currentPage, perPage, totalItems, totalPages, pageNumbers, goPage, resetPage, setFetchFn } = usePagination({
  perPageDefault: 20,
})

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
setFetchFn(() => fetchProducts())
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
      totalItems.value = data.total || 0
      categories.value = data.categories || []
      suppliers.value = data.suppliers || []
      cacheVersion = data.version
      await nextTick()
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
  if (!p.has_image && !p.image_url) return ''
  const token = authToken.value
  if (p.has_image) return BASE_URL + '/api/products/' + p.id + '/image' + (token ? '?token=' + token : '')
  if (p.image_url.startsWith('/uploads/')) {
    return BASE_URL + p.image_url + (token ? '?token=' + token : '')
  }
  return p.image_url.startsWith('http') ? p.image_url : BASE_URL + p.image_url
}

// ─── Select all / single ───
const selectableProducts = computed(() =>
  isAdmin() ? products.value : products.value.filter(p => p.created_by === currentUser.value?.id)
)
const allSelected = computed(() =>
  selectableProducts.value.length > 0 && selectableProducts.value.every(p => selectedIds.has(p.id))
)

function toggleAll() {
  if (allSelected.value) {
    selectableProducts.value.forEach(p => selectedIds.delete(p.id))
  } else {
    selectableProducts.value.forEach(p => selectedIds.add(p.id))
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

// ─── Image preview ───
const previewImage = ref('')

// ─── Expose for parent ───
defineExpose({ fetchProducts, selectedIds, categories, suppliers, exportTemplate, products })

// ─── Init ───
onMounted(() => {
  setTimeout(() => fetchProducts(), 0)
})
</script>

<template>
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
        <span v-if="!loading" class="text-muted" style="font-size:.82rem">共 {{ totalItems }} 个产品</span>
        <select class="per-page-select" v-model.number="perPage" @change="resetPage()">
          <option :value="10">10条/页</option>
          <option :value="20">20条/页</option>
          <option :value="50">50条/页</option>
          <option :value="100">100条/页</option>
          <option :value="500">全部</option>
        </select>
      </div>
    </div>

    <!-- Batch action bar -->
    <div v-if="selectedIds.size > 0" class="d-flex align-items-center gap-2 p-2 rounded mb-3" style="position:sticky;top:0;z-index:10;background:var(--primary);color:#fff">
      <i class="bi bi-check2-square me-1"></i>
      <span class="small fw-medium">已选 {{ selectedIds.size }} 个产品</span>
      <button class="btn btn-sm btn-light btn-modern ms-2" @click="batchDelete">
        <i class="bi bi-trash"></i> 批量删除
      </button>
      <button class="btn btn-sm btn-outline-light btn-modern" @click="selectedIds.clear()">
        取消选择
      </button>
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
            <th style="width:36px">
              <input type="checkbox" class="form-check-input"
                :checked="allSelected"
                @change="toggleAll">
            </th>
            <th>产品名称</th>
            <th class="d-none d-md-table-cell">规格型号</th>
            <th class="d-none d-md-table-cell">图片</th>
            <th class="d-none d-md-table-cell">分类</th>
            <th class="d-none d-md-table-cell">厂商</th>
            <th>销售单价</th>
            <th class="d-none d-md-table-cell">创建人</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="products.length === 0">
            <td colspan="9">
              <div class="empty-state">
                <i class="bi bi-inbox"></i>
                <p>暂无产品</p>
                <button class="btn btn-primary btn-modern mt-2" @click="$emit('edit', null)">新增第一个产品</button>
              </div>
            </td>
          </tr>
          <tr v-for="p in products" :key="p.id" :class="{ 'opacity-50': !p.is_active }">
            <td v-if="isAdmin() || p.created_by === currentUser?.id">
              <input type="checkbox" class="form-check-input product-check"
                :checked="selectedIds.has(p.id)"
                @change="toggleSelect(p.id)">
            </td>
            <td v-else></td>
            <td style="cursor:pointer" @click="$emit('view', p)">
              <div class="text-truncate fw-medium" style="max-width:200px;color:var(--gray-800)">{{ p.name }}</div>
              <div v-if="p.function_desc" class="text-truncate small text-muted" style="max-width:200px">{{ p.function_desc }}</div>
            </td>
            <td class="d-none d-md-table-cell">
              <span class="text-truncate d-inline-block" style="max-width:120px" :title="p.spec || ''">{{ p.spec || '—' }}</span>
            </td>
            <td class="d-none d-md-table-cell">
              <div class="img-cell" style="position:relative;display:inline-block">
                <img v-if="p.has_image || p.image_url" :src="imageSrc(p)" style="width:40px;height:40px;object-fit:cover;border-radius:4px;cursor:pointer"
                  class="img-thumb"
                  @click="previewImage = imageSrc(p)">
                <img v-if="p.has_image || p.image_url" :src="imageSrc(p)" class="img-thumb-large">
                <i v-else class="bi bi-image text-muted" style="font-size:1.2rem;opacity:.4"></i>
              </div>
            </td>
            <td class="d-none d-md-table-cell">
              <span v-for="(tag, i) in (p.category || '').split(',').filter(Boolean)" :key="i"
                class="badge bg-light text-dark me-1" style="font-weight:400">{{ tag.trim() }}</span>
              <span v-if="!p.category" class="text-muted">—</span>
            </td>
            <td class="td-name d-none d-md-table-cell" style="max-width:100px">{{ p.supplier || '—' }}</td>
            <td class="text-end fw-medium">{{ formatMoney(p.price) }}</td>
            <td class="small text-muted d-none d-md-table-cell">{{ p.created_by_name || '系统' }}</td>
            <td v-if="isAdmin() || p.created_by === currentUser?.id">
              <div class="d-flex gap-1">
                <button class="btn btn-sm btn-outline-primary btn-sm-icon" @click="$emit('edit', p)" title="编辑">
                  <i class="bi bi-pencil"></i>
                </button>
                <button v-if="isAdmin()" class="btn btn-sm btn-outline-warning btn-sm-icon"
                  @click="toggleActive(p.id)" :title="p.is_active ? '停用' : '恢复'">
                  <i :class="p.is_active ? 'bi bi-eye-slash' : 'bi bi-eye'"></i>
                </button>
                <button class="btn btn-sm btn-outline-danger btn-sm-icon" @click="deleteProduct(p.id)" title="删除">
                  <i class="bi bi-trash"></i>
                </button>
              </div>
            </td>
            <td v-else>
              <span class="text-muted small">—</span>
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

  <!-- Image Preview Modal -->
  <Teleport to="body">
    <div v-if="previewImage" class="modal-backdrop show" style="z-index:2000" @click="previewImage = ''"></div>
    <div v-if="previewImage" class="modal d-block" tabindex="-1" style="z-index:2001;display:flex!important;align-items:center;justify-content:center" @click="previewImage = ''">
      <div class="bg-white p-3 rounded-3" style="box-shadow:0 8px 32px rgba(0,0,0,.3)" @click.stop>
        <img :src="previewImage" style="max-width:400px;max-height:400px;border-radius:6px;cursor:zoom-out">
      </div>
    </div>
  </Teleport>
</template>
