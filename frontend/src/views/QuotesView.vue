<script setup>
import { ref, computed, onMounted, inject, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useApi } from '../composables/useApi'
import { formatMoney } from '../composables/useUtils'
import QuotePreviewModal from '../components/QuotePreviewModal.vue'

const BASE_URL = import.meta.env.BASE_URL === '/' ? '' : import.meta.env.BASE_URL.replace(/\/$/, '')

const router = useRouter()
const route = useRoute()
const toast = inject('toast')
const { api, isAdmin } = useApi()

const quotes = ref([])
const statusFilter = ref('')
const loading = ref(true)

// ─── Search & Pagination ───
const searchTerm = ref('')
const currentPage = ref(1)
const perPage = ref(20)
const totalQuotes = ref(0)
const totalPages = computed(() => Math.max(1, Math.ceil(totalQuotes.value / perPage.value)))

// ─── IME composition ───
const isComposing = ref(false)
function onCompositionStart() { isComposing.value = true }
function onCompositionEnd(e) {
  isComposing.value = false
  debouncedSearch(e.target.value)
}

// ─── Debounced search ───
let searchTimer = null
function debouncedSearch(val) {
  if (isComposing.value) return
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    searchTerm.value = val
    currentPage.value = 1
    fetchQuotes()
  }, 500)
}
function clearSearch() {
  searchTerm.value = ''
  currentPage.value = 1
  fetchQuotes()
}

// ─── Pagination pages ───
const pageNumbers = computed(() => {
  const total = totalPages.value
  if (total <= 1) return []

  // 始终显示最多 7 页，当前页居中
  const half = 3
  let start = Math.max(1, currentPage.value - half)
  let end = Math.min(total, currentPage.value + half)

  // 靠近边界时补齐
  if (start === 1) end = Math.min(total, start + 6)
  else if (end === total) start = Math.max(1, end - 6)

  const pages = []
  for (let p = start; p <= end; p++) pages.push(p)
  return pages
})

function goPage(p) {
  if (p < 1 || p > totalPages.value) return
  currentPage.value = p
  fetchQuotes()
}

async function fetchQuotes() {
  loading.value = true
  try {
    const params = new URLSearchParams({
      page: currentPage.value,
      per_page: perPage.value,
    })
    if (statusFilter.value) params.set('status', statusFilter.value)
    if (searchTerm.value) params.set('search', searchTerm.value)

    const data = await api(`/api/quotes?${params}`)
    if (!data.error) {
      quotes.value = data.quotes || []
      totalQuotes.value = data.total || 0
      await nextTick()
    }
  } catch (e) {
    toast('加载报价单失败', 'danger')
  } finally {
    loading.value = false
  }
}

// ─── Preview modal ───
const showPreview = ref(false)
const previewQuoteId = ref(null)
const previewTitle = ref('')

function viewQuote(id, title) {
  previewQuoteId.value = id
  previewTitle.value = title || '报价单预览'
  showPreview.value = true
}

// ─── Status toggle ───
const validStatuses = [
  { value: 'draft', label: '草稿', cls: 'bg-light text-dark' },
  { value: 'sent', label: '已发送', cls: 'bg-primary' },
  { value: 'confirmed', label: '已接受', cls: 'bg-success' },
  { value: 'rejected', label: '已拒绝', cls: 'bg-danger' },
  { value: 'expired', label: '已过期', cls: 'bg-secondary' },
]

async function updateStatus(quote, newStatus) {
  const r = await api(`/api/quotes/${quote.id}/status`, 'PATCH', { status: newStatus })
  if (r.error) { toast(r.error, 'danger'); return }
  quote.status = newStatus
  toast('状态已更新')
}

// ─── Edit quote ───
function editQuote(id) {
  router.push({ name: 'newquote', query: { edit: id } })
}

// ─── Batch Delete ───
const selectedIds = ref(new Set())
const selectAll = ref(false)

function toggleSelectAll() {
  if (selectAll.value) {
    selectedIds.value = new Set(quotes.value.map(q => q.id))
  } else {
    selectedIds.value = new Set()
  }
}

function toggleSelect(id) {
  const s = new Set(selectedIds.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  selectedIds.value = s
  selectAll.value = s.size === quotes.value.length && quotes.value.length > 0
}

async function batchDelete() {
  const ids = [...selectedIds.value]
  if (!ids.length) return
  if (!confirm(`确定删除选中的 ${ids.length} 条报价单吗？`)) return

  const r = await api('/api/quotes/batch', 'DELETE', { ids })
  if (r.error) { toast(r.error, 'danger'); return }

  const msg = `已删除 ${r.deleted} 条`
  if (r.forbidden?.length) toast(`${msg}，${r.forbidden.length} 条无权限`, 'warning')
  else toast(msg, 'success')

  selectedIds.value = new Set()
  selectAll.value = false
  fetchQuotes()
}

async function deleteQuote(id) {
  if (!confirm('确定删除该报价单吗？')) return
  const r = await api(`/api/quotes/${id}`, 'DELETE')
  if (r.error) { toast(r.error, 'danger'); return }
  toast('已删除')
  selectedIds.value.delete(id)
  fetchQuotes()
}

function statusBadge(s) {
  const map = { draft: '草稿', sent: '已发送', accepted: '已接受', rejected: '已拒绝', confirmed: '已接受', expired: '已过期' }
  return map[s] || s || '草稿'
}

function statusClass(s) {
  const map = { draft: 'bg-light text-dark', sent: 'bg-primary', accepted: 'bg-success', rejected: 'bg-danger', confirmed: 'bg-success', expired: 'bg-secondary' }
  return map[s] || 'bg-light text-dark'
}

onMounted(() => {
  setTimeout(() => fetchQuotes(), 0)
})

// Watch route param → open preview modal
watch(() => route.params.id, async (id) => {
  if (!id) return
  const q = quotes.value.find(q => q.id == id)
  const title = q?.title || '报价单详情'
  viewQuote(id, title)
}, { immediate: true })

// Sync route when preview closes
watch(showPreview, (val) => {
  if (!val && route.params.id) router.push({ name: 'quotes', params: {} })
})

function closePreview() {
  showPreview.value = false
  if (route.params.id) router.push({ name: 'quotes', params: {} })
}
</script>

<template>
  <div>
    <div class="page-header justify-content-between">
      <h5><i class="bi bi-file-text"></i>报价单管理</h5>
      <button class="btn btn-primary btn-modern" @click="router.push({name:'newquote'})">
        <i class="bi bi-plus-lg"></i> 新建报价单
      </button>
    </div>

    <div class="card-modern">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <div class="d-flex align-items-center gap-2">
          <select class="form-select form-select-sm d-inline-block w-auto" v-model="statusFilter" @change="currentPage=1;fetchQuotes()">
            <option value="">全部状态</option>
            <option value="draft">草稿</option>
            <option value="sent">已发送</option>
            <option value="confirmed">已接受</option>
            <option value="rejected">已拒绝</option>
            <option value="expired">已过期</option>
          </select>
          <div class="input-group input-group-sm" style="width:220px">
            <span class="input-group-text bg-white border-end-0"><i class="bi bi-search text-muted"></i></span>
            <input type="text" class="form-control border-start-0" placeholder="搜索标题/客户..."
              :value="searchTerm"
              @input="debouncedSearch($event.target.value)"
              @compositionstart="onCompositionStart"
              @compositionend="onCompositionEnd">
            <button v-if="searchTerm" class="btn btn-outline-secondary" type="button" @click="clearSearch">
              <i class="bi bi-x-lg"></i>
            </button>
          </div>
        </div>
        <div v-if="selectedIds.size > 0" class="d-flex align-items-center gap-2 p-2 bg-warning bg-opacity-10 rounded">
          <span class="small fw-medium">已选 {{ selectedIds.size }} 条</span>
          <button class="btn btn-danger btn-sm" @click="batchDelete">
            <i class="bi bi-trash"></i> 批量删除
          </button>
          <button class="btn btn-outline-secondary btn-sm" @click="selectedIds = new Set(); selectAll = false">取消选择</button>
        </div>
      </div>

      <div v-if="loading" class="text-center py-5">
        <div class="spinner-border text-primary" role="status"></div>
      </div>

      <div v-else class="table-responsive">
        <table class="table table-modern">
          <thead>
            <tr>
              <th style="width:36px">
                <input type="checkbox" class="form-check-input" v-model="selectAll" @change="toggleSelectAll">
              </th>
              <th>标题</th>
              <th>客户</th>
              <th>状态</th>
              <th>金额</th>
              <th>创建者</th>
              <th>日期</th>
              <th>下载</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="quotes.length === 0">
              <td colspan="9"><div class="empty-state"><i class="bi bi-inbox"></i><p>暂无报价单</p></div></td>
            </tr>
            <tr v-for="q in quotes" :key="q.id">
              <td>
                <input type="checkbox" class="form-check-input" :checked="selectedIds.has(q.id)" @change="toggleSelect(q.id)">
              </td>
              <td>
                <span class="fw-medium" style="cursor:pointer;color:var(--primary)" @click="router.push({name:'quotes',params:{id:q.id}})">{{ q.title || '未命名' }}</span>
              </td>
              <td>{{ q.client || '—' }}</td>
              <td>
                <div class="dropdown">
                  <button class="btn btn-sm dropdown-toggle" style="font-size:.75rem;padding:.15rem .5rem"
                    :class="statusClass(q.status)"
                    type="button" data-bs-toggle="dropdown" aria-expanded="false">
                    {{ statusBadge(q.status) }}
                  </button>
                  <ul class="dropdown-menu" style="font-size:.82rem;min-width:100px">
                    <li v-for="s in validStatuses" :key="s.value">
                      <a class="dropdown-item" :class="{ active: q.status === s.value }"
                        href="#" @click.prevent="updateStatus(q, s.value)">
                        <span class="badge me-1" :class="s.cls" style="width:8px;height:8px;border-radius:50%;display:inline-block;padding:0"></span>
                        {{ s.label }}
                      </a>
                    </li>
                  </ul>
                </div>
              </td>
              <td class="fw-medium">{{ formatMoney(q.total_amount) }}</td>
              <td>{{ q.created_by_name || '—' }}</td>
              <td class="text-muted small">{{ q.quote_date || '—' }}</td>
              <td>{{ q.download_count || 0 }}次</td>
              <td>
                <div class="d-flex flex-wrap gap-1">
                  <button class="btn btn-sm btn-outline-primary btn-sm-icon" @click="viewQuote(q.id, q.title)" title="预览">
                    <i class="bi bi-eye"></i>
                  </button>
                  <button class="btn btn-sm btn-outline-danger btn-sm-icon" @click="deleteQuote(q.id)" title="删除">
                    <i class="bi bi-trash"></i>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="d-flex justify-content-between align-items-center mt-3">
      <small class="text-muted">共 {{ totalQuotes }} 条，第 {{ currentPage }}/{{ totalPages }} 页</small>
      <nav>
        <ul class="pagination pagination-sm mb-0">
          <li class="page-item" :class="{ disabled: currentPage === 1 }">
            <a class="page-link" href="#" @click.prevent="goPage(1)"><i class="bi bi-chevron-double-left"></i></a>
          </li>
          <li class="page-item" :class="{ disabled: currentPage === 1 }">
            <a class="page-link" href="#" @click.prevent="goPage(currentPage - 1)"><i class="bi bi-chevron-left"></i></a>
          </li>
          <li v-for="p in pageNumbers" :key="p" class="page-item" :class="{ active: p === currentPage }">
            <a class="page-link" href="#" @click.prevent="goPage(p)">{{ p }}</a>
          </li>
          <li class="page-item" :class="{ disabled: currentPage === totalPages }">
            <a class="page-link" href="#" @click.prevent="goPage(currentPage + 1)"><i class="bi bi-chevron-right"></i></a>
          </li>
          <li class="page-item" :class="{ disabled: currentPage === totalPages }">
            <a class="page-link" href="#" @click.prevent="goPage(totalPages)"><i class="bi bi-chevron-double-right"></i></a>
          </li>
        </ul>
      </nav>
    </div>

    <!-- Preview Modal (shared component) -->
    <QuotePreviewModal v-model:show="showPreview" :quote-id="previewQuoteId" :quote-title="previewTitle" />
  </div>
</template>
