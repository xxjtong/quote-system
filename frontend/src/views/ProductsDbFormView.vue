<template>
  <div>
    <!-- Page header -->
    <div class="page-header justify-content-between">
      <h5><i class="bi bi-database me-2"></i>{{ isEdit ? '编辑产品' : '新增产品' }}</h5>
      <div style="display:flex;gap:8px">
        <button class="btn btn-outline-secondary btn-modern" @click="$router.push('/products-db')"><i class="bi bi-x-lg me-1"></i>取消</button>
        <button class="btn btn-primary btn-modern" @click="save" :disabled="saving">
          <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
          <i v-else class="bi bi-check-lg me-1"></i>
          保存
        </button>
      </div>
    </div>

    <div v-if="loaded" class="row g-3">
      <!-- Basic info -->
      <div class="col-12">
        <div class="card-modern">
        <div class="card-title-modern"><i class="bi bi-info-circle text-primary"></i>基本信息</div>
          <div style="padding:16px">
            <div class="row g-2">
              <div class="col-md-4">
                <label class="form-label small">产品名称 <span class="text-danger">*</span></label>
                <input class="form-control form-control-sm" v-model="form.name" placeholder="产品名称" />
              </div>
              <div class="col-md-4">
                <label class="form-label small">型号</label>
                <input class="form-control form-control-sm" v-model="form.model" placeholder="e.g. EG71" />
              </div>
              <div class="col-md-4">
                <label class="form-label small">SKU</label>
                <input class="form-control form-control-sm" v-model="form.sku" />
              </div>
              <div class="col-md-4">
                <label class="form-label small">品类 <span class="text-danger">*</span></label>
                <select class="form-select form-select-sm" v-model="form.category_id" @change="onCategoryChange">
                  <option :value="null">—</option>
                  <option v-for="c in flatCategories" :key="c.id" :value="c.id">{{ c.name }}</option>
                </select>
              </div>
              <div class="col-md-4">
                <label class="form-label small">厂商</label>
                <select class="form-select form-select-sm" v-model="form.manufacturer_id">
                  <option :value="null">—</option>
                  <option v-for="m in manufacturers" :key="m.id" :value="m.id">{{ m.name }}</option>
                </select>
              </div>
              <div class="col-md-4">
                <label class="form-label small">供应商</label>
                <select class="form-select form-select-sm" v-model="form.supplier_id">
                  <option :value="null">—</option>
                  <option v-for="s in suppliers" :key="s.id" :value="s.id">{{ s.name }}</option>
                </select>
              </div>
              <div class="col-md-3">
                <label class="form-label small">价格</label>
                <input class="form-control form-control-sm" v-model.number="form.price" type="number" step="0.01" min="0" />
              </div>
              <div class="col-md-3">
                <label class="form-label small">成本价</label>
                <input class="form-control form-control-sm" v-model.number="form.cost_price" type="number" step="0.01" min="0" />
              </div>
              <div class="col-md-3">
                <label class="form-label small">状态</label>
                <select class="form-select form-select-sm" v-model="form.status">
                  <option value="active">在售</option>
                  <option value="discontinued">停售</option>
                  <option value="planned">规划中</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Images -->
      <div class="col-12">
        <div class="card-modern">
        <div class="card-title-modern"><i class="bi bi-images text-primary"></i>产品图片</div>
          <div style="padding:16px">
            <div v-if="form.images.length" class="d-flex gap-2 flex-wrap mb-2">
              <div v-for="(img, idx) in form.images" :key="idx" style="position:relative">
                <img :src="img.url" style="width:72px;height:72px;object-fit:cover;border-radius:4px;border:1px solid #dee2e6" />
                <button class="btn btn-sm py-0 px-1 position-absolute top-0 end-0"
                  style="background:rgba(255,255,255,.9);font-size:.65rem;line-height:1;border-radius:0 4px 0 4px"
                  @click="form.images.splice(idx, 1)">
                  <i class="bi bi-x"></i>
                </button>
              </div>
            </div>
            <div class="d-flex gap-2 flex-wrap align-items-center">
              <label class="btn btn-outline-secondary btn-sm btn-modern" style="cursor:pointer">
                <i class="bi bi-upload me-1"></i>上传图片
                <input type="file" accept="image/*" style="display:none" @change="onFileSelect" />
              </label>
              <input v-model="imageUrlInput" class="form-control form-control-sm" style="flex:1;min-width:200px" placeholder="粘贴图片URL，回车下载" @keyup.enter="onDownloadImage" />
              <button class="btn btn-outline-secondary btn-sm btn-modern" @click="onDownloadImage" :disabled="imageDownloading">
                <span v-if="imageDownloading" class="spinner-border spinner-border-sm"></span>
                <span v-else><i class="bi bi-cloud-download me-1"></i>下载</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Comm Methods -->
      <div class="col-12">
        <div class="card-modern">
          <div class="card-title-modern"><i class="bi bi-wifi text-primary"></i>通讯方式</div>
          <div>
            <table class="table table-modern">
              <thead>
                <tr><th style="width:150px">方式</th><th>详情</th><th style="width:40px"></th></tr>
              </thead>
              <tbody>
                <tr v-for="(cm, idx) in form.comm_methods" :key="idx">
                  <td>
                    <select class="form-select form-select-sm" v-model="cm.dict_id">
                      <option :value="null">—</option>
                      <option v-for="m in commMethods" :key="m.id" :value="m.id">{{ m.name }}</option>
                    </select>
                  </td>
                  <td><input class="form-control form-control-sm" v-model="cm.detail" placeholder="e.g. CN470 8通道" /></td>
                  <td><button class="btn btn-sm btn-outline-danger btn-sm-icon" @click="form.comm_methods.splice(idx, 1)"><i class="bi bi-trash"></i></button></td>
                </tr>
              </tbody>
            </table>
            <div class="p-2">
              <button class="btn btn-outline-secondary btn-sm btn-modern" @click="form.comm_methods.push({ dict_id: null, detail: '' })">
                <i class="bi bi-plus-lg me-1"></i>添加通讯方式
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Comm Protocols -->
      <div class="col-12">
        <div class="card-modern">
          <div class="card-title-modern"><i class="bi bi-diagram-3 text-primary"></i>通讯协议</div>
          <div>
            <table class="table table-modern">
              <thead>
                <tr><th style="width:150px">协议</th><th style="width:120px">方向</th><th style="width:40px"></th></tr>
              </thead>
              <tbody>
                <tr v-for="(cp, idx) in form.comm_protocols" :key="idx">
                  <td>
                    <select class="form-select form-select-sm" v-model="cp.dict_id">
                      <option :value="null">—</option>
                      <option v-for="p in commProtocols" :key="p.id" :value="p.id">{{ p.name }}</option>
                    </select>
                  </td>
                  <td>
                    <select class="form-select form-select-sm" v-model="cp.direction">
                      <option value="both">双向</option>
                      <option value="acquisition">采集(下行)</option>
                      <option value="forwarding">转发(上行)</option>
                    </select>
                  </td>
                  <td><button class="btn btn-sm btn-outline-danger btn-sm-icon" @click="form.comm_protocols.splice(idx, 1)"><i class="bi bi-trash"></i></button></td>
                </tr>
              </tbody>
            </table>
            <div class="p-2">
              <button class="btn btn-outline-secondary btn-sm btn-modern" @click="form.comm_protocols.push({ dict_id: null, direction: 'both' })">
                <i class="bi bi-plus-lg me-1"></i>添加协议
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Power Supplies -->
      <div class="col-12">
        <div class="card-modern">
          <div class="card-title-modern"><i class="bi bi-battery-full text-primary"></i>供电方式</div>
          <div>
            <table class="table table-modern">
              <thead>
                <tr><th style="width:150px">方式</th><th>电压/规格</th><th>续航</th><th style="width:40px"></th></tr>
              </thead>
              <tbody>
                <tr v-for="(ps, idx) in form.power_supplies" :key="idx">
                  <td>
                    <select class="form-select form-select-sm" v-model="ps.dict_id">
                      <option :value="null">—</option>
                      <option v-for="p in powerSupplies" :key="p.id" :value="p.id">{{ p.name }}</option>
                    </select>
                  </td>
                  <td><input class="form-control form-control-sm" v-model="ps.voltage_range" placeholder="e.g. 9-24V DC" /></td>
                  <td><input class="form-control form-control-sm" v-model="ps.battery_life" placeholder="e.g. 5年" /></td>
                  <td><button class="btn btn-sm btn-outline-danger btn-sm-icon" @click="form.power_supplies.splice(idx, 1)"><i class="bi bi-trash"></i></button></td>
                </tr>
              </tbody>
            </table>
            <div class="p-2">
              <button class="btn btn-outline-secondary btn-sm btn-modern" @click="form.power_supplies.push({ dict_id: null, voltage_range: '', battery_life: '' })">
                <i class="bi bi-plus-lg me-1"></i>添加供电方式
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Hardware Interfaces -->
      <div class="col-12">
        <div class="card-modern">
          <div class="card-title-modern"><i class="bi bi-plug text-primary"></i>硬件接口</div>
          <div>
            <table class="table table-modern">
              <thead>
                <tr><th>接口名称</th><th style="width:80px">数量</th><th>描述</th><th style="width:40px"></th></tr>
              </thead>
              <tbody>
                <tr v-for="(hi, idx) in form.hardware_interfaces" :key="idx">
                  <td><input class="form-control form-control-sm" v-model="hi.interface_name" placeholder="e.g. RS485" /></td>
                  <td><input class="form-control form-control-sm" v-model.number="hi.quantity" type="number" min="1" /></td>
                  <td><input class="form-control form-control-sm" v-model="hi.description" placeholder="e.g. 波特率1200~115200" /></td>
                  <td><button class="btn btn-sm btn-outline-danger btn-sm-icon" @click="form.hardware_interfaces.splice(idx, 1)"><i class="bi bi-trash"></i></button></td>
                </tr>
              </tbody>
            </table>
            <div class="p-2">
              <button class="btn btn-outline-secondary btn-sm btn-modern" @click="form.hardware_interfaces.push({ interface_name: '', quantity: 1, description: '' })">
                <i class="bi bi-plus-lg me-1"></i>添加接口
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Sensor Capabilities -->
      <div class="col-12">
        <div class="card-modern">
          <div class="card-title-modern"><i class="bi bi-activity text-primary"></i>传感能力</div>
          <div>
            <table class="table table-modern">
              <thead>
                <tr><th style="width:120px">指标</th><th>量程</th><th>精度</th><th>分辨率</th><th style="width:40px"></th></tr>
              </thead>
              <tbody>
                <tr v-for="(sc, idx) in form.sensor_capabilities" :key="idx">
                  <td>
                    <select class="form-select form-select-sm" v-model="sc.dict_id">
                      <option :value="null">—</option>
                      <option v-for="m in sensorMetrics" :key="m.id" :value="m.id">{{ m.name }}</option>
                    </select>
                  </td>
                  <td><input class="form-control form-control-sm" v-model="sc.measure_range" placeholder="e.g. -20°C~60°C" /></td>
                  <td><input class="form-control form-control-sm" v-model="sc.accuracy" placeholder="e.g. ±0.2°C" /></td>
                  <td><input class="form-control form-control-sm" v-model="sc.resolution" placeholder="e.g. 0.1°C" /></td>
                  <td><button class="btn btn-sm btn-outline-danger btn-sm-icon" @click="form.sensor_capabilities.splice(idx, 1)"><i class="bi bi-trash"></i></button></td>
                </tr>
              </tbody>
            </table>
            <div class="p-2">
              <button class="btn btn-outline-secondary btn-sm btn-modern" @click="form.sensor_capabilities.push({ dict_id: null, measure_range: '', accuracy: '', resolution: '' })">
                <i class="bi bi-plus-lg me-1"></i>添加传感指标
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Dynamic Specs -->
      <div class="col-12" v-if="specDefs.length">
        <div class="card-modern">
          <div class="card-title-modern"><i class="bi bi-sliders text-primary"></i>品类规格参数</div>
          <div style="padding:16px">
            <div class="row g-2">
              <div v-for="sd in specDefs" :key="sd.id" class="col-md-4">
                <label class="form-label small">
                  {{ sd.display_name }}
                  <span v-if="sd.unit" class="text-muted">({{ sd.unit }})</span>
                </label>
                <input v-if="sd.spec_type === 'string'" class="form-control form-control-sm" v-model="form.specs[sd.spec_key]" />
                <input v-else-if="sd.spec_type === 'number'" class="form-control form-control-sm" v-model.number="form.specs[sd.spec_key]" type="number" step="any" />
                <div v-else-if="sd.spec_type === 'boolean'" class="form-check">
                  <input class="form-check-input" type="checkbox" v-model="form.specs[sd.spec_key]" :id="'spec_' + sd.id" />
                  <label class="form-check-label small" :for="'spec_' + sd.id">{{ sd.display_name }}</label>
                </div>
                <select v-else-if="sd.spec_type === 'enum' && sd.options" class="form-select form-select-sm" v-model="form.specs[sd.spec_key]">
                  <option :value="null">—</option>
                  <option v-for="opt in sd.options" :key="opt" :value="opt">{{ opt }}</option>
                </select>
                <input v-else class="form-control form-control-sm" v-model="form.specs[sd.spec_key]" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Description -->
      <div class="col-12">
        <div class="card-modern">
        <div class="card-title-modern"><i class="bi bi-text-paragraph text-primary"></i>描述</div>
          <div style="padding:16px">
            <textarea class="form-control" v-model="form.function_desc" rows="3" placeholder="功能描述"></textarea>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-else class="text-center py-5 text-muted">
      <div class="spinner-border spinner-border-sm text-primary me-2" role="status"></div>
      加载中...
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, inject } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApi, BASE_URL } from '../composables/useApi'
import { useAdvancedApi } from '../composables/useAdvancedApi'

const route = useRoute()
const router = useRouter()
const toast = inject('toast')
const { api } = useApi()
const { dicts, categories, productAdvanced } = useAdvancedApi()

const isEdit = computed(() => !!route.params.id)
const saving = ref(false)
const loaded = ref(false)

// Dict data
const flatCategories = ref([])
const suppliers = ref([])
const manufacturers = ref([])
const commMethods = ref([])
const commProtocols = ref([])
const powerSupplies = ref([])
const sensorMetrics = ref([])
const specDefs = ref([])

const imageUrlInput = ref('')
const imageDownloading = ref(false)

const form = ref({
  name: '', model: '', sku: '', category_id: null, manufacturer_id: null, supplier_id: null,
  price: 0, cost_price: 0, function_desc: '', status: 'active', parent_id: null,
  comm_methods: [], comm_protocols: [], power_supplies: [],
  hardware_interfaces: [], sensor_capabilities: [], images: [],
  specs: {},
})

function flattenTree(nodes, result = []) {
  for (const n of nodes) {
    result.push(n)
    if (n.children?.length) flattenTree(n.children, result)
  }
  return result
}

// ─── Image handling ───
async function onFileSelect(e) {
  const file = e.target.files?.[0]
  if (!file) return
  const fd = new FormData()
  fd.append('file', file)
  try {
    const res = await api('/api/upload/image', 'POST', fd)
    if (res.url) {
      form.value.images.push({ url: res.url, is_primary: form.value.images.length === 0, sort_order: form.value.images.length })
      toast('图片已上传')
    } else {
      toast(res.error || '上传失败', 'warning')
    }
  } catch (err) {
    toast('上传失败', 'danger')
  }
  e.target.value = ''
}

async function onDownloadImage() {
  const url = imageUrlInput.value.trim()
  if (!url) return
  imageDownloading.value = true
  try {
    const res = await api('/api/download-image', 'POST', { url })
    if (res.url) {
      form.value.images.push({ url: res.url, is_primary: form.value.images.length === 0, sort_order: form.value.images.length })
      imageUrlInput.value = ''
      toast('图片已下载')
    } else {
      toast(res.error || '下载失败', 'warning')
    }
  } catch (err) {
    toast('下载失败', 'danger')
  }
  imageDownloading.value = false
}

// ─── Category change → load spec defs ───
async function onCategoryChange() {
  form.value.specs = {}
  if (form.value.category_id) {
    try {
      const res = await categories.specDefs(form.value.category_id)
      specDefs.value = res?.items || []
      for (const sd of specDefs.value) {
        if (!(sd.spec_key in form.value.specs)) {
          form.value.specs[sd.spec_key] = sd.spec_type === 'boolean' ? false : null
        }
      }
    } catch (e) {
      specDefs.value = []
    }
  } else {
    specDefs.value = []
  }
}

// ─── Save ───
async function save() {
  if (!form.value.name.trim()) {
    toast('请输入产品名称', 'warning')
    return
  }
  saving.value = true
  try {
    // Extract basic product data
    const payload = {
      name: form.value.name.trim(),
      model: form.value.model.trim(),
      sku: form.value.sku.trim(),
      category_id: form.value.category_id,
      manufacturer_id: form.value.manufacturer_id,
      supplier_id: form.value.supplier_id,
      price: form.value.price || 0,
      cost_price: form.value.cost_price || 0,
      function_desc: form.value.function_desc.trim(),
      status: form.value.status,
      parent_id: form.value.parent_id,
      specs: form.value.specs || {},
    }

    // Set primary image URL
    const primaryImg = form.value.images.find(i => i.is_primary)
    if (primaryImg) payload.image_url = primaryImg.url

    // Extract M2M data
    const comm_methods = form.value.comm_methods.filter(m => m.dict_id)
    const comm_protocols = form.value.comm_protocols.filter(m => m.dict_id)
    const power_supplies = form.value.power_supplies.filter(m => m.dict_id)
    const hardware_interfaces = form.value.hardware_interfaces.filter(i => i.interface_name)
    const sensor_capabilities = form.value.sensor_capabilities.filter(s => s.dict_id)
    const images = form.value.images

    let productId
    if (isEdit.value) {
      const r = await api('/api/products/' + route.params.id, 'PUT', payload)
      if (r && r.error) { toast(r.error, 'danger'); return }
      productId = Number(route.params.id)
    } else {
      const r = await api('/api/products', 'POST', payload)
      if (r && r.error) { toast(r.error, 'danger'); return }
      productId = r.product?.id
      if (!productId) { toast('创建失败', 'danger'); return }
    }

    // Save M2M data
    const m2mPromises = []
    if (comm_methods.length) m2mPromises.push(productAdvanced.updateCommMethods(productId, { methods: comm_methods }))
    if (comm_protocols.length) m2mPromises.push(productAdvanced.updateCommProtocols(productId, { methods: comm_protocols }))
    if (power_supplies.length) m2mPromises.push(productAdvanced.updatePowerSupplies(productId, { methods: power_supplies }))
    if (hardware_interfaces.length) m2mPromises.push(productAdvanced.updateHardwareInterfaces(productId, { methods: hardware_interfaces }))
    if (sensor_capabilities.length) m2mPromises.push(productAdvanced.updateSensorCapabilities(productId, { methods: sensor_capabilities }))
    if (images.length) m2mPromises.push(productAdvanced.updateImages(productId, { images }))
    await Promise.allSettled(m2mPromises)

    toast(isEdit.value ? '产品已更新' : '产品已创建')
    router.push('/products-db')
  } catch (e) {
    toast('保存失败', 'danger')
  } finally {
    saving.value = false
  }
}

// ─── Lifecycle ───
onMounted(async () => {
  try {
    const [catRes, supRes, mfgRes, cmRes, cpRes, psRes, smRes] = await Promise.all([
      categories.list(), dicts.suppliers(), dicts.manufacturers(),
      dicts.commMethods(), dicts.commProtocols(), dicts.powerSupplies(), dicts.sensorMetrics(),
    ])
    const cats = catRes?.items || []
    flatCategories.value = flattenTree(cats)
    suppliers.value = supRes?.items || []
    manufacturers.value = mfgRes?.items || []
    commMethods.value = cmRes?.items || []
    commProtocols.value = cpRes?.items || []
    powerSupplies.value = psRes?.items || []
    sensorMetrics.value = smRes?.items || []

    if (isEdit.value) {
      const res = await api('/api/products/' + route.params.id)
      const p = res.product
      if (p) {
        form.value = {
          name: p.name || '', model: p.model || '', sku: p.sku || '',
          category_id: p.category_id || null,
          manufacturer_id: p.manufacturer_id || null,
          supplier_id: p.supplier_id || null,
          price: p.price || 0, cost_price: p.cost_price || 0,
          function_desc: p.function_desc || '', status: p.status || 'active',
          parent_id: p.parent_id || null,
          comm_methods: p.comm_methods || [],
          comm_protocols: p.comm_protocols || [],
          power_supplies: p.power_supplies || [],
          hardware_interfaces: p.hardware_interfaces || [],
          sensor_capabilities: p.sensor_capabilities || [],
          images: p.images || [],
          specs: { ...(p.specs || {}) },
        }
        if (p.category_id) await onCategoryChange()
      }
    }
    loaded.value = true
  } catch (e) {
    toast('加载数据失败', 'danger')
    loaded.value = true
  }
})
</script>
