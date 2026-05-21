import { ref, computed } from 'vue'

/**
 * 通用分页 composable — ProductsView / QuotesView 共用
 * 用法:
 *   const { currentPage, perPage, totalItems, totalPages, pageNumbers, goPage, setFetchFn } = usePagination()
 *   // 定义fetch后:
 *   setFetchFn(fetchProducts)
 */
export function usePagination({ perPageDefault = 20 } = {}) {
  const currentPage = ref(1)
  const perPage = ref(perPageDefault)
  const totalItems = ref(0)
  let _fetchFn = null

  const totalPages = computed(() => Math.max(1, Math.ceil(totalItems.value / perPage.value)))

  const pageNumbers = computed(() => {
    const total = totalPages.value
    if (total <= 1) return []
    let start = Math.max(1, Math.min(currentPage.value - 3, total - 6))
    let end = Math.min(total, start + 6)
    if (end - start < 6) start = Math.max(1, end - 6)
    const pages = []
    for (let p = start; p <= end; p++) pages.push(p)
    return pages
  })

  function setFetchFn(fn) { _fetchFn = fn }

  function goPage(p) {
    if (p < 1 || p > totalPages.value) return
    currentPage.value = p
    _fetchFn?.()
  }

  function resetPage() {
    currentPage.value = 1
    _fetchFn?.()
  }

  return { currentPage, perPage, totalItems, totalPages, pageNumbers, goPage, resetPage, setFetchFn }
}
