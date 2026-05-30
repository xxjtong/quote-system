<template>
  <div>
    <!-- Page header -->
    <div class="page-header justify-content-between">
      <h5><i class="bi bi-database me-2"></i>{{ product?.name || '产品详情' }}</h5>
      <div style="display:flex;gap:8px">
        <a v-if="product?.product_url" :href="product.product_url" target="_blank" class="btn btn-outline-primary btn-modern">
          <i class="bi bi-link-45deg me-1"></i>产品链接
        </a>
        <a v-if="product" :href="specSheetUrl" target="_blank" class="btn btn-outline-primary btn-modern">
          <i class="bi bi-file-text me-1"></i>规格书
        </a>
        <button class="btn btn-outline-primary btn-modern" @click="$router.push('/products-db/' + product?.id + '/edit')">
          <i class="bi bi-pencil me-1"></i>编辑
        </button>
        <button class="btn btn-outline-secondary btn-modern" @click="$router.back()">
          <i class="bi bi-arrow-left me-1"></i>返回
        </button>
      </div>
    </div>

    <div v-if="product" class="row g-3">
      <!-- Images -->
      <div class="col-12" v-if="product.images?.length">
        <div class="card-modern">
          <div style="padding:12px">
            <img v-for="img in primaryImages" :key="img.id || img.url"
              :src="getImageSrc(img.url)" style="max-height:180px;max-width:300px;border-radius:6px;border:1px solid #dee2e6" />
            <div v-if="product.images.length > 1" class="d-flex gap-2 flex-wrap mt-2">
              <img v-for="img in secondaryImages" :key="img.id || img.url"
                :src="getImageSrc(img.url)" style="width:60px;height:60px;object-fit:cover;border-radius:4px;border:1px solid #dee2e6" />
            </div>
          </div>
        </div>
      </div>

      <!-- Basic info -->
      <div class="col-12">
        <div class="card-modern">
          <div class="card-title-modern"><i class="bi bi-info-circle text-primary"></i>基本信息</div>
          <div style="padding:16px">
            <div class="row g-3">
              <div class="col-md-3">
                <div class="small text-muted">型号</div>
                <div class="fw-medium" style="font-family:monospace">{{ product.model || '—' }}</div>
              </div>
              <div class="col-md-3">
                <div class="small text-muted">SKU</div>
                <div class="fw-medium">{{ product.sku || '—' }}</div>
              </div>
              <div class="col-md-3">
                <div class="small text-muted">品类</div>
                <div class="fw-medium">{{ product.category_name || '—' }}</div>
              </div>
              <div class="col-md-3">
                <div class="small text-muted">厂商</div>
                <div class="fw-medium">{{ product.manufacturer_name || '—' }}</div>
              </div>
              <div class="col-md-3">
                <div class="small text-muted">供应商</div>
                <div class="fw-medium">{{ product.supplier_name || product.supplier || '—' }}</div>
              </div>
              <div class="col-md-3">
                <div class="small text-muted">价格</div>
                <div class="fw-medium" style="font-family:monospace">{{ product.price != null ? product.price : '—' }}</div>
              </div>
              <div class="col-md-3">
                <div class="small text-muted">成本</div>
                <div class="fw-medium" style="font-family:monospace">{{ product.cost_price != null ? product.cost_price : '—' }}</div>
              </div>
              <div class="col-md-3">
                <div class="small text-muted">状态</div>
                <div class="fw-medium">{{ product.status }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Comm Methods -->
      <div class="col-12" v-if="product.comm_methods?.length">
        <div class="card-modern">
          <div class="card-title-modern"><i class="bi bi-wifi text-primary"></i>通讯方式</div>
          <div>
            <table class="table table-modern">
              <thead>
                <tr><th>类型</th><th>方式</th><th>详情</th></tr>
              </thead>
              <tbody>
                <tr v-for="cm in product.comm_methods" :key="cm.method_id || cm.dict_id">
                  <td>{{ cm.method_type === 'wired' ? '有线' : '无线' }}</td>
                  <td><TagBadge :label="cm.method_name || cm.dict_name" /></td>
                  <td>{{ cm.detail || cm.details || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Comm Protocols -->
      <div class="col-12" v-if="product.comm_protocols?.length">
        <div class="card-modern">
          <div class="card-title-modern"><i class="bi bi-diagram-3 text-primary"></i>通讯协议</div>
          <div>
            <table class="table table-modern">
              <thead>
                <tr><th>协议</th><th>方向</th></tr>
              </thead>
              <tbody>
                <tr v-for="cp in product.comm_protocols" :key="cp.protocol_id || cp.dict_id">
                  <td><TagBadge :label="cp.protocol_name || cp.dict_name" /></td>
                  <td>{{ formatDirection(cp.direction) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Power Supplies -->
      <div class="col-12" v-if="product.power_supplies?.length">
        <div class="card-modern">
          <div class="card-title-modern"><i class="bi bi-battery-full text-primary"></i>供电方式</div>
          <div>
            <table class="table table-modern">
              <thead>
                <tr><th>方式</th><th>电池/电压/规格</th><th>续航/寿命</th></tr>
              </thead>
              <tbody>
                <tr v-for="ps in product.power_supplies" :key="ps.power_id || ps.dict_id">
                  <td><TagBadge :label="ps.power_name || ps.dict_name" /></td>
                  <td>{{ ps.voltage_range || '—' }}</td>
                  <td>{{ ps.battery_life || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Hardware Interfaces -->
      <div class="col-12" v-if="product.hardware_interfaces?.length">
        <div class="card-modern">
          <div class="card-title-modern"><i class="bi bi-plug text-primary"></i>硬件接口</div>
          <div>
            <table class="table table-modern">
              <thead>
                <tr><th>接口</th><th>数量</th><th>描述</th></tr>
              </thead>
              <tbody>
                <tr v-for="hi in product.hardware_interfaces" :key="hi.id">
                  <td>{{ hi.interface_name }}</td>
                  <td>&times;{{ hi.quantity }}</td>
                  <td>{{ hi.description || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Sensor Capabilities -->
      <div class="col-12" v-if="product.sensor_capabilities?.length">
        <div class="card-modern">
          <div class="card-title-modern"><i class="bi bi-activity text-primary"></i>传感/控制能力</div>
          <div>
            <table class="table table-modern">
              <thead>
                <tr><th>指标</th><th>单位</th><th>量程/说明</th><th>精度</th><th>分辨率</th></tr>
              </thead>
              <tbody>
                <tr v-for="sc in product.sensor_capabilities" :key="sc.metric_id || sc.dict_id">
                  <td>{{ sc.metric_name || sc.dict_name }}</td>
                  <td>{{ sc.unit || '—' }}</td>
                  <td>{{ sc.measure_range || '—' }}</td>
                  <td>{{ sc.accuracy || '—' }}</td>
                  <td>{{ sc.resolution || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Specs by group -->
      <div class="col-12" v-if="specDefs.length">
        <div class="card-modern">
          <div class="card-title-modern"><i class="bi bi-sliders text-primary"></i>规格参数</div>
          <div style="padding:16px">
            <div v-for="group in specGroups" :key="group.name" class="mb-3">
              <div v-if="group.name" class="small text-muted fw-semibold mb-1">{{ group.name }}</div>
              <table class="table table-modern">
                <tbody>
                  <tr v-for="sd in group.items" :key="sd.spec_key">
                    <td style="width:200px">{{ sd.display_name }} <span v-if="sd.unit" class="text-muted">({{ sd.unit }})</span></td>
                    <td>{{ formatSpecVal(product.specs?.[sd.spec_key], sd) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="unmatchedSpecs.length">
              <div class="small text-muted fw-semibold mb-1">其他</div>
              <table class="table table-modern">
                <tbody>
                  <tr v-for="key in unmatchedSpecs" :key="key">
                    <td style="width:200px">{{ key }}</td>
                    <td>{{ product.specs?.[key] }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <!-- Variants -->
      <div class="col-12" v-if="product.variants?.length">
        <div class="card-modern">
          <div class="card-title-modern"><i class="bi bi-diagram-2 text-primary"></i>变体</div>
          <div>
            <table class="table table-modern">
              <thead>
                <tr><th>名称</th><th>型号</th></tr>
              </thead>
              <tbody>
                <tr v-for="v in product.variants" :key="v.id">
                  <td><router-link :to="'/products-db/' + v.id" class="text-decoration-none">{{ v.name }}</router-link></td>
                  <td class="text-muted small" style="font-family:monospace">{{ v.model || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Dependencies -->
      <div class="col-12" v-if="product.dependencies?.length">
        <div class="card-modern">
          <div class="card-title-modern"><i class="bi bi-link-45deg text-primary"></i>依赖关系</div>
          <div>
            <table class="table table-modern">
              <thead>
                <tr><th>类型</th><th>目标</th><th>描述</th></tr>
              </thead>
              <tbody>
                <tr v-for="d in product.dependencies" :key="d.id">
                  <td>
                    <span class="badge" :class="d.dependency_type === 'required' ? 'bg-primary' : 'bg-light text-dark'">
                      {{ d.dependency_type }}
                    </span>
                  </td>
                  <td>{{ d.depends_on_product_id || d.depends_on_category_id }}</td>
                  <td>{{ d.description }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Description -->
      <div class="col-12" v-if="product.function_desc">
        <div class="card-modern">
          <div class="card-title-modern"><i class="bi bi-text-paragraph text-primary"></i>描述</div>
          <div style="padding:16px">
            <p class="mb-0" style="white-space:pre-wrap">{{ product.function_desc }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-else class="text-center py-5 text-muted">
      <div class="spinner-border spinner-border-sm text-primary me-2" role="status"></div>
      加载中...
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useApi, BASE_URL } from '../composables/useApi'
import { useAdvancedApi } from '../composables/useAdvancedApi'
import TagBadge from '../components/TagBadge.vue'

const FLASK_DEV = import.meta.env.DEV ? 'http://127.0.0.1:5001' : ''
function getImageSrc(url) {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return FLASK_DEV + url
}

const route = useRoute()
const { api } = useApi()
const { categories } = useAdvancedApi()

const product = ref(null)
const specDefs = ref([])

const specSheetUrl = computed(() => {
  if (!product.value?.id) return '#'
  const token = localStorage.getItem('quote_token') || ''
  return (BASE_URL || '') + '/api/products/' + product.value.id + '/spec-sheet?token=' + encodeURIComponent(token)
})

const primaryImages = computed(() => {
  if (!product.value?.images?.length) return []
  const primaries = product.value.images.filter(i => i.is_primary)
  if (primaries.length) return primaries
  return [product.value.images[0]]  // fallback: first image
})

const secondaryImages = computed(() => {
  if (!product.value?.images?.length) return []
  const primarySet = new Set(primaryImages.value.map(i => i.id || i.url))
  return product.value.images.filter(i => !primarySet.has(i.id || i.url))
})

const specGroups = computed(() => {
  const groups = {}
  for (const sd of specDefs.value) {
    const g = sd.display_group || ''
    if (!groups[g]) groups[g] = []
    groups[g].push(sd)
  }
  return Object.entries(groups).map(([name, items]) => ({ name, items }))
})

const unmatchedSpecs = computed(() => {
  if (!product.value) return []
  const defined = new Set(specDefs.value.map(sd => sd.spec_key))
  return Object.keys(product.value.specs || {}).filter(k => !defined.has(k))
})

function formatSpecVal(val, sd) {
  if (val === null || val === undefined) return '—'
  if (sd.spec_type === 'boolean') return val ? '✓' : '—'
  return String(val)
}

function formatDirection(dir) {
  if (dir === 'acquisition') return '采集(下行)'
  if (dir === 'forwarding') return '转发(上行)'
  return '双向'
}

onMounted(async () => {
  try {
    const res = await api('/api/products/' + route.params.id)
    product.value = res.product
    if (res.product?.category_id) {
      const specRes = await categories.specDefs(res.product.category_id)
      specDefs.value = specRes?.items || []
    }
  } catch (e) {
    // 404 or error — handled by empty state
  }
})
</script>
