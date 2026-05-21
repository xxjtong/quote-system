<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useApi } from '../composables/useApi'
import ProductTable from '../components/ProductTable.vue'
import ProductDetailModal from '../components/ProductDetailModal.vue'
import ProductFormModal from '../components/ProductFormModal.vue'

const router = useRouter()
const route = useRoute()
const { api } = useApi()

// ─── Product table ref ───
const productTable = ref(null)

// ─── Product detail modal ───
const detailProduct = ref(null)
const showDetailModal = computed({
  get: () => !!detailProduct.value,
  set: (v) => { if (!v) closeDetail() },
})

function showDetail(p) {
  detailProduct.value = p
}

function closeDetail() {
  detailProduct.value = null
  if (route.params.id) router.push({ name: 'products', params: {} })
}

// Watch route param → open detail modal
watch(() => route.params.id, async (id) => {
  if (!id) { detailProduct.value = null; return }
  // Try from ProductTable's loaded list first
  const pt = productTable.value
  if (pt) {
    const p = pt.products?.find(p => p.id == id)
    if (p) { showDetail(p); return }
  }
  try {
    const data = await api(`/api/products/${id}`)
    if (data && data.product) showDetail(data.product)
  } catch (e) { /* 404 — do nothing */ }
}, { immediate: true })

// ─── Product Form Modal ───
const showForm = ref(false)
const formProduct = ref(null)  // null = add, object = edit

function showAddProduct() {
  formProduct.value = null
  showForm.value = true
}

function onFormSaved() {
  showForm.value = false
  productTable.value?.fetchProducts()
}

function onEdit(product) {
  formProduct.value = product
  showForm.value = true
}

function onView(product) {
  router.push({ name: 'products', params: { id: product.id } })
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="page-header justify-content-between">
      <h5><i class="bi bi-box"></i>产品管理</h5>
      <div class="d-flex gap-2">
        <button class="btn btn-outline-primary btn-modern" @click="productTable?.exportTemplate()">
          <i class="bi bi-download"></i> 下载模板
        </button>
        <button class="btn btn-primary btn-modern" @click="showAddProduct">
          <i class="bi bi-plus-lg"></i> 新增产品
        </button>
      </div>
    </div>

    <ProductTable
      ref="productTable"
      @edit="onEdit"
      @view="onView"
    />

    <!-- Product Form Modal -->
    <ProductFormModal
      :show="showForm"
      :product="formProduct"
      :categories="productTable?.categories || []"
      :suppliers="productTable?.suppliers || []"
      @update:show="showForm = $event"
      @saved="onFormSaved"
    />

    <!-- Product Detail Modal -->
    <ProductDetailModal
      :show="showDetailModal"
      :product="detailProduct"
      @update:show="showDetailModal = $event"
      @edit="onEdit($event); closeDetail()"
    />
  </div>
</template>
