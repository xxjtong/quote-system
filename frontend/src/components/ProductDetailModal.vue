<script setup>
import { ref, watch, nextTick, computed, inject } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { BASE_URL, useApi } from '../composables/useApi'
import { useFocusTrap } from '../composables/useFocusTrap'
import { formatMoney } from '../composables/useUtils'
import { useAdvancedApi } from '../composables/useAdvancedApi'

const props = defineProps({
  show: Boolean,
  product: Object,
})

const emit = defineEmits(['update:show', 'edit'])

const { authToken, isAdmin, currentUser } = useApi()

const route = useRoute()
const router = useRouter()
const toast = inject('toast')
const { productAdvanced } = useAdvancedApi()

// Comparison
const compareIds = ref([])
try {
  const stored = localStorage.getItem('quote_compare_ids')
  if (stored) compareIds.value = JSON.parse(stored)
} catch (e) { /* ignore */ }

const isInCompare = computed(() => compareIds.value.includes(props.product?.id))

function toggleCompare() {
  const id = props.product?.id
  if (!id) return
  const idx = compareIds.value.indexOf(id)
  if (idx >= 0) {
    compareIds.value.splice(idx, 1)
  } else {
    if (compareIds.value.length >= 5) {
      toast('最多选择5个产品对比', 'warning')
      return
    }
    compareIds.value.push(id)
  }
  localStorage.setItem('quote_compare_ids', JSON.stringify(compareIds.value))
}

const productHasSpecs = computed(() => props.product?.specs && typeof props.product.specs === 'object' && Object.keys(props.product.specs).length > 0)
const productHasImages = computed(() => props.product?.images && props.product.images.length > 0)

function hasM2MData(arr) { return arr && arr.length > 0 }

function imageThumbSrc(imgUrl) {
  if (!imgUrl) return ''
  if (imgUrl.startsWith('http')) return imgUrl
  const token = authToken.value
  return BASE_URL + imgUrl + (token ? '?token=' + token : '')
}

function openSpecSheet() {
  if (props.product?.id) {
    window.open(`/products/${props.product.id}/spec-sheet`, '_blank')
  }
}

const modalRef = ref(null)
function close() {
  emit('update:show', false)
}
const { activate, deactivate } = useFocusTrap(modalRef, close)

watch(() => props.show, (val) => {
  if (val) nextTick(() => activate())
  else deactivate()
})

function detailImageSrc(p) {
  if (!p || (!p.has_image && !p.image_url)) return ''
  const token = authToken.value
  if (p.has_image) return BASE_URL + '/api/products/' + p.id + '/image' + (token ? '?token=' + token : '')
  return p.image_url.startsWith('http') ? p.image_url : BASE_URL + p.image_url
}

function onEdit() {
  emit('edit', props.product)
  close()
}
</script>

<template>
  <Teleport to="body">
    <div v-if="show && product" class="modal-backdrop show" @click="close"></div>
    <div v-if="show && product" ref="modalRef" class="modal d-block modern-modal" tabindex="-1" @click.self="close">
      <div class="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title fw-semibold" style="word-break:break-all;white-space:normal">{{ product.name }}</h5>
            <button type="button" class="btn-close" @click="close"></button>
          </div>
          <div class="modal-body">
            <div class="text-center mb-3">
              <img v-if="product.has_image || product.image_url" :src="detailImageSrc(product)"
                style="max-width:400px;max-height:300px;object-fit:contain;border-radius:8px;border:1px solid var(--gray-200)">
              <div v-else class="text-muted py-3"><i class="bi bi-image" style="font-size:2rem"></i><p class="small mt-1">暂无图片</p></div>
            </div>
            <table class="table table-sm" style="font-size:.85rem">
              <tbody>
                <tr><td class="text-muted" style="width:80px">分类</td><td class="fw-medium">{{ product.category || '—' }}</td></tr>
                <tr><td class="text-muted">规格型号</td><td>{{ product.spec || '—' }}</td></tr>
                <tr><td class="text-muted">单位</td><td>{{ product.unit || '—' }}</td></tr>
                <tr><td class="text-muted">厂商</td><td>{{ product.supplier || '—' }}</td></tr>
                <tr><td class="text-muted">销售单价</td><td class="fw-medium text-primary">{{ formatMoney(product.price) }}</td></tr>
                <tr v-if="isAdmin() && product.cost_price"><td class="text-muted">成本价</td><td>¥{{ product.cost_price }}</td></tr>
                <tr v-if="product.function_desc"><td class="text-muted">功能描述</td><td>{{ product.function_desc }}</td></tr>
                <tr v-if="product.remark"><td class="text-muted">备注</td><td>{{ product.remark }}</td></tr>
              </tbody>
            </table>

            <!-- Specs -->
            <div v-if="productHasSpecs" class="mb-3">
              <h6 class="fw-semibold border-bottom pb-1">
                <i class="bi bi-sliders me-1"></i>技术规格
              </h6>
              <table class="table table-sm" style="font-size:.82rem">
                <tbody>
                  <tr v-for="(val, key) in (product.specs || {})" :key="key">
                    <td class="text-muted" style="width:100px">{{ key }}</td>
                    <td class="fw-medium">{{ val || '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- M2M sections -->
            <div v-if="hasM2MData(product.comm_methods) || hasM2MData(product.comm_protocols) || hasM2MData(product.power_supplies) || hasM2MData(product.hardware_interfaces) || hasM2MData(product.sensor_capabilities)" class="mb-3">
              <h6 class="fw-semibold border-bottom pb-1">
                <i class="bi bi-diagram-3 me-1"></i>技术参数
              </h6>
              <details v-if="hasM2MData(product.comm_methods)" class="mb-1">
                <summary class="small fw-medium text-secondary" style="cursor:pointer">通讯方式 ({{ product.comm_methods.length }})</summary>
                <div class="mt-1 small" v-for="cm in product.comm_methods" :key="cm.id">
                  <span class="badge bg-info me-1">{{ cm.dict_name }}</span>
                  <span v-if="cm.detail" class="text-muted">{{ cm.detail }}</span>
                </div>
              </details>
              <details v-if="hasM2MData(product.comm_protocols)" class="mb-1">
                <summary class="small fw-medium text-secondary" style="cursor:pointer">通讯协议 ({{ product.comm_protocols.length }})</summary>
                <div class="mt-1 small" v-for="cp in product.comm_protocols" :key="cp.id">
                  <span class="badge bg-info me-1">{{ cp.dict_name }}</span>
                  <span v-if="cp.detail" class="text-muted">{{ cp.detail }}</span>
                </div>
              </details>
              <details v-if="hasM2MData(product.power_supplies)" class="mb-1">
                <summary class="small fw-medium text-secondary" style="cursor:pointer">供电方式 ({{ product.power_supplies.length }})</summary>
                <div class="mt-1 small" v-for="ps in product.power_supplies" :key="ps.id">
                  <span class="badge bg-warning text-dark me-1">{{ ps.dict_name }}</span>
                  <span v-if="ps.voltage" class="text-muted me-1">电压: {{ ps.voltage }}</span>
                  <span v-if="ps.power" class="text-muted">功率: {{ ps.power }}</span>
                </div>
              </details>
              <details v-if="hasM2MData(product.hardware_interfaces)" class="mb-1">
                <summary class="small fw-medium text-secondary" style="cursor:pointer">硬件接口 ({{ product.hardware_interfaces.length }})</summary>
                <div class="mt-1 small" v-for="hi in product.hardware_interfaces" :key="hi.id">
                  <span class="badge bg-secondary me-1">{{ hi.dict_name }}</span>
                  <span v-if="hi.quantity" class="text-muted">x{{ hi.quantity }}</span>
                </div>
              </details>
              <details v-if="hasM2MData(product.sensor_capabilities)" class="mb-1">
                <summary class="small fw-medium text-secondary" style="cursor:pointer">传感能力 ({{ product.sensor_capabilities.length }})</summary>
                <div class="mt-1 small" v-for="sc in product.sensor_capabilities" :key="sc.id">
                  <span class="badge bg-success me-1">{{ sc.dict_name }}</span>
                  <span v-if="sc.range" class="text-muted me-1">量程: {{ sc.range }}</span>
                  <span v-if="sc.accuracy" class="text-muted">精度: {{ sc.accuracy }}</span>
                </div>
              </details>
            </div>

            <!-- Multi images -->
            <div v-if="productHasImages" class="mb-2">
              <h6 class="fw-semibold border-bottom pb-1">
                <i class="bi bi-images me-1"></i>产品图片
              </h6>
              <div class="d-flex flex-wrap gap-2">
                <img v-for="(img, idx) in (product.images || [])" :key="idx"
                  :src="imageThumbSrc(img.url)"
                  style="width:80px;height:80px;object-fit:cover;border-radius:6px;border:1px solid var(--gray-200);cursor:pointer"
                  :title="img.is_primary ? '主图' : ''"
                  @click="window.open(imageThumbSrc(img.url), '_blank')">
              </div>
            </div>
          </div>
          <div class="modal-footer d-flex justify-content-between">
            <div class="d-flex align-items-center gap-2">
              <div class="form-check mb-0">
                <input class="form-check-input" type="checkbox" :id="'compare-'+product.id"
                  :checked="isInCompare" @change="toggleCompare">
                <label class="form-check-label small" :for="'compare-'+product.id">加入对比</label>
              </div>
            </div>
            <div class="d-flex gap-2">
              <button class="btn btn-outline-info btn-modern btn-sm" @click="openSpecSheet">
                <i class="bi bi-file-text"></i> 查看规格书
              </button>
              <button v-if="isAdmin() || product.created_by === currentUser?.id" class="btn btn-outline-primary btn-modern btn-sm" @click="onEdit">
                <i class="bi bi-pencil"></i> 编辑
              </button>
              <button class="btn btn-secondary btn-modern btn-sm" @click="close">关闭</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
