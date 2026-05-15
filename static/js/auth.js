// ─── Auth / Session ────────────────────────────────────
async function checkSession() {
  if (!authToken) return false;
  try {
    const r = await fetch(BASE_URL + '/api/session', {
      headers: {'Authorization': 'Bearer ' + authToken, 'Accept': 'application/json'}
    });
    if (r.status === 401) { setToken(''); showLoginPage(); return false; }
    const d = await r.json();
    // 自动续签token
    const newToken = r.headers.get('X-New-Token');
    if (newToken) setToken(newToken);
    if (d.user) {
      currentUser = d.user;
      fieldVisibility = d.field_visibility || {};
      registrationOpen = d.registration_open !== false;
      updateUserUI();
      return true;
    }
  } catch(e) {}
  return false;
}

function updateUserUI() {
  const u = $('topbarUser');
  const dd = $('userDropdown');
  if (currentUser) {
    u.textContent = currentUser.username + (currentUser.role === 'admin' ? ' [管理员]' : '');
    dd.style.display = 'block';
    document.querySelectorAll('.admin-only').forEach(el => el.style.display = currentUser.role === 'admin' ? '' : 'none');
  }
}

function showLoginPage() {
  const regHtml = registrationOpen ? '<p class="mt-3 text-muted">没有账号？<a style="cursor:pointer;color:var(--primary)" onclick="showRegisterPage()">注册新账号</a></p>' : '';
  $('mainContent').innerHTML = `
    <div class="d-flex justify-content-center align-items-center" style="min-height:70vh">
      <div class="card-modern" style="max-width:400px;width:100%">
        <h4 class="text-center mb-3"><i class="bi bi-lock me-2"></i>登录报价系统</h4>
        <div class="mb-2"><input class="form-control" id="loginUser" placeholder="用户名" autocomplete="username"></div>
        <div class="mb-3"><input class="form-control" type="password" id="loginPass" placeholder="密码" onkeydown="if(event.key==='Enter')doLogin()"></div>
        <button class="btn btn-primary btn-modern w-100" onclick="doLogin()">登录</button>
        <div id="loginError" class="text-danger small mt-2" style="display:none"></div>
        ${regHtml}
      </div>
    </div>`;
  $('topbarTitle').textContent = '登录';
}

async function doLogin() {
  const u = $('loginUser').value.trim();
  const p = $('loginPass').value.trim();
  if (!u || !p) { $('loginError').textContent = '请输入用户名和密码'; $('loginError').style.display=''; return; }
  try {
    const d = await fetch(BASE_URL + '/api/auth/login', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})}).then(r=>r.json());
    if (d.token) {
      setToken(d.token);
      currentUser = d.user;
      updateUserUI();
      renderPage();
    } else {
      $('loginError').textContent = d.error || '登录失败';
      $('loginError').style.display='';
    }
  } catch(e) { $('loginError').textContent='网络错误'; $('loginError').style.display=''; }
}

function showRegisterPage() {
  $('mainContent').innerHTML = `
    <div class="d-flex justify-content-center align-items-center" style="min-height:70vh">
      <div class="card-modern" style="max-width:400px;width:100%">
        <h4 class="text-center mb-3"><i class="bi bi-person-plus me-2"></i>注册账号</h4>
        <div class="mb-2"><input class="form-control" id="regUser" placeholder="用户名"></div>
        <div class="mb-2"><input class="form-control" type="password" id="regPass" placeholder="密码"></div>
        <div class="mb-3"><input class="form-control" id="regEmail" placeholder="邮箱（选填）"></div>
        <button class="btn btn-primary btn-modern w-100" onclick="doRegister()">注册</button>
        <div id="regError" class="text-danger small mt-2" style="display:none"></div>
        <p class="mt-3 text-muted">已有账号？<a style="cursor:pointer;color:var(--primary)" onclick="showLoginPage()">返回登录</a></p>
      </div>
    </div>`;
}

async function doRegister() {
  const u = $('regUser').value.trim();
  const p = $('regPass').value.trim();
  const e = $('regEmail').value.trim();
  if (!u || !p) { $('regError').textContent='用户名和密码不能为空'; $('regError').style.display=''; return; }
  try {
    const d = await fetch(BASE_URL+'/api/auth/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p,email:e})}).then(r=>r.json());
    if (d.token) {
      setToken(d.token);
      currentUser = d.user;
      updateUserUI();
      renderPage();
    } else {
      $('regError').textContent = d.error || '注册失败';
      $('regError').style.display='';
    }
  } catch(e) { $('regError').textContent='网络错误'; $('regError').style.display=''; }
}

function logout() {
  setToken('');
  currentUser = null;
  fieldVisibility = {};
  $('userDropdown').style.display = 'none';
  document.querySelectorAll('.admin-only').forEach(el => el.style.display = 'none');
  clearCaches();
  showLoginPage();
}

function showProfileModal() {
  if (!currentUser) return;
  showFormModal('个人信息',
    `<div class="mb-3">
      <label class="form-label small">用户名</label>
      <input class="form-control" value="${escHtml(currentUser.username)}" disabled>
    </div>
    <div class="mb-3">
      <label class="form-label small">角色</label>
      <input class="form-control" value="${currentUser.role === 'admin' ? '管理员' : '普通用户'}" disabled>
    </div>
    <div class="mb-3">
      <label class="form-label small">邮箱</label>
      <input class="form-control" id="pf_email" value="${escHtml(currentUser.email || '')}" placeholder="选填">
    </div>
    <hr>
    <div class="mb-2">
      <label class="form-label small">当前密码 <span class="text-danger">*</span></label>
      <input class="form-control" type="password" id="pf_curpw" placeholder="修改邮箱或密码需验证">
    </div>
    <div class="mb-2">
      <label class="form-label small">新密码 <span class="text-muted">（留空不修改）</span></label>
      <input class="form-control" type="password" id="pf_newpw" placeholder="至少3位">
    </div>`,
    '保存', async () => {
      const email = ($('pf_email')?.value || '').trim();
      const curpw = ($('pf_curpw')?.value || '').trim();
      const newpw = ($('pf_newpw')?.value || '').trim();
      const body = {email};
      if (newpw) { body.current_password = curpw; body.new_password = newpw; }
      const r = await api('/api/auth/profile', 'PUT', body);
      if (r.user) {
        currentUser = r.user;
        updateUserUI();
        hideModal();
        toast(r.message || '已更新', 'success');
      } else {
        toast(r.error || '修改失败', 'warning');
      }
    }, '取消', true
  );
}
