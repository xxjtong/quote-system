<script setup>
import { ref, onMounted, inject } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '../composables/useApi'
import { formatMoney } from '../composables/useUtils'
import QuotePreviewModal from '../components/QuotePreviewModal.vue'
import AiChat from '../components/AiChat.vue'

const router = useRouter()
const toast = inject('toast')
const { api } = useApi()

const stats = ref({ prodCount: 0, quoteCount: 0, downloadTotal: 0, totalAmount: 0, catCount: 0, aiMyCount: 0, aiTotalCount: 0 })
const recentQuotes = ref([])
const loading = ref(true)

async function fetchDashboard() {
  try {
    const [p, q, ai] = await Promise.all([api('/api/products?per_page=1'), api('/api/quotes'), api('/api/ai/my-usage?t=' + Date.now()).catch(() => ({my_count:0,total_count:0}))])
    const quotes = q.quotes || []
    stats.value = {
      prodCount: p.total || 0, quoteCount: quotes.length,
      totalAmount: quotes.reduce((s, qq) => s + (qq.total_amount || 0), 0),
      downloadTotal: quotes.reduce((s, qq) => s + (qq.download_count || 0), 0),
      catCount: p.categories?.length || 0,
      aiMyCount: ai.my_count || 0, aiTotalCount: ai.total_count || 0,
    }
    recentQuotes.value = quotes.slice(0, 10)
  } catch (e) { toast('加载概览失败', 'danger') }
  finally { loading.value = false }
}

function goTo(name) { router.push({ name }) }

// ─── Quote Preview Modal ──────────────────────────────────
const showQuotePreview = ref(false)
const previewQuoteId = ref(null)
const previewQuoteTitle = ref('')

// ─── AiChat event handlers ────────────────────────────────
function onAiChatNavigate(route) {
  router.push(route)
}

function onAiChatCreateQuote(payload) {
  if (payload.type === 'single') {
    router.push({ name: 'newquote', query: { product: payload.product } })
  } else if (payload.type === 'multi') {
    const query = {}
    if (payload.product_ids) query.product_ids = payload.product_ids
    if (payload.products) query.products = payload.products
    router.push({ name: 'newquote', query })
  }
}

onMounted(() => { fetchDashboard() })
</script>

<template>
  <div v-if="loading" class="text-center py-5">
    <div class="spinner-border text-primary mb-2" role="status"></div>
    <p class="text-muted small">加载概览...</p>
  </div>

  <template v-else>
    <div class="page-header">
      <h5><i class="bi bi-speedometer2"></i>系统概览</h5>
    </div>

    <!-- Stat Cards -->
    <div class="row g-3 mb-3 anim-in">
      <div class="col-6 col-md-3">
        <div class="stat-card">
          <div class="d-flex align-items-center gap-3">
            <div class="stat-icon" :style="{background: stats.catCount > 0 ? 'var(--primary-light)' : '#f1f5f9', color: 'var(--primary)'}">
              <i class="bi bi-box-seam"></i>
            </div>
            <div><div class="text-muted" style="font-size:.72rem">产品总数</div><div class="fw-bold fs-4">{{ stats.prodCount }}</div></div>
          </div>
          <div class="mt-2 small text-muted">{{ stats.catCount }} 个分类</div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="stat-card">
          <div class="d-flex align-items-center gap-3">
            <div class="stat-icon" style="background:#d1fae5;color:var(--success)"><i class="bi bi-file-earmark-text"></i></div>
            <div><div class="text-muted" style="font-size:.72rem">报价单</div><div class="fw-bold fs-4">{{ stats.quoteCount }}</div></div>
          </div>
          <div class="mt-2 small text-muted">共 {{ formatMoney(stats.totalAmount) }}</div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="stat-card">
          <div class="d-flex align-items-center gap-3">
            <div class="stat-icon" style="background:#fef3c7;color:var(--warning)"><i class="bi bi-download"></i></div>
            <div><div class="text-muted" style="font-size:.72rem">下载</div><div class="fw-bold fs-4">{{ stats.downloadTotal }}</div></div>
          </div>
          <div class="mt-2 small text-muted">报价单下载次数</div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="stat-card">
          <div class="d-flex align-items-center gap-3">
            <div class="stat-icon" style="background:#ede9fe;color:#7c3aed"><i class="bi bi-robot"></i></div>
            <div><div class="text-muted" style="font-size:.72rem">AI 使用</div><div class="fw-bold fs-4">{{ stats.aiMyCount }}</div></div>
          </div>
          <div class="mt-2 small text-muted">全部 {{ stats.aiTotalCount }} 次</div>
        </div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="card-modern anim-in">
      <div class="card-title-modern"><i class="bi bi-lightning text-primary"></i>快速操作</div>
      <div class="d-flex flex-wrap gap-2">
        <button class="btn btn-outline-primary btn-modern" @click="goTo('import')"><i class="bi bi-upload me-1"></i>从Excel导入产品</button>
        <button class="btn btn-outline-primary btn-modern" @click="goTo('newquote')"><i class="bi bi-plus-circle me-1"></i>新建报价单</button>
        <button class="btn btn-outline-primary btn-modern" @click="goTo('products')"><i class="bi bi-box-seam me-1"></i>管理产品库</button>
      </div>
    </div>

    <!-- AI Chat (extracted component) -->
    <AiChat @navigate="onAiChatNavigate" @create-quote="onAiChatCreateQuote" @chat-completed="fetchDashboard" />

    <!-- Recent Quotes -->
    <div class="card-modern anim-in">
      <div class="card-title-modern"><i class="bi bi-clock-history text-primary"></i>最近报价</div>
      <template v-if="recentQuotes.length">
        <div v-for="qq in recentQuotes" :key="qq.id" class="d-flex justify-content-between align-items-center py-2"
          style="border-bottom:1px solid var(--gray-100);cursor:pointer" @click="previewQuoteId = qq.id; previewQuoteTitle = qq.title; showQuotePreview = true">
          <span><i class="bi bi-file-text me-2 text-muted"></i>{{ qq.title || '未命名' }}</span>
          <span class="text-muted small fw-medium">{{ formatMoney(qq.total_amount) }}</span>
        </div>
      </template>
      <div v-else class="text-muted text-center py-3 small">暂无报价单</div>
    </div>

    <!-- Quote Preview Modal (shared component) -->
    <QuotePreviewModal v-model:show="showQuotePreview" :quote-id="previewQuoteId" :quote-title="previewQuoteTitle" />
  </template>
</template>
