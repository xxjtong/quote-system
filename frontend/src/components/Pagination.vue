<template>
  <div class="d-flex justify-content-between align-items-center mt-3" v-if="total > perPage">
    <small class="text-muted">共 {{ total }} 条</small>
    <div class="btn-group btn-group-sm">
      <button class="btn btn-outline-secondary" :disabled="page <= 1" @click="$emit('change', page - 1)">上一页</button>
      <span class="btn btn-outline-secondary disabled">{{ page }} / {{ Math.ceil(total / perPage) }}</span>
      <button class="btn btn-outline-secondary" :disabled="page >= Math.ceil(total / perPage)" @click="$emit('change', page + 1)">下一页</button>
    </div>
  </div>
</template>

<script setup>
defineProps({ total: Number, page: Number, perPage: Number })
defineEmits(['change'])
</script>
