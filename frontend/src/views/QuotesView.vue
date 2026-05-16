<script setup>
import { ref, onMounted, inject } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '../composables/useApi'
import { formatMoney } from '../composables/useUtils'

const BASE_URL = import.meta.env.BASE_URL === '/' ? '' : import.meta.env.BASE_URL.replace(/\/$/, '')

const router = useRouter()
const toast = inject('toast')
const { api, isAdmin } = useApi()

const quotes = ref([])
const statusFilter = ref('')
const loading = ref(true)

async function fetchQuotes() {
  loading.value = true
  try {
    const params = statusFilter.value ? `?status=${statusFilter.value}` : ''
    const data = await api(`/api/quotes${params}`)
    if (!data.error) quotes.value = data.quotes || []
  } catch (e) {
    toast('加载报价单失败', 'danger')
  } finally {
    loading.value = false
  }
}

// ─── Preview modal ───
const showPreview = ref(false)
const previewHtml = ref('')
const previewTitle = ref('')
const previewLoading = ref(false)

async function viewQuote(id, title) {
  previewTitle.value = title || '报价单预览'
  showPreview.value = true
  previewHtml.value = ''
  previewLoading.value = true
  try {
    const r = await fetch(BASE_URL + `/api/quotes/${id}/preview`, {
      headers: {
        Authorization: 'Bearer ' + localStorage.getItem('quote_token'),
        Accept: 'text/html',
      }
    })
    if (r.status === 401) {
      previewHtml.value = '<p class="text-danger text-center py-4">会话已过期，请重新登录</p>'
    } else if (!r.ok) {
      previewHtml.value = `<p class="text-danger text-center py-4">加载失败 (${r.status})</p>`
    } else {
      previewHtml.value = await r.text()
    }
  } catch (e) {
    previewHtml.value = '<p class="text-danger text-center py-4">网络错误，请重试</p>'
  } finally {
    previewLoading.value = false
  }
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

// ─── Download Excel ───
function downloadQuote(q) {
  const token = localStorage.getItem('quote_token')
  const url = BASE_URL + `/api/quotes/${q.id}/export-excel?token=${encodeURIComponent(token)}`
  const a = document.createElement('a')
  a.href = url
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

// ─── Send email ───
async function sendEmail(id) {
  const email = prompt('请输入收件人邮箱：')
  if (!email) return
  const r = await api(`/api/quotes/${id}/send-email`, 'POST', { email })
  if (r.error) { toast(r.error, 'danger'); return }
  toast(r.message || '邮件已发送')
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
  let ok = 0, fail = 0
  for (const id of ids) {
    const r = await api(`/api/quotes/${id}`, 'DELETE')
    if (r.error) fail++
    else ok++
  }
  toast(`已删除 ${ok} 条` + (fail ? `，${fail} 条失败` : ''), fail ? 'warning' : 'success')
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

onMounted(fetchQuotes)
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
        <select class="form-select form-select-sm d-inline-block w-auto" v-model="statusFilter" @change="fetchQuotes">
          <option value="">全部状态</option>
          <option value="draft">草稿</option>
          <option value="sent">已发送</option>
          <option value="accepted">已接受</option>
          <option value="rejected">已拒绝</option>
          <option value="expired">已过期</option>
        </select>
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
                <span class="fw-medium" style="cursor:pointer;color:var(--primary)" @click="viewQuote(q.id, q.title)">{{ q.title || '未命名' }}</span>
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
              <td>{{ q.created_by_username || '—' }}</td>
              <td class="text-muted small">{{ q.quote_date || '—' }}</td>
              <td>{{ q.download_count || 0 }}</td>
              <td>
                <div class="d-flex flex-wrap gap-1">
                  <button class="btn btn-sm btn-outline-primary btn-sm-icon" @click="viewQuote(q.id, q.title)" title="预览">
                    <i class="bi bi-eye"></i>
                  </button>
                  <button class="btn btn-sm btn-outline-secondary btn-sm-icon" @click="editQuote(q.id)" title="编辑">
                    <i class="bi bi-pencil"></i>
                  </button>
                  <button class="btn btn-sm btn-outline-success btn-sm-icon" @click="downloadQuote(q)" title="下载Excel">
                    <i class="bi bi-download"></i>
                  </button>
                  <button class="btn btn-sm btn-outline-info btn-sm-icon" @click="sendEmail(q.id)" title="发送邮件">
                    <i class="bi bi-envelope"></i>
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

    <!-- Preview Modal -->
    <Teleport to="body">
      <div v-if="showPreview" class="modal-backdrop show" @click="showPreview = false"></div>
      <div v-if="showPreview" class="modal d-block modern-modal" tabindex="-1">
        <div class="modal-dialog modal-xl modal-dialog-centered modal-dialog-scrollable">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title fw-semibold">📄 {{ previewTitle }}</h5>
              <button type="button" class="btn-close" @click="showPreview = false"></button>
            </div>
            <div class="modal-body" style="background:#f8f9fa">
              <div v-if="previewLoading" class="text-center py-5">
                <div class="spinner-border text-primary" role="status"></div>
                <p class="text-muted mt-2 small">加载预览...</p>
              </div>
              <div v-else class="preview-wrapper" v-html="previewHtml"></div>
            </div>
            <div class="modal-footer">
              <button class="btn btn-secondary btn-modern" @click="showPreview = false">关闭</button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
