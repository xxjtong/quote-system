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

  async function api(url, method = 'GET', body = null, timeoutMs = 0) {
    const isFormData = body instanceof FormData
    const headers = isFormData
      ? { Accept: 'application/json' }
      : { 'Content-Type': 'application/json', Accept: 'application/json' }
    if (authToken.value) headers['Authorization'] = 'Bearer ' + authToken.value
    const opts = { method, headers }
    if (body) opts.body = isFormData ? body : JSON.stringify(body)
    if (timeoutMs > 0) {
      const controller = new AbortController()
      opts.signal = controller.signal
      setTimeout(() => controller.abort(), timeoutMs)
    }
    const r = await fetch(BASE_URL + url, opts)
    if (r.status === 401) {
      setToken('')
      currentUser.value = null
      fieldVisibility.value = {}
      return { error: '请先登录' }
    }
    return r.json()
  }

  return { api, authToken, currentUser, fieldVisibility, registrationOpen, setToken, isLoggedIn, isAdmin }
}
