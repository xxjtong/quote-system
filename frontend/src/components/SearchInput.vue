<template>
  <div class="input-group input-group-sm">
    <span class="input-group-text"><i class="bi bi-search"></i></span>
    <input type="text" class="form-control" :value="modelValue" :placeholder="placeholder || '搜索...'"
      @input="onInput" @compositionstart="composing = true" @compositionend="onCompositionEnd" />
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({ modelValue: String, placeholder: String })
const emit = defineEmits(['update:modelValue'])
const composing = ref(false)
let timer = null

function onInput(e) {
  if (composing.value) return
  debounce(e.target.value)
}

function onCompositionEnd(e) {
  composing.value = false
  debounce(e.target.value)
}

function debounce(val) {
  clearTimeout(timer)
  timer = setTimeout(() => emit('update:modelValue', val), 400)
}
</script>
