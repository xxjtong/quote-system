// ─── State ──────────────────────────────────────────────
const BASE_URL = location.pathname.replace(/\/[^\/]*$/, '') || '';
let currentTab = 'dashboard';
let products = [], categories = [], suppliers = [];
let currentPage = 1, totalProducts = 0, perPage = 20;
let searchTerm = '', categoryFilter = '', supplierFilter = '';
let selectedIds = new Set();
let quoteItems = [];
let editingQuoteId = null;
let productIndex = {};
// ─── Cache (instant tab switch) ──────────────────────────
let dashboardCache = null;  // { prodCount, quotes, totalAmount, downloadTotal, catCount }
let productsCache = null;   // { products, categories, suppliers, total, page, perPage, search, category, supplier }
function clearCaches() { dashboardCache = null; productsCache = null; }

// ─── Tools ──────────────────────────────────────────────
function toast(msg, type='success') {
  const t = document.getElementById('liveToast');
  const icon = document.querySelector('#liveToast .toast-header i');
  icon.className = type==='success' ? 'bi bi-check-circle-fill text-success me-2' :
                   type==='warning' ? 'bi bi-exclamation-triangle-fill text-warning me-2' :
                   'bi bi-x-circle-fill text-danger me-2';
  document.getElementById('toastBody').textContent = msg;
  bootstrap.Toast.getOrCreateInstance(t).show();
}

function $(id) { return document.getElementById(id); }

// ─── Auth State ─────────────────────────────────────────
let authToken = localStorage.getItem('quote_token') || '';
let currentUser = null;
let fieldVisibility = {};
let registrationOpen = true;

function setToken(token) { authToken = token; if (token) localStorage.setItem('quote_token', token); else localStorage.removeItem('quote_token'); }
function isLoggedIn() { return !!authToken; }
function isAdmin() { return currentUser && currentUser.role === 'admin'; }

async function api(url, method='GET', body=null) {
  const isFormData = body instanceof FormData;
  const headers = isFormData ? {'Accept':'application/json'} : {'Content-Type':'application/json','Accept':'application/json'};
  if (authToken) headers['Authorization'] = 'Bearer ' + authToken;
  const opts = { method, headers };
  if (body) opts.body = isFormData ? body : JSON.stringify(body);
  const r = await fetch(BASE_URL + url, opts);
  if (r.status === 401) { setToken(''); currentUser = null; fieldVisibility = {}; showLoginPage(); return {error: '请先登录'}; }
  return r.json();
}

function formatMoney(v) { return '¥' + Number(v || 0).toLocaleString('zh-CN', {minimumFractionDigits:2, maximumFractionDigits:2}); }
function escHtml(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }
function escJs(s) { return escHtml(s).replace(/\\/g,'\\\\').replace(/'/g,"\\'").replace(/\n/g,' ').replace(/\r/g,''); }

// ─── Sidebar ────────────────────────────────────────────
function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('sidebarOverlay').classList.toggle('show');
}
function closeSidebar() {
  if (window.innerWidth < 992) {
    document.getElementById('sidebar').classList.remove('open');
    document.getElementById('sidebarOverlay').classList.remove('show');
  }
}

function toggleCollapse() {
  const sb = document.getElementById('sidebar');
  const mw = document.getElementById('mainWrapper');
  const btn = sb.querySelector('.sidebar-collapse-btn i');
  sb.classList.toggle('collapsed');
  mw.classList.toggle('expanded');
  btn.className = sb.classList.contains('collapsed') ? 'bi bi-chevron-right' : 'bi bi-chevron-left';
}

// ─── Navigation ─────────────────────────────────────────
function switchTab(tab) {
  currentTab = tab;
  document.querySelectorAll('.sidebar-nav .nav-link').forEach(a => {
    a.classList.remove('active');
    if (a.getAttribute('onclick')?.includes(`'${tab}'`)) a.classList.add('active');
  });
  const titles = {dashboard:'概览', products:'产品管理', quotes:'报价单', newquote:'新建报价单', import:'导入产品', admin:'管理'};
  $('topbarTitle').textContent = titles[tab] || tab;
  closeSidebar();
  renderPage();
}

function renderPage() {
  if (!isLoggedIn()) { showLoginPage(); return; }
  const el = $('mainContent');
  if (currentTab === 'dashboard') renderDashboard(el);
  else if (currentTab === 'products') renderProducts(el);
  else if (currentTab === 'quotes') renderQuotes(el);
  else if (currentTab === 'newquote') renderNewQuote(el);
  else if (currentTab === 'import') renderImport(el);
  else if (currentTab === 'admin') renderAdmin(el);
  else el.innerHTML = '<div class="card-modern"><h5>页面建设中</h5></div>';
}

// ─── Dashboard ──────────────────────────────────────────
async function prefetchDashboard() {
  try {
    const [p, q] = await Promise.all([
      api('/api/products?per_page=1'),
      api('/api/quotes')
    ]);
    const quotes = q.quotes || [];
    dashboardCache = {
      prodCount: p.total || 0,
      quotes: quotes,
      totalAmount: quotes.reduce((s, qq) => s + (qq.total_amount || 0), 0),
      downloadTotal: quotes.reduce((s, qq) => s + (qq.download_count || 0), 0),
      catCount: p.categories?.length || 0,
    };
  } catch(e) { dashboardCache = null; }
}

function renderDashboardHTML(data) {
  const { prodCount, quotes, totalAmount, downloadTotal, catCount } = data;
  return `
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h5 class="fw-bold mb-0">系统概览</h5>
    </div>
    <div class="row g-3 mb-4 anim-in">
      <div class="col-6 col-md-3">
        <div class="stat-card">
          <div class="d-flex align-items-center gap-3">
            <div class="stat-icon" style="background:${catCount > 0 ? 'var(--primary-light)' : '#f1f5f9'};color:var(--primary)">
              <i class="bi bi-box-seam"></i>
            </div>
            <div>
              <div class="text-muted" style="font-size:.72rem">产品总数</div>
              <div class="fw-bold fs-4">${prodCount}</div>
            </div>
          </div>
          <div class="mt-2 small text-muted">${catCount} 个分类</div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="stat-card">
          <div class="d-flex align-items-center gap-3">
            <div class="stat-icon" style="background:#d1fae5;color:var(--success)">
              <i class="bi bi-file-earmark-text"></i>
            </div>
            <div>
              <div class="text-muted" style="font-size:.72rem">报价单</div>
              <div class="fw-bold fs-4">${quotes.length}</div>
            </div>
          </div>
          <div class="mt-2 small text-muted">共 ${formatMoney(totalAmount)}</div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="stat-card">
          <div class="d-flex align-items-center gap-3">
            <div class="stat-icon" style="background:#fef3c7;color:var(--warning)">
              <i class="bi bi-download"></i>
            </div>
            <div>
              <div class="text-muted" style="font-size:.72rem">下载</div>
              <div class="fw-bold fs-4">${downloadTotal}</div>
            </div>
          </div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="stat-card">
          <div class="d-flex align-items-center gap-3">
            <div class="stat-icon" style="background:#fee2e2;color:var(--danger)">
              <i class="bi bi-currency-yen"></i>
            </div>
            <div>
              <div class="text-muted" style="font-size:.72rem">总金额</div>
              <div class="fw-bold fs-4" style="color:var(--danger)">${formatMoney(totalAmount)}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div class="row g-3">
      <div class="col-md-6">
        <div class="card-modern anim-in">
          <div class="card-title-modern"><i class="bi bi-clock-history text-primary"></i>最近报价</div>
          ${quotes.length ? quotes.slice(0, 10).map(qq => `
            <div class="d-flex justify-content-between align-items-center py-2" style="border-bottom:1px solid var(--gray-100);cursor:pointer" onclick="viewQuote(${qq.id})" title="点击查看预览">
              <span><i class="bi bi-file-text me-2 text-muted"></i>${escHtml(qq.title || '未命名')}</span>
              <span class="text-muted small fw-medium">${formatMoney(qq.total_amount)}</span>
            </div>
          `).join('') : '<div class="text-muted text-center py-3 small">暂无报价单</div>'}
        </div>
      </div>
      <div class="col-md-6">
        <div class="card-modern anim-in">
          <div class="card-title-modern"><i class="bi bi-lightning text-primary"></i>快速操作</div>
          <div class="d-grid gap-2">
            <button class="btn btn-outline-primary text-start btn-modern" onclick="switchTab('import')"><i class="bi bi-upload me-2"></i>从Excel导入产品（支持多Sheet）</button>
            <button class="btn btn-outline-primary text-start btn-modern" onclick="switchTab('newquote')"><i class="bi bi-plus-circle me-2"></i>新建报价单</button>
            <button class="btn btn-outline-primary text-start btn-modern" onclick="switchTab('products')"><i class="bi bi-box-seam me-2"></i>管理产品库</button>
          </div>
        </div>
      </div>
    </div>
  `;
}

async function renderDashboard(el) {
  if (dashboardCache) {
    // Instant render from cache
    el.innerHTML = renderDashboardHTML(dashboardCache);
    // Silent background refresh — only re-render if data changed
    const snap = JSON.stringify(dashboardCache);
    prefetchDashboard().then(() => {
      if (currentTab === 'dashboard' && JSON.stringify(dashboardCache) !== snap) {
        el.innerHTML = renderDashboardHTML(dashboardCache);
      }
    });
  } else {
    el.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary mb-2" role="status"></div><p class="text-muted small">加载概览...</p></div>';
    await prefetchDashboard();
    if (dashboardCache) el.innerHTML = renderDashboardHTML(dashboardCache);
  }
}

// ─── Modal Helper ──────────────────────────────────────
let modalFormCallback = null;

function showFormModal(title, body, btnText, callback, closeText, wide) {
  $('formModalTitle').textContent = title;
  $('formModalBody').innerHTML = body;
  const dialog = document.querySelector('#formModal .modal-dialog');
  if (dialog) dialog.style.maxWidth = wide ? '85vw' : '';
  const footer = $('formModalFooter');
  modalFormCallback = callback;
  if (btnText && callback) {
    footer.innerHTML = `<button class="btn btn-primary btn-modern" onclick="modalFormCallback()">${btnText}</button><button class="btn btn-secondary btn-modern" data-bs-dismiss="modal">${closeText || '取消'}</button>`;
  } else {
    footer.innerHTML = `<button class="btn btn-secondary btn-modern" data-bs-dismiss="modal">${closeText || '关闭'}</button>`;
  }
  bootstrap.Modal.getOrCreateInstance($('formModal')).show();
}

function hideModal() { bootstrap.Modal.getInstance($('formModal'))?.hide(); }

function viewImage(src, name) {
  showFormModal(name || '产品图片', `
    <div class="text-center">
      <img src="${src}" style="max-width:100%;max-height:75vh;object-fit:contain;border-radius:8px">
    </div>
  `, '', null, '关闭');
}

// ─── Tip tooltip ───────────────────────────────────────
document.addEventListener('mouseover', e => {
  const cell = e.target.closest('.tip-cell');
  if (!cell) return;
  const pop = cell.querySelector('.tip-pop');
  if (!pop) return;
  const onMove = (ev) => {
    const gap = 50;
    let left = ev.clientX + gap;
    let top = ev.clientY - 10;
    const rect = pop.getBoundingClientRect();
    if (left + pop.offsetWidth > window.innerWidth - gap) {
      left = ev.clientX - pop.offsetWidth - gap;
    }
    if (top + pop.offsetHeight > window.innerHeight - gap) {
      top = window.innerHeight - pop.offsetHeight - gap;
    }
    if (top < gap) top = gap;
    pop.style.left = left + 'px';
    pop.style.top = top + 'px';
    pop.classList.add('show');
  };
  cell._tipMove = onMove;
  document.addEventListener('mousemove', onMove);
});
document.addEventListener('mouseout', e => {
  const cell = e.target.closest('.tip-cell');
  if (!cell) return;
  const pop = cell.querySelector('.tip-pop');
  if (pop) pop.classList.remove('show');
  if (cell._tipMove) {
    document.removeEventListener('mousemove', cell._tipMove);
    cell._tipMove = null;
  }
});

// ─── Auto-trim inputs on blur ──────────────────────────
document.addEventListener('blur', e => {
  const el = e.target;
  if ((el.tagName === 'INPUT' && (el.type === 'text' || el.type === 'search' || el.type === 'url' || !el.type)) || el.tagName === 'TEXTAREA') {
    el.value = el.value.trim();
  }
}, true);

// ─── IME Composition Detection ─────────────────────────
// Prevent search from firing during IME composition (拼音输入)
window._isComposing = false;
document.addEventListener('compositionstart', () => { window._isComposing = true; });
document.addEventListener('compositionend', () => {
  window._isComposing = false;
  // 组字完成后手动触发对应搜索框的搜索
  const el = document.activeElement;
  if (!el || el.tagName !== 'INPUT') return;
  if (el.id === 'prodSearchBox') { searchDelay(el.value); }
  else if (el.id === 'prodSearch') { searchProductsForQuote(el.value); }
  else if (el.id === 'pickerSearch') { filterProductPicker(); }
});
