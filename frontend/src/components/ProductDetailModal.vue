<script setup>
import { ref, watch, nextTick, computed } from 'vue'
import { useApi } from '../composables/useApi'
import { useFocusTrap } from '../composables/useFocusTrap'
import { formatMoney } from '../composables/useUtils'

const props = defineProps({
  show: Boolean,
  product: Object,
})

const emit = defineEmits(['update:show', 'edit'])

const { authToken, isAdmin, currentUser } = useApi()

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
      <div class="modal-dialog modal-dialog-centered">
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
          </div>
          <div class="modal-footer">
            <button v-if="isAdmin() || product.created_by === currentUser?.id" class="btn btn-outline-primary btn-modern btn-sm" @click="onEdit">
              <i class="bi bi-pencil"></i> 编辑
            </button>
            <button class="btn btn-secondary btn-modern btn-sm" @click="close">关闭</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
