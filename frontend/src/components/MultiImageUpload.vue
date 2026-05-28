<script setup>
import { ref, inject } from 'vue'
import { useApi } from '../composables/useApi'

const props = defineProps({
  images: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:images'])

const toast = inject('toast')
const { api, authToken } = useApi()

const showUrlInput = ref(false)
const urlValue = ref('')
const imageUploading = ref(false)

function updateImages(newImages) {
  emit('update:images', newImages)
}

function setPrimary(index) {
  const updated = props.images.map((img, i) => ({
    ...img,
    is_primary: i === index,
  }))
  updateImages(updated)
}

function removeImage(index) {
  const updated = props.images.filter((_, i) => i !== index)
  updateImages(updated)
}

function addImage(newUrl) {
  const updated = [...props.images, {
    url: newUrl,
    is_primary: props.images.length === 0,
    sort_order: props.images.length,
    alt_text: '',
  }]
  updateImages(updated)
}

async function handleUrlSubmit() {
  const url = urlValue.value.trim()
  if (!url) return
  if (!url.startsWith('http')) {
    toast('请输入有效的URL', 'warning')
    return
  }
  addImage(url)
  urlValue.value = ''
  showUrlInput.value = false
}

async function handleFileUpload(e) {
  const file = e.target.files?.[0]
  if (!file) return
  imageUploading.value = true
  try {
    const form = new FormData()
    form.append('file', file)
    const r = await api('/api/upload/image', 'POST', form)
    if (r.url) {
      addImage(r.url)
      toast('图片已上传')
    } else {
      toast(r.error || '上传失败', 'warning')
    }
  } catch (err) {
    toast('上传失败', 'warning')
  } finally {
    imageUploading.value = false
    e.target.value = ''
  }
}

function imageSrc(imgUrl) {
  if (!imgUrl) return ''
  if (imgUrl.startsWith('http')) return imgUrl
  const token = authToken.value
  return (import.meta.env.BASE_URL === '/' ? '' : import.meta.env.BASE_URL.replace(/\/$/, '')) + imgUrl + (token ? '?token=' + token : '')
}
</script>

<template>
  <div class="multi-image-upload">
    <div class="d-flex flex-wrap gap-2 mb-2">
      <div v-for="(img, idx) in images" :key="idx"
        class="position-relative"
        style="width:100px;height:100px">
        <img :src="imageSrc(img.url)"
          style="width:100%;height:100%;object-fit:cover;border-radius:6px;border:1px solid var(--gray-200)">
        <div class="position-absolute top-0 start-0 p-1">
          <span v-if="img.is_primary"
            class="badge bg-warning text-dark" style="font-size:.6rem;cursor:pointer"
            @click="setPrimary(idx)">主图</span>
        </div>
        <div class="position-absolute bottom-0 end-0 p-1 d-flex gap-1">
          <button v-if="!img.is_primary" class="btn btn-sm btn-outline-primary py-0 px-1"
            @click="setPrimary(idx)" title="设为主图" style="font-size:.6rem;line-height:1;background:rgba(255,255,255,.8)">
            <i class="bi bi-star"></i>
          </button>
          <button class="btn btn-sm btn-outline-danger py-0 px-1"
            @click="removeImage(idx)" title="删除" style="font-size:.6rem;line-height:1;background:rgba(255,255,255,.8)">
            <i class="bi bi-trash"></i>
          </button>
        </div>
      </div>

      <!-- Add button -->
      <div class="d-flex align-items-center justify-content-center"
        style="width:100px;height:100px;border:2px dashed var(--gray-300);border-radius:6px;cursor:pointer">
        <div class="text-center">
          <button class="btn btn-sm btn-outline-secondary py-1 px-2"
            @click="showUrlInput = !showUrlInput" title="添加图片">
            <i class="bi bi-plus-lg"></i>
          </button>
          <div class="mt-1">
            <label class="btn btn-sm btn-outline-secondary py-0 px-1" style="font-size:.7rem;cursor:pointer">
              <i class="bi bi-upload"></i>
              <input type="file" accept="image/*" class="d-none" @change="handleFileUpload"
                :disabled="imageUploading">
            </label>
          </div>
        </div>
      </div>
    </div>

    <!-- URL input -->
    <div v-if="showUrlInput" class="input-group input-group-sm mb-2">
      <input class="form-control" v-model="urlValue" placeholder="输入图片URL"
        @keydown.enter.prevent="handleUrlSubmit">
      <button class="btn btn-outline-primary" @click="handleUrlSubmit">添加</button>
      <button class="btn btn-outline-secondary" @click="showUrlInput = false; urlValue = ''">取消</button>
    </div>

    <div v-if="imageUploading" class="text-muted small">
      <span class="spinner-border spinner-border-sm me-1"></span>上传中...
    </div>
  </div>
</template>
