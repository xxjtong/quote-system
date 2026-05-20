<script setup>
import { ref, computed, onMounted, inject, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '../composables/useApi'
import { formatMoney } from '../composables/useUtils'
import QuotePreviewModal from '../components/QuotePreviewModal.vue'

const router = useRouter()
const toast = inject('toast')
const { api, isAdmin } = useApi()

const stats = ref({ prodCount: 0, quoteCount: 0, downloadTotal: 0, totalAmount: 0, catCount: 0 })
const recentQuotes = ref([])
const loading = ref(true)

async function fetchDashboard() {
  try {
    const [p, q] = await Promise.all([api('/api/products?per_page=1'), api('/api/quotes')])
    const quotes = q.quotes || []
    stats.value = {
      prodCount: p.total || 0, quoteCount: quotes.length,
      totalAmount: quotes.reduce((s, qq) => s + (qq.total_amount || 0), 0),
      downloadTotal: quotes.reduce((s, qq) => s + (qq.download_count || 0), 0),
      catCount: p.categories?.length || 0,
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

// ─── AI Chat ────────────────────────────────────────────────

const chatMessages = ref([])
const chatInput = ref('')
const chatLoading = ref(false)
const chatBox = ref(null)
const elapsedSeconds = ref(0)
const currentPhase = ref(-1)
// SSE real progress tracking
const lastPhase = ref('')
const phases = ['连接', '思考', '生成回复']
const phaseIcons = ['bi-plug', 'bi-cpu', 'bi-pencil']
let timerInterval = null

// Model selector
const availableModels = ref([])
const selectedModel = ref(localStorage.getItem('ai_model') || '')
const defaultModel = ref('')

async function fetchModels() {
  try {
    const token = localStorage.getItem('quote_token')
    const BASE_URL = import.meta.env.BASE_URL === '/' ? '' : import.meta.env.BASE_URL.replace(/\/$/, '')
    const resp = await fetch(BASE_URL + '/api/chat/models', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    if (resp.ok) {
      const data = await resp.json()
      availableModels.value = data.models || []
      defaultModel.value = data.default || 'deepseek-v4-flash'
      if (!selectedModel.value) selectedModel.value = defaultModel.value
    }
  } catch (e) { /* silent */ }
}

function onModelChange(e) {
  selectedModel.value = e.target.value
  localStorage.setItem('ai_model', selectedModel.value)
}

const historyBtn = ref(null)
const historyOpen = ref(false)
const chatHistory = ref([])
const panelStyle = ref({ top: '0px', right: '0px' })

function openHistory() {
  if (historyOpen.value) { historyOpen.value = false; return }
  if (historyBtn.value) {
    const rect = historyBtn.value.getBoundingClientRect()
    panelStyle.value = {
      top: (rect.bottom + 4) + 'px',
      right: (window.innerWidth - rect.right) + 'px',
    }
  }
  historyOpen.value = true
}

function loadHistory() {
  try {
    chatHistory.value = JSON.parse(localStorage.getItem('ai_chat_history') || '[]')
  } catch { chatHistory.value = [] }
}

function saveHistory() {
  if (chatMessages.value.length === 0) return
  // Save full messages to localStorage keyed by session
  try {
    localStorage.setItem('ai_chat_msg_' + currentSessionId.value, JSON.stringify(chatMessages.value))
  } catch {}
  const existing = chatHistory.value.find(h => h.id === currentSessionId.value)
  const preview = chatMessages.value[0]?.content?.slice(0, 30) || '新对话'
  const entry = { id: currentSessionId.value, preview, count: chatMessages.value.length, time: Date.now() }
  if (existing) {
    Object.assign(existing, entry)
  } else {
    chatHistory.value.unshift(entry)
  }
  chatHistory.value = chatHistory.value.slice(0, 50)
  try { localStorage.setItem('ai_chat_history', JSON.stringify(chatHistory.value)) } catch {}
}

function loadChat(id) {
  // Save current session before switching
  saveHistory()
  // Load messages from localStorage
  try {
    const stored = localStorage.getItem('ai_chat_msg_' + id)
    chatMessages.value = stored ? JSON.parse(stored) : []
  } catch {
    chatMessages.value = []
  }
  currentSessionId.value = id
  historyOpen.value = false
}

const currentSessionId = ref(Date.now().toString(36))

function newChat() {
  saveHistory()
  chatMessages.value = []
  currentSessionId.value = Date.now().toString(36)
  historyOpen.value = false
}

// SSE stream

const currentPhaseIcon = computed(() => {
  if (currentPhase.value < 0) return 'bi-hourglass-split'
  return phaseIcons[currentPhase.value] || 'bi-pencil'
})

// Selected products for comparison
const compareList = ref([])
const showCompare = ref(false)

function toggleCompare(product) {
  const idx = compareList.value.findIndex(p => p.name === product.name)
  if (idx >= 0) {
    compareList.value.splice(idx, 1)
  } else {
    compareList.value.push(product)
  }
}

function isCompared(product) {
  return compareList.value.some(p => p.name === product.name)
}

async function sendMessage(textOverride) {
  const text = (textOverride || chatInput.value).trim()
  if (!text || chatLoading.value) return

  chatMessages.value.push({ role: 'user', content: text })
  chatInput.value = ''
  chatLoading.value = true

  elapsedSeconds.value = 0
  currentPhase.value = 0
  lastPhase.value = ''
  timerInterval = setInterval(() => { elapsedSeconds.value++ }, 1000)

  await nextTick(); scrollChat()

  try {
    // Use SSE streaming — need raw fetch for ReadableStream
    const token = localStorage.getItem('quote_token')
    const BASE_URL = import.meta.env.BASE_URL === '/' ? '' : import.meta.env.BASE_URL.replace(/\/$/, '')

    const resp = await fetch(BASE_URL + '/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ input: text, stream: true, model: selectedModel.value }),
    })

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      throw new Error(err.error || `HTTP ${resp.status}`)
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let accumulated = ''
    const msgIndex = chatMessages.value.length
    chatMessages.value.push({ role: 'assistant', content: '', parsed: null, elapsed: 0 })
    await nextTick(); scrollChat()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const dataStr = line.slice(6)
        if (dataStr === '[DONE]') continue
        try {
          const data = JSON.parse(dataStr)

          if (data.type === 'connect') {
            currentPhase.value = 0
            lastPhase.value = 'connect'
            await nextTick(); scrollChat()
          } else if (data.type === 'first_token') {
            currentPhase.value = 1  // model thinking done, generating
            lastPhase.value = 'first_token'
            await nextTick(); scrollChat()
          } else if (data.type === 'tool') {
            currentPhase.value = Math.min(currentPhase.value + 1, phases.length - 1)
            lastPhase.value = 'tool'
          } else if (data.type === 'text') {
            accumulated += data.text
            chatMessages.value[msgIndex].content = accumulated
            // Advance phase: first text means "generating"
            if (lastPhase.value !== 'reply') {
              currentPhase.value = Math.max(currentPhase.value, phases.length - 1)
              lastPhase.value = 'reply'
            }
            await nextTick(); scrollChat()
          } else if (data.type === 'done') {
            chatMessages.value[msgIndex].parsed = data.parsed
            chatMessages.value[msgIndex].elapsed = parseFloat(data.elapsed) || elapsedSeconds.value
            currentPhase.value = phases.length - 1
          } else if (data.type === 'error') {
            chatMessages.value[msgIndex].content = `❌ ${data.error}`
          }
        } catch {}
      }
    }
  } catch (e) {
    chatMessages.value.push({
      role: 'assistant', content: `❌ ${e.message || '网络错误，请重试'}`,
      elapsed: elapsedSeconds.value,
    })
  } finally {
    clearInterval(timerInterval)
    chatLoading.value = false
    currentPhase.value = -1
    saveHistory()
    await nextTick(); scrollChat()
  }
}

function scrollChat() {
  if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight
}

function onChatKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
}

// ─── Message Actions ────────────────────────────────────────
function copyMessage(text) {
  navigator.clipboard.writeText(text).then(() => toast('已复制', 'success'))
}

function regenerateLast() {
  if (chatMessages.value.length < 2) return
  const lastUser = [...chatMessages.value].reverse().find(m => m.role === 'user')
  if (!lastUser) return
  chatMessages.value = chatMessages.value.slice(0, -1) // Remove last AI reply
  sendMessage(lastUser.content)
}

function rateMessage(idx, rating) {
  chatMessages.value[idx].rating = rating
}

// ─── Render markdown with clickable #N ──────────────────────

// Jump to quote
function jumpToQuote(id) {
  router.push({ name: 'quotes', query: { highlight: id } })
}

// Create quote from product
async function createQuoteFromProduct(productName) {
  router.push({ name: 'newquote', query: { product: productName } })
}

// Handle quick reply button
function quickReply(text) {
  sendMessage(text)
}

function formatTimings(t) {
  if (!t) return ''
  const lines = []
  if (t['获取Agent']) lines.push(`会话 ${t['获取Agent']}`)
  if (t['LLM+工具调用']) lines.push(`推理 ${t['LLM+工具调用']}`)
  return lines.join(' · ')
}

onMounted(() => { fetchDashboard(); loadHistory(); fetchModels() })
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
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="stat-card">
          <div class="d-flex align-items-center gap-3">
            <div class="stat-icon" style="background:#fee2e2;color:var(--danger)"><i class="bi bi-currency-yen"></i></div>
            <div style="min-width:0"><div class="text-muted" style="font-size:.72rem">总金额</div><div class="fw-bold fs-4 text-truncate" style="color:var(--danger)">{{ formatMoney(stats.totalAmount) }}</div></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="card-modern anim-in">
      <div class="card-title-modern"><i class="bi bi-lightning text-primary"></i>快速操作</div>
      <div class="d-flex flex-wrap gap-2">
        <button v-if="isAdmin()" class="btn btn-outline-primary btn-modern" @click="goTo('import')"><i class="bi bi-upload me-1"></i>从Excel导入产品</button>
        <button class="btn btn-outline-primary btn-modern" @click="goTo('newquote')"><i class="bi bi-plus-circle me-1"></i>新建报价单</button>
        <button v-if="isAdmin()" class="btn btn-outline-primary btn-modern" @click="goTo('products')"><i class="bi bi-box-seam me-1"></i>管理产品库</button>
      </div>
    </div>

    <!-- AI Chat -->
    <div class="card-modern anim-in" style="position:relative">
      <div class="card-title-modern d-flex align-items-center justify-content-between">
        <div>
          <i class="bi bi-robot text-primary"></i>AI 产品助手
          <small class="text-muted ms-2" style="font-weight:400">问产品、推方案、查参数</small>
        </div>
        <div class="d-flex align-items-center gap-2">
          <select v-if="availableModels.length" class="form-select form-select-sm" style="width:auto;font-size:.75rem"
            :value="selectedModel" @change="onModelChange" title="选择 AI 模型">
            <option v-for="m in availableModels" :key="m.id" :value="m.id"
              :selected="m.id === (selectedModel || defaultModel)">{{ m.name }}</option>
          </select>
          <button class="btn btn-sm btn-outline-secondary" @click="newChat" title="新对话"><i class="bi bi-plus-lg"></i></button>
          <button class="btn btn-sm btn-outline-secondary" @click="openHistory" ref="historyBtn" :class="{ active: historyOpen }" title="历史记录"><i class="bi bi-list"></i></button>
        </div>
      </div>

      <!-- Chat History Sidebar (teleported to avoid clipping) -->
      <Teleport to="body">
        <div v-if="historyOpen" class="history-backdrop" @click="historyOpen = false"></div>
        <div v-if="historyOpen" class="chat-history-panel" :style="panelStyle">
          <div class="d-flex justify-content-between align-items-center mb-2">
            <span class="small fw-bold text-muted">对话历史</span>
            <button class="btn-close btn-close-sm" @click="historyOpen = false" style="font-size:.5rem"></button>
          </div>
          <div v-if="chatHistory.length === 0" class="text-muted small">暂无历史</div>
          <div v-for="h in chatHistory" :key="h.id"
            class="history-item py-1 px-2 rounded small"
            :class="{ 'bg-light': h.id === currentSessionId }"
            style="cursor:pointer"
            @click="loadChat(h.id)">
            <div class="text-truncate">{{ h.preview }}</div>
            <div class="d-flex justify-content-between" style="font-size:.65rem;color:var(--gray-500)">
              <span>{{ h.count }} 条消息</span>
              <span>{{ new Date(h.time).toLocaleDateString() }}</span>
            </div>
          </div>
        </div>
      </Teleport>

      <!-- Messages -->
      <div ref="chatBox" class="chat-messages" style="max-height:60vh;overflow-y:auto;margin-bottom:.75rem">
        <div v-if="chatMessages.length === 0" class="text-muted text-center py-3 small">
          💡 试试问我：20间会议室安装人数感应器 | 推荐最便宜的网关 | 比较星纵VS121和VS321
        </div>

        <div v-for="(msg, i) in chatMessages" :key="i"
          :class="msg.role === 'user' ? 'chat-msg-user' : 'chat-msg-ai'">
          <div class="chat-bubble"
            :class="msg.role === 'user' ? 'bg-primary text-white' : 'bg-light'"
            style="max-width:88%;padding:.5rem .75rem;border-radius:12px;font-size:.85rem;line-height:1.5;white-space:pre-wrap">

            <!-- AI message: render with clickable #N references -->
            <template v-if="msg.role === 'assistant' && msg.content">
              <span v-for="(part, pi) in msg.content.split(/(#\d+|报价单\s*\d+)/g)" :key="pi">
                <template v-if="/^(?:#|报价单)\s*\d+$/.test(part)">
                  <a href="#" class="chat-ref-link" @click.prevent="jumpToQuote(parseInt(part.replace(/\D/g,'')))">{{ part }}</a>
                </template>
                <template v-else>{{ part }}</template>
              </span>
            </template>
            <template v-else>{{ msg.content }}</template>

            <!-- Parsed: Product Cards -->
            <div v-if="msg.role === 'assistant' && msg.parsed?.products?.length" class="mt-2">
              <div v-for="(prod, pi) in msg.parsed.products.slice(0, 4)" :key="pi"
                class="product-card d-flex align-items-center gap-2 p-2 rounded mb-1"
                style="background:white;border:1px solid var(--gray-200);cursor:pointer"
                @click="toggleCompare(prod)">
                <div class="flex-grow-1">
                  <div class="fw-medium small">{{ prod.name }}</div>
                  <div class="text-primary fw-bold">{{ formatMoney(prod.price) }}</div>
                </div>
                <div class="d-flex gap-1">
                  <button class="btn btn-sm btn-outline-primary" style="font-size:.7rem;padding:1px 6px"
                    @click.stop="createQuoteFromProduct(prod.name)" title="创建报价单">
                    <i class="bi bi-cart-plus"></i>
                  </button>
                  <div v-if="isCompared(prod)" class="text-success"><i class="bi bi-check-circle-fill"></i></div>
                  <div v-else class="text-muted" style="font-size:.7rem">对比</div>
                </div>
              </div>

              <!-- Compare action -->
              <div v-if="compareList.length >= 2" class="mt-2 d-flex gap-2">
                <button class="btn btn-sm btn-outline-success" @click="showCompare = true">
                  <i class="bi bi-bar-chart me-1"></i>对比 {{ compareList.length }} 款
                </button>
                <button class="btn btn-sm btn-outline-secondary" @click="compareList = []">清除选择</button>
              </div>
            </div>

            <!-- Parsed: Quick Reply Buttons -->
            <div v-if="msg.role === 'assistant' && msg.parsed?.quick_replies?.length && !chatLoading" class="mt-2 d-flex flex-wrap gap-1">
              <button v-for="(qr, qi) in msg.parsed.quick_replies" :key="qi"
                class="btn btn-sm btn-outline-primary" style="font-size:.78rem"
                @click="quickReply(qr)">{{ qr }}</button>
              <button class="btn btn-sm btn-outline-primary" style="font-size:.78rem"
                @click="createQuoteFromProduct('')">
                <i class="bi bi-plus-circle me-1"></i>一键创建报价单
              </button>
            </div>

            <!-- Message Footer: time/loading + actions -->
            <div v-if="msg.role === 'assistant'" class="d-flex align-items-center justify-content-between mt-2 pt-1"
              style="border-top:1px solid var(--gray-200)">
              <div style="font-size:.7rem;color:var(--gray-500)">
                <!-- Loading status during streaming -->
                <template v-if="chatLoading && i === chatMessages.length - 1">
                  <span class="spinner-grow spinner-grow-sm text-primary" style="width:10px;height:10px;margin-right:4px"></span>
                  {{ phases[currentPhase] || '处理中' }}
                  <span class="ms-2">⏱ {{ elapsedSeconds }}s</span>
                </template>
                <template v-else>
                  <span v-if="msg.elapsed">⏱ {{ msg.elapsed }}s</span>
                  <span v-if="msg.timings"> · {{ formatTimings(msg.timings) }}</span>
                </template>
              </div>
              <div class="d-flex gap-1" v-if="!chatLoading || i !== chatMessages.length - 1">
                <button class="msg-action-btn" @click="copyMessage(msg.content)" title="复制"><i class="bi bi-clipboard"></i></button>
                <button class="msg-action-btn" @click="regenerateLast()" title="重新生成"><i class="bi bi-arrow-repeat"></i></button>
                <button class="msg-action-btn" @click="rateMessage(i, 'up')"
                  :class="{ 'text-success': msg.rating === 'up' }" title="有用"><i class="bi bi-hand-thumbs-up"></i></button>
                <button class="msg-action-btn" @click="rateMessage(i, 'down')"
                  :class="{ 'text-danger': msg.rating === 'down' }" title="没用"><i class="bi bi-hand-thumbs-down"></i></button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Input -->
      <div class="input-group">
        <input v-model="chatInput" class="form-control" placeholder="输入问题，Enter 发送..."
          style="font-size:.85rem" @keydown="onChatKeydown" :disabled="chatLoading">
        <button class="btn btn-primary" @click="sendMessage()" :disabled="chatLoading || !chatInput.trim()">
          <i class="bi bi-send"></i>
        </button>
      </div>
    </div>

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

    <!-- Compare Modal -->
    <div v-if="showCompare" class="modal-backdrop fade show" style="z-index:1055" @click.self="showCompare = false"></div>
    <div v-if="showCompare" class="modal fade show d-block" style="z-index:1056" tabindex="-1">
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h6 class="modal-title"><i class="bi bi-bar-chart me-2"></i>产品对比</h6>
            <button class="btn-close" @click="showCompare = false"></button>
          </div>
          <div class="modal-body">
            <table class="table table-sm table-hover">
              <thead>
                <tr>
                  <th>产品名称</th>
                  <th class="text-end">价格</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(prod, ci) in compareList" :key="ci">
                  <td>{{ prod.name }}</td>
                  <td class="text-end fw-bold">{{ formatMoney(prod.price) }}</td>
                  <td><button class="btn btn-sm btn-outline-danger" @click="compareList.splice(ci, 1); if (compareList.length < 2) showCompare = false"><i class="bi bi-x"></i></button></td>
                </tr>
              </tbody>
            </table>
            <div v-if="compareList.length >= 2" class="mt-3">
              <button class="btn btn-primary" @click="showCompare = false; createQuoteFromProduct(compareList.map(p=>p.name).join(', '))">
                <i class="bi bi-cart me-1"></i>用对比结果创建报价
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Quote Preview Modal (shared component) -->
    <QuotePreviewModal v-model:show="showQuotePreview" :quote-id="previewQuoteId" :quote-title="previewQuoteTitle" />
  </template>
</template>

<style scoped>
.chat-msg-user { display: flex; justify-content: flex-end; margin-bottom: .5rem; }
.chat-msg-ai { display: flex; justify-content: flex-start; margin-bottom: .5rem; }
.chat-messages::-webkit-scrollbar { width: 4px; }
.chat-messages::-webkit-scrollbar-thumb { background: var(--gray-300); border-radius: 4px; }

.chat-ref-link {
  color: var(--primary);
  font-weight: 600;
  text-decoration: underline;
  text-decoration-style: dotted;
  cursor: pointer;
}
.chat-ref-link:hover { color: var(--primary-dark); }

.product-card {
  transition: all 0.15s;
}
.product-card:hover {
  border-color: var(--primary) !important;
  box-shadow: 0 1px 4px rgba(0,0,0,.06);
}

.msg-action-btn {
  background: none;
  border: none;
  padding: 1px 4px;
  font-size: .7rem;
  color: var(--gray-500);
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.15s;
}
.msg-action-btn:hover { background: var(--gray-200); color: var(--gray-700); }

.chat-history-panel {
  position: fixed;
  width: 260px;
  max-height: 400px;
  overflow-y: auto;
  background: white;
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  padding: 10px;
  box-shadow: 0 8px 24px rgba(0,0,0,.12);
  z-index: 1060;
}
.history-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1059;
}
.history-item:hover { background: var(--gray-100); }
.history-item.active { background: var(--primary-light); }

.modal-backdrop { background: rgba(0,0,0,.3); }
</style>
