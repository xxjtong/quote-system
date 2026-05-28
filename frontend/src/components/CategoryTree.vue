<script setup>
import { ref } from 'vue'

defineOptions({ name: 'CategoryTree' })

const props = defineProps({
  nodes: { type: Array, required: true },
  selectedId: { type: Number, default: null },
  level: { type: Number, default: 0 },
})
const emit = defineEmits(['select'])

const expanded = ref(new Set())

function toggle(id) {
  const s = new Set(expanded.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  expanded.value = s
}
</script>

<template>
  <ul v-if="nodes && nodes.length" class="list-unstyled mb-0 category-tree" :style="{ paddingLeft: level > 0 ? '1.2rem' : '0' }">
    <li v-for="node in nodes" :key="node.id">
      <div class="d-flex align-items-center py-1 px-2 rounded"
        :class="node.id === selectedId ? 'bg-primary text-white' : 'tree-node-hover'"
        style="cursor:pointer;user-select:none"
        @click="emit('select', node)">
        <span v-if="node.children && node.children.length" class="tree-toggle me-1"
          @click.stop="toggle(node.id)" style="width:1rem;text-align:center;flex-shrink:0">
          <i :class="expanded.has(node.id) ? 'bi bi-chevron-down' : 'bi bi-chevron-right'" class="small"></i>
        </span>
        <span v-else style="width:1rem;flex-shrink:0;display:inline-block"></span>
        <i class="me-1 small"
          :class="node.children && node.children.length ? 'bi bi-folder' : 'bi bi-file-earmark'"></i>
        <span class="small">{{ node.name }}</span>
      </div>
      <CategoryTree v-if="node.children && node.children.length && expanded.has(node.id)"
        :nodes="node.children"
        :selectedId="selectedId"
        :level="level + 1"
        @select="(n) => emit('select', n)" />
    </li>
  </ul>
</template>

<style scoped>
.category-tree .tree-node-hover:hover {
  background-color: rgba(13, 110, 253, 0.08);
}
.tree-toggle {
  transition: transform 0.15s;
}
</style>
