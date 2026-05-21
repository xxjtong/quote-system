<script setup>
import { ref, reactive } from 'vue'
import { useApi } from '../composables/useApi'
import { inject } from 'vue'

const props = defineProps({
  show: { type: Boolean, default: true },
  product: { type: Object, default: null },
})

const emit = defineEmits(['fill', 'clear'])

const toast = inject('toast')
const { api } = useApi()

// ─── Smart Paste State ───
const smartRecognizing = ref(false)
const smartResult = ref(null)
const smartSource = ref('')
const smartRawText = ref('')
const smartTextInput = ref('')
const smartElapsed = ref(0)
const smartStatus = ref('')  // idle | recognizing | success | error
let _smartTimer = null
const smartEdit = reactive({ name: '', spec: '', supplier: '', category: '', price: '', cost_price: '', unit: '', function_desc: '', remark: '' })
const smartError = ref('')

const SOURCE_LABELS = {
  'doubao-vision': '豆包 Vision',
  'deepseek-parse': '豆包 Seed Mini',
  'regex-parse': '正则解析',
}

function _startSmartTimer() {
  smartElapsed.value = 0
  smartStatus.value = 'recognizing'
  if (_smartTimer) clearInterval(_smartTimer)
  _smartTimer = setInterval(() => { smartElapsed.value += 0.1 }, 100)
}

function _stopSmartTimer() {
  if (_smartTimer) { clearInterval(_smartTimer); _smartTimer = null }
}

function populateSmartEdit(result) {
  smartEdit.name = result.name || ''
  smartEdit.spec = result.spec || ''
  smartEdit.supplier = result.supplier || ''
  smartEdit.category = result.category || ''
  smartEdit.price = result.price || ''
  smartEdit.cost_price = result.cost_price || ''
  smartEdit.unit = result.unit || ''
  smartEdit.function_desc = result.function_desc || ''
  smartEdit.remark = result.remark || ''
  smartStatus.value = 'success'
  // 自动填入上方表单
  fillFromSmartResult()
  // 识别成功提示
  const src = SOURCE_LABELS[smartSource.value] || smartSource.value || 'AI'
  toast(`${src} 识别成功，已填入表单`)
}

function resetSmartEdit() {
  smartEdit.name = ''; smartEdit.spec = ''; smartEdit.supplier = ''; smartEdit.category = ''
  smartEdit.price = ''; smartEdit.cost_price = ''; smartEdit.unit = ''; smartEdit.function_desc = ''; smartEdit.remark = ''
}

async function recognizeFromText() {
  const text = smartTextInput.value.trim()
  if (!text || smartRecognizing.value) return
  smartRecognizing.value = true
  smartError.value = ''
  smartResult.value = null
  _startSmartTimer()
  try {
    const r = await api('/api/products/recognize', 'POST', { text })
    if (r.products && r.products.length > 0) {
      smartResult.value = r.products[0]
      smartSource.value = r.source || ''
      smartRawText.value = r.raw_text || ''
      populateSmartEdit(r.products[0])
    } else {
      smartError.value = r.error || '未能识别出产品信息'
      smartStatus.value = 'error'
    }
  } catch (err) {
    smartError.value = '识别失败，请重试'
    smartStatus.value = 'error'
  } finally {
    smartRecognizing.value = false
    _stopSmartTimer()
  }
}

async function onSmartPaste(e) {
  const items = e.clipboardData?.items
  if (!items) return

  for (const item of items) {
    // 模式1: 图片粘贴
    if (item.type.startsWith('image/')) {
      e.preventDefault()
      const blob = item.getAsFile()
      if (!blob) continue
      smartRecognizing.value = true
      smartError.value = ''
      smartResult.value = null
      _startSmartTimer()
      try {
        const form = new FormData()
        form.append('file', blob, 'smart.' + (item.type.split('/')[1] || 'png'))
        const r = await api('/api/products/recognize', 'POST', form)
        if (r.products && r.products.length > 0) {
          smartResult.value = r.products[0]
          smartSource.value = r.source || ''
          smartRawText.value = r.raw_text || ''
          populateSmartEdit(r.products[0])
        } else {
          smartError.value = r.error || '未能识别出产品信息'
        }
      } catch (err) {
        smartError.value = '识别失败，请重试'
      } finally {
        smartRecognizing.value = false
        _stopSmartTimer()
      }
      return
    }

    // 模式2: 文字粘贴
    if (item.type === 'text/plain' || item.type === 'text/html') {
      e.preventDefault()
      item.getAsString(async (str) => {
        const text = str.trim()
        if (!text || text.length < 3) return
        smartRecognizing.value = true
        smartError.value = ''
        smartResult.value = null
        _startSmartTimer()
        try {
          const r = await api('/api/products/recognize', 'POST', { text })
          if (r.products && r.products.length > 0) {
            smartResult.value = r.products[0]
            smartSource.value = r.source || ''
            smartRawText.value = r.raw_text || ''
            populateSmartEdit(r.products[0])
          } else {
            smartError.value = r.error || '未能识别出产品信息'
          }
        } catch (err) {
          smartError.value = '识别失败，请重试'
        } finally {
          smartRecognizing.value = false
          _stopSmartTimer()
        }
      })
      return
    }
  }
}

function fillFromSmartResult() {
  emit('fill', { ...smartEdit })
  smartResult.value = null
  smartSource.value = ''
  smartRawText.value = ''
  resetSmartEdit()
}

function clearSmartResult() {
  // 清空识别结果 + textarea输入
  smartResult.value = null
  smartSource.value = ''
  smartRawText.value = ''
  smartError.value = ''
  smartTextInput.value = ''
  smartStatus.value = 'idle'
  resetSmartEdit()
  // 通知父组件清空表单中被识别填入的字段
  emit('clear')
}

// Expose resetAll for parent to call on form open/close
function resetAll() {
  smartResult.value = null
  smartSource.value = ''
  smartRawText.value = ''
  smartError.value = ''
  smartTextInput.value = ''
  smartStatus.value = 'idle'
  smartRecognizing.value = false
  resetSmartEdit()
}

defineExpose({ resetAll })
</script>

<template>
  <div v-show="show" class="col-12 mt-3" @paste="onSmartPaste">
    <div class="p-3 rounded-3" style="background:var(--gray-50);border:2px dashed var(--gray-300)">
      <label class="form-label-modern mb-1 d-flex align-items-center gap-2" style="font-size:.82rem">
        <span><i class="bi bi-magic"></i> 智能识别</span>
        <span v-if="smartStatus === 'recognizing'" class="text-primary" style="font-size:.78rem">
          <span class="spinner-border spinner-border-sm" style="width:.7rem;height:.7rem"></span>
          识别中... {{ smartElapsed > 0 ? smartElapsed.toFixed(1) + 's' : '' }}
        </span>
        <span v-else-if="smartStatus === 'success'" class="text-success" style="font-size:.78rem">
          <i class="bi bi-check-circle-fill"></i>
          {{ SOURCE_LABELS[smartSource.value] || smartSource.value || 'AI' }} 识别完成 {{ smartElapsed > 0 ? smartElapsed.toFixed(1) + 's' : '' }}
        </span>
        <span v-else-if="smartStatus === 'error'" class="text-danger" style="font-size:.78rem">
          <i class="bi bi-x-circle-fill"></i> 识别失败
        </span>
      </label>
      <!-- 文字输入区 -->
      <div class="d-flex gap-2 mb-2">
        <textarea class="form-control form-control-sm" v-model="smartTextInput"
          placeholder="粘贴产品文字/参数，或直接 Ctrl+V 粘贴截图"
          rows="2" style="font-size:.78rem;resize:vertical"></textarea>
        <div class="d-flex flex-column gap-1" style="min-width:70px">
          <button class="btn btn-primary btn-sm px-2" @click="recognizeFromText"
            :disabled="smartRecognizing || !smartTextInput.trim()" style="white-space:nowrap;font-size:.78rem">
            <i class="bi bi-magic"></i> 识别
          </button>
          <button class="btn btn-outline-secondary btn-sm px-2" @click="clearSmartResult"
            style="white-space:nowrap;font-size:.78rem" title="清空所有内容重新识别">
            <i class="bi bi-arrow-counterclockwise"></i> 重置
          </button>
        </div>
      </div>
      <div v-if="smartError" class="alert alert-warning py-1 px-2 mb-0 small" style="font-size:.8rem">
        {{ smartError }}
      </div>
      <!-- 识别结果预览（可编辑） -->
      <div v-if="smartResult" class="mt-2 p-2 rounded-2" style="background:white;border:2px solid var(--primary);font-size:.82rem">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <span class="fw-semibold text-primary"><i class="bi bi-check-circle"></i> 识别结果（可编辑修正）</span>
          <small v-if="smartSource" class="text-muted" style="font-size:.7rem;background:var(--gray-100);padding:1px 6px;border-radius:4px">{{ SOURCE_LABELS[smartSource] || smartSource }}</small>
        </div>
        <div v-if="smartResult.existing_product_id" class="alert alert-info py-1 px-2 mb-2" style="font-size:.78rem">
          <i class="bi bi-link-45deg"></i> 产品库已有该产品（ID:{{ smartResult.existing_product_id }}），当前为新增录入
        </div>
        <div class="row g-1">
          <div class="col-6 mb-1">
            <label class="form-label-modern mb-0" style="font-size:.7rem">产品名称</label>
            <input class="form-control form-control-sm" v-model="smartEdit.name" style="font-size:.78rem">
          </div>
          <div class="col-6 mb-1">
            <label class="form-label-modern mb-0" style="font-size:.7rem">规格型号</label>
            <input class="form-control form-control-sm" v-model="smartEdit.spec" style="font-size:.78rem">
          </div>
          <div class="col-6 mb-1">
            <label class="form-label-modern mb-0" style="font-size:.7rem">厂商</label>
            <input class="form-control form-control-sm" v-model="smartEdit.supplier" style="font-size:.78rem">
          </div>
          <div class="col-6 mb-1">
            <label class="form-label-modern mb-0" style="font-size:.7rem">分类</label>
            <input class="form-control form-control-sm" v-model="smartEdit.category" style="font-size:.78rem">
          </div>
          <div class="col-4 mb-1">
            <label class="form-label-modern mb-0" style="font-size:.7rem">销售单价</label>
            <input class="form-control form-control-sm" v-model="smartEdit.price" style="font-size:.78rem">
          </div>
          <div class="col-4 mb-1">
            <label class="form-label-modern mb-0" style="font-size:.7rem">成本价</label>
            <input class="form-control form-control-sm" v-model="smartEdit.cost_price" style="font-size:.78rem">
          </div>
          <div class="col-4 mb-1">
            <label class="form-label-modern mb-0" style="font-size:.7rem">单位</label>
            <input class="form-control form-control-sm" v-model="smartEdit.unit" style="font-size:.78rem">
          </div>
          <div class="col-12 mb-1">
            <label class="form-label-modern mb-0" style="font-size:.7rem">功能描述</label>
            <textarea class="form-control form-control-sm" v-model="smartEdit.function_desc" rows="2" style="font-size:.78rem;resize:vertical"></textarea>
          </div>
          <div class="col-12 mb-1">
            <label class="form-label-modern mb-0" style="font-size:.7rem">备注</label>
            <input class="form-control form-control-sm" v-model="smartEdit.remark" style="font-size:.78rem">
          </div>
        </div>
        <!-- 原始识别数据 -->
        <details v-if="smartRawText" class="mt-2">
          <summary class="text-muted" style="font-size:.72rem;cursor:pointer">📋 模型返回原始数据</summary>
          <pre class="mt-1 p-2 rounded-1" style="background:var(--gray-50);font-size:.7rem;max-height:200px;overflow:auto;white-space:pre-wrap;word-break:break-all">{{ smartRawText }}</pre>
        </details>
        <button class="btn btn-sm btn-outline-primary w-100 mt-1" @click="fillFromSmartResult">
          <i class="bi bi-arrow-up"></i> 重新填入上方表单
        </button>
      </div>
    </div>
  </div>
</template>
