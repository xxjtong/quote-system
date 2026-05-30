<script setup>
import { ref, reactive, computed, onMounted, nextTick, inject } from 'vue'
import { useApi, BASE_URL } from '../composables/useApi'
import { formatMoney } from '../composables/useUtils'
import { usePagination } from '../composables/usePagination'
import TagBadge from './TagBadge.vue'

const emit = defineEmits(['edit', 'view', 'delete', 'toggle-active', 'export-template', 'createQuote'])
const props = defineProps({
  manufacturers: { type: Array, default: () => [] },
  categoryList: { type: Array, default: () => [] }
})

const toast = inject('toast')
const { api, isAdmin, currentUser } = useApi()

const FLASK_DEV = import.meta.env.DEV ? 'http://127.0.0.1:5001' : ''
function getImageSrc(url) {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return FLASK_DEV + url
}

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
const manufacturerFilter = ref('')
const manufacturerList = computed(() => props.manufacturers || [])
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
    if (categoryFilter.value) params.set('category_id', categoryFilter.value)
    if (supplierFilter.value) params.set('supplier', supplierFilter.value)
    if (manufacturerFilter.value) params.set('manufacturer_id', manufacturerFilter.value)

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
  if (p.model) parts.push('型号: ' + p.model)
  else if (p.spec) parts.push('规格: ' + p.spec)
  if (p.function_desc) parts.push('功能: ' + p.function_desc)
  if (p.manufacturer_name) parts.push('制造商: ' + p.manufacturer_name)
  if (p.supplier_name || p.supplier) parts.push('厂商: ' + (p.supplier_name || p.supplier))
  if (p.remark) parts.push('备注: ' + p.remark)
  if (p.cost_price) parts.push('成本: ¥' + p.cost_price)
  return parts.join('\n')
}

// ─── Select all / single ───
const selectableProducts = computed(() => products.value)
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
          <option v-for="c in categoryList" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>
      </div>
      <div class="col-md-2">
        <select class="form-select form-select-sm" style="border-radius:8px"
          v-model="manufacturerFilter" @change="currentPage = 1; fetchProducts()">
          <option value="">全部厂商</option>
          <option v-for="m in manufacturerList" :key="m.id" :value="m.id">{{ m.name }}</option>
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
      <button class="btn btn-sm btn-light btn-modern ms-2" @click="$emit('createQuote', [...selectedIds])">
        <i class="bi bi-file-earmark-text"></i> 新建报价单
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
            <th class="d-none d-md-table-cell">型号</th>
            <th class="d-none d-md-table-cell">分类</th>
            <th>销售单价</th>
            <th class="d-none d-md-table-cell">状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="products.length === 0">
            <td colspan="7">
              <div class="empty-state">
                <i class="bi bi-inbox"></i>
                <p>暂无产品</p>
                <button class="btn btn-primary btn-modern mt-2" @click="$emit('edit', null)">新增第一个产品</button>
              </div>
            </td>
          </tr>
          <tr v-for="p in products" :key="p.id" :class="{ 'opacity-50': !p.is_active }">
            <td>
              <input type="checkbox" class="form-check-input product-check"
                :checked="selectedIds.has(p.id)"
                @change="toggleSelect(p.id)">
            </td>
            <td style="cursor:pointer" @click="$emit('view', p)">
              <div class="d-flex align-items-center gap-2">
                <img v-if="p.image_url" :src="getImageSrc(p.image_url)"
                  style="width:32px;height:32px;object-fit:cover;border-radius:4px;border:1px solid #dee2e6;flex-shrink:0" />
                <div>
                  <div class="text-truncate fw-medium" style="max-width:200px;color:var(--gray-800)">{{ p.name }}</div>
                  <div v-if="p.function_desc" class="text-truncate small text-muted" style="max-width:200px">{{ p.function_desc }}</div>
                </div>
              </div>
            </td>
            <!-- 型号 -->
            <td class="d-none d-md-table-cell">
              <span class="text-truncate d-inline-block" style="max-width:120px">{{ p.model || p.spec || '—' }}</span>
            </td>
            <!-- 分类 -->
            <td class="d-none d-md-table-cell">
              <span v-if="p.category_name || p.category" class="badge bg-light text-dark" style="font-weight:400">{{ p.category_name || p.category }}</span>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="text-end fw-medium">{{ formatMoney(p.price) }}</td>
            <!-- 状态 -->
            <td class="d-none d-md-table-cell">
              <span v-if="p.status === 'active' || (!p.status && p.is_active !== false)" class="badge bg-success">在售</span>
              <span v-else-if="p.status === 'discontinued'" class="badge bg-danger">停售</span>
              <span v-else-if="p.status === 'planned'" class="badge bg-primary">规划中</span>
              <span v-else-if="p.status === 'archived'" class="badge bg-secondary">已归档</span>
              <span v-else class="text-muted">—</span>
            </td>
            <td v-if="isAdmin() || p.created_by === currentUser?.id">
              <div class="d-flex gap-1">
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

</template>
