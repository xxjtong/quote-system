import { ref } from 'vue'

const BASE_URL = import.meta.env.BASE_URL === '/' ? '' : import.meta.env.BASE_URL.replace(/\/$/, '')
const authToken = ref(localStorage.getItem('quote_token') || '')
const currentUser = ref(null)
const fieldVisibility = ref({})
const registrationOpen = ref(true)

export { BASE_URL }

export function useApi() {
  function setToken(token) {
    authToken.value = token
    if (token) localStorage.setItem('quote_token', token)
    else localStorage.removeItem('quote_token')
  }

  function isLoggedIn() {
    return !!authToken.value
  }

  function isAdmin() {
    return currentUser.value?.role === 'admin'
  }

  function _buildOpts(method, body, extraHeaders = {}) {
    const isFormData = body instanceof FormData
    const headers = isFormData
      ? { Accept: 'application/json', ...extraHeaders }
      : { 'Content-Type': 'application/json', Accept: 'application/json', ...extraHeaders }
    if (authToken.value) headers['Authorization'] = 'Bearer ' + authToken.value
    const opts = { method, headers }
    if (body) opts.body = isFormData ? body : JSON.stringify(body)
    return opts
  }

  function _handle401() {
    setToken('')
    currentUser.value = null
    fieldVisibility.value = {}
  }

  async function api(url, method = 'GET', body = null, timeoutMs = 0) {
    const opts = _buildOpts(method, body)
    if (timeoutMs > 0) {
      const controller = new AbortController()
      opts.signal = controller.signal
      setTimeout(() => controller.abort(), timeoutMs)
    }
    const r = await fetch(BASE_URL + url, opts)
    if (r.status === 401) { _handle401(); return { error: '请先登录' } }
    if (r.status === 204) return null
    const ct = r.headers.get('Content-Type') || ''
    if (!ct.includes('application/json')) return r
    return r.json()
  }

  // 返回原始 Response（用于文本/HTML/Blob 响应），统一 401 处理
  async function apiRaw(url, method = 'GET', body = null, extraHeaders = {}) {
    const opts = _buildOpts(method, body, extraHeaders)
    const r = await fetch(BASE_URL + url, opts)
    if (r.status === 401) { _handle401(); return null }
    return r
  }

  // SSE 流式请求（不读 body，由调用方处理 ReadableStream）
  function apiStream(url, body) {
    const headers = { Accept: 'text/event-stream' }
    if (authToken.value) headers['Authorization'] = 'Bearer ' + authToken.value
    return fetch(BASE_URL + url, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    })
  }

  return { api, apiRaw, apiStream, authToken, currentUser, fieldVisibility, registrationOpen, setToken, isLoggedIn, isAdmin }
}
