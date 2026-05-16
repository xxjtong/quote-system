export function formatMoney(v) {
  return '¥' + Number(v || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

export function escHtml(s) {
  const d = document.createElement('div')
  d.textContent = s || ''
  return d.innerHTML
}

export function escAttr(s) {
  return escHtml(s).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\n/g, ' ').replace(/\r/g, '')
}
