<script setup>
import { ref, computed, onMounted, inject } from 'vue'
import { useApi } from '../composables/useApi'

const toast = inject('toast')
const { api } = useApi()

// ─── Registration toggle ───
const registrationOpen = ref(true)

async function toggleRegistration() {
  const r = await api('/api/admin/registration', 'PUT', {
    registration_open: registrationOpen.value
  })
  if (r.error) {
    toast(r.error, 'danger')
    registrationOpen.value = !registrationOpen.value
  } else {
    toast(registrationOpen.value ? '注册已开放' : '注册已关闭')
  }
}

// ─── Users ───
const users = ref([])
const userSearch = ref('')
const userCurrentPage = ref(1)
const userPerPage = ref(20)
const userTotal = ref(0)
const userTotalPages = computed(() => Math.max(1, Math.ceil(userTotal.value / userPerPage.value)))
const loadingUsers = ref(true)

// ─── User pagination pages ───
const userPageNumbers = computed(() => {
  const total = userTotalPages.value
  if (total <= 1) return []
  const half = 3
  let start = Math.max(1, userCurrentPage.value - half)
  let end = Math.min(total, userCurrentPage.value + half)
  if (start === 1) end = Math.min(total, start + 6)
  else if (end === total) start = Math.max(1, end - 6)
  const pages = []
  for (let p = start; p <= end; p++) pages.push(p)
  return pages
})

function userGoPage(p) {
  if (p < 1 || p > userTotalPages.value) return
  userCurrentPage.value = p
  fetchUsers()
}

// Debounced user search
let userSearchTimer = null
function onUserSearch(val) {
  clearTimeout(userSearchTimer)
  userSearchTimer = setTimeout(() => {
    userSearch.value = val
    userCurrentPage.value = 1
    fetchUsers()
  }, 400)
}

async function fetchUsers() {
  try {
    const params = new URLSearchParams({
      page: userCurrentPage.value,
      per_page: userPerPage.value,
    })
    if (userSearch.value) params.set('search', userSearch.value)
    const data = await api(`/api/admin/users?${params}`)
    if (!data.error) {
      users.value = data.users || []
      userTotal.value = data.total || 0
    }
  } catch (e) {
    toast('加载用户失败', 'danger')
  } finally {
    loadingUsers.value = false
  }
}

async function toggleUserRole(user) {
  const newRole = user.role === 'admin' ? 'user' : 'admin'
  const r = await api(`/api/admin/users/${user.id}`, 'PUT', { role: newRole })
  if (r.error) { toast(r.error, 'danger'); return }
  user.role = newRole
  toast('已更新')
}

async function resetPassword(user) {
  const pw = prompt(`为 ${user.username} 设置新密码（至少3位）：`)
  if (!pw) return
  const r = await api(`/api/admin/users/${user.id}/password`, 'PUT', { password: pw })
  if (r.error) { toast(r.error, 'danger'); return }
  toast('密码已重置')
}

async function deleteUser(user) {
  if (!confirm(`确定删除用户「${user.username}」吗？此操作不可撤销。`)) return
  const r = await api(`/api/admin/users/${user.id}`, 'DELETE')
  if (r.error) { toast(r.error, 'danger'); return }
  toast(r.message || '已删除')
  users.value = users.value.filter(u => u.id !== user.id)
}

// ─── Field visibility ───
const fieldNames = {
  show_cost_price: 'cost_price',
  show_supplier: 'supplier',
  show_function_desc: 'function_desc',
  show_remark: 'remark',
}
const fieldLabels = {
  show_cost_price: '显示成本价', show_supplier: '显示厂商',
  show_function_desc: '显示功能描述', show_remark: '显示备注',
}
const fields = ref({})
const loadingFields = ref(true)

async function fetchFields() {
  try {
    const data = await api('/api/admin/fields')
    if (!data.error) {
      const obj = {}
      for (const f of (data.fields || [])) {
        for (const [frontKey, backendKey] of Object.entries(fieldNames)) {
          if (backendKey === f.field_name) {
            obj[frontKey] = f.user_visible
            break
          }
        }
      }
      fields.value = obj
    }
  } finally {
    loadingFields.value = false
  }
}

async function toggleField(frontKey) {
  fields.value[frontKey] = !fields.value[frontKey]
  const payload = {}
  for (const [fk, bk] of Object.entries(fieldNames)) {
    payload[bk] = fields.value[fk]
  }
  const r = await api('/api/admin/fields', 'PUT', { fields: payload })
  if (r.error) {
    toast(r.error, 'danger')
    fields.value[frontKey] = !fields.value[frontKey]
  } else {
    toast('已更新')
  }
}

// ─── Settings ───
const settings = ref({})
async function fetchSettings() {
  try {
    const data = await api('/api/admin/settings')
    if (!data.error) {
      settings.value = data.settings || {}
      registrationOpen.value = data.settings?.registration_open === 'true'
    }
  } catch (e) { /* ignore */ }
}

// ─── AI Prompt ───
const aiPrompt = ref('')
const aiPromptDefault = ref('')
const aiPromptCustom = ref(false)
const aiPromptLoading = ref(true)
const aiPromptSaving = ref(false)

async function fetchAiPrompt() {
  aiPromptLoading.value = true
  try {
    const data = await api('/api/admin/prompt')
    aiPrompt.value = data.prompt || ''
    aiPromptDefault.value = data.default || ''
    aiPromptCustom.value = data.is_custom
  } catch (e) {
    toast('加载 Prompt 失败', 'danger')
  } finally {
    aiPromptLoading.value = false
  }
}

async function saveAiPrompt() {
  aiPromptSaving.value = true
  try {
    const r = await api('/api/admin/prompt', 'PUT', { prompt: aiPrompt.value })
    if (r.error) { toast(r.error, 'danger'); return }
    aiPromptCustom.value = true
    toast('Prompt 已保存')
  } catch (e) {
    toast('保存失败', 'danger')
  } finally {
    aiPromptSaving.value = false
  }
}

async function resetAiPrompt() {
  if (!confirm('确定恢复为默认 Prompt？当前定制内容将丢失。')) return
  aiPrompt.value = aiPromptDefault.value
  aiPromptCustom.value = false
  await saveAiPrompt()
}

onMounted(() => {
  fetchUsers()
  fetchFields()
  fetchSettings()
  fetchAiPrompt()
})
</script>

<template>
  <div>
    <div class="page-header">
      <h5><i class="bi bi-gear"></i>系统管理</h5>
    </div>

    <!-- AI Prompt -->
    <div class="card-modern mb-3">
      <div class="card-title-modern d-flex align-items-center justify-content-between">
        <div><i class="bi bi-robot text-primary"></i>AI 系统提示词</div>
        <div class="d-flex gap-1">
          <button class="btn btn-primary btn-sm" @click="saveAiPrompt" :disabled="aiPromptSaving">
            <i v-if="aiPromptSaving" class="bi bi-hourglass-split me-1"></i>
            <i v-else class="bi bi-check-lg me-1"></i>
            {{ aiPromptSaving ? '保存中...' : '保存' }}
          </button>
          <button v-if="aiPromptCustom" class="btn btn-sm btn-outline-secondary" @click="resetAiPrompt" :disabled="aiPromptSaving">
            <i class="bi bi-arrow-counterclockwise"></i> 恢复默认
          </button>
        </div>
      </div>
      <div v-if="aiPromptLoading" class="text-center py-3">
        <div class="spinner-border spinner-border-sm text-primary"></div>
      </div>
      <div v-else>
        <div class="mb-2 d-flex align-items-center gap-2">
          <span class="small text-muted">状态：</span>
          <span v-if="aiPromptCustom" class="badge bg-primary">自定义</span>
          <span v-else class="badge bg-light text-dark">使用默认</span>
        </div>
        <textarea v-model="aiPrompt" class="form-control"
          style="font-family:monospace;font-size:.78rem;min-height:200px;line-height:1.4"
          placeholder="输入 AI 系统提示词..."></textarea>
        <div class="mt-2 d-flex justify-content-between align-items-center">
          <small class="text-muted">{{ aiPrompt.length }} 字符</small>
          <button class="btn btn-primary btn-sm" @click="saveAiPrompt" :disabled="aiPromptSaving">
            <i v-if="aiPromptSaving" class="bi bi-hourglass-split me-1"></i>
            <i v-else class="bi bi-check-lg me-1"></i>
            {{ aiPromptSaving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Registration -->
    <div class="card-modern mb-3">
      <div class="card-title-modern"><i class="bi bi-people text-primary"></i>注册控制</div>
      <div class="d-flex align-items-center gap-3 py-1">
        <label class="switch">
          <input type="checkbox" v-model="registrationOpen" @change="toggleRegistration">
          <span class="slider"></span>
        </label>
        <span class="fw-medium">{{ registrationOpen ? '允许新用户注册' : '已关闭注册' }}</span>
        <small class="text-muted ms-auto">{{ registrationOpen ? '任何人可注册账号' : '仅管理员可创建用户' }}</small>
      </div>
    </div>

    <!-- Users -->
    <div class="card-modern mb-3">
      <div class="card-title-modern"><i class="bi bi-person-lines-fill text-primary"></i>用户管理</div>
      <div v-if="loadingUsers" class="text-center py-3">
        <div class="spinner-border spinner-border-sm text-primary"></div>
      </div>
      <div v-else class="table-responsive">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <div class="d-flex align-items-center gap-2">
            <input :value="userSearch" @input="onUserSearch($event.target.value)" class="form-control form-control-sm" placeholder="搜索用户名或邮箱..." style="max-width:260px">
            <span v-if="!loadingUsers" class="text-muted flex-shrink-0" style="font-size:.82rem;white-space:nowrap">共 {{ userTotal }} 个用户</span>
          </div>
          <select class="per-page-select" v-model.number="userPerPage" @change="userCurrentPage = 1; fetchUsers()">
            <option :value="10">10条/页</option>
            <option :value="20">20条/页</option>
            <option :value="50">50条/页</option>
            <option :value="100">100条/页</option>
          </select>
        </div>
        <table class="table table-modern">
          <thead>
            <tr>
              <th>用户名</th>
              <th>邮箱</th>
              <th>角色</th>
              <th>创建时间</th>
              <th>上次登录</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.id">
              <td class="fw-medium">{{ u.username }}</td>
              <td class="text-muted small">{{ u.email || '—' }}</td>
              <td>
                <span class="badge" :class="u.role === 'admin' ? 'bg-primary' : 'bg-light text-dark'">
                  {{ u.role === 'admin' ? '管理员' : '用户' }}
                </span>
              </td>
              <td class="text-muted small">{{ u.created_at || '—' }}</td>
              <td class="text-muted small">{{ u.last_login || '从未登录' }}</td>
              <td>
                <div class="d-flex gap-1">
                  <button class="btn btn-sm btn-outline-warning btn-sm-icon" @click="toggleUserRole(u)"
                    :title="u.role === 'admin' ? '降为普通用户' : '升为管理员'">
                    <i :class="u.role === 'admin' ? 'bi bi-arrow-down' : 'bi bi-arrow-up'"></i>
                  </button>
                  <button class="btn btn-sm btn-outline-secondary btn-sm-icon" @click="resetPassword(u)" title="重置密码">
                    <i class="bi bi-key"></i>
                  </button>
                  <button v-if="u.role !== 'admin'" class="btn btn-sm btn-outline-danger btn-sm-icon" @click="deleteUser(u)" title="删除用户">
                    <i class="bi bi-trash"></i>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        <!-- User pagination -->
        <nav v-if="userTotalPages > 1" class="mt-3">
          <ul class="pagination pagination-modern justify-content-center mb-0">
            <li class="page-item" :class="{ disabled: userCurrentPage <= 1 }">
              <a class="page-link" @click="userGoPage(1)" title="首页"><i class="bi bi-chevron-double-left"></i></a>
            </li>
            <li class="page-item" :class="{ disabled: userCurrentPage <= 1 }">
              <a class="page-link" @click="userGoPage(userCurrentPage - 1)">上一页</a>
            </li>
            <li v-for="p in userPageNumbers" :key="p" class="page-item" :class="{ active: p === userCurrentPage }">
              <a class="page-link" @click="userGoPage(p)">{{ p }}</a>
            </li>
            <li class="page-item" :class="{ disabled: userCurrentPage >= userTotalPages }">
              <a class="page-link" @click="userGoPage(userCurrentPage + 1)">下一页</a>
            </li>
            <li class="page-item" :class="{ disabled: userCurrentPage >= userTotalPages }">
              <a class="page-link" @click="userGoPage(userTotalPages)" title="末页"><i class="bi bi-chevron-double-right"></i></a>
            </li>
          </ul>
        </nav>
      </div>
    </div>

    <!-- Field Visibility -->
    <div class="card-modern">
      <div class="card-title-modern"><i class="bi bi-eye text-primary"></i>字段可见性（普通用户视图）</div>
      <div v-if="loadingFields" class="text-center py-3">
        <div class="spinner-border spinner-border-sm text-primary"></div>
      </div>
      <div v-else class="d-flex flex-wrap gap-3">
        <div v-for="(label, key) in fieldLabels" :key="key" class="d-flex align-items-center gap-2">
          <label class="switch">
            <input type="checkbox" :checked="fields[key]" @change="toggleField(key)">
            <span class="slider"></span>
          </label>
          <span class="small">{{ label }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
