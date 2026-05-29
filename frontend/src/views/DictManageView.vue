<script setup>
import { ref, computed, onMounted, watch, inject } from 'vue'
import { useAdvancedApi } from '../composables/useAdvancedApi'

const toast = inject('toast')
const { dicts } = useAdvancedApi()

// ─── Tabs ───
const tabs = [
  { id: 'commMethods', label: '通讯方式' },
  { id: 'commProtocols', label: '通讯协议' },
  { id: 'powerSupplies', label: '供电方式' },
  { id: 'sensorMetrics', label: '传感指标' },
  { id: 'manufacturers', label: '制造商' },
  { id: 'suppliers', label: '供应商' },
]
const activeTab = ref('commMethods')

// ─── Tab configurations ───
const tabConfig = {
  commMethods: {
    columns: [
      { key: 'name', label: '名称' },
      { key: 'method_type', label: '类型' },
    ],
    form: [
      { key: 'method_type', label: '类型', type: 'select', options: ['wired', 'wireless'] },
      { key: 'name', label: '名称', type: 'text' },
    ],
    fetch: () => dicts.commMethods(),
    create: (data) => dicts.createCommMethod(data),
    update: (id, data) => dicts.updateCommMethod(id, data),
    remove: (id) => dicts.deleteCommMethod(id),
  },
  commProtocols: {
    columns: [{ key: 'name', label: '名称' }],
    form: [{ key: 'name', label: '名称', type: 'text' }],
    fetch: () => dicts.commProtocols(),
    create: (data) => dicts.createCommProtocol(data),
    update: (id, data) => dicts.updateCommProtocol(id, data),
    remove: (id) => dicts.deleteCommProtocol(id),
  },
  powerSupplies: {
    columns: [
      { key: 'name', label: '名称' },
      { key: 'supply_category', label: '类别' },
    ],
    form: [
      { key: 'name', label: '名称', type: 'text' },
      { key: 'supply_category', label: '类别', type: 'text' },
    ],
    fetch: () => dicts.powerSupplies(),
    create: (data) => dicts.createPowerSupply(data),
    update: (id, data) => dicts.updatePowerSupply(id, data),
    remove: (id) => dicts.deletePowerSupply(id),
  },
  sensorMetrics: {
    columns: [
      { key: 'name', label: '名称' },
      { key: 'unit', label: '单位' },
    ],
    form: [
      { key: 'name', label: '名称', type: 'text' },
      { key: 'unit', label: '单位', type: 'text' },
    ],
    fetch: () => dicts.sensorMetrics(),
    create: (data) => dicts.createSensorMetric(data),
    update: (id, data) => dicts.updateSensorMetric(id, data),
    remove: (id) => dicts.deleteSensorMetric(id),
  },
  manufacturers: {
    columns: [
      { key: 'name', label: '名称' },
      { key: 'website', label: '网站' },
    ],
    form: [
      { key: 'name', label: '名称', type: 'text' },
      { key: 'website', label: '网站', type: 'text' },
      { key: 'description', label: '描述', type: 'textarea' },
    ],
    fetch: () => dicts.manufacturers(),
    create: (data) => dicts.createManufacturer(data),
    update: (id, data) => dicts.updateManufacturer(id, data),
    remove: (id) => dicts.deleteManufacturer(id),
  },
  suppliers: {
    columns: [
      { key: 'name', label: '名称' },
      { key: 'contact_person', label: '联系人' },
      { key: 'phone', label: '电话' },
      { key: 'email', label: '邮箱' },
    ],
    form: [
      { key: 'name', label: '名称', type: 'text' },
      { key: 'contact_person', label: '联系人', type: 'text' },
      { key: 'phone', label: '电话', type: 'text' },
      { key: 'email', label: '邮箱', type: 'text' },
      { key: 'website', label: '网站', type: 'text' },
      { key: 'notes', label: '备注', type: 'textarea' },
    ],
    fetch: () => dicts.suppliers(supplierSearch.value),
    create: (data) => dicts.createSupplier(data),
    update: (id, data) => dicts.updateSupplier(id, data),
    remove: (id) => dicts.deleteSupplier(id),
  },
}

const currentConfig = computed(() => tabConfig[activeTab.value])
const currentTabLabel = computed(() => {
  const tab = tabs.find(t => t.id === activeTab.value)
  return tab ? tab.label : activeTab.value
})

// ─── State ───
const items = ref([])
const loading = ref(false)
const showModal = ref(false)
const editingId = ref(null)
const form = ref({})

// Supplier search
const supplierSearch = ref('')
let supplierSearchTimer = null
function onSupplierSearch(val) {
  clearTimeout(supplierSearchTimer)
  supplierSearchTimer = setTimeout(() => {
    supplierSearch.value = val
    if (activeTab.value === 'suppliers') fetchItems()
  }, 400)
}

// ─── CRUD ───
async function fetchItems() {
  loading.value = true
  try {
    const data = await currentConfig.value.fetch()
    if (!data.error) items.value = data.items || []
    else toast(data.error, 'danger')
  } catch (e) {
    toast('加载失败', 'danger')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  const defaults = {}
  for (const field of currentConfig.value.form) {
    if (field.type === 'select') {
      defaults[field.key] = field.options ? field.options[0] : ''
    } else {
      defaults[field.key] = ''
    }
  }
  form.value = defaults
  showModal.value = true
}

function openEdit(item) {
  editingId.value = item.id
  form.value = { ...item }
  showModal.value = true
}

function closeModal() {
  showModal.value = false
}

async function saveItem() {
  try {
    let r
    if (editingId.value) {
      r = await currentConfig.value.update(editingId.value, form.value)
    } else {
      r = await currentConfig.value.create(form.value)
    }
    if (r.error) { toast(r.error, 'danger'); return }
    toast(editingId.value ? '已更新' : '已创建')
    showModal.value = false
    await fetchItems()
  } catch (e) {
    toast('操作失败', 'danger')
  }
}

async function removeItem(item) {
  if (!confirm(`确定删除「${item.name || item.id}」吗？`)) return
  try {
    const r = await currentConfig.value.remove(item.id)
    if (r.error) { toast(r.error, 'danger'); return }
    toast('已删除')
    await fetchItems()
  } catch (e) {
    toast('删除失败', 'danger')
  }
}

// ─── Watch tab changes ───
watch(activeTab, () => {
  fetchItems()
})

onMounted(() => {
  fetchItems()
})
</script>

<template>
  <div>
    <div class="page-header">
      <h5><i class="bi bi-book"></i>字典管理</h5>
    </div>

    <!-- Tabs -->
    <ul class="nav nav-tabs mb-3">
      <li v-for="tab in tabs" :key="tab.id" class="nav-item">
        <a class="nav-link" :class="{ active: activeTab === tab.id }"
          href="#" @click.prevent="activeTab = tab.id">
          {{ tab.label }}
        </a>
      </li>
    </ul>

    <!-- Content -->
    <div class="card-modern">
      <div class="card-title-modern d-flex justify-content-between align-items-center">
        <span><i class="bi bi-list text-primary"></i>{{ currentTabLabel }}列表</span>
        <button class="btn btn-primary btn-modern" @click="openCreate">
          <i class="bi bi-plus-lg"></i> 新增
        </button>
      </div>

      <!-- Supplier search bar -->
      <div v-if="activeTab === 'suppliers'" class="mb-2">
        <input :value="supplierSearch" @input="onSupplierSearch($event.target.value)"
          class="form-control form-control-sm" placeholder="搜索供应商名称..." style="max-width:260px">
      </div>

      <!-- Loading -->
      <div v-if="loading" class="text-center py-3">
        <div class="spinner-border spinner-border-sm text-primary"></div>
      </div>

      <!-- Table -->
      <div v-else class="table-responsive">
        <table class="table table-modern">
          <thead>
            <tr>
              <th v-for="col in currentConfig.columns" :key="col.key">{{ col.label }}</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="items.length === 0">
              <td :colspan="currentConfig.columns.length + 1">
                <div class="empty-state"><i class="bi bi-inbox"></i><p>暂无数据</p></div>
              </td>
            </tr>
            <tr v-for="item in items" :key="item.id">
              <td v-for="col in currentConfig.columns" :key="col.key" class="fw-medium">
                {{ item[col.key] || '—' }}
              </td>
              <td>
                <div class="d-flex gap-1">
                  <button class="btn btn-sm btn-outline-secondary btn-sm-icon" @click="openEdit(item)" title="编辑">
                    <i class="bi bi-pencil"></i>
                  </button>
                  <button class="btn btn-sm btn-outline-danger btn-sm-icon" @click="removeItem(item)" title="删除">
                    <i class="bi bi-trash"></i>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Create/Edit Modal -->
    <Teleport to="body">
      <div v-if="showModal" class="modal-backdrop show" @click="closeModal"></div>
      <div v-if="showModal" class="modal d-block modern-modal" tabindex="-1">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title fw-semibold">
                {{ editingId ? '编辑' : '新增' }}{{ currentTabLabel || '' }}
              </h5>
              <button type="button" class="btn-close" @click="closeModal"></button>
            </div>
            <div class="modal-body">
              <div v-for="field in currentConfig.form" :key="field.key" class="mb-3">
                <label class="form-label small">{{ field.label }}</label>
                <select v-if="field.type === 'select'" v-model="form[field.key]" class="form-select form-select-sm">
                  <option v-for="opt in field.options" :key="opt" :value="opt">{{ opt }}</option>
                </select>
                <textarea v-else-if="field.type === 'textarea'"
                  v-model="form[field.key]" class="form-control form-control-sm" rows="3"></textarea>
                <input v-else v-model="form[field.key]" type="text" class="form-control form-control-sm">
              </div>
            </div>
            <div class="modal-footer">
              <button class="btn btn-primary btn-modern" @click="saveItem">保存</button>
              <button class="btn btn-secondary btn-modern" @click="closeModal">取消</button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
