<script setup>
import { ref, reactive, computed, watch, nextTick, inject, onMounted } from 'vue'
import { useApi } from '../composables/useApi'
import { useAdvancedApi } from '../composables/useAdvancedApi'
import { useFocusTrap } from '../composables/useFocusTrap'
import SmartRecognition from './SmartRecognition.vue'
import SpecFieldGroup from './SpecFieldGroup.vue'
import M2MSelector from './M2MSelector.vue'
import MultiImageUpload from './MultiImageUpload.vue'

const props = defineProps({
  show: Boolean,
  product: { type: Object, default: null },
  categories: { type: Array, default: () => [] },
  suppliers: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:show', 'saved'])

const toast = inject('toast')
const { api, authToken } = useApi()

// ─── Form state ───
const formTitle = computed(() => props.product ? '编辑产品' : '新增产品')
const editingId = computed(() => props.product?.id ?? null)

const formData = reactive({
  name: '', category: '', spec: '', unit: '', price: '',
  cost_price: '', supplier: '', function_desc: '', remark: '', image_url: ''
})
const existingImageUrl = ref('')
const imageData = ref('')
const imageDataMime = ref('')
const formSaving = ref(false)
const imageDownloading = ref(false)
const imageUploading = ref(false)

const smartRecognitionRef = ref(null)
const modalRef = ref(null)
const { activate, deactivate } = useFocusTrap(modalRef, closeForm)

const activeTab = ref('basic')
const { dicts, categories: catApi, productAdvanced } = useAdvancedApi()

const specDefs = ref([])
const advancedData = reactive({
  model: '', product_url: '', status: 'active', parent_id: null,
  category_id: null, manufacturer_id: null, supplier_id: null,
  specs: {},
  comm_methods: [], comm_protocols: [], power_supplies: [],
  hardware_interfaces: [], sensor_capabilities: [],
  images: [], dependencies: [],
})

// Dict data for M2M selectors
const dictData = reactive({
  commMethods: [], commProtocols: [], powerSupplies: [],
  hardwareInterfaces: [], sensorMetrics: [], manufacturers: [],
})

onMounted(async () => {
  await loadAllDicts()
})

async function loadAllDicts() {
  try {
    const [cm, cp, ps, hi, sm, mf] = await Promise.all([
      dicts.commMethods(), dicts.commProtocols(), dicts.powerSupplies(),
      dicts.sensorMetrics(), dicts.hardwareInterfaces(), dicts.manufacturers(),
    ])
    dictData.commMethods = cm?.items || []
    dictData.commProtocols = cp?.items || []
    dictData.powerSupplies = ps?.items || []
    dictData.hardwareInterfaces = hi?.items || []
    dictData.sensorMetrics = sm?.items || []
    dictData.manufacturers = mf?.items || []
  } catch (e) { /* silent */ }
}

watch(() => advancedData.category_id, async (catId) => {
  if (!catId) { specDefs.value = []; return }
  try {
    const r = await catApi.specDefs(catId)
    specDefs.value = r?.items || []
  } catch (e) { /* silent */ }
})

// ─── Watch product prop → populate form ───
watch(() => props.show, (visible) => {
  if (!visible) { deactivate(); return }
  nextTick(() => activate())
  if (props.product) {
    formData.name = props.product.name || ''
    formData.category = props.product.category || ''
    formData.spec = props.product.spec || ''
    formData.unit = props.product.unit || ''
    formData.price = props.product.price || ''
    formData.cost_price = props.product.cost_price || ''
    formData.supplier = props.product.supplier || ''
    formData.function_desc = props.product.function_desc || ''
    formData.remark = props.product.remark || ''
    formData.image_url = ''
    existingImageUrl.value = props.product.image_url || ''
    // Advanced data
    advancedData.model = props.product.model || ''
    advancedData.product_url = props.product.product_url || ''
    advancedData.status = props.product.status || 'active'
    advancedData.parent_id = props.product.parent_id || null
    advancedData.category_id = props.product.category_id || null
    advancedData.manufacturer_id = props.product.manufacturer_id || null
    advancedData.supplier_id = props.product.supplier_id || null
    advancedData.specs = props.product.specs || {}
    advancedData.comm_methods = props.product.comm_methods || []
    advancedData.comm_protocols = props.product.comm_protocols || []
    advancedData.power_supplies = props.product.power_supplies || []
    advancedData.hardware_interfaces = props.product.hardware_interfaces || []
    advancedData.sensor_capabilities = props.product.sensor_capabilities || []
    advancedData.images = props.product.images || []
  } else {
    formData.name = ''; formData.category = ''; formData.spec = ''; formData.unit = ''
    formData.price = ''; formData.cost_price = ''; formData.supplier = ''
    formData.function_desc = ''; formData.remark = ''; formData.image_url = ''
    existingImageUrl.value = ''
    // Reset advanced data
    advancedData.model = ''; advancedData.product_url = ''; advancedData.status = 'active'
    advancedData.parent_id = null; advancedData.category_id = null
    advancedData.manufacturer_id = null; advancedData.supplier_id = null
    advancedData.specs = {}; advancedData.comm_methods = []
    advancedData.comm_protocols = []; advancedData.power_supplies = []
    advancedData.hardware_interfaces = []; advancedData.sensor_capabilities = []
    advancedData.images = []
  }
  // Fetch spec defs if category is set
  if (props.product?.category_id) {
    catApi.specDefs(props.product.category_id).then(r => { specDefs.value = r?.items || [] }).catch(() => {})
  } else {
    specDefs.value = []
  }
  imageDownloading.value = false
  imageData.value = ''
  imageDataMime.value = ''
  nextTick(() => { smartRecognitionRef.value?.resetAll() })
})

// ─── Auto-download image on blur/enter ───
async function onImageUrlBlur() {
  const url = formData.image_url.trim()
  if (!url || !url.startsWith('http')) return
  if (url.startsWith('/uploads/')) return
  imageDownloading.value = true
  try {
    const r = await api('/api/download-image', 'POST', { url })
    if (r.url) {
      formData.image_url = r.url
      if (r.image_data) { imageData.value = r.image_data; imageDataMime.value = r.image_mime || 'image/jpeg' }
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

// ─── Smart Recognition ───
function onSmartFill(data) {
  if (data.name) formData.name = data.name
  if (data.spec) formData.spec = data.spec
  if (data.supplier) formData.supplier = data.supplier
  if (data.price) formData.price = data.price
  if (data.cost_price) formData.cost_price = data.cost_price
  if (data.category) formData.category = data.category
  if (data.unit) formData.unit = data.unit
  if (data.function_desc) formData.function_desc = data.function_desc
  if (data.remark) formData.remark = data.remark
}

function onSmartClear() {
  formData.name = ''
  formData.spec = ''
  formData.supplier = ''
  formData.category = ''
  formData.price = ''
  formData.cost_price = ''
  formData.unit = ''
  formData.function_desc = ''
  formData.remark = ''
}

// ─── Image paste handler ───
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
          if (r.image_data) { imageData.value = r.image_data; imageDataMime.value = r.image_mime || 'image/jpeg' }
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

// ─── Preview image ───
function currentImagePreview() {
  const url = existingImageUrl.value || formData.image_url.trim()
  if (!url) return ''
  if (url.startsWith('http')) return url
  const token = authToken.value
  return BASE_URL + url + (token ? '?token=' + token : '')
}

function deleteImage() {
  existingImageUrl.value = ''
  formData.image_url = ''
}

// ─── Close / Save ───
function closeForm() {
  emit('update:show', false)
  smartRecognitionRef.value?.resetAll()
  imageDownloading.value = false
  imageData.value = ''
  imageDataMime.value = ''
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
      ...(imageData.value ? { image_data: imageData.value, image_mime: imageDataMime.value } : {}),
      // Advanced fields
      model: advancedData.model,
      product_url: advancedData.product_url,
      status: advancedData.status,
      parent_id: advancedData.parent_id,
      category_id: advancedData.category_id,
      manufacturer_id: advancedData.manufacturer_id,
      supplier_id: advancedData.supplier_id,
      specs: advancedData.specs,
    }
    const url = editingId.value ? `/api/products/${editingId.value}` : '/api/products'
    const method = editingId.value ? 'PUT' : 'POST'
    const r = await api(url, method, body)
    if (r.error) { toast(r.error, 'danger'); return }
    toast(editingId.value ? '已更新' : '已添加')
    // Save M2M data after product save
    const productId = editingId.value || r.product?.id
    if (productId) {
      const m2mPromises = []
      if (advancedData.comm_methods.length) m2mPromises.push(productAdvanced.updateCommMethods(productId, { methods: advancedData.comm_methods }))
      if (advancedData.comm_protocols.length) m2mPromises.push(productAdvanced.updateCommProtocols(productId, { methods: advancedData.comm_protocols }))
      if (advancedData.power_supplies.length) m2mPromises.push(productAdvanced.updatePowerSupplies(productId, { methods: advancedData.power_supplies }))
      if (advancedData.hardware_interfaces.length) m2mPromises.push(productAdvanced.updateHardwareInterfaces(productId, { methods: advancedData.hardware_interfaces }))
      if (advancedData.sensor_capabilities.length) m2mPromises.push(productAdvanced.updateSensorCapabilities(productId, { methods: advancedData.sensor_capabilities }))
      if (advancedData.images.length) m2mPromises.push(productAdvanced.updateImages(productId, { images: advancedData.images }))
      await Promise.allSettled(m2mPromises)
    }
    emit('update:show', false)
    emit('saved')
  } catch (e) {
    toast('保存失败', 'danger')
  } finally {
    formSaving.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="show" class="modal-backdrop show"></div>
    <div v-if="show" ref="modalRef" class="modal d-block modern-modal" tabindex="-1">
      <div class="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title fw-semibold">{{ formTitle }}</h5>
            <button type="button" class="btn-close" @click="closeForm"></button>
          </div>
          <div class="modal-body">
            <ul class="nav nav-tabs nav-fill mb-3">
              <li class="nav-item">
                <a class="nav-link" :class="{active: activeTab === 'basic'}" href="#" @click.prevent="activeTab='basic'">
                  <i class="bi bi-info-circle me-1"></i>基本信息
                </a>
              </li>
              <li class="nav-item">
                <a class="nav-link" :class="{active: activeTab === 'specs'}" href="#" @click.prevent="activeTab='specs'">
                  <i class="bi bi-sliders me-1"></i>高级规格
                </a>
              </li>
              <li class="nav-item">
                <a class="nav-link" :class="{active: activeTab === 'params'}" href="#" @click.prevent="activeTab='params'">
                  <i class="bi bi-diagram-3 me-1"></i>技术参数
                </a>
              </li>
              <li class="nav-item">
                <a class="nav-link" :class="{active: activeTab === 'images'}" href="#" @click.prevent="activeTab='images'">
                  <i class="bi bi-images me-1"></i>图片管理
                </a>
              </li>
            </ul>

            <div class="tab-content">
              <!-- Basic Tab -->
              <div class="tab-pane" v-show="activeTab==='basic'">
                <div class="row g-2">
                  <div class="col-md-6">
                    <label class="form-label-modern">产品名称 <span class="text-danger">*</span></label>
                    <input class="form-control" v-model="formData.name" maxlength="20" placeholder="产品名称">
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
                  <div class="col-md-3">
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
                  <SmartRecognition
                    ref="smartRecognitionRef"
                    :show="true"
                    @fill="onSmartFill"
                    @clear="onSmartClear"
                  />
                </div>
              </div>

              <!-- Specs Tab -->
              <div class="tab-pane" v-show="activeTab==='specs'">
                <SpecFieldGroup
                  :specDefs="specDefs"
                  :modelValue="advancedData.specs"
                  @update:modelValue="advancedData.specs = $event"
                />
              </div>

              <!-- Params Tab -->
              <div class="tab-pane" v-show="activeTab==='params'">
                <M2MSelector
                  :dictItems="dictData.commMethods"
                  :selectedItems="advancedData.comm_methods"
                  :extraFields="[{key:'detail', label:'详情', type:'text', width:'120px'}]"
                  label="通讯方式"
                  @update:selectedItems="advancedData.comm_methods = $event"
                />
                <M2MSelector
                  :dictItems="dictData.commProtocols"
                  :selectedItems="advancedData.comm_protocols"
                  :extraFields="[{key:'detail', label:'协议详情', type:'text', width:'120px'}]"
                  label="通讯协议"
                  @update:selectedItems="advancedData.comm_protocols = $event"
                />
                <M2MSelector
                  :dictItems="dictData.powerSupplies"
                  :selectedItems="advancedData.power_supplies"
                  :extraFields="[{key:'voltage', label:'电压', type:'text', width:'80px'}, {key:'power', label:'功率', type:'text', width:'80px'}]"
                  label="供电方式"
                  @update:selectedItems="advancedData.power_supplies = $event"
                />
                <M2MSelector
                  :dictItems="dictData.hardwareInterfaces"
                  :selectedItems="advancedData.hardware_interfaces"
                  :extraFields="[{key:'quantity', label:'数量', type:'number', width:'70px'}]"
                  label="硬件接口"
                  @update:selectedItems="advancedData.hardware_interfaces = $event"
                />
                <M2MSelector
                  :dictItems="dictData.sensorMetrics"
                  :selectedItems="advancedData.sensor_capabilities"
                  :extraFields="[{key:'range', label:'量程', type:'text', width:'80px'}, {key:'accuracy', label:'精度', type:'text', width:'80px'}]"
                  label="传感能力"
                  @update:selectedItems="advancedData.sensor_capabilities = $event"
                />
              </div>

              <!-- Images Tab -->
              <div class="tab-pane" v-show="activeTab==='images'">
                <MultiImageUpload
                  :images="advancedData.images"
                  @update:images="advancedData.images = $event"
                />
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
</template>
