<script setup>
import { ref } from 'vue'

const props = defineProps({
  quoteId: { type: Number, required: true },
  title: { type: String, default: '' },
  client: { type: String, default: '' },
  items: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
})

const showPreview = ref(false)

function preview() {
  showPreview.value = true
}

function downloadExcel() {
  const token = localStorage.getItem('quote_token') || ''
  const base = import.meta.env.DEV ? 'http://127.0.0.1:5001' : ''
  const a = document.createElement('a')
  a.href = `${base}/api/quotes/${props.quoteId}/export-excel?token=${token}`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}
</script>

<template>
  <div class="genui-card card-modern mb-2">
    <div class="card-title-modern d-flex justify-content-between align-items-center">
      <span><i class="bi bi-file-earmark-text me-1"></i>报价单 #{{ quoteId }}</span>
      <small class="text-muted">{{ title }}{{ client ? ' · ' + client : '' }}</small>
    </div>
    <div class="p-2">
      <table class="table table-sm table-modern mb-2" v-if="items.length">
        <thead><tr><th>产品</th><th>规格</th><th>数量</th><th>单价</th><th>小计</th></tr></thead>
        <tbody>
          <tr v-for="(it, i) in items" :key="i">
            <td class="small">{{ it.product_name }}</td>
            <td class="small text-muted">{{ it.product_spec || '—' }}</td>
            <td>{{ it.quantity }}</td>
            <td class="text-nowrap">¥{{ (it.unit_price || 0).toLocaleString() }}</td>
            <td class="text-nowrap fw-medium">¥{{ ((it.unit_price || 0) * (it.quantity || 1)).toLocaleString() }}</td>
          </tr>
        </tbody>
      </table>
      <div class="d-flex justify-content-between align-items-center" v-if="total">
        <strong>合计：¥{{ total.toLocaleString() }}</strong>
        <div class="d-flex gap-2">
          <button class="btn btn-sm btn-outline-primary" @click="preview">
            <i class="bi bi-eye me-1"></i>预览
          </button>
          <button class="btn btn-sm btn-outline-secondary" @click="downloadExcel">
            <i class="bi bi-download me-1"></i>下载
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- Preview modal -->
  <Teleport to="body">
    <QuotePreviewModal v-model:show="showPreview" :quote-id="quoteId" :quote-title="'报价单 #' + quoteId" />
  </Teleport>
</template>

<script>
import QuotePreviewModal from '../QuotePreviewModal.vue'
export default { components: { QuotePreviewModal } }
</script>

<style scoped>
.genui-card { border-left: 3px solid var(--bs-success, #198754); }
</style>
