<template>
  <div>
    <!-- Page header -->
    <div class="d-flex flex-wrap align-items-center justify-content-between mb-3 gap-2">
      <h5 class="mb-0"><i class="bi bi-database me-2"></i>产品数据库</h5>
      <div class="d-flex align-items-center gap-2">
        <div style="min-width:200px">
          <SearchInput v-model="search" placeholder="搜索型号/名称..." />
        </div>
        <a :href="exportUrl" target="_blank" class="btn btn-outline-secondary btn-sm">
          <i class="bi bi-download me-1"></i>导出
        </a>
        <button class="btn btn-primary btn-sm" @click="$router.push('/products-db/new')">
          <i class="bi bi-plus-lg me-1"></i>新增
        </button>
      </div>
    </div>

    <!-- Filter panel -->
    <div class="card mb-3">
      <div class="card-body py-2 px-3">
        <div class="d-flex flex-wrap align-items-center gap-2" v-if="categoryTree.length">
          <span class="small text-muted fw-medium me-1">品类</span>
          <span v-for="c in flatCategories" :key="c.id"
            class="badge rounded-pill"
            :class="filters.category_id === c.id ? 'bg-primary' : 'bg-light text-dark'"
            style="cursor:pointer"
            @click="toggleCategory(c.id)">{{ c.name }}</span>
        </div>
        <div class="d-flex flex-wrap align-items-center gap-2 mt-1">
          <span class="small text-muted fw-medium me-1">通讯方式</span>
          <span v-for="m in commMethods" :key="m.id"
            class="badge rounded-pill"
            :class="filters.comm_method === m.id ? 'bg-primary' : 'bg-light text-dark'"
            style="cursor:pointer"
            @click="toggleFilter('comm_method', m.id)">{{ m.name }}</span>
        </div>
        <div class="d-flex flex-wrap align-items-center gap-2 mt-1">
          <span class="small text-muted fw-medium me-1">协议</span>
          <span v-for="p in commProtocols" :key="p.id"
            class="badge rounded-pill"
            :class="filters.comm_protocol === p.id ? 'bg-primary' : 'bg-light text-dark'"
            style="cursor:pointer"
            @click="toggleFilter('comm_protocol', p.id)">{{ p.name }}</span>
        </div>
        <div class="d-flex flex-wrap align-items-center gap-2 mt-1">
          <span class="small text-muted fw-medium me-1">供电</span>
          <span v-for="p in powerSupplies" :key="p.id"
            class="badge rounded-pill"
            :class="filters.power_supply === p.id ? 'bg-primary' : 'bg-light text-dark'"
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
    <div class="card">
      <div class="table-responsive">
        <table class="table table-hover align-middle mb-0" v-if="products.length">
          <thead class="table-light">
            <tr>
              <th>名称</th>
              <th>型号</th>
              <th>品类</th>
              <th>厂商</th>
              <th>通讯</th>
              <th>供电</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in products" :key="p.id">
              <td>
                <div class="d-flex align-items-center gap-2">
                  <img v-if="p.image_url" :src="p.image_url"
                    style="width:32px;height:32px;object-fit:cover;border-radius:4px;border:1px solid #dee2e6" />
                  <router-link :to="'/products-db/' + p.id" class="text-decoration-none">{{ p.name }}</router-link>
                </div>
              </td>
              <td class="text-muted small" style="font-family:monospace">{{ p.model || p.sku || '—' }}</td>
              <td>{{ p.category_name }}</td>
              <td>{{ p.manufacturer_name }}</td>
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
        <div v-else class="text-center py-5 text-muted">
          <i class="bi bi-inbox" style="font-size:2rem"></i>
          <p class="mt-2">暂无产品</p>
        </div>
      </div>
      <div class="card-footer" v-if="products.length">
        <Pagination :total="total" :page="page" :per-page="perPage" @change="onPageChange" />
      </div>
    </div>

    <!-- Delete confirmation modal -->
    <Teleport to="body">
      <div v-if="deleteTarget" class="modal-backdrop show" @click="deleteTarget = null"></div>
      <div v-if="deleteTarget" class="modal d-block" tabindex="-1">
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
              <button class="btn btn-danger btn-sm" @click="doDelete">确定删除</button>
              <button class="btn btn-secondary btn-sm" @click="deleteTarget = null">取消</button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted, inject } from 'vue'
import { useRouter } from 'vue-router'
import { useApi, BASE_URL } from '../composables/useApi'
import { useAdvancedApi } from '../composables/useAdvancedApi'
import SearchInput from '../components/SearchInput.vue'
import TagBadge from '../components/TagBadge.vue'
import Pagination from '../components/Pagination.vue'

const toast = inject('toast')
const router = useRouter()
const { api } = useApi()
const { dicts, categories } = useAdvancedApi()

const products = ref([])
const total = ref(0)
const page = ref(1)
const perPage = 20
const search = ref('')

const filters = reactive({
  category_id: null,
  comm_method: null,
  comm_protocol: null,
  power_supply: null,
  manufacturer_id: null,
})

const commMethods = ref([])
const commProtocols = ref([])
const powerSupplies = ref([])
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
  filters[key] = filters[key] === value ? null : value
  page.value = 1
  loadProducts()
}

function buildParams() {
  const parts = []
  if (search.value) parts.push('search=' + encodeURIComponent(search.value))
  if (filters.category_id) parts.push('category_id=' + filters.category_id)
  if (filters.comm_method) parts.push('comm_method=' + filters.comm_method)
  if (filters.comm_protocol) parts.push('comm_protocol=' + filters.comm_protocol)
  if (filters.power_supply) parts.push('power_supply=' + filters.power_supply)
  if (filters.manufacturer_id) parts.push('manufacturer_id=' + filters.manufacturer_id)
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

function onPageChange(newPage) {
  page.value = newPage
  loadProducts()
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

watch(search, () => {
  page.value = 1
  loadProducts()
})

onMounted(async () => {
  try {
    const [cmRes, cpRes, psRes, mfgRes, catRes] = await Promise.all([
      dicts.commMethods(), dicts.commProtocols(), dicts.powerSupplies(),
      dicts.manufacturers(), categories.tree(),
    ])
    commMethods.value = cmRes?.items || []
    commProtocols.value = cpRes?.items || []
    powerSupplies.value = psRes?.items || []
    manufacturers.value = mfgRes?.items || []
    categoryTree.value = catRes?.tree || []
    flatCategories.value = flattenTree(categoryTree.value)
  } catch (e) {
    toast('加载字典数据失败', 'danger')
  }
  await loadProducts()
})
</script>
