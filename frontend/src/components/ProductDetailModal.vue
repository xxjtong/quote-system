<script setup>
import { ref, watch, nextTick, computed, inject } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { BASE_URL, useApi } from '../composables/useApi'
import { useFocusTrap } from '../composables/useFocusTrap'
import { formatMoney } from '../composables/useUtils'
import { useAdvancedApi } from '../composables/useAdvancedApi'
import TagBadge from './TagBadge.vue'

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

function directionLabel(d) {
  return { acquisition: '采集', forwarding: '转发', both: '双向' }[d] || d || ''
}

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

function openImage(url) {
  if (url) window.open(url, '_blank')
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
            <table class="table table-sm" style="font-size:.85rem">
              <tbody>
                <tr v-if="(product.category_names || []).length > 0">
                  <td class="text-muted" style="width:80px">品类</td>
                  <td><span v-for="c in product.category_names" :key="c" class="badge bg-light text-dark me-1">{{ c }}</span></td>
                </tr>
                <tr><td class="text-muted">型号</td><td>{{ product.model || product.spec || '—' }}</td></tr>
                <tr><td class="text-muted">单位</td><td>{{ product.unit || '—' }}</td></tr>
                <tr><td class="text-muted">厂商</td><td>{{ product.manufacturer_name || product.supplier_name || '—' }}</td></tr>
                <tr><td class="text-muted">销售单价</td><td class="fw-medium text-primary">{{ formatMoney(product.price) }}</td></tr>
                <tr v-if="product.cost_price"><td class="text-muted">成本价</td><td>¥{{ product.cost_price }}</td></tr>
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
                <div class="mt-1 small" v-for="cm in product.comm_methods" :key="cm.method_id || cm.dict_id">
                  <TagBadge :label="cm.method_name || cm.dict_name" />
                  <span v-if="cm.details || cm.detail" class="text-muted">{{ cm.details || cm.detail }}</span>
                </div>
              </details>
              <details v-if="hasM2MData(product.comm_protocols)" class="mb-1">
                <summary class="small fw-medium text-secondary" style="cursor:pointer">通讯协议 ({{ product.comm_protocols.length }})</summary>
                <div class="mt-1 small" v-for="cp in product.comm_protocols" :key="cp.protocol_id || cp.dict_id">
                  <TagBadge :label="cp.protocol_name || cp.dict_name" />
                  <span v-if="cp.direction" class="text-muted ms-1">{{ directionLabel(cp.direction) }}</span>
                </div>
              </details>
              <details v-if="hasM2MData(product.power_supplies)" class="mb-1">
                <summary class="small fw-medium text-secondary" style="cursor:pointer">供电方式 ({{ product.power_supplies.length }})</summary>
                <div class="mt-1 small" v-for="ps in product.power_supplies" :key="ps.power_id || ps.dict_id">
                  <TagBadge :label="ps.power_name || ps.dict_name" />
                  <span v-if="ps.voltage_range" class="text-muted ms-1">{{ ps.voltage_range }}</span>
                  <span v-if="ps.battery_life" class="text-muted ms-1">· {{ ps.battery_life }}</span>
                </div>
              </details>
              <details v-if="hasM2MData(product.hardware_interfaces)" class="mb-1">
                <summary class="small fw-medium text-secondary" style="cursor:pointer">硬件接口 ({{ product.hardware_interfaces.length }})</summary>
                <div class="mt-1 small" v-for="hi in product.hardware_interfaces" :key="hi.id">
                  <span class="badge bg-secondary me-1">{{ hi.interface_name }}</span>
                  <span class="text-muted">×{{ hi.quantity || 1 }}</span>
                  <span v-if="hi.description" class="text-muted ms-1">{{ hi.description }}</span>
                </div>
              </details>
              <details v-if="hasM2MData(product.sensor_capabilities)" class="mb-1">
                <summary class="small fw-medium text-secondary" style="cursor:pointer">传感/控制功能 ({{ product.sensor_capabilities.length }})</summary>
                <div class="mt-1 small" v-for="sc in product.sensor_capabilities" :key="sc.metric_id || sc.dict_id">
                  <TagBadge :label="sc.metric_name || sc.dict_name" />
                  <span v-if="sc.measure_range || sc.range" class="text-muted ms-1">{{ sc.measure_range || sc.range }}</span>
                  <span v-if="sc.accuracy" class="text-muted ms-1">· {{ sc.accuracy }}</span>
                  <span v-if="sc.resolution" class="text-muted ms-1">· {{ sc.resolution }}</span>
                </div>
              </details>
            </div>

            <!-- Function description -->
            <div v-if="product.function_desc" class="mb-2">
              <h6 class="fw-semibold border-bottom pb-1">
                <i class="bi bi-text-paragraph me-1"></i>功能描述
              </h6>
              <p class="small text-muted mb-0" style="white-space:pre-line">{{ product.function_desc }}</p>
            </div>

            <!-- Remark -->
            <div v-if="product.remark" class="mb-2">
              <h6 class="fw-semibold border-bottom pb-1">
                <i class="bi bi-pencil me-1"></i>备注
              </h6>
              <p class="small text-muted mb-0">{{ product.remark }}</p>
            </div>

            <!-- Product image -->
            <div v-if="product.image_url || product.has_image || productHasImages" class="mb-2">
              <h6 class="fw-semibold border-bottom pb-1">
                <i class="bi bi-images me-1"></i>产品图片
              </h6>
              <img v-if="product.image_url || product.has_image" :src="detailImageSrc(product)"
                style="max-width:100%;max-height:400px;object-fit:contain;border-radius:8px;border:1px solid var(--gray-200);cursor:pointer"
                @click="openImage(product.image_url || detailImageSrc(product))" />
              <div class="d-flex flex-wrap gap-2 mt-2">
                <img v-for="(img, idx) in (product.images || [])" :key="idx"
                  :src="imageThumbSrc(img.url)"
                  style="width:80px;height:80px;object-fit:cover;border-radius:6px;border:1px solid var(--gray-200);cursor:pointer"
                  :title="img.is_primary ? '主图' : ''"
                  @click="openImage(img.url)">
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
              <button class="btn btn-secondary btn-modern btn-sm" @click="close">关闭</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
