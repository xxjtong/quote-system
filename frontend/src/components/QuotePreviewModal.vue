<script setup>
import { ref, watch, inject, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '../composables/useApi'
import { useFocusTrap } from '../composables/useFocusTrap'
import DOMPurify from 'dompurify'

const props = defineProps({
  show: { type: Boolean, default: false },
  quoteId: { type: Number, default: null },
  quoteTitle: { type: String, default: '' },
})
const emit = defineEmits(['update:show'])

const router = useRouter()
const toast = inject('toast')
const { api, apiRaw, authToken } = useApi()

const modalRef = ref(null)
const emailModalRef = ref(null)
const { activate, deactivate } = useFocusTrap(modalRef, close)
const { activate: activateEmail, deactivate: deactivateEmail } = useFocusTrap(emailModalRef, () => { showEmailModal.value = false })

const previewHtml = ref('')
const safeHtml = computed(() => DOMPurify.sanitize(previewHtml.value, {
  ALLOWED_TAGS: ['table','thead','tbody','tfoot','tr','th','td','strong','em','b','i','span','div','p','br','img','style'],
  ALLOWED_ATTR: ['class','style','colspan','rowspan','src'],
}))
const previewLoading = ref(false)
const title = ref('')

// Email
const showEmailModal = ref(false)
const emailRecipient = ref('')
const emailSending = ref(false)

watch(() => props.show, (val) => {
  if (val && props.quoteId) {
    title.value = props.quoteTitle || '报价单预览'
    loadPreview()
    nextTick(() => activate())
  } else if (!val) {
    deactivate()
  }
})

async function loadPreview() {
  previewHtml.value = ''
  previewLoading.value = true
  try {
    const r = await apiRaw(`/api/quotes/${props.quoteId}/preview`, 'GET', null, { Accept: 'text/html' })
    if (!r) {
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

async function downloadQuote() {
  const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, '')
  try {
    const ticketResp = await api('/api/download-ticket', 'POST')
    if (ticketResp.error) { toast(`获取下载凭证失败: ${ticketResp.error}`, 'danger'); return }
    const ticket = ticketResp.ticket
    const url = `/api/quotes/${props.quoteId}/export-excel?download_ticket=${encodeURIComponent(ticket)}&download_date=${dateStr}`
    const r = await apiRaw(url)
    if (!r) return
    if (!r.ok) { toast(`下载失败 (${r.status})`, 'danger'); return }
    const blob = await r.blob()
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    // Use server Content-Disposition filename, or fallback to quote title
    const cd = r.headers.get('Content-Disposition') || ''
    let fname = ''
    // 优先解析 filename*=UTF-8'' （完整UTF-8编码文件名）
    const mStar = cd.match(/filename\*=UTF-8''(.+?)(?:;|$)/)
    if (mStar && mStar[1]) {
      fname = decodeURIComponent(mStar[1])
    } else {
      const m = cd.match(/filename="?([^";\n]+)"?/)
      if (m && m[1]) fname = m[1].replace(/\\"/g, '')
    }
    a.download = fname || (props.quoteTitle || '报价单') + '.xlsx'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(a.href)
  } catch (e) {
    toast('网络错误，下载失败', 'danger')
  }
}

function openEmailModal() {
  emailRecipient.value = ''
  showEmailModal.value = true
  nextTick(() => activateEmail())
}

async function sendEmail() {
  const email = emailRecipient.value.trim()
  if (!email) { toast('请输入收件人邮箱', 'warning'); return }
  emailSending.value = true
  const r = await api(`/api/quotes/${props.quoteId}/send-email`, 'POST', { email })
  if (r.error) { toast(r.error, 'danger') }
  else toast(r.message || '邮件已发送')
  emailSending.value = false
  showEmailModal.value = false
}

function close() {
  emit('update:show', false)
}

function editQuote() {
  close()
  router.push({ name: 'newquote', query: { edit: props.quoteId } })
}
</script>

<template>
  <!-- Preview Modal -->
  <Teleport to="body">
    <div v-if="show" class="modal-backdrop show" @click="close()"></div>
    <div v-if="show" ref="modalRef" class="modal d-block modern-modal" tabindex="-1">
      <div class="modal-dialog modal-xl modal-dialog-centered modal-dialog-scrollable">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title fw-semibold">{{ title }}</h5>
          </div>
          <div class="modal-body" style="background:#f8f9fa">
            <div v-if="previewLoading" class="text-center py-5">
              <div class="spinner-border text-primary" role="status"></div>
              <p class="text-muted mt-2 small">加载预览...</p>
            </div>
            <div v-else class="preview-wrapper" v-html="safeHtml"></div>
          </div>
          <div class="modal-footer" style="gap:8px">
            <button class="btn btn-primary btn-modern" @click="editQuote()">编辑</button>
            <button class="btn btn-outline-success btn-modern" @click="downloadQuote()">下载</button>
            <button class="btn btn-outline-info btn-modern" @click="openEmailModal()">邮件</button>
            <button class="btn btn-secondary btn-modern" @click="close()">关闭</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- Email Modal -->
  <Teleport to="body">
    <div v-if="showEmailModal" class="modal-backdrop show" @click="showEmailModal = false"></div>
    <div v-if="showEmailModal" ref="emailModalRef" class="modal d-block modern-modal" tabindex="-1">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title fw-semibold">发送邮件</h5>
            <button type="button" class="btn-close" @click="showEmailModal = false"></button>
          </div>
          <div class="modal-body">
            <label class="form-label-modern">收件人邮箱</label>
            <input class="form-control" v-model="emailRecipient" type="email" placeholder="example@domain.com" @keydown.enter="sendEmail">
          </div>
          <div class="modal-footer">
            <button class="btn btn-primary btn-modern" @click="sendEmail" :disabled="emailSending || !emailRecipient.trim()">
              <span v-if="emailSending" class="spinner-border spinner-border-sm me-1"></span>
              发送
            </button>
            <button class="btn btn-secondary btn-modern" @click="showEmailModal = false">取消</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
