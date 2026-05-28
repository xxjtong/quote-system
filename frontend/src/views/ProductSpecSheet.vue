<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApi, BASE_URL } from '../composables/useApi'

const route = useRoute()
const router = useRouter()
const { api, authToken, isAdmin, currentUser } = useApi()

const product = ref(null)
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  const id = route.params.id
  if (!id) {
    error.value = '无效的产品ID'
    loading.value = false
    return
  }
  try {
    const r = await api(`/api/products/${id}`)
    if (r?.product) {
      product.value = r.product
    } else {
      error.value = '产品不存在'
    }
  } catch (e) {
    error.value = '加载失败'
  } finally {
    loading.value = false
  }
})

function imgSrc(url) {
  if (!url) return ''
  if (url.startsWith('http')) return url
  const token = authToken.value
  return BASE_URL + url + (token ? '?token=' + token : '')
}

function hasM2MData(arr) { return arr && arr.length > 0 }

function specEntries(obj) {
  if (!obj || typeof obj !== 'object') return []
  return Object.entries(obj)
}

function formatPrice(v) {
  return '¥' + Number(v || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function goBack() {
  router.push({ name: 'products' })
}
</script>

<template>
  <div class="spec-sheet-page">
    <!-- Loading -->
    <div v-if="loading" class="text-center py-5">
      <div class="spinner-border text-primary" role="status"></div>
      <p class="mt-2 text-muted">加载中...</p>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="text-center py-5">
      <i class="bi bi-exclamation-triangle text-warning" style="font-size:3rem"></i>
      <p class="mt-2 text-muted">{{ error }}</p>
      <button class="btn btn-primary" @click="goBack">返回产品列表</button>
    </div>

    <!-- Spec Sheet -->
    <div v-else-if="product" class="spec-sheet-content">
      <!-- Header section -->
      <div class="spec-sheet-header text-center mb-4 pb-3 border-bottom">
        <h2 class="fw-bold mb-1">{{ product.name }}</h2>
        <div class="text-muted">
          <span v-if="product.model" class="me-3">型号: {{ product.model }}</span>
          <span v-if="product.spec">规格: {{ product.spec }}</span>
        </div>
      </div>

      <!-- Product info grid -->
      <div class="row mb-4">
        <div class="col-md-6">
          <table class="table table-bordered spec-table">
            <tbody>
              <tr><td class="spec-label">分类</td><td>{{ product.category || '—' }}</td></tr>
              <tr><td class="spec-label">规格型号</td><td>{{ product.spec || '—' }}</td></tr>
              <tr><td class="spec-label">厂商</td><td>{{ product.supplier || '—' }}</td></tr>
              <tr><td class="spec-label">单位</td><td>{{ product.unit || '—' }}</td></tr>
              <tr><td class="spec-label">销售单价</td><td class="fw-medium">{{ formatPrice(product.price) }}</td></tr>
              <tr v-if="isAdmin() && product.cost_price"><td class="spec-label">成本价</td><td>{{ formatPrice(product.cost_price) }}</td></tr>
            </tbody>
          </table>
        </div>
        <div class="col-md-6 text-center">
          <img v-if="product.has_image || product.image_url"
            :src="product.has_image
              ? BASE_URL + '/api/products/' + product.id + '/image' + (authToken.value ? '?token=' + authToken.value : '')
              : imgSrc(product.image_url)"
            style="max-width:100%;max-height:250px;object-fit:contain;border:1px solid #dee2e6;border-radius:6px">
          <div v-else class="text-muted py-5"><i class="bi bi-image" style="font-size:3rem"></i></div>
        </div>
      </div>

      <!-- Specs -->
      <div v-if="specEntries(product.specs).length" class="mb-4">
        <h5 class="fw-semibold border-bottom pb-2 mb-3">
          <i class="bi bi-sliders me-2"></i>技术规格
        </h5>
        <table class="table table-bordered spec-table">
          <tbody>
            <tr v-for="[key, val] in specEntries(product.specs)" :key="key">
              <td class="spec-label" style="width:140px">{{ key }}</td>
              <td>{{ val || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- M2M sections -->
      <div v-if="hasM2MData(product.comm_methods) || hasM2MData(product.comm_protocols) || hasM2MData(product.power_supplies) || hasM2MData(product.hardware_interfaces) || hasM2MData(product.sensor_capabilities)" class="mb-4">
        <h5 class="fw-semibold border-bottom pb-2 mb-3">
          <i class="bi bi-diagram-3 me-2"></i>技术参数
        </h5>
        <div class="row">
          <div v-if="hasM2MData(product.comm_methods)" class="col-md-6 mb-3">
            <h6 class="small fw-semibold text-secondary">通讯方式</h6>
            <div v-for="cm in product.comm_methods" :key="cm.id" class="mb-1">
              <span class="badge bg-info me-1">{{ cm.dict_name }}</span>
              <span v-if="cm.detail" class="text-muted small">{{ cm.detail }}</span>
            </div>
          </div>
          <div v-if="hasM2MData(product.comm_protocols)" class="col-md-6 mb-3">
            <h6 class="small fw-semibold text-secondary">通讯协议</h6>
            <div v-for="cp in product.comm_protocols" :key="cp.id" class="mb-1">
              <span class="badge bg-info me-1">{{ cp.dict_name }}</span>
              <span v-if="cp.detail" class="text-muted small">{{ cp.detail }}</span>
            </div>
          </div>
          <div v-if="hasM2MData(product.power_supplies)" class="col-md-6 mb-3">
            <h6 class="small fw-semibold text-secondary">供电方式</h6>
            <div v-for="ps in product.power_supplies" :key="ps.id" class="mb-1">
              <span class="badge bg-warning text-dark me-1">{{ ps.dict_name }}</span>
              <span v-if="ps.voltage" class="text-muted small me-2">电压: {{ ps.voltage }}</span>
              <span v-if="ps.power" class="text-muted small">功率: {{ ps.power }}</span>
            </div>
          </div>
          <div v-if="hasM2MData(product.hardware_interfaces)" class="col-md-6 mb-3">
            <h6 class="small fw-semibold text-secondary">硬件接口</h6>
            <div v-for="hi in product.hardware_interfaces" :key="hi.id" class="mb-1">
              <span class="badge bg-secondary me-1">{{ hi.dict_name }}</span>
              <span v-if="hi.quantity" class="text-muted small">x{{ hi.quantity }}</span>
            </div>
          </div>
          <div v-if="hasM2MData(product.sensor_capabilities)" class="col-md-6 mb-3">
            <h6 class="small fw-semibold text-secondary">传感能力</h6>
            <div v-for="sc in product.sensor_capabilities" :key="sc.id" class="mb-1">
              <span class="badge bg-success me-1">{{ sc.dict_name }}</span>
              <span v-if="sc.range" class="text-muted small me-2">量程: {{ sc.range }}</span>
              <span v-if="sc.accuracy" class="text-muted small">精度: {{ sc.accuracy }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Multi images -->
      <div v-if="product.images && product.images.length" class="mb-4">
        <h5 class="fw-semibold border-bottom pb-2 mb-3">
          <i class="bi bi-images me-2"></i>产品图片
        </h5>
        <div class="d-flex flex-wrap gap-2">
          <img v-for="(img, idx) in product.images" :key="idx"
            :src="imgSrc(img.url)"
            style="width:120px;height:120px;object-fit:cover;border:1px solid #dee2e6;border-radius:6px">
        </div>
      </div>

      <!-- Function description / remarks -->
      <div v-if="product.function_desc" class="mb-3">
        <h5 class="fw-semibold border-bottom pb-2 mb-2">功能描述</h5>
        <p class="text-muted">{{ product.function_desc }}</p>
      </div>
      <div v-if="product.remark" class="mb-3">
        <h5 class="fw-semibold border-bottom pb-2 mb-2">备注</h5>
        <p class="text-muted">{{ product.remark }}</p>
      </div>

      <!-- Footer -->
      <div class="text-center text-muted small border-top pt-3 mt-4">
        <p>报价系统 · 规格书 · {{ new Date().toLocaleDateString('zh-CN') }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.spec-sheet-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 2rem 1.5rem;
}

.spec-table {
  font-size: 0.88rem;
}

.spec-label {
  width: 120px;
  font-weight: 500;
  color: #6c757d;
  background-color: #f8f9fa;
}

@media print {
  .spec-sheet-page {
    max-width: 100%;
    padding: 0.5in;
  }
  .spec-sheet-page :deep(.btn) {
    display: none !important;
  }
  .spec-table {
    border-color: #000;
  }
  .spec-label {
    background-color: #f0f0f0 !important;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
}
</style>
