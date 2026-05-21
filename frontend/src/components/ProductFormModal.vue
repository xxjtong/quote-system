<script setup>
import { ref, reactive, computed, watch, nextTick, inject } from 'vue'
import { useApi, BASE_URL } from '../composables/useApi'
import SmartRecognition from './SmartRecognition.vue'

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

// ─── Watch product prop → populate form ───
watch(() => props.show, (visible) => {
  if (!visible) return
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
  } else {
    formData.name = ''; formData.category = ''; formData.spec = ''; formData.unit = ''
    formData.price = ''; formData.cost_price = ''; formData.supplier = ''
    formData.function_desc = ''; formData.remark = ''; formData.image_url = ''
    existingImageUrl.value = ''
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
    }
    const url = editingId.value ? `/api/products/${editingId.value}` : '/api/products'
    const method = editingId.value ? 'PUT' : 'POST'
    const r = await api(url, method, body)
    if (r.error) { toast(r.error, 'danger'); return }
    toast(editingId.value ? '已更新' : '已添加')
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
    <div v-if="show" class="modal d-block modern-modal" tabindex="-1">
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
