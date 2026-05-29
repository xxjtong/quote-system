<template>
  <span class="badge me-1" :class="tagClass">{{ label }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ label: String })

const colorMap = {
  'LoRaWAN': 'bg-primary', 'WiFi': 'bg-success', '4G': 'bg-info', '5G': 'bg-info',
  'Ethernet': 'bg-secondary', 'RS485': 'bg-warning text-dark', 'Battery': 'bg-warning text-dark',
  'PoE': 'bg-danger', 'MQTT': 'bg-dark', 'MQTTS': 'bg-dark',
  'ModbusRTU': 'bg-warning text-dark', 'ModbusTCP': 'bg-warning text-dark', 'NFC': 'bg-info',
}

const tagClass = computed(() => colorMap[props.label] || 'bg-light text-dark')
</script>
