<template>
  <div>
    <!-- Page header -->
    <div class="page-header justify-content-between">
      <h5><i class="bi bi-database me-2"></i>产品数据库</h5>
      <div style="display:flex;gap:8px">
        <div style="position:relative;width:200px">
          <i class="bi bi-search text-muted" style="position:absolute;left:10px;top:50%;transform:translateY(-50%);z-index:5"></i>
          <input class="form-control form-control-sm ps-4" placeholder="搜索型号/名称..."
            v-model="search" />
        </div>
        <a :href="exportUrl" target="_blank" class="btn btn-outline-primary btn-modern">
          <i class="bi bi-download me-1"></i>导出
        </a>
        <button class="btn btn-primary btn-modern" @click="$router.push('/products-db/new')">
          <i class="bi bi-plus-lg me-1"></i>新增
        </button>
      </div>
    </div>

    <!-- Filter panel -->
    <div class="card-modern mb-3">
      <div style="padding:8px 12px">
        <div class="d-flex flex-wrap align-items-center gap-2" v-if="categoryTree.length">
          <span class="small text-muted fw-medium me-1">品类</span>
          <span v-for="c in flatCategories" :key="c.id"
            class="badge rounded-pill"
            :class="filters.category_id === c.id ? 'bg-primary' : 'bg-light text-dark'"
            style="cursor:pointer"
            @click="toggleCategory(c.id)">{{ c.name }}</span>
        </div>
        <div class="d-flex flex-wrap align-items-center gap-2 mt-1" v-if="sensorMetrics.length">
          <span class="small text-muted fw-medium me-1">传感功能</span>
          <span v-for="s in sensorMetrics" :key="s.id"
            class="badge rounded-pill"
            :class="filters.sensor_metric.includes(s.id) ? 'bg-primary' : 'bg-light text-dark'"
            style="cursor:pointer"
            @click="toggleFilter('sensor_metric', s.id)">{{ s.name }}</span>
        </div>
        <div class="d-flex flex-wrap align-items-center gap-2 mt-1">
          <span class="small text-muted fw-medium me-1">通讯方式</span>
          <span v-for="m in commMethods" :key="m.id"
            class="badge rounded-pill"
            :class="filters.comm_method.includes(m.id) ? 'bg-primary' : 'bg-light text-dark'"
            style="cursor:pointer"
            @click="toggleFilter('comm_method', m.id)">{{ m.name }}</span>
        </div>
        <div class="d-flex flex-wrap align-items-center gap-2 mt-1">
          <span class="small text-muted fw-medium me-1">供电</span>
          <span v-for="p in powerSupplies" :key="p.id"
            class="badge rounded-pill"
            :class="filters.power_supply.includes(p.id) ? 'bg-primary' : 'bg-light text-dark'"
            style="cursor:pointer"
            @click="toggleFilter('power_supply', p.id)">{{ p.name }}</span>
        </div>
        <div class="d-flex flex-wrap align-items-center gap-2 mt-1" v-if="manufacturers.length > 1">
          <span class="small text-muted fw-medium me-1">厂商</span>
          <span v-for="m in manufacturers" :key="m.id"
            class="badge rounded-pill"
            :class="filters.manufacturer_id === m.id ? 'bg-primary' : 'bg-light text-dark'"
            style="cursor:pointer"
            @click="toggleFilter('manufacturer_id', m.id)">{{ m.name }}</span>
        </div>
      </div>
    </div>

    <!-- Data table -->
    <div class="card-modern">
      <div class="table-responsive">
        <table class="table table-modern" v-if="products.length">
          <thead>
            <tr>
              <th>名称</th>
              <th>型号</th>
              <th>功能</th>
              <th>通讯</th>
              <th>供电</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in products" :key="p.id">
              <td>
                <div class="d-flex align-items-center gap-2">
                  <img v-if="p.image_url" :src="getImageSrc(p.image_url)"
                    style="width:32px;height:32px;object-fit:cover;border-radius:4px;border:1px solid #dee2e6" />
                  <router-link :to="'/products-db/' + p.id" class="text-decoration-none">{{ p.name }}</router-link>
                </div>
              </td>
              <td class="text-muted small" style="font-family:monospace">{{ p.model || p.sku || '—' }}</td>
              <td>
                <TagBadge v-for="sc in (p.sensor_capabilities || []).slice(0,3)" :key="sc.metric_id || sc.dict_id" :label="sc.metric_name || sc.dict_name" />
                <span v-if="(p.sensor_capabilities || []).length > 3" class="small text-muted">+{{ p.sensor_capabilities.length - 3 }}</span>
              </td>
              <td>
                <TagBadge v-for="cm in (p.comm_methods || []).slice(0,3)" :key="cm.method_id || cm.dict_id" :label="cm.method_name || cm.dict_name" />
                <span v-if="(p.comm_methods || []).length > 3" class="small text-muted">+{{ p.comm_methods.length - 3 }}</span>
              </td>
              <td>
                <TagBadge v-for="ps in (p.power_supplies || [])" :key="ps.power_id || ps.dict_id" :label="ps.power_name || ps.dict_name" />
              </td>
              <td>
                <div class="d-flex gap-1">
                  <button class="btn btn-sm btn-outline-secondary" @click="$router.push('/products-db/' + p.id + '/edit')" title="编辑">
                    <i class="bi bi-pencil"></i>
                  </button>
                  <button class="btn btn-sm btn-outline-danger" @click="confirmDelete(p)" title="删除">
                    <i class="bi bi-trash"></i>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-else>
          <div class="empty-state">
            <i class="bi bi-inbox"></i>
            <p>暂无产品</p>
          </div>
        </div>
      </div>
      <div class="card-footer" v-if="products.length">
        <nav v-if="totalPages > 1" class="mt-3">
          <ul class="pagination pagination-modern justify-content-center mb-0">
            <li class="page-item" :class="{ disabled: page <= 1 }">
              <a class="page-link" @click="goPage(1)" title="首页"><i class="bi bi-chevron-double-left"></i></a>
            </li>
            <li class="page-item" :class="{ disabled: page <= 1 }">
              <a class="page-link" @click="goPage(page - 1)">上一页</a>
            </li>
            <li v-for="p in pageNumbers" :key="p" class="page-item" :class="{ active: p === page }">
              <a class="page-link" @click="goPage(p)">{{ p }}</a>
            </li>
            <li class="page-item" :class="{ disabled: page >= totalPages }">
              <a class="page-link" @click="goPage(page + 1)">下一页</a>
            </li>
            <li class="page-item" :class="{ disabled: page >= totalPages }">
              <a class="page-link" @click="goPage(totalPages)" title="末页"><i class="bi bi-chevron-double-right"></i></a>
            </li>
          </ul>
        </nav>
      </div>
    </div>

    <!-- Delete confirmation modal -->
    <Teleport to="body">
      <div v-if="deleteTarget" class="modal-backdrop show" @click="deleteTarget = null"></div>
      <div v-if="deleteTarget" class="modal d-block modern-modal" tabindex="-1">
        <div class="modal-dialog modal-dialog-centered modal-sm">
          <div class="modal-content">
            <div class="modal-header">
              <h6 class="modal-title">删除产品</h6>
              <button type="button" class="btn-close" @click="deleteTarget = null"></button>
            </div>
            <div class="modal-body">
              <p class="mb-0">确定删除「{{ deleteTarget?.name }}」？</p>
            </div>
            <div class="modal-footer">
              <button class="btn btn-danger btn-modern" @click="doDelete">确定删除</button>
              <button class="btn btn-secondary btn-modern" @click="deleteTarget = null">取消</button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, inject } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useApi, BASE_URL } from '../composables/useApi'

const FLASK_DEV = import.meta.env.DEV ? 'http://127.0.0.1:5001' : ''
function getImageSrc(url) {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return FLASK_DEV + url
}
import { useAdvancedApi } from '../composables/useAdvancedApi'
import TagBadge from '../components/TagBadge.vue'

const toast = inject('toast')
const router = useRouter()
const route = useRoute()
const { api } = useApi()
const { dicts, categories } = useAdvancedApi()

const products = ref([])
const total = ref(0)
const page = ref(1)
const perPage = 20
const search = ref('')

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / perPage)))

const pageNumbers = computed(() => {
  const total = totalPages.value
  if (total <= 1) return []
  const half = 3
  let start = Math.max(1, page.value - half)
  let end = Math.min(total, page.value + half)
  if (start === 1) end = Math.min(total, start + 6)
  else if (end === total) start = Math.max(1, end - 6)
  const pages = []
  for (let p = start; p <= end; p++) pages.push(p)
  return pages
})

function goPage(p) {
  if (p < 1 || p > totalPages.value) return
  page.value = p
  loadProducts()
}

const filters = reactive({
  category_id: null,
  comm_method: [],
  power_supply: [],
  sensor_metric: [],
  manufacturer_id: null,
})

const commMethods = ref([])
const powerSupplies = ref([])
const sensorMetrics = ref([])
const manufacturers = ref([])
const categoryTree = ref([])
const flatCategories = ref([])

const deleteTarget = ref(null)

const exportUrl = (BASE_URL || '') + '/api/products/export'

function flattenTree(nodes, result = []) {
  for (const n of nodes) {
    result.push(n)
    if (n.children?.length) flattenTree(n.children, result)
  }
  return result
}

function toggleCategory(id) {
  filters.category_id = filters.category_id === id ? null : id
  page.value = 1
  loadProducts()
}

function toggleFilter(key, value) {
  if (Array.isArray(filters[key])) {
    const idx = filters[key].indexOf(value)
    if (idx >= 0) filters[key].splice(idx, 1)
    else filters[key].push(value)
  } else {
    filters[key] = filters[key] === value ? null : value
  }
  page.value = 1
  loadProducts()
}

function buildParams() {
  const parts = []
  if (search.value) parts.push('search=' + encodeURIComponent(search.value))
  if (filters.category_id) parts.push('category_id=' + filters.category_id)
  if (filters.comm_method.length) parts.push('comm_method=' + filters.comm_method.join(','))
  if (filters.power_supply.length) parts.push('power_supply=' + filters.power_supply.join(','))
  if (filters.sensor_metric.length) parts.push('sensor_metric=' + filters.sensor_metric.join(','))
  if (filters.manufacturer_id) parts.push('manufacturer_id=' + filters.manufacturer_id)
  parts.push('sort_by=id')
  parts.push('sort_order=desc')
  parts.push('page=' + page.value)
  parts.push('per_page=' + perPage)
  return parts.join('&')
}

async function loadProducts() {
  try {
    const res = await api('/api/products?' + buildParams())
    products.value = res.products || []
    total.value = res.total || 0
  } catch (e) {
    toast('加载产品失败', 'danger')
  }
}
function confirmDelete(p) {
  deleteTarget.value = p
}

async function doDelete() {
  if (!deleteTarget.value) return
  try {
    const r = await api('/api/products/' + deleteTarget.value.id, 'DELETE')
    if (r && r.error) { toast(r.error, 'danger'); return }
    toast('已删除')
    deleteTarget.value = null
    await loadProducts()
  } catch (e) {
    toast('删除失败', 'danger')
  }
}

let searchTimer = null
watch(search, () => {
  page.value = 1
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => loadProducts(), 300)
})

// Reload products when navigating back to this page
watch(() => route.path, (path) => {
  if (path === '/products-db') loadProducts()
})

onMounted(async () => {
  try {
    const [cmRes, psRes, smRes, mfgRes, catRes] = await Promise.all([
      dicts.commMethods(), dicts.powerSupplies(), dicts.sensorMetrics(),
      dicts.manufacturers(), categories.tree(),
    ])
    commMethods.value = cmRes?.items || []
    powerSupplies.value = psRes?.items || []
    sensorMetrics.value = smRes?.items || []
    manufacturers.value = mfgRes?.items || []
    categoryTree.value = catRes?.tree || []
    flatCategories.value = flattenTree(categoryTree.value)
  } catch (e) {
    toast('加载字典数据失败', 'danger')
  }
  await loadProducts()
})
</script>
