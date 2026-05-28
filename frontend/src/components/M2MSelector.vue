<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  dictItems: { type: Array, default: () => [] },
  selectedItems: { type: Array, default: () => [] },
  extraFields: { type: Array, default: () => [] },
  label: { type: String, default: '' },
})

const emit = defineEmits(['update:selectedItems'])

const searchQuery = ref('')
const dropdownOpen = ref(false)
const containerRef = ref(null)

const filteredDict = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return props.dictItems
  return props.dictItems.filter(d => d.name.toLowerCase().includes(q))
})

const selectedIds = computed(() => new Set(props.selectedItems.map(s => s.dict_id ?? s.id)))

function isSelected(dictItem) {
  return selectedIds.value.has(dictItem.id)
}

function toggleItem(dictItem) {
  const id = dictItem.id
  if (selectedIds.value.has(id)) {
    emit('update:selectedItems', props.selectedItems.filter(s => (s.dict_id ?? s.id) !== id))
  } else {
    const entry = { dict_id: id, dict_name: dictItem.name }
    for (const ef of props.extraFields) {
      entry[ef.key] = ef.default ?? ''
    }
    emit('update:selectedItems', [...props.selectedItems, entry])
  }
  searchQuery.value = ''
}

function updateExtra(index, key, value) {
  const updated = [...props.selectedItems]
  updated[index] = { ...updated[index], [key]: value }
  emit('update:selectedItems', updated)
}

function removeItem(index) {
  const updated = props.selectedItems.filter((_, i) => i !== index)
  emit('update:selectedItems', updated)
}

function onSearchInput() {
  if (!dropdownOpen.value) dropdownOpen.value = true
}

// Click outside handler with proper cleanup
function onClickOutside(e) {
  if (containerRef.value && !containerRef.value.contains(e.target)) {
    dropdownOpen.value = false
  }
}
onMounted(() => document.addEventListener('click', onClickOutside))
onUnmounted(() => document.removeEventListener('click', onClickOutside))
</script>

<template>
  <div class="m2m-selector mb-3" ref="containerRef">
    <label v-if="label" class="form-label-modern fw-medium mb-1">{{ label }}</label>

    <!-- Search / multi-select -->
    <div class="position-relative">
      <input class="form-control"
        :value="searchQuery"
        @input="searchQuery = $event.target.value; onSearchInput()"
        @focus="dropdownOpen = true"
        @keydown.escape="dropdownOpen = false"
        placeholder="搜索并选择..."
        autocomplete="off">
      <ul v-if="dropdownOpen && filteredDict.length" class="list-unstyled dropdown-menu show w-100 p-1"
        style="max-height:200px;overflow-y:auto;z-index:1060">
        <li v-for="item in filteredDict" :key="item.id">
          <a class="dropdown-item small py-1"
            :class="{ 'bg-light': isSelected(item) }"
            href="#"
            @click.prevent="toggleItem(item)">
            <i v-if="isSelected(item)" class="bi bi-check-square me-1 text-primary"></i>
            <i v-else class="bi bi-square me-1" style="opacity:.4"></i>
            {{ item.name }}
          </a>
        </li>
      </ul>
    </div>

    <!-- Selected items list -->
    <div v-if="selectedItems.length" class="mt-2 border rounded p-2" style="max-height:240px;overflow-y:auto">
      <div v-for="(item, idx) in selectedItems" :key="idx"
        class="d-flex align-items-center gap-1 mb-1 pb-1 border-bottom">
        <span class="badge bg-primary me-1" style="font-size:.75rem">{{ item.dict_name }}</span>

        <template v-for="ef in extraFields" :key="ef.key">
          <input v-if="ef.type === 'number'"
            class="form-control form-control-sm"
            :style="{ width: ef.width || '80px' }"
            type="number"
            :value="item[ef.key] ?? ''"
            @input="updateExtra(idx, ef.key, $event.target.value)"
            :placeholder="ef.label">
          <input v-else
            class="form-control form-control-sm"
            :style="{ width: ef.width || '100px' }"
            :value="item[ef.key] ?? ''"
            @input="updateExtra(idx, ef.key, $event.target.value)"
            :placeholder="ef.label">
        </template>

        <button class="btn btn-sm btn-outline-danger py-0 px-1 ms-auto" @click="removeItem(idx)"
          title="移除" style="font-size:.7rem;line-height:1">
          <i class="bi bi-x"></i>
        </button>
      </div>
    </div>
  </div>
</template>
