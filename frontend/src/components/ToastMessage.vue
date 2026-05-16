<script setup>
import { ref } from 'vue'

const msg = ref('')
const type = ref('success')
const show = ref(false)
let timer = null

function toast(m, t = 'success') {
  msg.value = m
  type.value = t
  show.value = true
  clearTimeout(timer)
  timer = setTimeout(() => { show.value = false }, 3000)
}

defineExpose({ toast })
</script>

<template>
  <Teleport to="body">
    <div v-if="show" class="position-fixed top-0 end-0 p-3" style="z-index:9999">
      <div
        class="toast show border-0 shadow"
        :class="{
          'bg-success text-white': type === 'success',
          'bg-warning': type === 'warning',
          'bg-danger text-white': type === 'danger',
        }"
      >
        <div class="toast-body d-flex align-items-center gap-2">
          <i
            :class="{
              'bi bi-check-circle-fill': type === 'success',
              'bi bi-exclamation-triangle-fill': type === 'warning',
              'bi bi-x-circle-fill': type === 'danger',
            }"
          ></i>
          {{ msg }}
        </div>
      </div>
    </div>
  </Teleport>
</template>
