<script setup>
import { ref, reactive, inject, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useApi } from '../composables/useApi'
import { formatMoney } from '../composables/useUtils'

const router = useRouter()
const route = useRoute()
const toast = inject('toast')
const { api } = useApi()

const editId = ref(route.query.edit || null)
const isEditing = computed(() => !!editId.value)

// ─── Form state ───
const form = reactive({
  title: '',
  client: '',
  client_contact: '',
  client_phone: '',
  client_email: '',
  valid_days: 30,
  notes: '',
})

const items = reactive([])
const saving = ref(false)

// ─── Load existing quote ───
async function loadQuote() {
  if (!editId.value) return
  try {
    const data = await api(`/api/quotes/${editId.value}`)
    if (data.error) { toast(data.error, 'danger'); editId.value = null; return }
    const q = data.quote
    form.title = q.title || ''
    form.client = q.client || ''
    form.client_contact = q.contact || ''
    form.client_phone = q.phone || ''
    form.client_email = q.client_email || ''
    form.valid_days = q.valid_days || 30
    form.notes = q.remark || ''
    // 加载明细
    items.length = 0
    for (const it of (q.items || [])) {
      items.push({
        product_id: it.product_id,
        name: it.product_name || it.name || '',
        spec: it.product_spec || it.spec || '',
        unit: it.product_unit || it.unit || '',
        price: it.unit_price || it.price || 0,
        quantity: it.quantity || 1,
        discount: Math.round((it.discount_rate || 100)),
        remark: it.remark || '',
      })
    }
  } catch (e) {
    toast('加载报价单失败', 'danger')
  }
}

// ─── Product picker ───
const showPicker = ref(false)
const pickerSearch = ref('')
const pickerProducts = ref([])
const pickerLoading = ref(false)
const pickedIds = reactive(new Set())
let pickerTimer = null

function openPicker() {
  showPicker.value = true
  pickerSearch.value = ''
  pickedIds.clear()
  searchProducts()
}

function searchProducts() {
  clearTimeout(pickerTimer)
  pickerTimer = setTimeout(async () => {
    pickerLoading.value = true
    try {
      const params = new URLSearchParams({ per_page: 50 })
      if (pickerSearch.value) params.set('search', pickerSearch.value)
      const data = await api(`/api/products?${params}`)
      if (!data.error) pickerProducts.value = (data.products || []).filter(p => p.is_active !== false)
    } finally {
      pickerLoading.value = false
    }
  }, 300)
}

function togglePick(id) {
  if (pickedIds.has(id)) pickedIds.delete(id)
  else pickedIds.add(id)
}

function addSelectedProducts() {
  for (const p of pickerProducts.value) {
    if (pickedIds.has(p.id)) {
      const existing = items.find(i => i.product_id === p.id)
      if (existing) {
        existing.quantity += 1
      } else {
        items.push({
          product_id: p.id,
          name: p.name,
          spec: p.spec || '',
          unit: p.unit || '',
          price: p.price || 0,
          quantity: 1,
          discount: 100,
          remark: '',
        })
      }
    }
  }
  pickedIds.clear()
  showPicker.value = false
}

// ─── Computed ───
const subtotal = computed(() => items.reduce((s, i) => s + i.price * i.quantity, 0))
const total = computed(() => items.reduce((s, i) => s + (i.price * i.quantity * i.discount / 100), 0))

function removeItem(idx) { items.splice(idx, 1) }

// ─── Save quote ───
async function saveQuote() {
  if (!form.title.trim()) { toast('请输入报价单标题', 'warning'); return }
  if (!form.client.trim()) { toast('请输入客户名称', 'warning'); return }
  if (items.length === 0) { toast('请添加产品', 'warning'); return }
  saving.value = true
  try {
    const body = {
      title: form.title.trim(),
      client: form.client.trim(),
      contact: form.client_contact.trim(),
      phone: form.client_phone.trim(),
      client_email: form.client_email.trim(),
      valid_days: form.valid_days,
      remark: form.notes.trim(),
      items: items.map(i => ({
        product_id: i.product_id,
        quantity: i.quantity,
        unit_price: i.price,
        discount_rate: i.discount,
        remark: i.remark || '',
      })),
    }
    if (isEditing.value) {
      const r = await api(`/api/quotes/${editId.value}`, 'PUT', body)
      if (r.error) { toast(r.error, 'danger'); return }
      toast('报价单已更新')
    } else {
      const r = await api('/api/quotes', 'POST', body)
      if (r.error) { toast(r.error, 'danger'); return }
      toast('报价单创建成功')
    }
    router.push({ name: 'quotes' })
  } catch (e) {
    toast('保存失败', 'danger')
  } finally {
    saving.value = false
  }
}

onMounted(loadQuote)
</script>

<template>
  <div>
    <div class="page-header">
      <h5><i class="bi bi-plus-circle"></i>{{ isEditing ? '编辑报价单' : '新建报价单' }}</h5>
      <button class="btn btn-primary btn-modern" @click="saveQuote" :disabled="saving">
        <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
        {{ isEditing ? '更新报价单' : '保存报价单' }}
      </button>
    </div>

    <!-- Client info -->
    <div class="card-modern mb-3">
      <div class="card-title-modern"><i class="bi bi-person text-primary"></i>客户信息</div>
      <div class="row g-2">
        <div class="col-md-6">
          <label class="form-label-modern">报价单标题 <span class="text-danger">*</span></label>
          <input class="form-control" v-model="form.title" placeholder="例如：XX项目网络设备报价">
        </div>
        <div class="col-md-6">
          <label class="form-label-modern">客户名称 <span class="text-danger">*</span></label>
          <input class="form-control" v-model="form.client" placeholder="客户公司/姓名">
        </div>
        <div class="col-md-4">
          <label class="form-label-modern">联系人</label>
          <input class="form-control" v-model="form.client_contact">
        </div>
        <div class="col-md-4">
          <label class="form-label-modern">电话</label>
          <input class="form-control" v-model="form.client_phone">
        </div>
        <div class="col-md-4">
          <label class="form-label-modern">邮箱</label>
          <input class="form-control" v-model="form.client_email" type="email">
        </div>
        <div class="col-md-3">
          <label class="form-label-modern">有效期（天）</label>
          <input class="form-control" v-model.number="form.valid_days" type="number" min="1">
        </div>
        <div class="col-md-9">
          <label class="form-label-modern">备注</label>
          <input class="form-control" v-model="form.notes" placeholder="备注">
        </div>
      </div>
    </div>

    <!-- Items -->
    <div class="card-modern">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <div class="card-title-modern mb-0"><i class="bi bi-box-seam text-primary"></i>产品明细</div>
        <button class="btn btn-outline-primary btn-modern btn-sm" @click="openPicker">
          <i class="bi bi-plus-lg"></i> 添加产品
        </button>
      </div>

      <div v-if="items.length === 0" class="text-muted text-center py-4 small">
        <i class="bi bi-inbox d-block mb-2" style="font-size:2rem"></i>
        点击"添加产品"从产品库中选择
      </div>

      <div v-else class="table-responsive">
        <table class="table table-modern">
          <thead>
            <tr>
              <th>产品</th>
              <th>规格</th>
              <th style="width:70px">数量</th>
              <th>单价</th>
              <th style="width:80px">折扣%</th>
              <th>小计</th>
              <th style="width:100px">备注</th>
              <th style="width:36px"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(it, idx) in items" :key="idx">
              <td class="td-name" style="max-width:150px">{{ it.name }}</td>
              <td class="text-muted small td-name" style="max-width:100px">{{ it.spec || '—' }}</td>
              <td><input class="form-control form-control-sm" v-model.number="it.quantity" type="number" min="1" step="1" @change="it.quantity = Math.round(it.quantity)" style="width:70px"></td>
              <td class="text-nowrap">{{ formatMoney(it.price) }}</td>
              <td><input class="form-control form-control-sm" v-model.number="it.discount" type="number" min="0" max="100" style="width:80px"></td>
              <td class="fw-medium text-nowrap">{{ formatMoney(it.price * it.quantity * it.discount / 100) }}</td>
              <td><input class="form-control form-control-sm" v-model="it.remark" placeholder="选填" style="width:100px;font-size:.75rem"></td>
              <td><button class="btn btn-sm btn-outline-danger btn-sm-icon" @click="removeItem(idx)"><i class="bi bi-x"></i></button></td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <td colspan="5"></td>
              <td class="text-muted small">原价:</td>
              <td class="fw-medium">{{ formatMoney(subtotal) }}</td>
              <td></td>
            </tr>
            <tr>
              <td colspan="5"></td>
              <td class="fw-bold small">合计:</td>
              <td class="amount-total">{{ formatMoney(total) }}</td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>

    <!-- Product Picker Modal -->
    <Teleport to="body">
      <div v-if="showPicker" class="modal-backdrop show" @click="showPicker = false"></div>
      <div v-if="showPicker" class="modal d-block modern-modal" tabindex="-1">
        <div class="modal-dialog modal-lg modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title fw-semibold">选择产品</h5>
              <button type="button" class="btn-close" @click="showPicker = false"></button>
            </div>
            <div class="modal-body">
              <input class="form-control search-box mb-3" placeholder="搜索产品名称/拼音..."
                v-model="pickerSearch" @input="searchProducts()">
              <div v-if="pickerLoading" class="text-center py-3">
                <div class="spinner-border spinner-border-sm text-primary"></div>
              </div>
              <div v-else style="max-height:50vh;overflow-y:auto">
                <div v-for="p in pickerProducts" :key="p.id"
                  class="d-flex align-items-center gap-3 p-2 picker-item"
                  style="cursor:pointer;border-bottom:1px solid var(--gray-100)"
                  @click="togglePick(p.id)">
                  <input type="checkbox" :checked="pickedIds.has(p.id)" style="pointer-events:none">
                  <div class="flex-grow-1">
                    <div class="fw-medium">{{ p.name }}</div>
                    <div class="small text-muted">{{ p.spec || '' }} {{ p.supplier ? '· ' + p.supplier : '' }}</div>
                  </div>
                  <span class="fw-medium">{{ formatMoney(p.price) }}</span>
                </div>
                <div v-if="pickerProducts.length === 0" class="text-center py-3 text-muted small">无匹配产品</div>
              </div>
            </div>
            <div class="modal-footer">
              <span class="text-muted small me-auto" v-if="pickedIds.size > 0">已选 {{ pickedIds.size }} 个</span>
              <button class="btn btn-primary btn-modern" @click="addSelectedProducts">确认添加</button>
              <button class="btn btn-secondary btn-modern" @click="showPicker = false">取消</button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
