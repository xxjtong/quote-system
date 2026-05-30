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
  '温度': 'bg-danger', '湿度': 'bg-info', 'CO2': 'bg-dark', 'TVOC': 'bg-secondary',
  'PM2.5': 'bg-warning text-dark', 'PM10': 'bg-warning text-dark', '气压': 'bg-primary',
  '光照': 'bg-warning text-dark', '噪声': 'bg-dark', '水浸': 'bg-info',
  '门磁': 'bg-secondary', '倾斜': 'bg-warning text-dark', '液位': 'bg-info',
  '压力': 'bg-dark', '距离': 'bg-success', '人数': 'bg-primary',
  '人体存在': 'bg-danger', 'CO': 'bg-dark', 'O3': 'bg-info',
  'HCHO': 'bg-warning text-dark', '电流': 'bg-warning text-dark',
}

const tagClass = computed(() => colorMap[props.label] || 'bg-light text-dark')
</script>
