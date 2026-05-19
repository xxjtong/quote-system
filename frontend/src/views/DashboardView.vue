<script setup>
import { ref, computed, onMounted, inject, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '../composables/useApi'
import { formatMoney } from '../composables/useUtils'

const router = useRouter()
const toast = inject('toast')
const { api, isAdmin } = useApi()

const stats = ref({
  prodCount: 0,
  quoteCount: 0,
  downloadTotal: 0,
  totalAmount: 0,
  catCount: 0,
})
const recentQuotes = ref([])
const loading = ref(true)

async function fetchDashboard() {
  try {
    const [p, q] = await Promise.all([
      api('/api/products?per_page=1'),
      api('/api/quotes'),
    ])
    const quotes = q.quotes || []
    stats.value = {
      prodCount: p.total || 0,
      quoteCount: quotes.length,
      totalAmount: quotes.reduce((s, qq) => s + (qq.total_amount || 0), 0),
      downloadTotal: quotes.reduce((s, qq) => s + (qq.download_count || 0), 0),
      catCount: p.categories?.length || 0,
    }
    recentQuotes.value = quotes.slice(0, 10)
  } catch (e) {
    toast('加载概览失败', 'danger')
  } finally {
    loading.value = false
  }
}

function goTo(name) {
  router.push({ name })
}

// ─── AI Chat ────────────────────────────────────────────────

const chatMessages = ref([])
const chatInput = ref('')
const chatLoading = ref(false)
const chatBox = ref(null)
const elapsedSeconds = ref(0)
const estimatedTotal = ref(0)
const currentPhase = ref(-1)
const estLabel = ref('')
let timerInterval = null

const phaseList = ['分析问题', '查询数据', '整理信息', '生成回复']

// 根据消息内容预估耗时
function estimateTime(text) {
  const hasQuote = /报价|创建|生成报价|导出|excel/i.test(text)
  const hasSearch = /搜索|查询|查找|有哪些|推荐|哪个|什么|怎么|比较|最低|最高/i.test(text)
  if (hasQuote) return { phases: 4, total: 75, label: '创建报价约 60-90s' }
  if (hasSearch && text.length > 6) return { phases: 3, total: 40, label: '数据查询约 20-60s' }
  return { phases: 2, total: 10, label: '快速问答约 5-15s' }
}

// 当前阶段名（实时）
const currentPhaseName = computed(() => {
  if (currentPhase.value < 0) return ''
  return phaseList[currentPhase.value] || phaseList[phaseList.length - 1]
})

// 进度百分比
const progressPercent = computed(() => {
  if (estimatedTotal.value <= 0) return 0
  return Math.min(100, Math.round((elapsedSeconds.value / estimatedTotal.value) * 100))
})

async function sendMessage() {
  const text = chatInput.value.trim()
  if (!text || chatLoading.value) return

  const est = estimateTime(text)
  estimatedTotal.value = est.total
  estLabel.value = est.label

  chatMessages.value.push({ role: 'user', content: text })
  chatInput.value = ''
  chatLoading.value = true

  // Start timer + phase tracker
  elapsedSeconds.value = 0
  currentPhase.value = 0
  timerInterval = setInterval(() => {
    elapsedSeconds.value++
    const ratio = elapsedSeconds.value / estimatedTotal.value
    currentPhase.value = Math.min(Math.floor(ratio * est.phases), est.phases - 1)
  }, 1000)

  await nextTick()
  scrollChat()

  try {
    const data = await api('/api/chat', 'POST', { input: text }, 180000)
    const elapsed = elapsedSeconds.value
    if (data.error) {
      chatMessages.value.push({
        role: 'assistant',
        content: `❌ ${data.error}`,
        elapsed,
        timings: data.timings || null,
      })
    } else {
      chatMessages.value.push({
        role: 'assistant',
        content: data.reply,
        elapsed,
        timings: data.timings || null,
      })
    }
  } catch (e) {
    chatMessages.value.push({
      role: 'assistant',
      content: `❌ 网络错误，请重试`,
      elapsed: elapsedSeconds.value,
      timings: null,
    })
  } finally {
    clearInterval(timerInterval)
    chatLoading.value = false
    currentPhase.value = -1
    await nextTick()
    scrollChat()
  }
}

function scrollChat() {
  if (chatBox.value) {
    chatBox.value.scrollTop = chatBox.value.scrollHeight
  }
}

function onChatKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

// 格式化 timings 为紧凑行
function formatTimings(t) {
  if (!t) return ''
  const lines = []
  if (t['获取Agent']) lines.push(`会话 ${t['获取Agent']}`)
  if (t['LLM+工具调用']) lines.push(`推理 ${t['LLM+工具调用']}`)
  return lines.join(' · ')
}

onMounted(fetchDashboard)
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
            <div>
              <div class="text-muted" style="font-size:.72rem">产品总数</div>
              <div class="fw-bold fs-4">{{ stats.prodCount }}</div>
            </div>
          </div>
          <div class="mt-2 small text-muted">{{ stats.catCount }} 个分类</div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="stat-card">
          <div class="d-flex align-items-center gap-3">
            <div class="stat-icon" style="background:#d1fae5;color:var(--success)">
              <i class="bi bi-file-earmark-text"></i>
            </div>
            <div>
              <div class="text-muted" style="font-size:.72rem">报价单</div>
              <div class="fw-bold fs-4">{{ stats.quoteCount }}</div>
            </div>
          </div>
          <div class="mt-2 small text-muted">共 {{ formatMoney(stats.totalAmount) }}</div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="stat-card">
          <div class="d-flex align-items-center gap-3">
            <div class="stat-icon" style="background:#fef3c7;color:var(--warning)">
              <i class="bi bi-download"></i>
            </div>
            <div>
              <div class="text-muted" style="font-size:.72rem">下载</div>
              <div class="fw-bold fs-4">{{ stats.downloadTotal }}</div>
            </div>
          </div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="stat-card">
          <div class="d-flex align-items-center gap-3">
            <div class="stat-icon" style="background:#fee2e2;color:var(--danger)">
              <i class="bi bi-currency-yen"></i>
            </div>
            <div style="min-width:0">
              <div class="text-muted" style="font-size:.72rem">总金额</div>
              <div class="fw-bold fs-4 text-truncate" style="color:var(--danger)">{{ formatMoney(stats.totalAmount) }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Recent Quotes -->
    <div class="card-modern anim-in">
      <div class="card-title-modern"><i class="bi bi-clock-history text-primary"></i>最近报价</div>
      <template v-if="recentQuotes.length">
        <div v-for="qq in recentQuotes" :key="qq.id"
          class="d-flex justify-content-between align-items-center py-2"
          style="border-bottom:1px solid var(--gray-100);cursor:pointer"
          @click="goTo('quotes')">
          <span><i class="bi bi-file-text me-2 text-muted"></i>{{ qq.title || '未命名' }}</span>
          <span class="text-muted small fw-medium">{{ formatMoney(qq.total_amount) }}</span>
        </div>
      </template>
      <div v-else class="text-muted text-center py-3 small">暂无报价单</div>
    </div>

    <!-- Quick Actions -->
    <div class="card-modern anim-in">
      <div class="card-title-modern"><i class="bi bi-lightning text-primary"></i>快速操作</div>
      <div class="d-flex flex-wrap gap-2">
        <button v-if="isAdmin()" class="btn btn-outline-primary btn-modern" @click="goTo('import')">
          <i class="bi bi-upload me-1"></i>从Excel导入产品
        </button>
        <button class="btn btn-outline-primary btn-modern" @click="goTo('newquote')">
          <i class="bi bi-plus-circle me-1"></i>新建报价单
        </button>
        <button v-if="isAdmin()" class="btn btn-outline-primary btn-modern" @click="goTo('products')">
          <i class="bi bi-box-seam me-1"></i>管理产品库
        </button>
      </div>
    </div>

    <!-- AI Chat -->
    <div class="card-modern anim-in">
      <div class="card-title-modern">
        <i class="bi bi-robot text-primary"></i>AI 产品助手
        <small class="text-muted ms-2" style="font-weight:400">问产品、推方案、查参数</small>
      </div>

      <!-- Messages -->
      <div ref="chatBox" class="chat-messages" style="max-height:400px;overflow-y:auto;margin-bottom:.75rem">
        <div v-if="chatMessages.length === 0" class="text-muted text-center py-3 small">
          💡 试试问我：房顶漏水用什么材料？最便宜的传感器是哪个？
        </div>
        <div v-for="(msg, i) in chatMessages" :key="i"
          :class="msg.role === 'user' ? 'chat-msg-user' : 'chat-msg-ai'">
          <div class="chat-bubble" :class="msg.role === 'user' ? 'bg-primary text-white' : 'bg-light'"
            style="max-width:85%;padding:.5rem .75rem;border-radius:12px;font-size:.85rem;line-height:1.5;white-space:pre-wrap">
            {{ msg.content }}
            <!-- 耗时标记 -->
            <div v-if="msg.role === 'assistant' && msg.elapsed" class="mt-2 pt-1" style="font-size:.7rem;color:var(--gray-500);border-top:1px solid var(--gray-200)">
              ⏱ {{ msg.elapsed }}s
              <span v-if="msg.timings"> · {{ formatTimings(msg.timings) }}</span>
            </div>
          </div>
        </div>

        <!-- Loading: 分阶段进度 -->
        <div v-if="chatLoading" class="chat-msg-ai">
          <div class="chat-bubble bg-light" style="padding:.6rem .8rem;border-radius:12px;min-width:260px">
            <!-- 进度条 -->
            <div class="progress mb-2" style="height:4px">
              <div class="progress-bar progress-bar-striped progress-bar-animated"
                :style="{width: progressPercent + '%'}"
                :class="progressPercent < 30 ? 'bg-info' : progressPercent < 70 ? 'bg-primary' : 'bg-success'"></div>
            </div>

            <!-- 阶段列表 -->
            <div style="font-size:.78rem">
              <div v-for="(p, idx) in phaseList.slice(0, estimatedTotal > 30 ? 4 : estimatedTotal > 10 ? 3 : 2)" :key="idx"
                class="d-flex align-items-center gap-2 mb-1"
                :style="{opacity: idx <= currentPhase ? 1 : 0.4}">
                <span v-if="idx < currentPhase" class="text-success"><i class="bi bi-check-circle-fill"></i></span>
                <span v-else-if="idx === currentPhase" class="spinner-grow spinner-grow-sm text-primary" style="width:10px;height:10px"></span>
                <span v-else style="width:10px;height:10px;display:inline-block;border-radius:50%;border:1.5px solid var(--gray-400)"></span>
                {{ p }}
              </div>
            </div>

            <!-- 预估 + 已用 -->
            <div class="mt-1 d-flex justify-content-between" style="font-size:.68rem;color:var(--gray-500)">
              <span>预估 {{ estLabel }}</span>
              <span>已用 {{ elapsedSeconds }}s</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Input -->
      <div class="input-group">
        <input v-model="chatInput" class="form-control" placeholder="输入问题，Enter 发送..."
          style="font-size:.85rem"
          @keydown="onChatKeydown"
          :disabled="chatLoading">
        <button class="btn btn-primary" @click="sendMessage" :disabled="chatLoading || !chatInput.trim()">
          <i class="bi bi-send"></i>
        </button>
      </div>
    </div>
  </template>
</template>

<style scoped>
.chat-msg-user {
  display: flex;
  justify-content: flex-end;
  margin-bottom: .5rem;
}
.chat-msg-ai {
  display: flex;
  justify-content: flex-start;
  margin-bottom: .5rem;
}
.chat-messages::-webkit-scrollbar {
  width: 4px;
}
.chat-messages::-webkit-scrollbar-thumb {
  background: var(--gray-300);
  border-radius: 4px;
}
</style>
