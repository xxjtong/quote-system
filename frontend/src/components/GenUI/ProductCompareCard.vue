<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

defineProps({ products: { type: Array, default: () => [] } })
const router = useRouter()

const checked = ref([])

function toggle(p) {
  const idx = checked.value.findIndex(c => c.name === p.name)
  if (idx >= 0) checked.value.splice(idx, 1)
  else if (checked.value.length < 5) checked.value.push(p)
}

function compareSelected() {
  if (checked.value.length >= 2) {
    const names = checked.value.map(p => p.name).join(',')
    router.push({ name: 'compare', query: { products: names } })
  }
}

function createQuote() {
  const names = checked.value.map(p => p.name).join(',')
  if (names) router.push({ name: 'newquote', query: { products: names } })
}
</script>

<template>
  <div class="genui-card card-modern mb-2">
    <div class="card-title-modern"><i class="bi bi-layout-split me-1"></i>产品推荐</div>
    <div class="p-2">
      <div v-for="p in products" :key="p.name" class="d-flex align-items-center gap-2 py-1 border-bottom"
        style="cursor:pointer" @click="toggle(p)">
        <i :class="checked.some(c => c.name === p.name) ? 'bi bi-check-circle-fill text-primary' : 'bi bi-circle text-muted'"></i>
        <div class="flex-grow-1">
          <div class="small fw-medium">{{ p.name }}</div>
          <div v-if="p.model" class="text-muted" style="font-size:.7rem;font-family:monospace">{{ p.model }}</div>
        </div>
        <span class="fw-bold text-nowrap" v-if="p.price">¥{{ p.price?.toLocaleString() }}</span>
      </div>
      <div class="d-flex gap-2 mt-2" v-if="checked.length > 0">
        <button class="btn btn-sm btn-outline-primary" @click="compareSelected" :disabled="checked.length < 2">
          <i class="bi bi-bar-chart me-1"></i>对比 {{ checked.length }} 款
        </button>
        <button class="btn btn-sm btn-primary" @click="createQuote">
          <i class="bi bi-cart-plus me-1"></i>创建报价单
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.genui-card { border-left: 3px solid var(--bs-primary, #0d6efd); }
</style>
