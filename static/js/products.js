// ─── Products ───────────────────────────────────────────
async function prefetchProducts() {
  const key = `${currentPage}|${perPage}|${searchTerm}|${categoryFilter}|${supplierFilter}`;
  try {
    const data = await api(`/api/products?page=${currentPage}&per_page=${perPage}&search=${encodeURIComponent(searchTerm)}&category=${encodeURIComponent(categoryFilter)}&supplier=${encodeURIComponent(supplierFilter)}`);
    productsCache = {
      data, key,
      products: data.products || [],
      categories: data.categories || [],
      suppliers: data.suppliers || [],
      total: data.total || 0,
    };
  } catch(e) { productsCache = null; }
}

function productsCacheValid() {
  if (!productsCache) return false;
  const key = `${currentPage}|${perPage}|${searchTerm}|${categoryFilter}|${supplierFilter}`;
  return productsCache.key === key;
}

function renderProductsHTML(d) {
  const { products, categories, suppliers, total } = d;
  totalProducts = total;
  const totalPages = Math.ceil(totalProducts / perPage);
  productIndex = {};
  products.forEach(p => productIndex[p.id] = p);

  const rows = products.map(p => {
    const isOff = p.is_active === false;
    return `
    <tr class="${selectedIds.has(p.id) ? 'table-primary' : ''}${isOff ? ' opacity-50' : ''}">
      <td><input type="checkbox" class="form-check-input product-check" value="${p.id}" ${selectedIds.has(p.id) ? 'checked' : ''} onchange="toggleSelect(${p.id})"></td>
      <td class="tip-cell">
        <strong style="font-size:.85rem;cursor:pointer" onclick="viewProductDetail(${p.id})">${escHtml(p.name)}</strong>${isOff ? ' <span class="badge" style="background:#fee2e2;color:#dc2626;font-size:.65rem">已下线</span>' : ''}
        <div class="tip-pop">${escHtml(p.name)}${p.spec ? '\n规格: ' + p.spec : ''}${p.supplier ? '\n厂商: ' + p.supplier : ''}${p.category ? '\n分类: ' + p.category : ''}${p.price ? '\n单价: ¥' + p.price : ''}${p.function_desc ? '\n功能: ' + p.function_desc : ''}</div>
        ${p.spec ? `<br><span class="text-muted" style="font-size:.75rem">${escHtml(p.spec)}</span>` : ''}
      </td>
      <td class="tip-cell" style="text-align:center">${p.image_url
        ? `<img src="${p.image_url.startsWith('/uploads/') ? BASE_URL + p.image_url : p.image_url}" style="width:36px;height:36px;object-fit:cover;border-radius:6px;border:1px solid var(--gray-200);cursor:pointer" onclick="viewImage('${p.image_url.startsWith('/uploads/') ? BASE_URL + p.image_url : p.image_url}','${escHtml(p.name)}')">
           <div class="tip-pop" style="padding:0;background:#fff;border-radius:8px;min-width:unset;max-width:unset;width:fit-content;box-shadow:0 4px 20px rgba(0,0,0,.25)">
             <img src="${p.image_url.startsWith('/uploads/') ? BASE_URL + p.image_url : p.image_url}" style="max-width:300px;max-height:300px;object-fit:contain;display:block;border-radius:8px">
           </div>`
        : '<span class="text-muted" style="font-size:.75rem">—</span>'}
      </td>
      <td>${(p.category||'').split(',').filter(Boolean).map(c => `<span class="badge me-1" style="background:var(--primary-light);color:var(--primary);font-weight:500;font-size:.72rem">${escHtml(c.trim())}</span>`).join('') || '<span class="text-muted" style="font-size:.75rem">—</span>'}</td>
      <td class="text-muted" style="font-size:.8rem">${escHtml(p.spec || '-')}</td>
      <td class="text-muted" style="font-size:.8rem">${escHtml(p.supplier || '-')}</td>
      <td class="fw-medium" style="font-size:.85rem">${formatMoney(p.price)}</td>
      <td style="white-space:nowrap">
        <button class="btn btn-sm btn-modern btn-outline-secondary" onclick="editProduct(${p.id})" title="编辑"><i class="bi bi-pencil"></i></button>
        <button class="btn btn-sm btn-modern btn-outline-danger" onclick="deleteProduct(${p.id})" title="删除"><i class="bi bi-trash"></i></button>
        ${isAdmin() ? `<button class="btn btn-sm btn-modern ${isOff ? 'btn-outline-success' : 'btn-outline-warning'}" onclick="toggleProductActive(${p.id})" title="${isOff ? '上线' : '下线'}"><i class="bi ${isOff ? 'bi-eye' : 'bi-eye-slash'}"></i></button>` : ''}
      </td>
    </tr>
  `;
  }).join('');

  // Pagination
  function paginationHTML() {
    if (totalPages <= 1) return '';
    let pages = [];
    let start = Math.max(1, Math.min(currentPage - 3, totalPages - 6));
    let end = Math.min(totalPages, start + 6);
    if (end - start < 6) start = Math.max(1, end - 6);
    for (let p = start; p <= end; p++) {
      pages.push(`<li class="page-item ${p === currentPage ? 'active' : ''}"><a class="page-link" onclick="goPage(${p})">${p}</a></li>`);
    }
    return `
      <nav class="mt-3"><ul class="pagination pagination-modern justify-content-center mb-0" style="flex-wrap:wrap">
        <li class="page-item ${currentPage <= 1 ? 'disabled' : ''}"><a class="page-link" onclick="goPage(1)" title="首页"><i class="bi bi-chevron-double-left"></i></a></li>
        <li class="page-item ${currentPage <= 1 ? 'disabled' : ''}"><a class="page-link" onclick="goPage(${currentPage-1})">上一页</a></li>
        ${pages.join('')}
        <li class="page-item ${currentPage >= totalPages ? 'disabled' : ''}"><a class="page-link" onclick="goPage(${currentPage+1})">下一页</a></li>
        <li class="page-item ${currentPage >= totalPages ? 'disabled' : ''}"><a class="page-link" onclick="goPage(${totalPages})" title="末页"><i class="bi bi-chevron-double-right"></i></a></li>
      </ul></nav>
    `;
  }

  return `
    <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
      <h5 class="fw-bold mb-0">产品管理</h5>
      <div class="d-flex gap-2">
        <button class="btn btn-outline-primary btn-modern" onclick="exportTemplate()"><i class="bi bi-download"></i> 下载模板</button>
        <button class="btn btn-primary btn-modern" onclick="showAddProduct()"><i class="bi bi-plus-lg"></i> 新增产品</button>
      </div>
    </div>
    <div class="card-modern">
      <div class="row g-2 mb-3 align-items-center">
        <div class="col-md-5">
          <div style="position:relative">
            <i class="bi bi-search text-muted" style="position:absolute;left:12px;top:50%;transform:translateY(-50%);z-index:10"></i>
            <input class="form-control search-box ps-5 pe-5" placeholder="搜索名称/规格/型号/功能/厂家...（支持拼音/缩写）" value="${escHtml(searchTerm)}" id="prodSearchBox" oninput="searchDelay(this.value);document.getElementById('prodSearchClear').style.display=this.value?'flex':'none'" onkeydown="if(event.key==='Enter'){searchTerm=this.value.trim();currentPage=1;renderProducts($('mainContent'))}">
            <span id="prodSearchClear" onclick="searchTerm='';$('prodSearchBox').value='';currentPage=1;renderProducts($('mainContent'));this.style.display='none'" style="display:${searchTerm?'flex':'none'};position:absolute;right:8px;top:50%;transform:translateY(-50%);width:24px;height:24px;border-radius:50%;background:var(--gray-300);align-items:center;justify-content:center;cursor:pointer;z-index:10" title="清除搜索">✕</span>
          </div>
        </div>
        <div class="col-md-2">
          <select class="form-select form-select-sm" style="border-radius:8px" onchange="categoryFilter=this.value;currentPage=1;renderProducts($('mainContent'))">
            <option value="">全部分类</option>
            ${categories.map(c => `<option value="${escHtml(c)}" ${c === categoryFilter ? 'selected' : ''}>${escHtml(c)}</option>`).join('')}
          </select>
        </div>
        <div class="col-md-2">
          <select class="form-select form-select-sm" style="border-radius:8px" onchange="supplierFilter=this.value;currentPage=1;renderProducts($('mainContent'))">
            <option value="">全部厂商</option>
            ${suppliers.map(c => `<option value="${escHtml(c)}" ${c === supplierFilter ? 'selected' : ''}>${escHtml(c)}</option>`).join('')}
          </select>
        </div>
        <div class="col-md-3 d-flex justify-content-md-end align-items-center gap-2" style="flex-wrap:wrap">
          <span class="text-muted" style="font-size:.82rem">共 ${totalProducts} 个产品</span>
          <select class="per-page-select" onchange="perPage=parseInt(this.value);currentPage=1;renderProducts($('mainContent'))">
            <option value="10" ${perPage===10?'selected':''}>10条/页</option>
            <option value="20" ${perPage===20?'selected':''}>20条/页</option>
            <option value="50" ${perPage===50?'selected':''}>50条/页</option>
            <option value="100" ${perPage===100?'selected':''}>100条/页</option>
            <option value="500" ${perPage===500?'selected':''}>全部</option>
          </select>
          ${selectedIds.size > 0 ? `<button class="btn btn-sm btn-modern btn-outline-danger" onclick="batchDelete()"><i class="bi bi-trash"></i> 删除(${selectedIds.size})</button>` : ''}
        </div>
      </div>
      <div class="table-responsive">
        <table class="table table-modern">
          <thead>
            <tr>
              <th style="width:36px"><input type="checkbox" class="form-check-input" onchange="toggleAll(this.checked)"></th>
              <th>产品信息</th>
              <th>图片</th>
              <th>分类</th>
              <th>规格型号</th>
              <th>厂商</th>
              <th>销售单价</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>${products.length ? rows : '<tr><td colspan="8"><div class="empty-state"><i class="bi bi-inbox"></i><p>暂无产品</p><button class="btn btn-primary btn-modern mt-2" onclick="showAddProduct()">新增第一个产品</button></div></td></tr>'}</tbody>
        </table>
      </div>
      ${paginationHTML()}
    </div>
  `;
}

async function renderProducts(el) {
  if (productsCacheValid()) {
    // Instant render from cache
    products = productsCache.products;
    categories = productsCache.categories;
    suppliers = productsCache.suppliers;
    el.innerHTML = renderProductsHTML(productsCache);
    // Silent background refresh — only re-render if data changed
    const snapData = JSON.stringify(productsCache.products);
    const snapTotal = productsCache.total;
    prefetchProducts().then(() => {
      if (currentTab === 'products' && productsCacheValid()) {
        if (JSON.stringify(productsCache.products) !== snapData || productsCache.total !== snapTotal) {
          products = productsCache.products;
          categories = productsCache.categories;
          suppliers = productsCache.suppliers;
          el.innerHTML = renderProductsHTML(productsCache);
        }
      }
    });
  } else {
    el.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary mb-2" role="status"></div><p class="text-muted small">加载产品数据...</p></div>';
    await prefetchProducts();
    if (productsCache) {
      products = productsCache.products;
      categories = productsCache.categories;
      suppliers = productsCache.suppliers;
      el.innerHTML = renderProductsHTML(productsCache);
    }
  }
}

function toggleAll(checked) {
  products.forEach(p => { if (checked) selectedIds.add(p.id); else selectedIds.delete(p.id); });
  renderProducts($('mainContent'));
}
function toggleSelect(id) { selectedIds.has(id) ? selectedIds.delete(id) : selectedIds.add(id); renderProducts($('mainContent')); }
function searchDelay(v) { if (window._isComposing) return; clearTimeout(window._st); window._st = setTimeout(() => { searchTerm = v; currentPage = 1; renderProducts($('mainContent')); }, 500); }
function goPage(p) { currentPage = p; renderProducts($('mainContent')); }

function exportTemplate() { window.open(BASE_URL + '/api/products/export-template'); }

// ── Product Form ──
function showAddProduct() {
  window._pfImageUrl = '';
  const catOpts = categories.map(c => `<option value="${escHtml(c)}">${escHtml(c)}</option>`).join('');
  showFormModal('新增产品', formBodyHtml({name:'',category:'',spec:'',unit:'',price:'',cost_price:'',supplier:'',function_desc:'',remark:'',image_url:''}, catOpts), '新增', async () => {
    const d = readFormFields();
    if (!d.name) { toast('请输入产品名称', 'warning'); return; }
    d.image_url = window._pfImageUrl || '';
    await api('/api/products', 'POST', d);
    window._pfImageUrl = '';
    toast('产品添加成功');
    clearCaches();
    hideModal();
    renderProducts($('mainContent'));
  });
}

async function editProduct(id) {
  const p = await api(`/api/products/${id}`);
  const pd = p.product;
  window._pfImageUrl = pd.image_url || '';
  const catOpts = categories.map(c => `<option value="${escHtml(c)}" ${c === pd.category ? 'selected' : ''}>${escHtml(c)}</option>`).join('');
  showFormModal('编辑产品', formBodyHtml(pd, catOpts), '保存', async () => {
    const d = readFormFields();
    d.image_url = window._pfImageUrl || '';
    await api(`/api/products/${id}`, 'PUT', d);
    toast('产品已更新');
    clearCaches();
    hideModal();
    renderProducts($('mainContent'));
  });
}

async function viewProductDetail(id) {
  const p = await api(`/api/products/${id}`);
  const pd = p.product;
  if (!pd) { toast('产品不存在', 'warning'); return; }
  const imgSrc = pd.image_url ? (pd.image_url.startsWith('/uploads/') ? BASE_URL + pd.image_url : pd.image_url) : '';
  const cats = (pd.category || '').split(',').filter(Boolean).map(c => `<span class="badge me-1" style="background:var(--primary-light);color:var(--primary);font-weight:500;font-size:.78rem">${escHtml(c.trim())}</span>`).join('') || '<span class="text-muted">—</span>';
  showFormModal(`产品详情 — ${escHtml(pd.name)}`, `
    <style scoped>.prod-view-table th,.prod-view-table td{border:1px solid #dee2e6!important;border-left:1px solid #dee2e6!important;border-right:1px solid #dee2e6!important;padding:8px 12px;font-size:.85rem}</style>
    ${imgSrc ? `<div class="text-center mb-3"><img src="${imgSrc}" style="max-width:300px;max-height:300px;object-fit:contain;border-radius:8px;border:1px solid var(--gray-200)"></div>` : ''}
    <div class="table-responsive">
      <table class="table table-sm prod-view-table mb-0">
        <tbody>
          <tr><th style="width:100px">产品名称</th><td class="fw-medium">${escHtml(pd.name)}</td></tr>
          <tr><th>规格型号</th><td>${escHtml(pd.spec || '—')}</td></tr>
          <tr><th>分类标签</th><td>${cats}</td></tr>
          <tr><th>单位</th><td>${escHtml(pd.unit || '—')}</td></tr>
          <tr><th>销售单价</th><td class="fw-medium" style="color:var(--danger)">${formatMoney(pd.price)}</td></tr>
          <tr><th>成本价</th><td>${formatMoney(pd.cost_price)}</td></tr>
          <tr><th>厂商</th><td>${escHtml(pd.supplier || '—')}</td></tr>
          <tr><th>功能描述</th><td style="white-space:pre-wrap">${escHtml(pd.function_desc || '—')}</td></tr>
          <tr><th>创建时间</th><td class="text-muted small">${pd.created_at || '—'}</td></tr>
        </tbody>
      </table>
    </div>
  `, '编辑', () => { hideModal(); editProduct(id); }, '关闭');
}

function formBodyHtml(p, catOpts) {
  const showPreview = !!(p.image_url || window._pfImageUrl);
  const previewSrc = p.image_url ? (p.image_url.startsWith('/uploads/') ? BASE_URL + p.image_url : p.image_url) : '';
  return `
    <div class="row g-3">
      <div class="col-md-6">
        <label class="form-label small fw-medium">产品名称 <span class="text-danger">*</span></label>
        <input class="form-control" id="pf_name" value="${escHtml(p.name)}" placeholder="请输入产品名称">
      </div>
      <div class="col-md-6">
        <label class="form-label small fw-medium">规格型号</label>
        <input class="form-control" id="pf_spec" value="${escHtml(p.spec)}">
      </div>
      <div class="col-md-6">
        <label class="form-label small fw-medium">分类标签 <span class="text-muted fw-normal" style="font-size:.72rem">（多个用逗号分隔）</span></label>
        <input class="form-control" id="pf_category" value="${escHtml(p.category)}" placeholder="如：网络设备,监控,安防">
      </div>
      <div class="col-4">
        <label class="form-label small fw-medium">厂商</label>
        <div class="autocomplete-wrap">
          <input class="form-control" id="pf_supplier" value="${escHtml(p.supplier)}" placeholder="输入或选择厂商" autocomplete="off"
                 oninput="filterSuppliers(this.value)" onfocus="filterSuppliers(this.value)" onblur="setTimeout(() => hideSupplierDropdown(), 200)">
          <div class="autocomplete-dropdown" id="pf_supplier_dd"></div>
        </div>
      </div>
      <div class="col-4">
        <label class="form-label small fw-medium">单位</label>
        <input class="form-control" id="pf_unit" value="${escHtml(p.unit)}" placeholder="个/套/台">
      </div>
      <div class="col-4">
        <label class="form-label small fw-medium">销售单价</label>
        <input class="form-control" id="pf_price" type="number" step="0.01" value="${p.price || ''}" placeholder="0.00">
      </div>
      <div class="col-4">
        <label class="form-label small fw-medium">成本价</label>
        <input class="form-control" id="pf_cost" type="number" step="0.01" value="${p.cost_price || ''}">
      </div>
      <div class="col-12">
        <label class="form-label small fw-medium">功能描述</label>
        <textarea class="form-control" id="pf_function_desc" rows="3">${escHtml(p.function_desc)}</textarea>
      </div>
      <div class="col-12">
        <label class="form-label small fw-medium">备注（内部备注，不会在报价单中展示）</label>
        <textarea class="form-control" id="pf_remark" rows="2">${escHtml(p.remark)}</textarea>
      </div>
      <div class="col-12">
        <label class="form-label small fw-medium">产品图片</label>
        <div class="d-flex gap-2 align-items-start flex-wrap">
          <div style="flex:1;min-width:150px">
            <input class="form-control" id="pf_image_url" placeholder="粘贴图片URL 或 Ctrl+V..."
                   value="${escHtml(p.image_url || '')}" onpaste="handleImagePaste(event)">
          </div>
          <div>
            <label class="btn btn-outline-primary btn-modern mb-0" style="cursor:pointer">
              <i class="bi bi-folder me-1"></i>选择图片
              <input type="file" id="pf_image_file" accept="image/*" onchange="uploadImageFile(this)" style="display:none">
            </label>
          </div>
        </div>
        <div id="pf_image_preview" class="mt-2" ${showPreview ? '' : 'style="display:none"'}>
          <img src="${previewSrc}" style="max-width:120px;max-height:120px;border-radius:8px;border:1px solid var(--gray-200);cursor:pointer" onclick="viewImage(this.src)" title="点击放大">
          <button class="btn btn-sm btn-modern btn-outline-danger ms-2" onclick="clearProductImage()"><i class="bi bi-x"></i> 移除</button>
        </div>
      </div>
      <div class="col-12">
        <label class="form-label small fw-medium">
          <i class="bi bi-magic text-primary"></i> 智能识别
          <span class="text-muted fw-normal" style="font-size:.75rem">— 粘贴文字或截图后识别</span>
        </label>
        <div class="d-flex gap-2">
          <textarea class="form-control" id="pf_paste_zone" rows="2" placeholder="粘贴Excel复制内容、产品清单等，或截图后点击「识别图片」" onpaste="handleTextareaPaste(event)"></textarea>
          <div style="white-space:nowrap">
            <button class="btn btn-primary btn-modern d-block mb-1" onclick="recognizePastedText()"><i class="bi bi-magic"></i> 粘贴并识别</button>
            <button class="btn btn-outline-secondary btn-modern d-block" onclick="recognizePastedImage()"><i class="bi bi-image"></i> 识别图片</button>
          </div>
        </div>
        <div class="text-muted mt-1" style="font-size:.72rem">
          <i class="bi bi-info-circle"></i> 格式：<strong>产品名称</strong> ｜ 规格型号 ｜ 厂商 ｜ 功能描述 ｜ 售价（Tab/多个空格分隔，每次识别一个产品）
        </div>
        <div id="pf_recognize_results" class="mt-2"></div>
      </div>
    </div>
  `;
}

function readFormFields() {
  return {
    name: ($('pf_name')?.value || '').trim(),
    category: ($('pf_category')?.value || '').trim(),
    spec: ($('pf_spec')?.value || '').trim(),
    unit: ($('pf_unit')?.value || '').trim(),
    price: parseFloat($('pf_price')?.value) || 0,
    cost_price: parseFloat($('pf_cost')?.value) || 0,
    supplier: ($('pf_supplier')?.value || '').trim(),
    function_desc: ($('pf_function_desc')?.value || '').trim(),
    remark: ($('pf_remark')?.value || '').trim(),
  };
}

// ── 厂商联想 ──
function filterSuppliers(val) {
  const dd = $('pf_supplier_dd');
  if (!dd) return;
  const q = (val || '').toLowerCase();
  const matches = suppliers.filter(s => s.toLowerCase().includes(q)).slice(0, 8);
  if (!matches.length || !q) {
    dd.classList.remove('show');
    dd.innerHTML = '';
    return;
  }
  dd.innerHTML = matches.map((s, i) =>
    `<div class="ac-item" data-idx="${i}" onmousedown="selectSupplier('${escHtml(s)}')">${highlight(s, q)}</div>`
  ).join('');
  dd.classList.add('show');
  window._supplierIdx = -1;
}

function highlight(text, query) {
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx < 0) return escHtml(text);
  return escHtml(text.slice(0, idx)) + '<strong>' + escHtml(text.slice(idx, idx + query.length)) + '</strong>' + escHtml(text.slice(idx + query.length));
}

function hideSupplierDropdown() {
  const dd = $('pf_supplier_dd');
  if (dd) dd.classList.remove('show');
}

function selectSupplier(val) {
  const input = $('pf_supplier');
  if (input) input.value = val;
  hideSupplierDropdown();
}

// 键盘导航
document.addEventListener('keydown', e => {
  const input = $('pf_supplier');
  const dd = $('pf_supplier_dd');
  if (!input || document.activeElement !== input || !dd || !dd.classList.contains('show')) return;
  const items = dd.querySelectorAll('.ac-item');
  if (!items.length) return;
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    window._supplierIdx = Math.min((window._supplierIdx || -1) + 1, items.length - 1);
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    window._supplierIdx = Math.max((window._supplierIdx || 0) - 1, -1);
  } else if (e.key === 'Enter' && window._supplierIdx >= 0) {
    e.preventDefault();
    input.value = items[window._supplierIdx].textContent;
    hideSupplierDropdown();
    return;
  } else { return; }
  items.forEach((el, i) => el.classList.toggle('active', i === window._supplierIdx));
});

// ── 图片上传 ──
async function uploadImageFile(input) {
  const file = input.files[0];
  if (!file) return;
  if (file.size > 10 * 1024 * 1024) { toast('图片不能超过10MB', 'warning'); return; }
  const formData = new FormData();
  formData.append('file', file);
  try {
    const r = await api('/api/upload/image', 'POST', formData);
    const data = r;
    if (data.url) {
      window._pfImageUrl = data.url;
      showImagePreview(BASE_URL + data.url);
      $('pf_image_url').value = data.url;
      toast('图片已上传');
    } else {
      toast(data.error || '上传失败', 'warning');
    }
  } catch(e) { toast('上传失败: ' + e.message, 'warning'); }
}

function handleImagePaste(event) {
  const items = (event.clipboardData || window.clipboardData).items;
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      event.preventDefault();
      const file = item.getAsFile();
      if (file) {
        const formData = new FormData();
        formData.append('file', file, 'pasted_image.png');
        api('/api/upload/image', 'POST', formData)
          .then(data => {
            if (data.url) { window._pfImageUrl = data.url; showImagePreview(BASE_URL + data.url); $('pf_image_url').value = data.url; toast('图片已粘贴'); }
          });
      }
      break;
    }
  }
}

function showImagePreview(src) {
  const div = $('pf_image_preview');
  if (!div) return;
  div.style.display = 'block';
  const img = div.querySelector('img');
  if (img) img.src = src;
}

function handleTextareaPaste(event) {
  const items = (event.clipboardData || window.clipboardData).items;
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      event.preventDefault();
      const file = item.getAsFile();
      if (file) {
        toast('图片已粘贴，正在上传识别...');
        const formData = new FormData();
        formData.append('file', file, 'pasted_image.png');
        api('/api/products/ocr', 'POST', formData)
          .then(data => {
            if (data.text) {
              if ($('pf_paste_zone')) $('pf_paste_zone').value = data.text;
              toast('OCR识别完成，正在解析...');
              recognizePastedText();
            } else {
              toast(data.error || 'OCR未能识别文字', 'warning');
            }
          }).catch(() => toast('上传失败', 'warning'));
      }
      break;
    }
  }
}

function clearProductImage() {
  window._pfImageUrl = '';
  $('pf_image_url').value = '';
  const div = $('pf_image_preview');
  if (div) { div.style.display = 'none'; const img = div.querySelector('img'); if(img) img.src = ''; }
}

document.addEventListener('change', function(e) {
  if (e.target && e.target.id === 'pf_image_url') {
    const val = e.target.value.trim();
    if (val) { window._pfImageUrl = val; showImagePreview(val); }
  }
});

// ── 智能识别 ──
let recognizedResults = [];

async function recognizePastedText() {
  const text = $('pf_paste_zone')?.value?.trim();
  if (!text) { toast('请先粘贴要识别的内容', 'warning'); return; }
  const rd = $('pf_recognize_results');
  if (!rd) return;
  rd.innerHTML = '<div class="text-center py-2"><div class="spinner-border spinner-border-sm text-primary" role="status"></div> 识别中...</div>';
  try {
    const res = await api('/api/products/recognize', 'POST', {text});
    recognizedResults = res.products || [];
    if (!recognizedResults.length) { rd.innerHTML = `<div class="alert alert-warning py-2 mb-0 small">${res.error || '未能识别出产品信息'}</div>`; return; }
    // 自动填入第一个（也是唯一一个）识别结果
    fillProductFromResult(0);
    rd.innerHTML = `<div class="p-2 rounded" style="background:#dcfce7;border:1px solid #bbf7d0"><div class="small fw-medium text-success"><i class="bi bi-check-circle\"></i> 已识别并填入：<strong>${escHtml(recognizedResults[0].name)}</strong>${recognizedResults[0].price ? ' ¥' + recognizedResults[0].price : ''}</div></div>`;
    toast('已自动填入识别结果');
  } catch(e) { rd.innerHTML = `<div class="alert alert-danger py-2 mb-0 small">识别失败: ${e.message}</div>`; }
}

function fillProductFromResult(index) {
  const p = recognizedResults[index];
  if (!p) return;
  if ($('pf_name') && p.name) $('pf_name').value = p.name;
  if ($('pf_spec') && (p.sku || p.spec)) $('pf_spec').value = p.sku || p.spec;
  if ($('pf_supplier') && p.supplier) $('pf_supplier').value = p.supplier;
  if ($('pf_unit') && p.unit) $('pf_unit').value = p.unit;
  if ($('pf_price') && p.price) $('pf_price').value = p.price;
  if ($('pf_function_desc') && (p.remark || p.function_desc)) $('pf_function_desc').value = p.remark || p.function_desc;
  toast(`已填入「${p.name}」`);
}

async function recognizePastedImage() {
  try {
    const clipboardItems = await navigator.clipboard.read();
    let imageFile = null;
    for (const item of clipboardItems) {
      for (const type of item.types) {
        if (type.startsWith('image/')) {
          const blob = await item.getType(type);
          imageFile = new File([blob], 'clipboard_image.png', {type});
          break;
        }
      }
      if (imageFile) break;
    }
    if (!imageFile) {
      toast('剪贴板中没有图片，请先截图到剪贴板', 'warning');
      return;
    }
    const formData = new FormData();
    formData.append('file', imageFile);
    const rd = $('pf_recognize_results');
    if (rd) rd.innerHTML = '<div class="text-center py-2"><div class="spinner-border spinner-border-sm text-primary" role="status"></div> OCR识别中...</div>';
    const r = await fetch(BASE_URL + '/api/products/ocr', { method: 'POST', body: formData });
    const data = await r.json();
    if (data.text) {
      if ($('pf_paste_zone')) $('pf_paste_zone').value = data.text;
      toast('OCR识别完成，正在分析');
      recognizePastedText();
    } else {
      if (rd) rd.innerHTML = `<div class="alert alert-warning py-2 mb-0 small">${data.error || 'OCR未能识别出文字'}</div>`;
    }
  } catch(e) {
    if (e.name === 'NotAllowedError') {
      toast('请在浏览器设置中允许剪贴板权限', 'warning');
    } else {
      const input = document.createElement('input');
      input.type = 'file'; input.accept = 'image/*';
      input.onchange = async (ev) => {
        const file = ev.target.files[0]; if (!file) return;
        const fd = new FormData(); fd.append('file', file);
        const rd = $('pf_recognize_results');
        if (rd) rd.innerHTML = '<div class="text-center py-2"><div class="spinner-border spinner-border-sm text-primary" role="status"></div> OCR识别中...</div>';
        const r = await fetch(BASE_URL + '/api/products/ocr', { method: 'POST', body: fd });
        const d = await r.json();
        if (d.text) { if ($('pf_paste_zone')) $('pf_paste_zone').value = d.text; toast('OCR完成'); recognizePastedText(); }
      };
      input.click();
    }
  }
}

async function deleteProduct(id) {
  if (!confirm('确定删除该产品？')) return;
  await api(`/api/products/${id}`, 'DELETE');
  clearCaches();
  toast('已删除');
  renderProducts($('mainContent'));
}

async function batchDelete() {
  if (!confirm(`确定删除选中的 ${selectedIds.size} 个产品？`)) return;
  await api('/api/products/batch-delete', 'POST', {ids: [...selectedIds]});
  selectedIds.clear();
  clearCaches();
  toast('批量删除成功');
  renderProducts($('mainContent'));
}

// ─── Quotes ─────────────────────────────────────────────
let quotesPerPage = 10;
let quoteStatusFilter = '';

async function renderQuotes(el) {
  const params = quoteStatusFilter ? `?status=${quoteStatusFilter}` : '';
  const data = await api(`/api/quotes${params}`);
  let quotes = data.quotes || [];
  quotes.sort((a, b) => b.id - a.id);
  const total = quotes.length;
  const totalPages = Math.ceil(total / quotesPerPage);
  const start = (currentPage - 1) * quotesPerPage;
  const pageQuotes = quotes.slice(start, start + quotesPerPage);

  function qPagination() {
    if (totalPages <= 1) return '';
    return `
      <nav class="mt-3"><ul class="pagination pagination-modern justify-content-center mb-0" style="flex-wrap:wrap">
        <li class="page-item ${currentPage <= 1 ? 'disabled' : ''}"><a class="page-link" onclick="quotesPage(${currentPage-1})">上一页</a></li>
        ${Array.from({length: Math.min(totalPages, 7)}, (_, i) => {
          let p = i + 1;
          if (totalPages > 7 && currentPage > 4) p = currentPage - 4 + i;
          if (p > totalPages) return '';
          return `<li class="page-item ${p === currentPage ? 'active' : ''}"><a class="page-link" onclick="quotesPage(${p})">${p}</a></li>`;
        }).join('')}
        <li class="page-item ${currentPage >= totalPages ? 'disabled' : ''}"><a class="page-link" onclick="quotesPage(${currentPage+1})">下一页</a></li>
      </ul></nav>
    `;
  }

  el.innerHTML = `
    <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
      <h5 class="fw-bold mb-0">报价单</h5>
      <div class="d-flex align-items-center gap-2">
        <select class="per-page-select" onchange="quoteStatusFilter=this.value;currentPage=1;renderQuotes($('mainContent'))">
          <option value="" ${!quoteStatusFilter?'selected':''}>全部状态</option>
          <option value="draft" ${quoteStatusFilter==='draft'?'selected':''}>草稿</option>
          <option value="sent" ${quoteStatusFilter==='sent'?'selected':''}>已发送</option>
          <option value="confirmed" ${quoteStatusFilter==='confirmed'?'selected':''}>已确认</option>
          <option value="rejected" ${quoteStatusFilter==='rejected'?'selected':''}>已拒绝</option>
        </select>
        <select class="per-page-select" onchange="quotesPerPage=parseInt(this.value);currentPage=1;renderQuotes($('mainContent'))">
          <option value="10" ${quotesPerPage===10?'selected':''}>10条/页</option>
          <option value="20" ${quotesPerPage===20?'selected':''}>20条/页</option>
          <option value="50" ${quotesPerPage===50?'selected':''}>50条/页</option>
        </select>
        <button class="btn btn-primary btn-modern" onclick="switchTab('newquote')"><i class="bi bi-plus-lg"></i> 新建报价</button>
      </div>
    </div>
    <div class="card-modern">
      <div class="table-responsive">
        <table class="table table-modern">
          <thead>
            <tr>
              <th style="width:50px">#</th>
              <th>标题</th>
              <th>客户</th>
              <th>日期</th>
              <th>状态</th>
              <th>总金额</th>
              <th style="width:130px">操作</th>
            </tr>
          </thead>
          <tbody>${pageQuotes.length ? pageQuotes.map(q => `
            <tr>
              <td class="text-muted">${q.id}</td>
              <td><strong style="font-size:.85rem">${escHtml(q.title || '未命名')}</strong></td>
              <td style="font-size:.82rem"><a style="cursor:pointer;color:var(--primary);text-decoration:underline dotted" onclick="showCustomerQuotes('${escHtml(q.client)}')">${escHtml(q.client || '-')}</a></td>
              <td class="text-muted" style="font-size:.8rem">${q.quote_date || '-'}</td>
              <td><span class="badge status-badge" style="font-weight:500;font-size:.75rem;cursor:pointer;background:${q.status==='draft'?'#f1f5f9':q.status==='sent'?'#dcfce7':q.status==='confirmed'?'#dbeafe':q.status==='rejected'?'#fee2e2':'#f1f5f9'};color:${q.status==='draft'?'#64748b':q.status==='sent'?'#16a34a':q.status==='confirmed'?'#2563eb':q.status==='rejected'?'#dc2626':'#64748b'}" onclick="event.stopPropagation();cycleQuoteStatus(${q.id}, '${q.status}', this)" title="点击切换状态">${q.status==='draft'?'草稿':q.status==='sent'?'已发送':q.status==='confirmed'?'已确认':q.status==='rejected'?'已拒绝':q.status}</span></td>
              <td class="fw-medium" style="color:var(--danger);font-size:.87rem">${formatMoney(q.total_amount)}</td>
              <td style="white-space:nowrap">
                <button class="btn btn-sm btn-modern btn-outline-primary" onclick="viewQuote(${q.id})" title="查看"><i class="bi bi-eye"></i></button>
                <button class="btn btn-sm btn-modern btn-outline-info" onclick="previewQuote(${q.id})" title="预览输出格式"><i class="bi bi-file-earmark-pdf"></i></button>
                <button class="btn btn-sm btn-modern btn-outline-success" onclick="emailQuote(${q.id})" title="发送邮件"><i class="bi bi-envelope"></i></button>
                <button class="btn btn-sm btn-modern btn-outline-danger" onclick="deleteQuote(${q.id})" title="删除"><i class="bi bi-trash"></i></button>
              </td>
            </tr>
          `).join('') : '<tr><td colspan="7"><div class="empty-state"><i class="bi bi-file-earmark"></i><p>暂无报价单</p></div></td></tr>'}</tbody>
        </table>
      </div>
      ${qPagination()}
    </div>
  `;
}

function quotesPage(p) { currentPage = p; renderQuotes($('mainContent')); }

async function cycleQuoteStatus(id, currentStatus, el) {
  const order = ['draft', 'sent', 'confirmed', 'rejected', 'draft'];
  const idx = order.indexOf(currentStatus);
  const next = order[idx + 1] || 'draft';
  const labels = {draft:'草稿', sent:'已发送', confirmed:'已确认', rejected:'已拒绝'};
  const colors = {
    draft: {bg:'#f1f5f9',fg:'#64748b'},
    sent: {bg:'#dcfce7',fg:'#16a34a'},
    confirmed: {bg:'#dbeafe',fg:'#2563eb'},
    rejected: {bg:'#fee2e2',fg:'#dc2626'}
  };
  try {
    await api(`/api/quotes/${id}/status`, 'PATCH', {status: next});
    el.style.background = colors[next].bg;
    el.style.color = colors[next].fg;
    el.textContent = labels[next];
    el.setAttribute('onclick', `event.stopPropagation();cycleQuoteStatus(${id}, '${next}', this)`);
    toast(`状态 → ${labels[next]}`);
  } catch(e) {
    toast('状态更新失败', 'warning');
  }
}

async function showCustomerQuotes(client) {
  const data = await api('/api/quotes/stats');
  const cust = (data.customers || []).find(c => c.client === client);
  if (!cust) { toast('未找到该客户记录', 'warning'); return; }
  const items = cust.quotes.map(q => `
    <tr>
      <td><a style="cursor:pointer;color:var(--primary)" onclick="hideModal();viewQuote(${q.id})">#${q.id}</a></td>
      <td>${escHtml(q.title)}</td>
      <td>${formatMoney(q.total_amount)}</td>
      <td><span class="badge" style="font-size:.7rem;background:${q.status==='draft'?'#f1f5f9':q.status==='sent'?'#dcfce7':q.status==='confirmed'?'#dbeafe':'#fee2e2'};color:${q.status==='draft'?'#64748b':q.status==='sent'?'#16a34a':q.status==='confirmed'?'#2563eb':'#dc2626'}">${q.status==='draft'?'草稿':q.status==='sent'?'已发送':q.status==='confirmed'?'已确认':'已拒绝'}</span></td>
      <td>${q.quote_date}</td>
      <td>${q.download_count}次</td>
    </tr>
  `).join('');
  showFormModal(`客户：${escHtml(client)}`,
    `<div class="mb-3 p-2 rounded" style="background:var(--gray-50)">
      <span class="text-muted small">累计报价：</span><strong>${cust.quote_count}次</strong>
      <span class="text-muted small ms-3">总金额：</span><strong style="color:var(--danger)">${formatMoney(cust.total_amount)}</strong>
    </div>
    <table class="table table-sm table-modern">
      <thead><tr><th>ID</th><th>标题</th><th>金额</th><th>状态</th><th>日期</th><th>下载</th></tr></thead>
    <tbody>${items}</tbody></table>`,
    '', null, '关闭', true);
}

function viewQuote(id) { getAndShowQuote(id, true); }
function editQuote(id) { editingQuoteId = id; getAndShowQuote(id, false); }

async function getAndShowQuote(id, readonly) {
  const d = await api(`/api/quotes/${id}`);
  const q = d.quote;
  if (!q) { toast('报价单不存在', 'warning'); return; }
  quoteItems = q.items.map(item => ({...item, _tmpId: Date.now() + Math.random()}));
  if (readonly) {
    showFormModal(`报价单 #${q.id}`, `
      <div class="p-3 rounded" style="background:var(--gray-50);border:1px solid var(--gray-200)">
        <div class="row g-2 small">
          <div class="col-md-4"><strong>标题：</strong>${escHtml(q.title)}</div>
          <div class="col-md-3"><strong>客户：</strong>${escHtml(q.client)}</div>
          <div class="col-md-2"><strong>日期：</strong>${q.quote_date}</div>
          <div class="col-md-2"><strong>状态：</strong><span class="badge" style="background:${q.status==='draft'?'#f1f5f9':q.status==='sent'?'#dcfce7':q.status==='confirmed'?'#dbeafe':'#fee2e2'};color:${q.status==='draft'?'#64748b':q.status==='sent'?'#16a34a':q.status==='confirmed'?'#2563eb':'#dc2626'}">${q.status==='draft'?'草稿':q.status==='sent'?'已发送':q.status==='confirmed'?'已确认':'已拒绝'}</span></div>
        </div>
      </div>
      <div class="table-responsive mt-3">
        <style scoped>.quote-view-table th,.quote-view-table td{border:1px solid #dee2e6!important;border-left:1px solid #dee2e6!important;border-right:1px solid #dee2e6!important}</style>
        <table class="table table-sm quote-view-table">
          <thead><tr><th>#</th><th>产品名称</th><th>规格型号</th><th>数量</th><th>单价</th><th>金额</th><th>毛利</th><th>毛利率</th></tr></thead>
          <tbody>${q.items.map((item, i) => { const p = item.profit || 0; const r = item.profit_rate || 0; const pc = p >= 0 ? 'var(--success)' : 'var(--danger)'; return '<tr><td>'+(i+1)+'</td><td>'+escHtml(item.product_name)+'</td><td>'+escHtml(item.product_spec||'-')+'</td><td>'+item.quantity+' '+escHtml(item.product_unit||'')+'</td><td>'+formatMoney(item.unit_price)+'</td><td class="fw-medium">'+formatMoney(item.amount)+'</td><td style="color:'+pc+';font-size:.82rem">'+(p!==0?formatMoney(p):'-')+'</td><td style="color:'+pc+';font-size:.78rem">'+(r!==0?r+'%':'-')+'</td></tr>'; }).join('')}</tbody>
          <tfoot><tr class="table-light"><td colspan="5" class="text-end fw-bold">合计</td><td class="fw-bold" style="color:var(--danger)">${formatMoney(q.total_amount)}</td><td colspan="2"></td></tr></tfoot>
        </table>
      </div>
    `, '编辑', () => { hideModal(); editQuote(q.id); }, '关闭');
  } else {
    renderQuoteForm(q);
  }
}

async function deleteQuote(id) {
  if (!confirm('确定删除此报价单？')) return;
  await api(`/api/quotes/${id}`, 'DELETE');
  clearCaches();
  toast('已删除');
  renderQuotes($('mainContent'));
}

async function exportQuote(id) { downloadQuote(id); }

async function emailQuote(id) {
  const email = prompt('收件人邮箱：');
  if (!email || !email.includes('@')) { toast('请输入有效邮箱', 'warning'); return; }
  const subject = prompt('邮件主题（可选）：', '报价单');
  try {
    const r = await api('/api/quotes/' + id + '/send-email', 'POST', {to_email: email.trim(), subject: (subject||'').trim(), body: ''});
    if (r.success) toast(r.message, 'success');
    else toast(r.error || '发送失败', 'warning');
  } catch(e) { toast('发送失败: ' + e.message, 'warning'); }
}

async function downloadQuote(id) {
  try {
    const d = new Date();
    const ds = d.getFullYear() + String(d.getMonth()+1).padStart(2,'0') + String(d.getDate()).padStart(2,'0');
    // 先获取报价单信息用于文件名
    let filename = `报价单_${id}.xlsx`;
    try {
      const qd = await api(`/api/quotes/${id}`);
      if (qd.quote) {
        filename = `${qd.quote.client || ''}_${qd.quote.title || ''}_${qd.quote.contact || ''}_${ds}`.replace(/\s/g,'').replace(/_{2,}/g,'_').replace(/_$/,'').replace(/^_/,'') + '.xlsx';
      }
    } catch(_) {}
    const resp = await fetch(BASE_URL + `/api/quotes/${id}/export-excel?download_date=${ds}`, {
      headers: authToken ? {'Authorization': 'Bearer ' + authToken} : {}
    });
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch(e) {
    toast('下载失败', 'warning');
  }
}

async function previewQuote(id) {
  showFormModal('报价单预览', `<div id="previewFrame" class="text-center py-5"><div class="spinner-border text-primary" role="status"></div><p class="text-muted small mt-2">加载预览...</p></div>`, '', null, '关闭', true);
  // 注入下载按钮
  const footer = $('formModalFooter');
  if (footer) {
    const btn = document.createElement('button');
    btn.className = 'btn btn-success btn-modern';
    btn.innerHTML = '<i class="bi bi-download me-1"></i>下载Excel';
    btn.onclick = () => downloadQuote(id);
    footer.insertBefore(btn, footer.firstChild);
  }
  // 通过 api() 带 token 获取预览 HTML，再注入 iframe
  try {
    const resp = await fetch(BASE_URL + '/api/quotes/' + id + '/preview', { headers: {'Authorization': 'Bearer ' + authToken} });
    const html = await resp.text();
    const blob = new Blob([html], {type: 'text/html'});
    const url = URL.createObjectURL(blob);
    const frame = $('previewFrame');
    if (frame) frame.innerHTML = `<iframe src="${url}" style="width:100%;height:75vh;border:none;border-radius:8px"></iframe>`;
  } catch(e) {
    const frame = $('previewFrame');
    if (frame) frame.innerHTML = '<div class="text-danger py-4">加载预览失败: ' + escHtml(e.message) + '</div>';
  }
}

// ─── New Quote ──────────────────────────────────────────
async function renderNewQuote(el) {
  editingQuoteId = null;
  quoteItems = [];
  renderQuoteForm(null, el);
}

async function renderQuoteForm(existingQuote, targetEl) {
  const el = targetEl || $('mainContent');
  const q = existingQuote || {title:'', client:'', contact:'', phone:'', quote_date:new Date().toISOString().slice(0,10), valid_days:15, tax_rate:0, remark:'', id: null};

  // 先渲染表单，避免等待产品数据加载
  el.innerHTML = `
    <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
      <h5 class="fw-bold mb-0"><i class="bi bi-plus-circle me-2"></i>${q.id ? '编辑报价单' : '新建报价单'}</h5>
      <button class="btn btn-success btn-modern" onclick="saveQuote()"><i class="bi bi-check-lg me-1"></i> 保存报价单</button>
      ${q.id ? `<button class="btn btn-outline-info btn-modern" onclick="previewQuote(${q.id})"><i class="bi bi-eye me-1"></i> 预览</button>` : ''}
    </div>

    <!-- 基本信息区域（上半部分） -->
    <div class="card-modern mb-3">
      <div class="card-title-modern"><i class="bi bi-info-circle"></i>基本信息</div>
      <div class="row g-3">
        <div class="col-md-4">
          <label class="form-label" style="font-size:.75rem;font-weight:500;color:var(--gray-600)">报价标题</label>
          <input class="form-control form-control-sm" id="qf_title" value="${escHtml(q.title)}" placeholder="例：XX项目报价单">
        </div>
        <div class="col-md-4">
          <label class="form-label" style="font-size:.75rem;font-weight:500;color:var(--gray-600)">客户名称</label>
          <input class="form-control form-control-sm" id="qf_client" value="${escHtml(q.client)}">
        </div>
        <div class="col-md-2">
          <label class="form-label" style="font-size:.75rem;font-weight:500;color:var(--gray-600)">联系人</label>
          <input class="form-control form-control-sm" id="qf_contact" value="${escHtml(q.contact)}">
        </div>
        <div class="col-md-2">
          <label class="form-label" style="font-size:.75rem;font-weight:500;color:var(--gray-600)">电话</label>
          <input class="form-control form-control-sm" id="qf_phone" value="${escHtml(q.phone)}">
        </div>
        <div class="col-md-2">
          <label class="form-label" style="font-size:.75rem;font-weight:500;color:var(--gray-600)">报价日期</label>
          <input class="form-control form-control-sm" id="qf_date" type="date" value="${q.quote_date}">
        </div>
        <div class="col-md-2">
          <label class="form-label" style="font-size:.75rem;font-weight:500;color:var(--gray-600)">有效期(天)</label>
          <input class="form-control form-control-sm" id="qf_valid" type="number" value="${q.valid_days}">
        </div>
        <div class="col-md-2">
          <label class="form-label" style="font-size:.75rem;font-weight:500;color:var(--gray-600)">税率(%)</label>
          <input class="form-control form-control-sm" id="qf_tax_rate" type="number" step="0.1" min="0" max="100" value="${q.tax_rate || 0}" onchange="renderQuoteItems();updateQuoteTotal()" placeholder="例：5">
        </div>
        <div class="col-md-6">
          <label class="form-label" style="font-size:.75rem;font-weight:500;color:var(--gray-600)">报价备注</label>
          <input class="form-control form-control-sm" id="qf_remark" value="${escHtml(q.remark)}" placeholder="报价备注">
        </div>
      </div>
    </div>

    <!-- 报价明细表格（下半部分） -->
    <div class="card-modern">
      <div class="card-title-modern"><i class="bi bi-cart"></i>报价明细</div>
      <div class="mb-2 position-relative">
        <div class="input-group">
          <input class="form-control search-box border" placeholder="搜索名称/规格/型号/功能/厂家...（支持拼音/缩写）" id="prodSearch" oninput="searchProductsForQuote(this.value)">
          <button class="btn btn-primary btn-modern" onclick="showProductPicker()"><i class="bi bi-plus-lg"></i> 从产品库选择</button>
        </div>
        <div id="searchResults" style="display:none" class="search-results" style="width:calc(100% - 120px)"></div>
      </div>
      <div class="table-responsive">
        <table class="table table-modern table-sm" id="quoteItemsTable">
          <thead><tr><th style="width:28px"></th><th style="width:32px">#</th><th>产品名称</th><th>规格型号</th><th style="width:60px">数量</th><th style="width:85px">单价</th><th style="width:85px">金额</th><th style="width:65px">毛利</th><th style="width:50px">%</th><th style="width:100px">备注</th><th style="width:36px"></th></tr></thead>
          <tbody id="quoteItemsBody"></tbody>
          <tfoot><tr><td colspan="6" class="text-end fw-bold">合计</td><td class="fw-bold" style="color:var(--danger)" id="quoteTotal">¥0.00</td><td id="quoteTotalProfit" class="fw-medium" style="font-size:.82rem"></td><td id="quoteTotalRate" class="fw-medium" style="font-size:.82rem"></td><td id="quoteTax" class="fw-medium text-muted" style="font-size:.78rem"></td><td></td></tr></tfoot>
        </table>
      </div>
      ${quoteItems.length === 0 ? '<div class="text-center text-muted py-3 small"><i class="bi bi-inbox d-block fs-2 mb-2"></i>点击「从产品库选择」或搜索添加产品</div>' : ''}
    </div>

    <div class="d-flex justify-content-between mt-3">
      <button class="btn btn-outline-secondary btn-modern" onclick="switchTab('quotes')"><i class="bi bi-arrow-left me-1"></i> 返回列表</button>
      <button class="btn btn-success" onclick="saveQuote()"><i class="bi bi-check-lg me-1"></i> 保存报价单</button>
    </div>
  `;
  renderQuoteItems();
}

function renderQuoteItems() {
  const tbody = $('quoteItemsBody');
  if (!tbody) return;
  if (!quoteItems.length) { tbody.innerHTML = ''; updateQuoteTotal(); return; }
  // Profit calculation — apply tax deduction if tax_rate > 0
  const taxRate = parseFloat($('qf_tax_rate')?.value) || 0;
  const profitData = quoteItems.map(item => {
    let profit = 0, rate = 0;
    // Determine pre-tax unit price
    let pretaxPrice = item.unit_price || 0;
    if (taxRate > 0) {
      pretaxPrice = Math.round((item.unit_price || 0) / (1 + taxRate / 100) * 100) / 100;
    }
    if (item.product_id && productsCache?.products) {
      const p = productsCache.products.find(p => p.id === item.product_id);
      if (p && p.cost_price) {
        const perUnitProfit = Math.round((pretaxPrice - p.cost_price) * 100) / 100;
        profit = Math.round(perUnitProfit * (item.quantity || 1) * 100) / 100;
        rate = pretaxPrice > 0 ? Math.round(perUnitProfit / pretaxPrice * 1000) / 10 : 0;
      }
    }
    return {...item, _profit: profit, _rate: rate};
  });
  tbody.innerHTML = profitData.map((item, i) => {
    const p = item._profit || item.profit || 0;
    const r = item._rate || item.profit_rate || 0;
    const pc = p >= 0 ? 'var(--success)' : 'var(--danger)';
    return `
    <tr draggable="true" class="quote-item-row" data-idx="${i}">
      <td class="drag-handle" style="cursor:grab;color:var(--gray-400);font-size:1.1rem;padding:0.3rem 0.2rem;text-align:center;user-select:none" title="拖拽排序">⋮⋮</td>
      <td class="text-muted small">${i+1}</td>
      <td>
        <input class="form-control form-control-sm border-0 bg-transparent" value="${escHtml(item.product_name)}" onchange="quoteItems[${i}].product_name=this.value;updateQuoteTotal()" readonly>
      </td>
      <td><input class="form-control form-control-sm border-0 bg-transparent small text-muted" value="${escHtml(item.product_spec||'')}" readonly></td>
      <td><input class="form-control form-control-sm" type="number" step="1" min="1" value="${item.quantity}" onchange="quoteItems[${i}].quantity=parseInt(this.value)||1;recalcItem(${i});updateQuoteTotal()" oninput="this.value=this.value.replace(/[^0-9]/g,'')"></td>
      <td><input class="form-control form-control-sm" type="number" step="0.01" min="0" value="${item.unit_price}" onchange="quoteItems[${i}].unit_price=parseFloat(this.value)||0;recalcItem(${i});updateQuoteTotal()"></td>
      <td class="fw-medium" style="font-size:.87rem">${formatMoney(item.amount)}</td>
      <td style="font-size:.82rem;color:${pc}">${p !== 0 ? formatMoney(p) : '-'}</td>
      <td style="font-size:.78rem;color:${pc}">${r !== 0 ? r + '%' : '-'}</td>
      <td><input class="form-control form-control-sm" value="${escHtml(item.remark||'')}" onchange="quoteItems[${i}].remark=this.value.trim()" placeholder="备注"></td>
      <td><button class="btn btn-sm btn-modern btn-outline-danger border-0" onclick="removeQuoteItem(${i})"><i class="bi bi-x"></i></button></td>
    </tr>
  `}).join('');
  updateQuoteTotal();
}

function recalcItem(i) {
  const item = quoteItems[i];
  item.amount = Math.round((item.quantity || 0) * (item.unit_price || 0) * 100) / 100;
  renderQuoteItems();
}
function updateQuoteTotal() {
  const total = quoteItems.reduce((s, item) => s + (item.amount || 0), 0);
  const el = $('quoteTotal');
  if (el) el.textContent = formatMoney(total);
  // Calculate total profit (shared by both display blocks)
  let tProfit = 0;
  const taxRate = parseFloat($('qf_tax_rate')?.value) || 0;
  quoteItems.forEach(item => {
    if (item.product_id && productsCache?.products) {
      const p = productsCache.products.find(p => p.id === item.product_id);
      if (p && p.cost_price) {
        let pretaxPrice = item.unit_price || 0;
        if (taxRate > 0) pretaxPrice = (item.unit_price || 0) / (1 + taxRate / 100);
        tProfit += (pretaxPrice - p.cost_price) * (item.quantity || 1);
      }
    }
  });
  // Update total profit (green/red like per-row profit)
  const tp = $('quoteTotalProfit');
  if (tp) {
    const tProfitRounded = Math.round(tProfit * 100) / 100;
    if (tProfitRounded !== 0) {
      const profitColor = tProfitRounded >= 0 ? 'var(--success)' : 'var(--danger)';
      tp.innerHTML = `<span style="color:${profitColor}">${formatMoney(tProfitRounded)}</span>`;
    } else {
      tp.textContent = '';
    }
  }
  // Update total profit rate (green/red like per-row rate)
  const tr = $('quoteTotalRate');
  if (tr) {
    const tRate = total > 0 ? Math.round(tProfit / total * 1000) / 10 : 0;
    if (tRate !== 0) {
      const rateColor = tRate >= 0 ? 'var(--success)' : 'var(--danger)';
      tr.innerHTML = `<span style="color:${rateColor}">${tRate}%</span>`;
    } else {
      tr.textContent = '';
    }
  }
  // Update tax amount display
  const tx = $('quoteTax');
  if (tx) {
    const tTax = taxRate > 0 && total > 0 ? Math.round((total - total / (1 + taxRate / 100)) * 100) / 100 : 0;
    tx.textContent = tTax > 0 ? '税额 ' + formatMoney(tTax) : '';
  }
}
function removeQuoteItem(i) { quoteItems.splice(i, 1); renderQuoteItems(); }

function showProductPicker() {
  window._pickerSelected = new Set();
  window._pickerCategory = '';
  // 优先从全局 categories，fallback 到 productsCache
  const cats = categories.length ? categories : (productsCache?.categories || []);
  const catChips = cats.slice(0, 12).map(c => `<button class="btn btn-sm btn-outline-secondary btn-modern picker-cat-btn" style="font-size:.75rem;padding:2px 10px" onclick="togglePickerCategory('${escHtml(c)}', this)">${escHtml(c)}</button>`).join('');
  const body = `
    <div class="mb-2" style="max-height:80px;overflow-y:auto">
      <div class="d-flex flex-wrap gap-1" id="pickerCatChips">${catChips}</div>
    </div>
    <div class="mb-2 d-flex gap-2">
      <input class="form-control search-box border" placeholder="搜索名称/规格/型号/功能/厂家...（支持拼音/缩写）" oninput="filterProductPicker()" id="pickerSearch" style="flex:1">
      <button class="btn btn-sm btn-modern btn-outline-secondary" onclick="togglePickerAll()" id="pickerToggleAll">全选</button>
    </div>
    <div id="pickerResults" style="max-height:60vh;overflow-y:auto;"><div class="text-center py-4"><div class="spinner-border spinner-border-sm text-primary" role="status"></div><span class="text-muted small ms-2">正在加载产品数据...</span></div></div>
  `;
  showFormModal('选择产品（支持多选）', body, '添加选中', async () => {
    if (!window._pickerSelected || window._pickerSelected.size === 0) {
      toast('请至少选择一个产品', 'warning');
      return;
    }
    const added = [];
    for (const id of window._pickerSelected) {
      const p = window._pickerData[id];
      if (!p) continue;
      const existing = quoteItems.findIndex(item => item.product_id === p.id);
      if (existing >= 0) {
        quoteItems[existing].quantity = (quoteItems[existing].quantity || 0) + 1;
        quoteItems[existing].amount = Math.round(quoteItems[existing].quantity * quoteItems[existing].unit_price * 100) / 100;
      } else {
        quoteItems.push({product_id: p.id, product_name: p.name, product_sku: p.spec || '', product_spec: p.spec || '', product_unit: p.unit || '', quantity: 1, unit_price: p.price, amount: p.price, remark: '', _tmpId: Date.now() + Math.random()});
      }
      added.push(p.name);
    }
    renderQuoteItems();
    hideModal();
    toast(`已添加 ${added.length} 个产品`);
  }, '取消');
  // 先检查版本，有变化才重新全量加载
  (async () => {
    if (window._pickerLoaded && Object.keys(window._pickerData||{}).length) {
      try {
        const v = await api('/api/products/version');
        const ver = `${v.count}_${v.max_updated_at || ''}`;
        if (ver === window._pickerVersion) {
          renderPickerList(Object.values(window._pickerData));
          return;
        }
      } catch(e) { /* 版本检查失败则全量加载 */ }
    }
    loadProductPicker('');
  })();
}

async function loadProductPicker(search) {
  const el = $('pickerResults');
  if (el) el.innerHTML = '<div class="text-center py-4"><div class="spinner-border spinner-border-sm text-primary" role="status"></div><span class="text-muted small ms-2">正在加载产品数据...</span></div>';
  const data = await api(`/api/products?per_page=10000&search=${encodeURIComponent(search)}`);
  const list = data.products || [];
  // 更新全局 categories（供分类按钮用）
  if (data.categories?.length) { data.categories.forEach(c => { if (!categories.includes(c)) categories.push(c); }); }
  window._pickerData = {};
  list.forEach(p => window._pickerData[p.id] = p);
  window._pickerLoaded = true;
  if (data.version) window._pickerVersion = `${data.version.count}_${data.version.max_updated_at || ''}`;
  renderPickerList(list);
}

function renderPickerList(list) {
  const el = $('pickerResults');
  if (!el) return;
  if (!list.length) { el.innerHTML = '<div class="text-center text-muted py-4">没有匹配的产品</div>'; return; }
  el.innerHTML = list.map(p => {
    const checked = window._pickerSelected?.has(p.id) ? 'checked' : '';
    return `
    <div class="d-flex justify-content-between align-items-center p-2 picker-item" style="border-bottom:1px solid var(--gray-100)">
      <div class="d-flex align-items-center gap-2" style="flex:1">
        <input type="checkbox" class="form-check-input" value="${p.id}" ${checked} onchange="togglePickerItem(${p.id}, this.checked)" style="cursor:pointer">
        <div style="cursor:pointer" onclick="clickPickerName(${p.id}, this)">
          <strong style="font-size:.85rem">${escHtml(p.name)}</strong>${p.supplier ? ` <span class="badge bg-light text-muted" style="font-size:.65rem;font-weight:400">${escHtml(p.supplier)}</span>` : ''}${p.category ? ` <span class="badge bg-light text-muted" style="font-size:.65rem;font-weight:400">${escHtml(p.category)}</span>` : ''}
          <br><span class="text-muted" style="font-size:.75rem">${escHtml(p.spec||'')}</span>
        </div>
      </div>
      <div class="text-end">
        <span class="fw-medium">${formatMoney(p.price)}</span>
        <br><span class="text-muted" style="font-size:.72rem">/${escHtml(p.unit||'个')}</span>
      </div>
    </div>
    `;
  }).join('');
}

function togglePickerItem(id, checked) {
  if (!window._pickerSelected) window._pickerSelected = new Set();
  if (checked) window._pickerSelected.add(id);
  else window._pickerSelected.delete(id);
}

function clickPickerName(id, el) {
  const cb = el.parentElement.querySelector('input[type=checkbox]');
  cb.checked = !cb.checked;
  togglePickerItem(id, cb.checked);
}

function togglePickerAll() {
  if (!window._pickerData) return;
  const allIds = Object.keys(window._pickerData).map(Number);
  if (!window._pickerSelected) window._pickerSelected = new Set();
  const isAllChecked = allIds.every(id => window._pickerSelected.has(id));
  if (isAllChecked) {
    window._pickerSelected.clear();
  } else {
    allIds.forEach(id => window._pickerSelected.add(id));
  }
  // Re-render checkboxes
  const checkboxes = document.querySelectorAll('#pickerResults input[type="checkbox"]');
  checkboxes.forEach(cb => {
    cb.checked = !isAllChecked;
  });
  $('pickerToggleAll').textContent = isAllChecked ? '全选' : '取消全选';
}

function filterProductPicker() {
  if (window._isComposing) return;
  clearTimeout(window._pp);
  window._pp = setTimeout(() => {
    const search = ($('pickerSearch')?.value || '').trim().toLowerCase();
    const cat = window._pickerCategory || '';
    const list = Object.values(window._pickerData).filter(p => {
      let matchSearch = true;
      if (search) {
        // 中文/ASCII 混合：按名称/规格/厂家/功能 + 拼音字段
        matchSearch = (p.name||'').toLowerCase().includes(search)
          || (p.spec||'').toLowerCase().includes(search)
          || (p.supplier||'').toLowerCase().includes(search)
          || (p.function_desc||'').toLowerCase().includes(search)
          || (p._py||'').includes(search)
          || (p._py_initials||'').includes(search);
      }
      const matchCat = !cat || (p.category||'').split(',').some(t => t.trim() === cat);
      return matchSearch && matchCat;
    });
    renderPickerList(list);
    updatePickerToggleAll();
  }, 500);
}

function updatePickerToggleAll() {
  const btn = $('pickerToggleAll');
  if (!btn) return;
  const allIds = Object.keys(window._pickerData || {}).map(Number);
  const allChecked = allIds.length > 0 && allIds.every(id => window._pickerSelected?.has(id));
  btn.textContent = allChecked ? '取消全选' : '全选';
}
function togglePickerCategory(cat, btn) {
  if (window._pickerCategory === cat) {
    window._pickerCategory = '';
    btn.classList.remove('active');
  } else {
    document.querySelectorAll('.picker-cat-btn').forEach(b => b.classList.remove('active'));
    window._pickerCategory = cat;
    btn.classList.add('active');
  }
  filterProductPicker();
}

function addProductToQuote(id, name, spec, unit, price) {
  const existing = quoteItems.findIndex(item => item.product_id === id);
  if (existing >= 0) {
    quoteItems[existing].quantity = (quoteItems[existing].quantity || 0) + 1;
    quoteItems[existing].amount = Math.round(quoteItems[existing].quantity * quoteItems[existing].unit_price * 100) / 100;
  } else {
    quoteItems.push({product_id: id, product_name: name, product_sku: spec, product_spec: spec, product_unit: unit, quantity: 1, unit_price: price, amount: price, remark: '', _tmpId: Date.now() + Math.random()});
  }
  renderQuoteItems();
  // 不关modal——支持连续单选或继续多选
  toast(`已添加「${name}」`);
}

function searchProductsForQuote(query) {
  if (window._isComposing) return;
  const resultsDiv = $('searchResults');
  if (!resultsDiv) return;
  if (!query || query.length < 1) { resultsDiv.style.display = 'none'; return; }
  clearTimeout(window._sq);
  window._sq = setTimeout(async () => {
    const data = await api(`/api/products?per_page=10&search=${encodeURIComponent(query)}`);
    const list = data.products || [];
    if (!list.length) { resultsDiv.style.display = 'none'; return; }
    resultsDiv.style.display = 'block';
    resultsDiv.innerHTML = list.map(p =>
      `<div class="p-2 border-bottom" style="cursor:pointer" onclick="addProductToQuote(${p.id}, '${escJs(p.name)}', '${escJs(p.spec)}', '${escJs(p.unit)}', ${p.price||0}); $('prodSearch').value=''; $('searchResults').style.display='none'">
        <strong style="font-size:.85rem">${escHtml(p.name)}</strong> <span class="text-muted small">${escHtml(p.spec||'')}</span>
        <span class="float-end text-primary fw-medium">${formatMoney(p.price)}</span>
      </div>`
    ).join('');
  }, 500);
}

document.addEventListener('click', function(e) {
  const r = $('searchResults');
  if (r && !e.target.closest('#prodSearch') && !e.target.closest('#searchResults')) r.style.display = 'none';
});

async function saveQuote() {
  const title = ($('qf_title')?.value || '').trim();
  const client = ($('qf_client')?.value || '').trim();
  const contact = ($('qf_contact')?.value || '').trim();
  const phone = ($('qf_phone')?.value || '').trim();
  const quote_date = ($('qf_date')?.value || new Date().toISOString().slice(0,10)).trim();
  const valid_days = parseInt($('qf_valid')?.value) || 15;
  const tax_rate = parseFloat($('qf_tax_rate')?.value) || 0;
  const remark = ($('qf_remark')?.value || '').trim();
  // 必填校验
  if (!title) { toast('请填写报价标题', 'warning'); return; }
  if (!client) { toast('请填写客户名称', 'warning'); return; }
  if (!contact) { toast('请填写联系人', 'warning'); return; }
  if (!phone) { toast('请填写电话', 'warning'); return; }
  if (!quoteItems.length) { toast('请至少添加一个产品', 'warning'); return; }
  const payload = {title, client, contact, phone, quote_date, valid_days, tax_rate, remark, items: quoteItems.map((item, i) => ({product_id: item.product_id||null, product_name: item.product_name, product_sku: item.product_sku||'', product_spec: item.product_spec||'', product_unit: item.product_unit||'', quantity: item.quantity, unit_price: item.unit_price, sort_order: i, remark: item.remark||''}))};
  try {
    if (editingQuoteId) { await api(`/api/quotes/${editingQuoteId}`, 'PUT', payload); toast('报价单已更新'); }
    else {
      const r = await api('/api/quotes', 'POST', payload);
      if (r.quote?.id) editingQuoteId = r.quote.id;
      toast('报价单已创建');
    }
    clearCaches();
    switchTab('quotes');
  } catch(e) { toast('保存失败: ' + e.message, 'warning'); }
}
// ─── Import ─────────────────────────────────────────────
function renderImport(el) {
  el.innerHTML = `
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h5 class="fw-bold mb-0"><i class="bi bi-upload me-2"></i>从Excel导入产品</h5>
    </div>
    <div class="row g-3">
      <div class="col-md-7">
        <div class="card-modern">
          <div class="card-title-modern"><i class="bi bi-file-earmark-excel text-success"></i>上传Excel文件</div>
          <div class="mb-3">
            <p class="text-muted small mb-1"><i class="bi bi-check-circle me-1 text-success"></i> 支持 <strong>多Sheet</strong> 导入，每张Sheet自动成为产品厂商</p>
            <p class="text-muted small">支持的字段：产品名称、规格型号、功能描述、单位、销售单价、成本价、供应商、备注</p>
            <p class="text-muted small">表头名称自动识别，支持多种格式。</p>
          </div>
          <div class="mb-3">
            <input class="form-control" type="file" id="importFile" accept=".xlsx,.xls">
          </div>
          <div class="d-flex gap-2">
            <button class="btn btn-primary btn-modern" onclick="doImport()"><i class="bi bi-upload me-1"></i> 开始导入</button>
            <button class="btn btn-outline-secondary btn-modern" onclick="window.open(BASE_URL + '/api/products/export-template')"><i class="bi bi-download me-1"></i> 下载原始模板</button>
          </div>
          <div id="importResult" class="mt-3"></div>
        </div>
      </div>
      <div class="col-md-5">
        <div class="card-modern">
          <div class="card-title-modern"><i class="bi bi-info-circle text-primary"></i>导入说明</div>
          <ul class="small text-muted mb-0" style="line-height:1.8">
            <li><strong>多Sheet支持</strong> — 所有Sheet自动导入</li>
            <li>每张Sheet名称自动设为<b>厂商</b></li>
            <li>支持 <code>.xlsx</code> / <code>.xls</code> 格式</li>
            <li>表头名称智能匹配，无需特定顺序</li>
            <li>自动跳过空行、「小计/合计」行</li>
            <li>当前已有 ${$('#mainContent') ? '...' : '0'} 个产品</li>
          </ul>
        </div>
      </div>
    </div>
  `;
}

async function doImport() {
  const fileInput = $('importFile');
  if (!fileInput.files.length) { toast('请选择文件', 'warning'); return; }
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  const el = $('importResult');
  el.innerHTML = '<div class="text-center py-3"><div class="spinner-border text-primary" role="status"></div><p class="mt-2 small text-muted">正在导入所有Sheet...</p></div>';
  try {
    const r = await fetch(BASE_URL + '/api/products/import', { method: 'POST', body: formData });
    const result = await r.json();
    if (result.error) {
      el.innerHTML = `<div class="alert alert-danger py-2 small">${result.error}</div>`;
      toast('导入失败', 'warning');
    } else {
      el.innerHTML = `
      <div class="alert alert-success py-2 small">
        <i class="bi bi-check-circle me-1"></i> 成功导入 <strong>${result.imported}</strong> 个产品
        ${result.errors?.length ? `<hr class="my-1"><p class="mb-0" style="font-size:.78rem;max-height:120px;overflow-y:auto">${result.errors.slice(0, 10).map(e => `• ${escHtml(e)}`).join('<br>')}${result.errors.length > 10 ? `<br>...还有 ${result.errors.length - 10} 个错误` : ''}</p>` : ''}
      </div>
    `;
      toast(`成功导入 ${result.imported} 个产品`);
      clearCaches();
      renderProducts($('mainContent'));
    }
  } catch (err) {
    el.innerHTML = `<div class="alert alert-danger py-2 small">网络错误或超时，请重试。</div>`;
    toast('上传失败，文件可能过大或网络中断', 'warning');
  }
}

// ─── Admin Panel ─────────────────────────────────────────

async function renderAdmin(el) {
  if (!isAdmin()) { toast('无权限', 'warning'); switchTab('dashboard'); return; }
  const [userData, fieldData, regData, logData, logStats, settingsData] = await Promise.all([
    api('/api/admin/users'),
    api('/api/admin/fields'),
    api('/api/admin/registration'),
    api('/api/download-logs'),
    api('/api/download-logs/stats'),
    api('/api/admin/settings'),
  ]);
  const users = userData.users || [];
  const fields = fieldData.fields || [];
  const regOpen = regData.registration_open !== false;
  const logs = logData.logs || [];
  const logUsers = logStats.users || [];
  const settings = settingsData.settings || {};

  el.innerHTML = `
    <div class="card-modern mb-3"><div class="card-title-modern"><i class="bi bi-people me-2"></i>用户管理</div>
          <div style="max-height:50vh;overflow-y:auto">
            <table class="table table-sm table-modern">
              <thead><tr><th>用户名</th><th>角色</th><th>状态</th><th>注册时间</th><th>操作</th></tr></thead>
              <tbody>${users.map(u => {
                const isSelf = currentUser && u.id === currentUser.id;
                return `<tr>
                  <td>${escHtml(u.username)}${u.email?'<br><small class="text-muted">'+escHtml(u.email)+'</small>':''}</td>
                  <td><span class="badge" style="background:${u.role==='admin'?'#dbeafe':'#f1f5f9'};color:${u.role==='admin'?'#2563eb':'#64748b'}">${u.role==='admin'?'管理员':'用户'}</span></td>
                  <td><span class="badge" style="background:${u.is_active?'#dcfce7':'#fee2e2'};color:${u.is_active?'#16a34a':'#dc2626'}">${u.is_active?'正常':'停用'}</span></td>
                  <td class="text-muted small">${u.created_at}</td>
                  <td>${isSelf ? '' : `<button class="btn btn-sm btn-modern btn-outline-secondary" onclick="toggleUser(${u.id},${!u.is_active})">${u.is_active?'停用':'启用'}</button> <button class="btn btn-sm btn-modern btn-outline-info" onclick="toggleUserRole(${u.id},'${u.role==='admin'?'user':'admin'}')">${u.role==='admin'?'降级':'升管理员'}</button> <button class="btn btn-sm btn-modern btn-outline-warning" onclick="changeUserPassword(${u.id},'${u.username}')">改密</button>`}</td>
                </tr>`;
              }).join('')}</tbody>
            </table>
          </div>
        </div>

    <div class="row g-3 mb-3">
      <div class="col-md-6">
        <div class="card-modern"><div class="card-title-modern"><i class="bi bi-eye-slash me-2"></i>字段可见性</div>
          <p class="text-muted small">控制普通用户能看到哪些字段</p>
          <div id="fieldSettings">${fields.map(f => `
            <div class="d-flex justify-content-between align-items-center mb-2 p-2 rounded" style="background:var(--gray-50)">
              <span>${escHtml(f.label)} (${f.field_name})</span>
              <label class="switch"><input type="checkbox" ${f.user_visible?'checked':''} onchange="updateFieldVisibility('${f.field_name}', this.checked)"><span class="slider"></span></label>
            </div>`).join('')}</div>
        </div>
      </div>
      <div class="col-md-6">
        <div class="card-modern"><div class="card-title-modern"><i class="bi bi-sliders me-2"></i>注册设置</div>
          <div class="d-flex justify-content-between align-items-center">
            <span>允许自主注册</span>
            <label class="switch"><input type="checkbox" ${regOpen?'checked':''} onchange="toggleRegistration(this.checked)"><span class="slider"></span></label>
          </div>
          <div class="text-muted small mt-1">关闭后只有管理员可以手动添加用户</div>
        </div>
      </div>
    </div>

    <div class="row g-3 mb-3">
      <div class="col-md-6">
        <div class="card-modern"><div class="card-title-modern"><i class="bi bi-gear me-2"></i>系统设置</div>
          <div class="mb-2"><label class="form-label small fw-medium">公司名称（显示在导出报价单顶部）</label>
            <input class="form-control form-control-sm" id="setCompany" value="${escHtml(settings.company_name||'')}" placeholder="如：XX科技有限公司">
          </div>
          <div class="mb-2"><label class="form-label small fw-medium">页脚文字（显示在导出报价单底部）</label>
            <textarea class="form-control form-control-sm" id="setFooter" rows="3" placeholder="如：开户行：XX银行 XX支行  账号：123456789">${escHtml(settings.footer_text||'')}</textarea>
          </div>
          <button class="btn btn-sm btn-modern btn-primary" onclick="saveSystemSettings()"><i class="bi bi-check me-1"></i>保存设置</button>
        </div>
      </div>
      <div class="col-md-6">
        <div class="card-modern"><div class="card-title-modern"><i class="bi bi-envelope me-2"></i>邮件SMTP设置</div>
          <div class="row g-2">
            <div class="col-6"><label class="form-label small">SMTP服务器</label><input class="form-control form-control-sm" id="setSmtpHost" value="${escHtml(settings.smtp_host||'')}" placeholder="smtp.qq.com"></div>
            <div class="col-3"><label class="form-label small">端口</label><input class="form-control form-control-sm" id="setSmtpPort" value="${escHtml(settings.smtp_port||'587')}" placeholder="587"></div>
            <div class="col-3"><label class="form-label small">TLS</label><select class="form-select form-select-sm" id="setSmtpTls"><option value="true" ${settings.smtp_use_tls!=='false'?'selected':''}>是</option><option value="false" ${settings.smtp_use_tls==='false'?'selected':''}>否</option></select></div>
            <div class="col-6"><label class="form-label small">发件邮箱</label><input class="form-control form-control-sm" id="setSmtpUser" value="${escHtml(settings.smtp_user||'')}" placeholder="xxx@qq.com"></div>
            <div class="col-6"><label class="form-label small">授权码/密码</label><input class="form-control form-control-sm" type="password" id="setSmtpPass" value="${escHtml(settings.smtp_password||'')}" placeholder="SMTP授权码"></div>
            <div class="col-6"><label class="form-label small">发件人显示名</label><input class="form-control form-control-sm" id="setSmtpFrom" value="${escHtml(settings.smtp_from||'')}" placeholder="XX公司 <xxx@qq.com>"></div>
          </div>
          <button class="btn btn-sm btn-modern btn-primary mt-2" onclick="saveSmtpSettings()"><i class="bi bi-check me-1"></i>保存SMTP</button>
        </div>
      </div>
    </div>

    <div class="card-modern mb-3"><div class="card-title-modern"><i class="bi bi-receipt me-2"></i>发票OCR → 更新成本价 <span class="badge bg-warning text-dark" style="font-size:.65rem">管理员</span></div>
      <p class="text-muted small">上传进货发票/采购单图片，自动识别产品+成本价，匹配现有产品并更新</p>
      <div class="mb-2">
        <input type="file" id="receiptFile" accept="image/*" class="form-control form-control-sm" onchange="uploadReceiptOCR()">
      </div>
      <div id="receiptResult" style="display:none;max-height:60vh;overflow-y:auto;margin-top:.5rem"></div>
    </div>

    <div class="card-modern"><div class="card-title-modern"><i class="bi bi-download me-2"></i>下载记录</div>
      <div class="d-flex gap-3 mb-2">
        <span class="text-muted small">总下载：<strong>${logs.length}</strong> 次</span>
        <span class="text-muted small">用户数：<strong>${logUsers.length}</strong></span>
      </div>
      <div style="max-height:40vh;overflow-y:auto">
        ${logs.length ? `<table class="table table-sm table-modern">
          <thead><tr><th>时间</th><th>用户</th><th>报价单</th><th>客户</th></tr></thead>
          <tbody>${logs.map(l => `<tr>
            <td class="text-muted small">${l.downloaded_at}</td>
            <td>${escHtml(l.user_name)}</td>
            <td><a style="cursor:pointer;color:var(--primary)" onclick="viewQuote(${l.quote_id})">#${l.quote_id} ${escHtml(l.quote_title)}</a></td>
            <td>${escHtml(l.quote_client)}</td>
          </tr>`).join('')}</tbody>
        </table>` : '<div class="text-muted small py-3 text-center">暂无下载记录</div>'}
      </div>
    </div>
  `;
}

async function toggleUser(id, active) {
  await api(`/api/admin/users/${id}`, 'PUT', {is_active: active});
  renderAdmin($('mainContent'));
}

async function toggleUserRole(id, role) {
  await api(`/api/admin/users/${id}`, 'PUT', {role: role});
  renderAdmin($('mainContent'));
}

async function changeUserPassword(id, username) {
  const pw = prompt(`为 ${username} 设置新密码（至少3位）：`);
  if (!pw || pw.trim().length < 3) return;
  const result = await api(`/api/admin/users/${id}/password`, 'PUT', {password: pw.trim()});
  if (result.success) toast(`${username} 密码已更新`, 'success');
  else toast(result.error || '修改失败', 'warning');
}


async function toggleProductActive(id) {
  const r = await api(`/api/products/${id}/toggle-active`, 'PUT');
  if (r.id) { clearCaches(); renderProducts($('mainContent')); toast(r.is_active ? '产品已上线' : '产品已下线'); }
}
async function updateFieldVisibility(field, visible) {
  await api('/api/admin/fields', 'PUT', {fields: [{field_name: field, user_visible: visible}]});
}

async function toggleRegistration(open) {
  await api('/api/admin/registration', 'PUT', {registration_open: open});
  registrationOpen = open;
}

async function saveSmtpSettings() {
  const data = {
    smtp_host: ($('setSmtpHost')?.value||'').trim(),
    smtp_port: ($('setSmtpPort')?.value||'').trim(),
    smtp_user: ($('setSmtpUser')?.value||'').trim(),
    smtp_password: ($('setSmtpPass')?.value||'').trim(),
    smtp_from: ($('setSmtpFrom')?.value||'').trim(),
    smtp_use_tls: $('setSmtpTls')?.value||'true'
  };
  await api('/api/admin/settings', 'PUT', data);
  toast('SMTP设置已保存', 'success');
}

async function saveSystemSettings() {
  const company = ($('setCompany')?.value || '').trim();
  const footer = ($('setFooter')?.value || '').trim();
  await api('/api/admin/settings', 'PUT', {company_name: company, footer_text: footer});
  toast('系统设置已保存', 'success');
}

document.addEventListener('DOMContentLoaded', async () => {
  const loggedIn = await checkSession();
  if (!loggedIn) { showLoginPage(); return; }
  renderPage();
  // 加载版本号
  fetch(BASE_URL + '/api/version').then(r => r.json()).then(d => {
    const el = document.getElementById('versionDisplay');
    if (el && d.version) el.textContent = 'v' + d.version;
  }).catch(() => {});
});

// ─── 拖拽排序 (v1.3.8) ──────────────────────────
let dragSrcIdx = null;
document.addEventListener('dragstart', function(e) {
  const row = e.target.closest('.quote-item-row');
  if (!row) return;
  dragSrcIdx = parseInt(row.dataset.idx);
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/plain', dragSrcIdx);
  row.style.opacity = '0.4';
  // Prevent drag from inputs inside the row
  if (e.target.tagName === 'INPUT') e.preventDefault();
});
document.addEventListener('dragend', function(e) {
  const row = e.target.closest('.quote-item-row');
  if (row) row.style.opacity = '';
  // Clean up all drag-over styles
  document.querySelectorAll('.quote-item-row').forEach(r => r.classList.remove('drag-over'));
  dragSrcIdx = null;
});
document.addEventListener('dragover', function(e) {
  const row = e.target.closest('.quote-item-row');
  if (!row || dragSrcIdx === null) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  // Visual indicator
  document.querySelectorAll('.quote-item-row').forEach(r => r.classList.remove('drag-over'));
  row.classList.add('drag-over');
});
document.addEventListener('drop', function(e) {
  const row = e.target.closest('.quote-item-row');
  if (!row || dragSrcIdx === null) return;
  e.preventDefault();
  row.classList.remove('drag-over');
  const dstIdx = parseInt(row.dataset.idx);
  if (dragSrcIdx !== dstIdx) {
    // Reorder the array
    const [moved] = quoteItems.splice(dragSrcIdx, 1);
    quoteItems.splice(dstIdx, 0, moved);
    renderQuoteItems();
  }
  dragSrcIdx = null;
});

// ─── 发票OCR成本更新 ──────────────────────────
async function uploadReceiptOCR() {
  const file = $('receiptFile')?.files?.[0];
  if (!file) return;
  const form = new FormData();
  form.append('file', file);
  const res = $('receiptResult');
  res.style.display = 'block';
  res.innerHTML = '<div class="text-center py-3"><div class="spinner-border spinner-border-sm text-primary"></div><span class="ms-2 text-muted small">OCR 识别中...</span></div>';

  try {
    const r = await fetch(BASE_URL + '/api/products/ocr-costs', {
      method: 'POST',
      headers: {'Authorization': 'Bearer ' + authToken},
      body: form,
    });
    const d = await r.json();
    if (d.error) { res.innerHTML = `<div class="alert alert-warning py-2 small">${escHtml(d.error)}</div>`; return; }

    const matches = d.matches || [];
    if (!matches.length) {
      res.innerHTML = `<div class="text-muted small py-2">未识别到产品价格对。<br>OCR 原文：<pre style="font-size:.75rem;max-height:150px;overflow:auto">${escHtml(d.raw_text)}</pre></div>`;
      return;
    }

    window._receiptMatches = matches;
    let html = '<div class="small fw-medium mb-2">识别到 <strong>' + matches.length + '</strong> 条产品-价格对：</div>';
    matches.forEach((m, i) => {
      html += `<div class="border rounded p-2 mb-2" style="background:var(--gray-50)">
        <div class="d-flex justify-content-between mb-1">
          <span class="fw-medium small">📄 ${escHtml(m.name_part)}</span>
          <span class="fw-bold" style="color:var(--primary)">¥${m.cost_price.toFixed(2)}</span>
        </div>`;
      if (m.candidates.length) {
        html += '<div class="small" style="font-size:.75rem">匹配产品：';
        m.candidates.forEach((c, j) => {
          const checked = j === 0 ? 'checked' : '';
          html += `<label class="d-block mb-1" style="cursor:pointer;font-weight:${j===0?'500':'normal'}">
            <input type="radio" name="rec_match_${i}" value="${c.id}" data-cost="${m.cost_price}" ${checked}>
            ${escHtml(c.name)} <span class="text-muted">${escHtml(c.spec||'')}</span>
            ${c.cost_price > 0 ? `<span class="text-muted">(现成本 ¥${c.cost_price.toFixed(2)})</span>` : '<span class="text-warning">(无成本)</span>'}
          </label>`;
        });
        html += '</div>';
      } else {
        html += '<span class="text-muted small">未找到匹配产品</span>';
      }
      html += '</div>';
    });
    html += `<button class="btn btn-sm btn-modern btn-success w-100 mt-2" onclick="applyReceiptCosts()"><i class="bi bi-check-lg me-1"></i>确认更新成本价</button>`;
    res.innerHTML = html;
  } catch(e) {
    res.innerHTML = `<div class="text-danger small">上传失败: ${escHtml(e.message)}</div>`;
  }
}

async function applyReceiptCosts() {
  const matches = window._receiptMatches || [];
  const updates = [];
  matches.forEach((m, i) => {
    const radio = document.querySelector(`input[name="rec_match_${i}"]:checked`);
    if (radio) {
      updates.push({id: parseInt(radio.value), cost_price: parseFloat(radio.dataset.cost)});
    }
  });
  if (!updates.length) { toast('请至少选择一个产品', 'warning'); return; }
  const r = await api('/api/products/batch-costs', 'POST', {updates});
  if (r.updated) {
    toast(r.message, 'success');
    $('receiptResult').style.display = 'none';
    clearCaches();
  } else {
    toast(r.error || '更新失败', 'warning');
  }
}

// Inject drag-over CSS
(function() {
  const style = document.createElement('style');
  style.textContent = '.quote-item-row.drag-over { border-top: 2px solid var(--primary) !important; } .quote-item-row { transition: opacity .15s; } .drag-handle:hover { color: var(--primary) !important; }';
  document.head.appendChild(style);
})();
