<script setup>
import { ref, inject, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '../composables/useApi'

const BASE_URL = import.meta.env.BASE_URL === '/' ? '' : import.meta.env.BASE_URL.replace(/\/$/, '')

const router = useRouter()
const toast = inject('toast')
const { api, authToken, currentUser, registrationOpen, setToken, isAdmin } = useApi()

// ─── Login ───
const loginUser = ref('')
const loginPass = ref('')
const loginError = ref('')

async function doLogin() {
  const u = loginUser.value.trim()
  const p = loginPass.value.trim()
  if (!u || !p) {
    loginError.value = '请输入用户名和密码'
    return
  }
  try {
    const d = await fetch(BASE_URL + '/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: u, password: p })
    }).then(r => r.json())
    if (d.token) {
      setToken(d.token)
      currentUser.value = d.user
      router.push({ name: 'dashboard' })
    } else {
      loginError.value = d.error || '登录失败'
    }
  } catch (e) {
    loginError.value = '网络错误'
  }
}

// ─── Register ───
const isRegister = ref(false)
const regUser = ref('')
const regPass = ref('')
const regEmail = ref('')
const regError = ref('')

function showRegister() {
  isRegister.value = true
  regError.value = ''
}
function showLogin() {
  isRegister.value = false
  loginError.value = ''
}

async function doRegister() {
  const u = regUser.value.trim()
  const p = regPass.value.trim()
  const e = regEmail.value.trim()
  if (!u || !p) {
    regError.value = '用户名和密码不能为空'
    return
  }
  try {
    const d = await fetch(BASE_URL + '/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: u, password: p, email: e })
    }).then(r => r.json())
    if (d.token) {
      setToken(d.token)
      currentUser.value = d.user
      router.push({ name: 'dashboard' })
    } else {
      regError.value = d.error || '注册失败'
    }
  } catch (e) {
    regError.value = '网络错误'
  }
}

// 每次进入登录页时查询注册开放状态
onMounted(async () => {
  try {
    const r = await fetch(BASE_URL + '/api/auth/registration-status')
    const d = await r.json()
    registrationOpen.value = d.registration_open !== false
  } catch (e) { /* 网络错误时默认显示注册链接 */ }
})
</script>

<template>
  <div class="d-flex justify-content-center align-items-center" style="min-height:70vh">
    <!-- Login Form -->
    <div v-if="!isRegister" class="card-modern" style="max-width:400px;width:100%">
      <h4 class="text-center mb-3"><i class="bi bi-lock me-2"></i>登录报价系统</h4>
      <div class="mb-2">
        <input class="form-control" v-model="loginUser" placeholder="用户名" autocomplete="username"
          @keyup.enter="doLogin">
      </div>
      <div class="mb-3">
        <input class="form-control" type="password" v-model="loginPass" placeholder="密码"
          @keyup.enter="doLogin">
      </div>
      <button class="btn btn-primary btn-modern w-100" @click="doLogin">登录</button>
      <div v-if="loginError" class="text-danger small mt-2">{{ loginError }}</div>
      <p v-if="registrationOpen" class="mt-3 text-muted">
        没有账号？<a style="cursor:pointer;color:var(--primary)" @click="showRegister">注册新账号</a>
      </p>
    </div>

    <!-- Register Form -->
    <div v-else class="card-modern" style="max-width:400px;width:100%">
      <h4 class="text-center mb-3"><i class="bi bi-person-plus me-2"></i>注册账号</h4>
      <div class="mb-2">
        <input class="form-control" v-model="regUser" placeholder="用户名">
      </div>
      <div class="mb-2">
        <input class="form-control" type="password" v-model="regPass" placeholder="密码">
      </div>
      <div class="mb-3">
        <input class="form-control" v-model="regEmail" placeholder="邮箱（选填）">
      </div>
      <button class="btn btn-primary btn-modern w-100" @click="doRegister">注册</button>
      <div v-if="regError" class="text-danger small mt-2">{{ regError }}</div>
      <p class="mt-3 text-muted">
        已有账号？<a style="cursor:pointer;color:var(--primary)" @click="showLogin">返回登录</a>
      </p>
    </div>
  </div>
</template>
