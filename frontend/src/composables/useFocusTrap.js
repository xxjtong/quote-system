import { onMounted, onUnmounted } from 'vue'

// 可聚焦元素选择器
const FOCUSABLE = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'

export function useFocusTrap(modalRef, onClose) {
  let previousActiveEl = null

  function trapFocus(e) {
    if (!modalRef.value) return
    const focusable = modalRef.value.querySelectorAll(FOCUSABLE)
    if (focusable.length === 0) return
    const first = focusable[0]
    const last = focusable[focusable.length - 1]

    if (e.key === 'Escape') { onClose(); return }
    if (e.key !== 'Tab') return

    if (e.shiftKey) {
      if (document.activeElement === first) { e.preventDefault(); last.focus() }
    } else {
      if (document.activeElement === last) { e.preventDefault(); first.focus() }
    }
  }

  function activate() {
    previousActiveEl = document.activeElement
    setTimeout(() => {
      if (!modalRef.value) return
      const focusable = modalRef.value.querySelectorAll(FOCUSABLE)
      if (focusable.length > 0) focusable[0].focus()
    }, 50)
    document.addEventListener('keydown', trapFocus)
  }

  function deactivate() {
    document.removeEventListener('keydown', trapFocus)
    if (previousActiveEl) previousActiveEl.focus()
  }

  return { activate, deactivate }
}
