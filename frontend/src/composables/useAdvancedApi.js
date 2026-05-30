import { BASE_URL, useApi } from './useApi.js'

export function useAdvancedApi() {
  const { api } = useApi()

  const dicts = {
    commMethods: () => api('/api/dicts/comm-methods'),
    createCommMethod: (data) => api('/api/dicts/comm-methods', 'POST', data),
    updateCommMethod: (id, data) => api(`/api/dicts/comm-methods/${id}`, 'PUT', data),
    deleteCommMethod: (id) => api(`/api/dicts/comm-methods/${id}`, 'DELETE'),

    commProtocols: () => api('/api/dicts/comm-protocols'),
    createCommProtocol: (data) => api('/api/dicts/comm-protocols', 'POST', data),
    updateCommProtocol: (id, data) => api(`/api/dicts/comm-protocols/${id}`, 'PUT', data),
    deleteCommProtocol: (id) => api(`/api/dicts/comm-protocols/${id}`, 'DELETE'),

    powerSupplies: () => api('/api/dicts/power-supplies'),
    createPowerSupply: (data) => api('/api/dicts/power-supplies', 'POST', data),
    updatePowerSupply: (id, data) => api(`/api/dicts/power-supplies/${id}`, 'PUT', data),
    deletePowerSupply: (id) => api(`/api/dicts/power-supplies/${id}`, 'DELETE'),

    sensorMetrics: () => api('/api/dicts/sensor-metrics'),
    createSensorMetric: (data) => api('/api/dicts/sensor-metrics', 'POST', data),
    updateSensorMetric: (id, data) => api(`/api/dicts/sensor-metrics/${id}`, 'PUT', data),
    deleteSensorMetric: (id) => api(`/api/dicts/sensor-metrics/${id}`, 'DELETE'),

    manufacturers: () => api('/api/dicts/manufacturers'),
    createManufacturer: (data) => api('/api/dicts/manufacturers', 'POST', data),
    updateManufacturer: (id, data) => api(`/api/dicts/manufacturers/${id}`, 'PUT', data),
    deleteManufacturer: (id) => api(`/api/dicts/manufacturers/${id}`, 'DELETE'),

    productTypes: () => api('/api/dicts/product-types'),

    suppliers: (search) => api(`/api/dicts/suppliers${search ? '?search=' + encodeURIComponent(search) : ''}`),
    createSupplier: (data) => api('/api/dicts/suppliers', 'POST', data),
    updateSupplier: (id, data) => api(`/api/dicts/suppliers/${id}`, 'PUT', data),
    deleteSupplier: (id) => api(`/api/dicts/suppliers/${id}`, 'DELETE'),
  }

  const categories = {
    tree: () => api('/api/categories/tree'),
    list: () => api('/api/categories'),
    create: (data) => api('/api/categories', 'POST', data),
    update: (id, data) => api(`/api/categories/${id}`, 'PUT', data),
    delete: (id) => api(`/api/categories/${id}`, 'DELETE'),
    specDefs: (catId) => api(`/api/categories/${catId}/spec-definitions`),
    createSpecDef: (catId, data) => api(`/api/categories/${catId}/spec-definitions`, 'POST', data),
    updateSpecDef: (id, data) => api(`/api/dicts/spec-definitions/${id}`, 'PUT', data),
    deleteSpecDef: (id) => api(`/api/dicts/spec-definitions/${id}`, 'DELETE'),
  }

  const productAdvanced = {
    compare: (ids) => api(`/api/products/compare?ids=${ids.join(',')}`),
    specSheetUrl: (id) => `${BASE_URL || ''}/api/products/${id}/spec-sheet`,
    updateCommMethods: (id, data) => api(`/api/products/${id}/comm-methods`, 'POST', data),
    updateCommProtocols: (id, data) => api(`/api/products/${id}/comm-protocols`, 'POST', data),
    updatePowerSupplies: (id, data) => api(`/api/products/${id}/power-supplies`, 'POST', data),
    hardwareInterfaces: (id) => api(`/api/products/${id}/hardware-interfaces`),
    updateHardwareInterfaces: (id, data) => api(`/api/products/${id}/hardware-interfaces`, 'POST', data),
    deleteHardwareInterface: (pid, iid) => api(`/api/products/${pid}/hardware-interfaces/${iid}`, 'DELETE'),
    updateSensorCapabilities: (id, data) => api(`/api/products/${id}/sensor-capabilities`, 'POST', data),
    images: (id) => api(`/api/products/${id}/images`),
    updateImages: (id, data) => api(`/api/products/${id}/images`, 'POST', data),
    dependencies: (id) => api(`/api/products/${id}/dependencies`),
    createDependency: (id, data) => api(`/api/products/${id}/dependencies`, 'POST', data),
    updateDependency: (pid, did, data) => api(`/api/products/${pid}/dependencies/${did}`, 'PUT', data),
    deleteDependency: (pid, did) => api(`/api/products/${pid}/dependencies/${did}`, 'DELETE'),
  }

  return { dicts, categories, productAdvanced }
}
