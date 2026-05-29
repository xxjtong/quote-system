<script setup>
import { ref, onMounted, inject } from 'vue'
import { useAdvancedApi } from '../composables/useAdvancedApi'
import CategoryTree from '../components/CategoryTree.vue'

const toast = inject('toast')
const { categories } = useAdvancedApi()

// ─── State ───
const treeData = ref([])
const flatList = ref([])
const selectedCategory = ref(null)
const creatingNew = ref(false)
const loading = ref(true)

// Category form
const catForm = ref({
  name: '',
  slug: '',
  parent_id: null,
  level: 1,
  sort_order: 0,
  is_active: true,
})

// Spec definitions
const specDefs = ref([])
const loadingSpecs = ref(false)

// Spec definition modal
const showSpecModal = ref(false)
const editingSpec = ref(null)
const specForm = ref({
  spec_key: '',
  display_name: '',
  spec_type: 'string',
  unit: '',
  sort_order: 0,
  is_filterable: false,
  is_comparable: false,
  display_group: '',
  options: '',
  validation: '',
})

// ─── Tree ───
async function fetchTree() {
  loading.value = true
  try {
    const [treeResult, listResult] = await Promise.all([
      categories.tree(),
      categories.list(),
    ])
    if (!treeResult.error) treeData.value = treeResult.tree || []
    if (!listResult.error) flatList.value = listResult.items || []
  } catch (e) {
    toast('加载分类失败', 'danger')
  } finally {
    loading.value = false
  }
}

// ─── Category CRUD ───
function selectCategory(node) {
  creatingNew.value = false
  selectedCategory.value = node
  catForm.value = {
    name: node.name || '',
    slug: node.slug || '',
    parent_id: node.parent_id || null,
    level: node.level || 1,
    sort_order: node.sort_order || 0,
    is_active: node.is_active !== false,
  }
  fetchSpecDefs(node.id)
}

function openCreateCat() {
  creatingNew.value = true
  selectedCategory.value = null
  specDefs.value = []
  catForm.value = {
    name: '',
    slug: '',
    parent_id: null,
    level: 1,
    sort_order: 0,
    is_active: true,
  }
}

async function saveCategory() {
  if (!selectedCategory.value) return
  const id = selectedCategory.value.id
  try {
    const r = await categories.update(id, { ...catForm.value })
    if (r.error) { toast(r.error, 'danger'); return }
    toast('已保存')
    await fetchTree()
    // Update selectedCategory data after save
    if (r.category) {
      selectedCategory.value = r.category
      catForm.value = {
        name: r.category.name || '',
        slug: r.category.slug || '',
        parent_id: r.category.parent_id || null,
        level: r.category.level || 1,
        sort_order: r.category.sort_order || 0,
        is_active: r.category.is_active !== false,
      }
    }
  } catch (e) {
    toast('保存失败', 'danger')
  }
}

async function createCategory() {
  try {
    const r = await categories.create({ ...catForm.value })
    if (r.error) { toast(r.error, 'danger'); return }
    toast('已创建')
    await fetchTree()
    if (r.category) {
      selectedCategory.value = r.category
      creatingNew.value = false
      catForm.value = {
        name: r.category.name || '',
        slug: r.category.slug || '',
        parent_id: r.category.parent_id || null,
        level: r.category.level || 1,
        sort_order: r.category.sort_order || 0,
        is_active: r.category.is_active !== false,
      }
      fetchSpecDefs(r.category.id)
    }
  } catch (e) {
    toast('创建失败', 'danger')
  }
}

async function deleteCategory() {
  if (!selectedCategory.value) return
  if (!confirm(`确定删除分类「${selectedCategory.value.name}」及其所有子分类吗？此操作不可撤销。`)) return
  try {
    const r = await categories.delete(selectedCategory.value.id)
    if (r.error) { toast(r.error, 'danger'); return }
    toast('已删除')
    selectedCategory.value = null
    creatingNew.value = false
    specDefs.value = []
    await fetchTree()
  } catch (e) {
    toast('删除失败', 'danger')
  }
}

// ─── Spec Definitions ───
async function fetchSpecDefs(catId) {
  loadingSpecs.value = true
  try {
    const data = await categories.specDefs(catId)
    if (!data.error) specDefs.value = data.items || []
    else toast(data.error, 'danger')
  } catch (e) {
    toast('加载规格定义失败', 'danger')
  } finally {
    loadingSpecs.value = false
  }
}

function openCreateSpec() {
  editingSpec.value = null
  specForm.value = {
    spec_key: '',
    display_name: '',
    spec_type: 'string',
    unit: '',
    sort_order: 0,
    is_filterable: false,
    is_comparable: false,
    display_group: '',
    options: '',
    validation: '',
  }
  showSpecModal.value = true
}

function openEditSpec(spec) {
  editingSpec.value = spec
  specForm.value = {
    spec_key: spec.spec_key || '',
    display_name: spec.display_name || '',
    spec_type: spec.spec_type || 'string',
    unit: spec.unit || '',
    sort_order: spec.sort_order || 0,
    is_filterable: spec.is_filterable || false,
    is_comparable: spec.is_comparable || false,
    display_group: spec.display_group || '',
    options: spec.options ? JSON.stringify(spec.options, null, 2) : '',
    validation: spec.validation ? JSON.stringify(spec.validation, null, 2) : '',
  }
  showSpecModal.value = true
}

async function saveSpec() {
  const payload = { ...specForm.value }

  // Parse JSON fields
  if (payload.options && typeof payload.options === 'string') {
    try { payload.options = JSON.parse(payload.options) }
    catch (e) { toast('Options 不是合法 JSON', 'warning'); return }
  } else if (!payload.options) {
    payload.options = null
  }
  if (payload.validation && typeof payload.validation === 'string') {
    try { payload.validation = JSON.parse(payload.validation) }
    catch (e) { toast('Validation 不是合法 JSON', 'warning'); return }
  } else if (!payload.validation) {
    payload.validation = null
  }

  try {
    let r
    if (editingSpec.value) {
      r = await categories.updateSpecDef(editingSpec.value.id, payload)
    } else {
      r = await categories.createSpecDef(selectedCategory.value.id, payload)
    }
    if (r.error) { toast(r.error, 'danger'); return }
    toast(editingSpec.value ? '已更新' : '已创建')
    showSpecModal.value = false
    await fetchSpecDefs(selectedCategory.value.id)
  } catch (e) {
    toast('保存失败', 'danger')
  }
}

async function deleteSpec(spec) {
  if (!confirm(`确定删除规格定义「${spec.display_name}」吗？`)) return
  try {
    const r = await categories.deleteSpecDef(spec.id)
    if (r.error) { toast(r.error, 'danger'); return }
    toast('已删除')
    await fetchSpecDefs(selectedCategory.value.id)
  } catch (e) {
    toast('删除失败', 'danger')
  }
}

onMounted(() => {
  fetchTree()
})
</script>

<template>
  <div>
    <div class="page-header">
      <h5><i class="bi bi-diagram-3"></i>分类管理</h5>
    </div>

    <div class="row g-3">
      <!-- Left Panel: Tree -->
      <div class="col-md-4">
        <div class="card-modern">
          <div class="card-title-modern d-flex justify-content-between align-items-center">
            <span><i class="bi bi-tree"></i>分类树</span>
            <button class="btn btn-sm btn-primary btn-modern" @click="openCreateCat">
              <i class="bi bi-plus-lg"></i> 新增分类
            </button>
          </div>
          <div v-if="loading" class="text-center py-3">
            <div class="spinner-border spinner-border-sm text-primary"></div>
          </div>
          <div v-else>
            <CategoryTree
              :nodes="treeData"
              :selectedId="selectedCategory?.id"
              @select="selectCategory" />
          </div>
        </div>
      </div>

      <!-- Right Panel -->
      <div class="col-md-8">
        <!-- No selection -->
        <div v-if="!selectedCategory && !creatingNew" class="card-modern">
          <div class="text-center py-5 text-muted">
            <i class="bi bi-diagram-3" style="font-size:2rem"></i>
            <p class="mt-2">请从左侧选择一个分类，或点击「新增分类」</p>
          </div>
        </div>

        <template v-else>
          <!-- Category Details Form -->
          <div class="card-modern">
            <div class="card-title-modern d-flex justify-content-between align-items-center">
              <span><i class="bi bi-pencil-square"></i>{{ creatingNew ? '新增分类' : '分类详情' }}</span>
              <div class="d-flex gap-1">
                <button v-if="creatingNew" class="btn btn-sm btn-primary btn-modern" @click="createCategory">
                  <i class="bi bi-check-lg"></i> 创建
                </button>
                <template v-else>
                  <button class="btn btn-sm btn-outline-primary btn-modern" @click="saveCategory">
                    <i class="bi bi-check-lg"></i> 保存
                  </button>
                  <button class="btn btn-sm btn-outline-danger btn-modern" @click="deleteCategory">
                    <i class="bi bi-trash"></i> 删除
                  </button>
                </template>
              </div>
            </div>
            <div class="row g-2">
              <div class="col-md-6">
                <label class="form-label small">名称</label>
                <input v-model="catForm.name" class="form-control form-control-sm" placeholder="分类名称">
              </div>
              <div class="col-md-6">
                <label class="form-label small">Slug</label>
                <input v-model="catForm.slug" class="form-control form-control-sm" placeholder="category-slug">
              </div>
              <div class="col-md-4">
                <label class="form-label small">父级分类</label>
                <select v-model="catForm.parent_id" class="form-select form-select-sm">
                  <option :value="null">无（顶级分类）</option>
                  <option v-for="cat in flatList" :key="cat.id" :value="cat.id"
                    :disabled="cat.id === selectedCategory?.id">
                    {{ cat.name }}
                  </option>
                </select>
              </div>
              <div class="col-md-2">
                <label class="form-label small">层级</label>
                <input v-model.number="catForm.level" type="number" min="1" class="form-control form-control-sm">
              </div>
              <div class="col-md-2">
                <label class="form-label small">排序</label>
                <input v-model.number="catForm.sort_order" type="number" min="0" class="form-control form-control-sm">
              </div>
              <div class="col-md-4 d-flex align-items-end pb-2">
                <div class="form-check">
                  <input v-model="catForm.is_active" type="checkbox" class="form-check-input" id="catActive">
                  <label class="form-check-label small" for="catActive">启用</label>
                </div>
              </div>
            </div>
          </div>

          <!-- Spec Definitions (only for existing categories) -->
          <div v-if="!creatingNew" class="card-modern mt-3">
            <div class="card-title-modern d-flex justify-content-between align-items-center">
              <span><i class="bi bi-list-columns"></i>规格定义</span>
              <button class="btn btn-sm btn-primary btn-modern" @click="openCreateSpec">
                <i class="bi bi-plus-lg"></i> 新增规格
              </button>
            </div>
            <div v-if="loadingSpecs" class="text-center py-3">
              <div class="spinner-border spinner-border-sm text-primary"></div>
            </div>
            <div v-else class="table-responsive">
              <table class="table table-modern">
                <thead>
                  <tr>
                    <th>Key</th>
                    <th>显示名称</th>
                    <th>类型</th>
                    <th>单位</th>
                    <th>分组</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="specDefs.length === 0">
                    <td colspan="6">
                      <div class="empty-state"><i class="bi bi-inbox"></i><p>暂无规格定义</p></div>
                    </td>
                  </tr>
                  <tr v-for="spec in specDefs" :key="spec.id">
                    <td><code class="small">{{ spec.spec_key }}</code></td>
                    <td class="fw-medium">{{ spec.display_name }}</td>
                    <td><span class="badge bg-light text-dark">{{ spec.spec_type }}</span></td>
                    <td class="text-muted small">{{ spec.unit || '—' }}</td>
                    <td class="text-muted small">{{ spec.display_group || '—' }}</td>
                    <td>
                      <div class="d-flex gap-1">
                        <button class="btn btn-sm btn-outline-secondary btn-sm-icon" @click="openEditSpec(spec)" title="编辑">
                          <i class="bi bi-pencil"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger btn-sm-icon" @click="deleteSpec(spec)" title="删除">
                          <i class="bi bi-trash"></i>
                        </button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- Spec Definition Modal -->
    <Teleport to="body">
      <div v-if="showSpecModal" class="modal-backdrop show" @click="showSpecModal = false"></div>
      <div v-if="showSpecModal" class="modal d-block modern-modal" tabindex="-1">
        <div class="modal-dialog modal-dialog-centered modal-lg">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title fw-semibold">
                {{ editingSpec ? '编辑规格' : '新增规格' }}
              </h5>
              <button type="button" class="btn-close" @click="showSpecModal = false"></button>
            </div>
            <div class="modal-body">
              <div class="row g-2">
                <div class="col-md-4">
                  <label class="form-label small">Key</label>
                  <input v-model="specForm.spec_key" class="form-control form-control-sm" placeholder="spec_key">
                </div>
                <div class="col-md-4">
                  <label class="form-label small">显示名称</label>
                  <input v-model="specForm.display_name" class="form-control form-control-sm" placeholder="规格名称">
                </div>
                <div class="col-md-4">
                  <label class="form-label small">类型</label>
                  <select v-model="specForm.spec_type" class="form-select form-select-sm">
                    <option value="string">string</option>
                    <option value="number">number</option>
                    <option value="enum">enum</option>
                    <option value="boolean">boolean</option>
                    <option value="range">range</option>
                  </select>
                </div>
                <div class="col-md-3">
                  <label class="form-label small">单位</label>
                  <input v-model="specForm.unit" class="form-control form-control-sm" placeholder="mm">
                </div>
                <div class="col-md-3">
                  <label class="form-label small">排序</label>
                  <input v-model.number="specForm.sort_order" type="number" min="0" class="form-control form-control-sm">
                </div>
                <div class="col-md-3">
                  <label class="form-label small">显示分组</label>
                  <input v-model="specForm.display_group" class="form-control form-control-sm" placeholder="基本参数">
                </div>
                <div class="col-md-3 d-flex align-items-end pb-2 gap-2">
                  <div class="form-check">
                    <input v-model="specForm.is_filterable" type="checkbox" class="form-check-input" id="specFilterable">
                    <label class="form-check-label small" for="specFilterable">可筛选</label>
                  </div>
                  <div class="form-check">
                    <input v-model="specForm.is_comparable" type="checkbox" class="form-check-input" id="specComparable">
                    <label class="form-check-label small" for="specComparable">可比较</label>
                  </div>
                </div>
                <div class="col-12">
                  <label class="form-label small">Options (JSON) <span class="text-muted fw-normal">可选</span></label>
                  <textarea v-model="specForm.options" class="form-control form-control-sm" rows="2"
                    placeholder='["option1", "option2"]'></textarea>
                </div>
                <div class="col-12">
                  <label class="form-label small">Validation (JSON) <span class="text-muted fw-normal">可选</span></label>
                  <textarea v-model="specForm.validation" class="form-control form-control-sm" rows="2"
                    placeholder='{"min": 0, "max": 100}'></textarea>
                </div>
              </div>
            </div>
            <div class="modal-footer">
              <button class="btn btn-primary btn-modern" @click="saveSpec">保存</button>
              <button class="btn btn-secondary btn-modern" @click="showSpecModal = false">取消</button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
