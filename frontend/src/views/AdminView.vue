<script setup>
import { ref, onMounted, inject } from 'vue'
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
const loadingUsers = ref(true)

async function fetchUsers() {
  try {
    const data = await api('/api/admin/users')
    if (!data.error) users.value = data.users || []
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

// ─── Field visibility ───
// fieldNames: { 前端key: 后端field_name }
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
      // data.fields 是数组 [{field_name, user_visible}, ...]
      // 转为 {前端key: boolean} 格式
      const obj = {}
      for (const f of (data.fields || [])) {
        // 反向查找前端 key
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
  // 构建后端期望的格式：{ fields: { backend_name: bool } }
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

onMounted(() => {
  fetchUsers()
  fetchFields()
  fetchSettings()
})
</script>

<template>
  <div>
    <div class="page-header">
      <h5><i class="bi bi-gear"></i>系统管理</h5>
    </div>

    <!-- Registration -->
    <div class="card-modern mb-3">
      <div class="card-title-modern"><i class="bi bi-people text-primary"></i>注册控制</div>
      <div class="d-flex align-items-center gap-3">
        <label class="switch">
          <input type="checkbox" v-model="registrationOpen" @change="toggleRegistration">
          <span class="slider"></span>
        </label>
        <span>{{ registrationOpen ? '允许新用户注册' : '已关闭注册' }}</span>
      </div>
    </div>

    <!-- Users -->
    <div class="card-modern mb-3">
      <div class="card-title-modern"><i class="bi bi-person-lines-fill text-primary"></i>用户管理</div>
      <div v-if="loadingUsers" class="text-center py-3">
        <div class="spinner-border spinner-border-sm text-primary"></div>
      </div>
      <div v-else class="table-responsive">
        <table class="table table-modern">
          <thead>
            <tr>
              <th>用户名</th>
              <th>邮箱</th>
              <th>角色</th>
              <th>创建时间</th>
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
              <td>
                <div class="d-flex gap-1">
                  <button class="btn btn-sm btn-outline-warning btn-sm-icon" @click="toggleUserRole(u)"
                    :title="u.role === 'admin' ? '降为普通用户' : '升为管理员'">
                    <i :class="u.role === 'admin' ? 'bi bi-arrow-down' : 'bi bi-arrow-up'"></i>
                  </button>
                  <button class="btn btn-sm btn-outline-secondary btn-sm-icon" @click="resetPassword(u)" title="重置密码">
                    <i class="bi bi-key"></i>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
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
