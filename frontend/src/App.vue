<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useApi } from './composables/useApi'
import { escHtml } from './composables/useUtils'
import ToastMessage from './components/ToastMessage.vue'

const BASE_URL = import.meta.env.BASE_URL === '/' ? '' : import.meta.env.BASE_URL.replace(/\/$/, '')

const router = useRouter()
const route = useRoute()
const { api, authToken, currentUser, fieldVisibility, registrationOpen, setToken, isLoggedIn, isAdmin } = useApi()

// ─── Toast ref ───
const toastRef = ref(null)
function toast(msg, type = 'success') { toastRef.value?.toast(msg, type) }
import { provide } from 'vue'
provide('toast', toast)

// ─── Auth-aware: hide sidebar on login page ───
const showSidebar = computed(() => isLoggedIn() && route.name !== 'login')

// ─── Sidebar ───
const sidebarOpen = ref(false)
const sidebarCollapsed = ref(false)
function toggleSidebar() { sidebarOpen.value = !sidebarOpen.value }
function closeSidebar() { sidebarOpen.value = false }
function toggleCollapse() { sidebarCollapsed.value = !sidebarCollapsed.value }

// Close sidebar on route change (mobile)
watch(() => route.name, () => { closeSidebar() })

// ─── Tabs ───
const tabs = [
  { id: 'dashboard', label: '概览', icon: 'bi bi-speedometer2' },
  { id: 'products', label: '产品管理', icon: 'bi bi-box-seam' },
  { id: 'quotes', label: '报价单', icon: 'bi bi-file-earmark-text' },
  { id: 'newquote', label: '新建报价', icon: 'bi bi-plus-circle', badge: '+' },
  { id: 'import', label: '导入产品', icon: 'bi bi-upload', adminOnly: true },
  { id: 'admin', label: '管理', icon: 'bi bi-gear', adminOnly: true },
]

const titles = {
  dashboard: '概览', products: '产品管理', quotes: '报价单',
  newquote: '新建报价单', import: '导入产品', admin: '管理',
  login: '登录'
}

// ─── Version ───
const version = ref('')

// ─── Profile Modal ───
const showProfile = ref(false)
const profileEmail = ref('')
const profileCurPw = ref('')
const profileNewPw = ref('')

async function openProfile() {
  if (!currentUser.value) return
  profileEmail.value = currentUser.value.email || ''
  profileCurPw.value = ''
  profileNewPw.value = ''
  showProfile.value = true
}

async function saveProfile() {
  const body = { email: profileEmail.value.trim() }
  const newpw = profileNewPw.value.trim()
  if (newpw) {
    body.current_password = profileCurPw.value.trim()
    body.new_password = newpw
  }
  const r = await api('/api/auth/profile', 'PUT', body)
  if (r.user) {
    currentUser.value = r.user
    showProfile.value = false
    toast(r.message || '已更新')
  } else {
    toast(r.error || '修改失败', 'warning')
  }
}

// ─── Modal backdrop click ───
function onBackdropClick() {
  showProfile.value = false
}

// ─── Logout ───
function logout() {
  setToken('')
  currentUser.value = null
  router.push({ name: 'login' })
}

// ─── Watch token — redirect to login when cleared elsewhere (401) ───
watch(authToken, (val) => {
  if (!val && route.name !== 'login') {
    router.push({ name: 'login' })
  }
})

// ─── Check session on mount ───
onMounted(async () => {
  if (!authToken.value) return
  try {
    const r = await fetch(BASE_URL + '/api/session', {
      headers: { Authorization: 'Bearer ' + authToken.value, Accept: 'application/json' }
    })
    if (r.status === 401) { setToken(''); return }
    const d = await r.json()
    if (d.user) {
      currentUser.value = d.user
      fieldVisibility.value = d.field_visibility || {}
      registrationOpen.value = d.registration_open !== false
    }
  } catch (e) { /* offline — stay on current page */ }
  try {
    const v = await api('/api/version')
    version.value = v.version || ''
  } catch (e) { /* ignore */ }
})
</script>

<template>
  <div class="d-flex">
    <!-- Sidebar Overlay (mobile) -->
    <div v-if="showSidebar" class="sidebar-overlay" :class="{ show: sidebarOpen }" @click="closeSidebar"></div>

    <!-- Sidebar -->
    <div v-if="showSidebar" class="sidebar" :class="{ open: sidebarOpen, collapsed: sidebarCollapsed }">
      <div class="sidebar-logo" style="position:relative">
        <h5><i class="bi bi-file-text me-2"></i>报价系统</h5>
        <small>硬件报价管理平台</small>
        <button class="sidebar-collapse-btn d-none d-lg-block" @click="toggleCollapse" :title="sidebarCollapsed ? '展开菜单' : '收起菜单'">
          <i :class="sidebarCollapsed ? 'bi bi-chevron-right' : 'bi bi-chevron-left'"></i>
        </button>
      </div>
      <div class="sidebar-nav">
        <a v-for="tab in tabs" :key="tab.id"
           class="nav-link"
           :class="{ active: route.name === tab.id }"
           :style="tab.adminOnly && !isAdmin() ? {display:'none'} : {}"
           @click="router.push({name: tab.id})">
          <i :class="tab.icon"></i> {{ tab.label }}
          <span v-if="tab.badge" class="badge">{{ tab.badge }}</span>
        </a>
        <hr style="border-color: rgba(255,255,255,.08); margin: .5rem 0;">
        <a class="nav-link" style="opacity:.6; font-size:.8rem; cursor:default">
          <i class="bi bi-info-circle"></i> <span>{{ version || 'v—' }}</span>
        </a>
      </div>
    </div>

    <!-- Main Wrapper -->
    <div class="main-wrapper" :class="{ expanded: sidebarCollapsed }" :style="!showSidebar ? {marginLeft:'0'} : {}">
      <div class="topbar">
        <button class="btn btn-link sidebar-toggle text-dark me-2 p-0" @click="toggleSidebar"
          style="font-size:1.2rem;text-decoration:none">
          <i class="bi bi-list"></i>
        </button>
        <span class="topbar-title">{{ titles[route.name] || route.name }}</span>
        <div style="margin-left:auto;display:flex;align-items:center;gap:.5rem">
          <div v-if="currentUser" class="dropdown">
            <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button"
              data-bs-toggle="dropdown" style="font-size:.75rem">
              {{ currentUser.username }}{{ isAdmin() ? ' [管理员]' : '' }}
            </button>
            <ul class="dropdown-menu dropdown-menu-end" style="font-size:.82rem;min-width:140px">
              <li><a class="dropdown-item" href="#" @click.prevent="openProfile"><i class="bi bi-person-gear me-2"></i>个人信息</a></li>
              <li><hr class="dropdown-divider" style="margin:.25rem 0"></li>
              <li><a class="dropdown-item text-danger" href="#" @click.prevent="logout"><i class="bi bi-box-arrow-right me-2"></i>退出</a></li>
            </ul>
          </div>
        </div>
      </div>
      <div class="main-content">
        <router-view v-slot="{ Component }">
          <template v-if="Component">
            <component :is="Component" />
          </template>
        </router-view>
      </div>
    </div>

    <!-- Profile Modal -->
    <Teleport to="body">
      <div v-if="showProfile" class="modal-backdrop show" @click="onBackdropClick"></div>
      <div v-if="showProfile" class="modal d-block modern-modal" tabindex="-1">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title fw-semibold">个人信息</h5>
              <button type="button" class="btn-close" @click="showProfile = false"></button>
            </div>
            <div class="modal-body">
              <div class="mb-3">
                <label class="form-label small">用户名</label>
                <input class="form-control" :value="currentUser?.username || ''" disabled>
              </div>
              <div class="mb-3">
                <label class="form-label small">角色</label>
                <input class="form-control" :value="isAdmin() ? '管理员' : '普通用户'" disabled>
              </div>
              <div class="mb-3">
                <label class="form-label small">邮箱</label>
                <input class="form-control" v-model="profileEmail" placeholder="选填">
              </div>
              <hr>
              <div class="mb-2">
                <label class="form-label small">当前密码 <span class="text-danger">*</span></label>
                <input class="form-control" type="password" v-model="profileCurPw" placeholder="修改邮箱或密码需验证">
              </div>
              <div class="mb-2">
                <label class="form-label small">新密码 <span class="text-muted">（留空不修改）</span></label>
                <input class="form-control" type="password" v-model="profileNewPw" placeholder="至少3位">
              </div>
            </div>
            <div class="modal-footer">
              <button class="btn btn-primary btn-modern" @click="saveProfile">保存</button>
              <button class="btn btn-secondary btn-modern" @click="showProfile = false">取消</button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Toast -->
    <ToastMessage ref="toastRef" />
  </div>
</template>
