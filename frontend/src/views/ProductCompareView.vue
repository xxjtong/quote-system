<script setup>
import { ref, reactive, computed, onMounted, inject } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApi } from '../composables/useApi'
import { useAdvancedApi } from '../composables/useAdvancedApi'

const route = useRoute()
const router = useRouter()
const toast = inject('toast')
const { api } = useApi()
const { productAdvanced } = useAdvancedApi()

// ─── Compare product IDs from URL / localStorage ───
const compareIds = ref([])
const compareData = ref(null)
const loading = ref(false)
const loaded = ref(false)

const searchQuery = ref('')
const searchResults = ref([])
const searchTimer = ref(null)
const showDropdown = ref(false)

const MAX_COMPARE = 5

const allProductIds = computed(() => compareIds.value)

// ─── Init from query or localStorage ───
onMounted(async () => {
  const idsParam = route.query.ids
  if (idsParam) {
    compareIds.value = idsParam.split(',').map(Number).filter(Boolean)
  } else {
    try {
      const stored = localStorage.getItem('quote_compare_ids')
      if (stored) compareIds.value = JSON.parse(stored)
    } catch (e) { /* ignore */ }
  }
  if (compareIds.value.length >= 2) {
    await loadCompare()
  }
})

// ─── API call ───
async function loadCompare() {
  if (compareIds.value.length < 2) return
  loading.value = true
  loaded.value = false
  try {
    const r = await productAdvanced.compare(compareIds.value)
    compareData.value = r
    loaded.value = true
  } catch (e) {
    toast('加载对比数据失败', 'danger')
  } finally {
    loading.value = false
  }
}

// ─── Product search ───
function onSearchInput() {
  const q = searchQuery.value.trim()
  if (!q) { searchResults.value = []; return }
  clearTimeout(searchTimer.value)
  searchTimer.value = setTimeout(async () => {
    try {
      const r = await api('/api/products?search=' + encodeURIComponent(q) + '&per_page=10')
      searchResults.value = (r?.items || []).filter(p => !compareIds.value.includes(p.id))
      showDropdown.value = true
    } catch (e) { /* silent */ }
  }, 300)
}

function addProduct(product) {
  if (compareIds.value.length >= MAX_COMPARE) {
    toast('最多选择5个产品对比', 'warning')
    return
  }
  if (compareIds.value.includes(product.id)) return
  compareIds.value.push(product.id)
  searchQuery.value = ''
  searchResults.value = []
  showDropdown.value = false
  if (compareIds.value.length >= 2) {
    loadCompare()
  }
}

function removeProduct(id) {
  compareIds.value = compareIds.value.filter(v => v !== id)
  localStorage.setItem('quote_compare_ids', JSON.stringify(compareIds.value))
  if (compareIds.value.length < 2) {
    compareData.value = null
    loaded.value = false
  } else {
    loadCompare()
  }
}

// ─── Spec field names from the first product's specs ───
const specKeys = computed(() => {
  if (!compareData.value || !compareData.value.products) return []
  const keys = new Set()
  for (const p of compareData.value.products) {
    if (p.specs && typeof p.specs === 'object') {
      for (const k of Object.keys(p.specs)) keys.add(k)
    }
  }
  return Array.from(keys)
})

// ─── M2M field defs ───
const m2mSections = [
  { key: 'comm_methods', label: '通讯方式' },
  { key: 'comm_protocols', label: '通讯协议' },
  { key: 'power_supplies', label: '供电方式' },
  { key: 'hardware_interfaces', label: '硬件接口' },
  { key: 'sensor_capabilities', label: '传感能力' },
]

function getM2MNames(product, sectionKey) {
  const items = product[sectionKey]
  if (!items || !items.length) return '—'
  return items.map(i => i.dict_name).join(', ')
}

function isDifferent(key, products) {
  const vals = products.map(p => {
    if (p.specs && key in p.specs) return String(p.specs[key])
    return ''
  })
  return new Set(vals).size > 1
}
</script>

<template>
  <div class="container-fluid py-3">
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h5 class="fw-semibold mb-0"><i class="bi bi-bar-chart-steps me-2"></i>产品对比</h5>
    </div>

    <!-- Search bar -->
    <div class="position-relative mb-3">
      <input class="form-control"
        v-model="searchQuery"
        @input="onSearchInput"
        @focus="showDropdown = searchResults.length > 0"
        @keydown.escape="showDropdown = false"
        placeholder="搜索产品添加到对比..."
        autocomplete="off">
      <ul v-if="showDropdown && searchResults.length" class="list-unstyled dropdown-menu show w-100 p-1"
        style="max-height:240px;overflow-y:auto;z-index:1060">
        <li v-for="p in searchResults" :key="p.id">
          <a class="dropdown-item small py-1" href="#" @click.prevent="addProduct(p)">
            <span class="fw-medium">{{ p.name }}</span>
            <span v-if="p.spec" class="text-muted ms-2">({{ p.spec }})</span>
          </a>
        </li>
        <li v-if="!searchResults.length" class="px-2 py-1 text-muted small">无结果</li>
      </ul>
    </div>

    <!-- Selected product pills -->
    <div class="d-flex flex-wrap gap-2 mb-3">
      <div v-for="pid in compareIds" :key="pid" class="d-inline-flex align-items-center">
        <span class="badge bg-primary fs-6 d-flex align-items-center gap-1 px-3 py-2">
          <template v-if="compareData?.products">
            {{ compareData.products.find(p => p.id === pid)?.name || '产品 #' + pid }}
          </template>
          <template v-else>产品 #{{ pid }}</template>
          <i class="bi bi-x-circle-fill ms-1" style="cursor:pointer;font-size:.75rem" @click="removeProduct(pid)"></i>
        </span>
      </div>
      <span v-if="!compareIds.length" class="text-muted small py-1">选择2-5个产品进行对比</span>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-5">
      <div class="spinner-border text-primary" role="status"></div>
      <p class="mt-2 text-muted">加载对比数据...</p>
    </div>

    <!-- Empty state -->
    <div v-else-if="!loaded || !compareData" class="text-center py-5 text-muted">
      <i class="bi bi-bar-chart-steps" style="font-size:3rem"></i>
      <p class="mt-2">选择2-5个产品进行对比</p>
    </div>

    <!-- Comparison table -->
    <div v-else class="table-responsive">
      <table class="table table-bordered table-hover" style="font-size:.85rem">
        <thead class="table-light">
          <tr>
            <th style="width:120px;min-width:120px" class="fw-semibold">对比项</th>
            <th v-for="p in compareData.products" :key="p.id" class="text-center fw-semibold" style="min-width:180px">
              <div class="small">{{ p.name }}</div>
              <div class="text-muted" style="font-size:.75rem">{{ p.spec || '' }}</div>
            </th>
          </tr>
        </thead>
        <tbody>
          <!-- Basic fields -->
          <tr class="table-secondary">
            <td colspan="100" class="fw-semibold small">基本信息</td>
          </tr>
          <tr>
            <td class="text-muted">分类</td>
            <td v-for="p in compareData.products" :key="p.id" class="text-center">{{ p.category || '—' }}</td>
          </tr>
          <tr>
            <td class="text-muted">厂商</td>
            <td v-for="p in compareData.products" :key="p.id" class="text-center">{{ p.supplier || '—' }}</td>
          </tr>
          <tr>
            <td class="text-muted">销售单价</td>
            <td v-for="p in compareData.products" :key="p.id" class="text-center fw-medium text-primary">
              ¥{{ Number(p.price || 0).toLocaleString('zh-CN', {minimumFractionDigits:2}) }}
            </td>
          </tr>

          <!-- Spec fields -->
          <tr v-if="specKeys.length" class="table-secondary">
            <td colspan="100" class="fw-semibold small">技术规格</td>
          </tr>
          <tr v-for="key in specKeys" :key="key"
            :class="isDifferent(key, compareData.products) ? 'table-warning' : ''">
            <td class="text-muted">{{ key }}</td>
            <td v-for="p in compareData.products" :key="p.id" class="text-center"
              :class="isDifferent(key, compareData.products) ? 'fw-medium' : ''">
              {{ p.specs?.[key] || '—' }}
            </td>
          </tr>

          <!-- M2M fields -->
          <tr class="table-secondary">
            <td colspan="100" class="fw-semibold small">技术参数</td>
          </tr>
          <tr v-for="section in m2mSections" :key="section.key">
            <td class="text-muted">{{ section.label }}</td>
            <td v-for="p in compareData.products" :key="p.id" class="text-center">
              {{ getM2MNames(p, section.key) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
