<script setup>
import { computed } from 'vue'

const props = defineProps({
  specDefs: { type: Array, default: () => [] },
  modelValue: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['update:modelValue'])

const grouped = computed(() => {
  const groups = {}
  for (const sd of props.specDefs) {
    const g = sd.display_group || '基本参数'
    if (!groups[g]) groups[g] = []
    groups[g].push(sd)
  }
  return groups
})

function getValue(key) {
  return props.modelValue[key] ?? ''
}

function setValue(key, value) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}
</script>

<template>
  <div class="spec-field-group">
    <template v-for="(defs, group) in grouped" :key="group">
      <h6 class="mt-3 mb-2 text-secondary fw-semibold border-bottom pb-1">{{ group }}</h6>
      <div v-for="sd in defs" :key="sd.key" class="mb-3">
        <label class="form-label-modern">
          {{ sd.display_name || sd.key }}
          <small v-if="sd.unit" class="text-muted ms-1">({{ sd.unit }})</small>
        </label>

        <!-- string -->
        <input v-if="sd.spec_type === 'string'"
          class="form-control"
          :value="getValue(sd.key)"
          @input="setValue(sd.key, $event.target.value)"
          :placeholder="sd.display_name || sd.key">

        <!-- number -->
        <input v-else-if="sd.spec_type === 'number'"
          class="form-control"
          type="number"
          :value="getValue(sd.key)"
          @input="setValue(sd.key, $event.target.value)"
          :step="sd.validation?.step || 'any'"
          :min="sd.validation?.min ?? ''"
          :max="sd.validation?.max ?? ''"
          :placeholder="sd.display_name || sd.key">

        <!-- enum -->
        <select v-else-if="sd.spec_type === 'enum'"
          class="form-select"
          :value="getValue(sd.key)"
          @change="setValue(sd.key, $event.target.value)">
          <option value="">-- 请选择 --</option>
          <option v-for="opt in (sd.options || [])" :key="opt" :value="opt">{{ opt }}</option>
        </select>

        <!-- boolean -->
        <div v-else-if="sd.spec_type === 'boolean'" class="form-check">
          <input class="form-check-input"
            type="checkbox"
            :checked="!!props.modelValue[sd.key]"
            @change="setValue(sd.key, $event.target.checked ? 'true' : 'false')"
            :id="'spec-' + sd.key">
          <label class="form-check-label" :for="'spec-' + sd.key">{{ sd.display_name || sd.key }}</label>
        </div>

        <!-- range (min / max) -->
        <div v-else-if="sd.spec_type === 'range'" class="d-flex gap-2 align-items-center">
          <input class="form-control"
            type="number"
            :value="getValue(sd.key + '_min')"
            @input="setValue(sd.key + '_min', $event.target.value)"
            placeholder="最小值"
            :step="sd.validation?.step || 'any'">
          <span class="text-muted">~</span>
          <input class="form-control"
            type="number"
            :value="getValue(sd.key + '_max')"
            @input="setValue(sd.key + '_max', $event.target.value)"
            placeholder="最大值"
            :step="sd.validation?.step || 'any'">
          <small v-if="sd.unit" class="text-muted">{{ sd.unit }}</small>
        </div>
      </div>
    </template>
    <div v-if="!specDefs.length" class="text-muted small py-2">暂未定义规格参数</div>
  </div>
</template>
