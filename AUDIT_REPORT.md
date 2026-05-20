# 报价系统全面代码审计报告

**审计日期：** 2026-05-20
**项目：** Quote Management System (Flask + Vue3 + SQLite)
**代码规模：** ~150KB 后端 + ~120KB 前端 + 3 模块文件

---

## A) 架构概览

### 技术栈
- **后端：** Flask + SQLAlchemy + SQLite + JWT + openpyxl + pypinyin
- **前端：** Vue3 (Composition API) + Vue Router + Bootstrap Icons + Vite
- **部署：** gunicorn + systemd + nginx 反代
- **AI集成：** 火山引擎豆包 Vision + DeepSeek V4 Flash（通过 Hermes Gateway）
- **数据库：** SQLite（单文件 quote.db）

### 目录结构
```
/tmp/quote-system/
├── app.py              # 主后端（2974行，124KB）— 单体路由文件
├── auth.py             # 认证 Blueprint
├── models.py           # SQLAlchemy 模型
├── extensions.py       # db 实例
├── quote-system.service # systemd 配置
├── quote.db            # SQLite 数据库
├── uploads/            # 上传图片
├── exports/            # 导出 Excel
├── frontend/
│   ├── src/
│   │   ├── App.vue           # 根组件（侧边栏 + 认证）
│   │   ├── main.js           # 入口
│   │   ├── router/index.js   # 路由 + 权限守卫
│   │   ├── composables/
│   │   │   ├── useApi.js     # 全局 API 调用 + 认证状态
│   │   │   └── useUtils.js   # 工具函数
│   │   ├── views/            # 7 个页面组件
│   │   └── components/       # 2 个模态框组件
│   ├── vite.config.js
│   └── package.json
└── .github/workflows/test.yml  # CI（但无实际测试文件）
```

### 前后端交互
- RESTful JSON API，JWT Bearer Token 认证
- 前端 `useApi.js` 封装 fetch + 401 自动跳转登录
- 图片以 BLOB 存入数据库 + 同时写文件系统，双存储
- Excel 导出由后端 openpyxl 生成，浏览器下载
- AI 对话通过 Hermes Gateway SSE 流式推送

---

## B) 后端分析

### B1. Flask App 结构

**问题：**
1. **单体巨文件：** app.py 2974行，所有路由、业务逻辑、Excel生成、AI集成混在一起。无蓝图拆分（仅 auth.py 是 Blueprint）。
2. **无统一错误处理：** 没有全局 error handler，每个路由自行 try/catch 或直接返回错误 JSON。错误格式不完全统一（有的 `{'error': ...}` 有的 `{'message': ...}`）。
3. **before_request 做认证：** 在 `check_auth()` 中对全部 `/api/` 路由做 JWT 校验，用白名单 `PUBLIC_ROUTES` 跳过公开路由。这种方式脆弱——新增公开路由容易漏加白名单。
4. **无请求日志中间件：** 没有 request/response 日志记录，排查问题困难。
5. **db.create_all() 在模块级执行：** 第2945行 `with app.app_context(): db.create_all()` — 每次导入 app.py 都会执行，无迁移管理。

### B2. 数据库模型设计

**优点：**
- Product/Quote/QuoteItem 关系清晰
- QuoteItem 有 CASCADE 删除
- DownloadLog 记录下载行为

**问题：**
1. **无数据库迁移工具：** 使用 `db.create_all()` 而非 Flask-Migrate/Alembic。任何 schema 变更都需要手动 SQL 或删库重建。
2. **SQLite 不适合多 worker：** gunicorn 多 worker + SQLite 存在并发写锁问题（WAL 模式未启用）。
3. **缺少索引：** Quote.created_by、Quote.status、QuoteItem.quote_id 无索引，数据量大时查询变慢。
4. **image_data BLOB 在 Product 表：** 图片二进制存在数据库中，导致列表查询时加载大量无用数据，严重影响性能。
5. **QuoteItem 缺少 discount_rate 字段：** 前端有折扣功能（`item.discount`），但数据库模型无此字段，折扣只在 Excel 中硬编码为 0%。
6. **datetime.now 作为默认值：** 使用 `default=datetime.now` 而非 `default=datetime.utcnow`，且 `datetime.now` 是函数引用但写法有 bug——应写 `default=datetime.now`（无括号），但如果在模型定义时执行了，所有记录会用相同时间。
7. **无软删除：** 产品和报价单直接物理删除，无法恢复。
8. **onupdate=datetime.now 问题：** 同样，`onupdate=datetime.now` 会在 update 时执行，但如果 SQLAlchemy 不追踪到变更，可能不触发。

### B3. API 设计

**RESTful 程度：中等偏下**

- 资源命名基本合理：`/api/products`, `/api/quotes`
- 但混用非 RESTful 端点：`/api/products/batch-delete`（应为 DELETE /api/products 批量）, `/api/products/toggle-active`
- 缺少 HATEOAS 或 API 版本化
- 输入校验不一致：创建产品有 XSS 检查和长度限制，创建报价单则完全没有校验
- **CRITICAL：** 报价单更新(PUT)直接用 `data.get('title')` 等，无类型校验、无长度限制

### B4. 安全性

#### CRITICAL 问题

1. **密码哈希使用 SHA256（弱算法）**
   - `auth.py:18-21` — `hash_password()` 使用 `SHA256(salt + password)`
   - SHA256 不是密码哈希算法，应使用 bcrypt/scrypt/argon2
   - 无迭代/工作因子，GPU 可每秒尝试数十亿次

2. **SSRF 攻击向量 — /api/download-image**
   - `app.py:705-758` — 从用户提供的 URL 下载图片
   - 无 URL 白名单、无内网 IP 过滤
   - 攻击者可访问 `http://169.254.169.254/`（AWS metadata）或内网服务
   - 虽然限定了 http/https，但不阻止 `http://127.0.0.1:5001/api/admin/settings`

3. **XSS — 报价单 HTML 预览**
   - `app.py:2429-2443` — `items_html` 拼接 HTML 时直接插入 `{item.product_name}` 等字段，无转义
   - 如果产品名被注入 `<script>alert(1)</script>`，预览页面将执行恶意脚本
   - 前端 `QuotePreviewModal.vue:120` 使用 `v-html="previewHtml"` 直接渲染

4. **JWT Secret 可能不安全**
   - `app.py:48` — 默认 `secrets.token_hex(32)` 每次重启生成新 secret
   - 这意味着重启后所有现有 token 失效，用户被强制登出
   - 如果通过环境变量设置但值太弱（如 `test`），也有风险

5. **产品图片路由无需认证**
   - `app.py:525-531` — `/api/products/<id>/image` 是公开路由
   - 任何人可遍历 id 获取所有产品图片

6. **管理员密码重置太弱**
   - `AdminView.vue:91` — 使用 `prompt()` 输入新密码，且最小长度仅 3 位
   - `app.py:285` — `len(new_pw) < 3` 即可

7. **AI System Prompt 泄露敏感信息**
   - `app.py:2583-2606` — `_GW_SYSTEM_PROMPT` 包含完整数据库路径、表结构、API 结构
   - 此 prompt 通过 `/api/admin/prompt` GET 端点暴露（虽然需管理员权限）

#### HIGH 问题

8. **CSRF 无防护**
   - 所有 POST/PUT/DELETE 请求仅靠 JWT Bearer Token
   - 但同时支持 `?token=xxx` URL 参数传递（app.py:323），这使 CSRF 成为可能
   - 如果用户点击恶意链接 `?token=valid_token`，可触发操作

9. **Token 通过 URL 传递**
   - `app.py:323` — `token = request.args.get('token', '')` 用于下载场景
   - URL 中的 token 会被浏览器历史、nginx access log、Referer 头记录
   - 应改用短时效的下载 ticket 或 cookie

10. **CORS 完全开放**
    - `app.py:34` — `CORS(app)` 无任何限制
    - 任何网站都可以跨域调用 API

11. **注册时无密码强度要求**
    - `auth.py:103` — 仅要求非空，最小 3 位
    - 无复杂度检查

12. **用户名无长度/格式限制**
    - `auth.py:105` — username 仅 trim()，无长度上限和字符限制
    - 可注入超长用户名或特殊字符

13. **下载日志仅记录 user_name（字符串）而非 user_id**
    - `DownloadLog.user_name` 是字符串，不可靠——用户改名后日志断裂

### B5. 性能

1. **N+1 查询（已部分优化）**
   - `list_quotes()` 已预加载创建者（users_map），这是好的
   - 但 `Product.to_dict()` 中每次都 `db.session.get(User, self.created_by)` 做单独查询（第30行）
   - `QuoteItem.to_dict()` 也可能单独查询 Product（第122行）

2. **拼音搜索全表扫描**
   - `list_products()` 和 `list_quotes()` 的拼音搜索：`all_products = query.all()` 然后内存过滤
   - 产品量大时（1000+）性能急剧下降
   - pypinyin 计算对每条记录都重复执行

3. **Excel 生成代码大量重复**
   - `export_quote_excel()` 和 `_build_excel()` 几乎完全相同的 ~120 行代码
   - 应提取为一个函数

4. **图片 BLOB 在列表 API 中加载**
   - `Product.to_dict()` 不含 image_data（好的），但 `preload_products_for_quote()` 加载所有产品含 BLOB
   - 产品列表页每次请求都查询所有分类和厂商（第454-463行），无条件缓存

5. **无分页上限检查**
   - `per_page` 参数无上限，用户可传 `per_page=100000` 导致 OOM
   - 前端虽限制到 500，但 API 无校验

6. **SQLite 并发写锁**
   - gunicorn 多 worker + SQLite = `database is locked` 错误
   - 未启用 WAL 模式

7. **导入时全量读入内存**
   - `/api/products/import` 将整个 Excel 读入内存，大文件可能 OOM

### B6. 代码质量

1. **2974 行单文件** — 违反单一职责，应拆分为多个 Blueprint（products_bp, quotes_bp, admin_bp, ai_bp）
2. **Excel 生成代码重复** — `export_quote_excel()` 和 `_build_excel()` 几乎完全相同
3. **硬编码路径** — `_debug_log()` 写死 `/opt/quote-system/gunicorn-error.log`
4. **硬编码 AI 模型列表** — `_AVAILABLE_MODELS` 写死在代码中
5. **`import` 散布各处** — `import re`, `import urllib.request` 等在函数内部导入
6. **bare except** — `app.py:334` `except:` 和 `app.py:2924` `except:` 无日志
7. **datetime.utcnow 已弃用** — Python 3.12+ 中 `datetime.utcnow()` 不推荐使用
8. **测试目录不存在** — CI 配置引用 `tests/test_*.py` 但目录和文件不存在
9. **dead code** — `_ocr_fallback()` 定义但未被任何代码调用
10. **magic numbers** — 文件大小限制、缓存时间等硬编码为数字

---

## C) 前端分析

### C1. 组件架构

**优点：**
- 使用 Vue3 Composition API + `<script setup>` — 现代写法
- `useApi` composable 提供全局认证状态
- Toast 组件通过 provide/inject 跨组件共享

**问题：**
1. **无全局状态管理** — 所有状态分散在各组件，无 Pinia/Vuex。跨组件数据（如 fieldVisibility）通过 useApi 的模块级 ref 模拟共享，但这是一种反模式。
2. **useApi 是模块级单例** — `authToken`, `currentUser` 是模块顶层 ref，所有组件共享同一实例。这在小项目中可行，但扩展性差。
3. **组件过于庞大** — ProductsView.vue 897行，包含搜索、分页、CRUD、图片处理、AI识别等全部逻辑，应拆分。

### C2. 路由与权限控制

1. **前端权限守卫仅客户端** — `router.beforeEach` 检查 `isLoggedIn()`，但仅基于 token 存在与否，不验证 token 有效性
2. **管理员路由靠 `meta.admin`** — 但对应的后端 API 依赖 `@require_admin`，前后端权限独立管理，不同步风险
3. **token 存储在 localStorage** — 易受 XSS 攻击窃取。应考虑 httpOnly cookie
4. **SPA catch-all** — 后端所有非 API 路径返回 index.html，合理

### C3. API 调用与错误处理

1. **useApi 的 api() 函数问题：**
   - 401 时自动清除 token 并返回 `{error: '请先登录'}`，但调用方还需再检查 `r.error`——双重检查
   - 非 JSON 响应（如文件下载）会 `r.json()` 报错
   - 无全局 loading 状态，每个组件自行管理
2. **无请求重试机制**
3. **无请求取消** — 组件卸载时 pending 请求继续执行

### C4. XSS 防护与输入校验

1. **CRITICAL: v-html 渲染预览 HTML** — `QuotePreviewModal.vue:120` 使用 `v-html="previewHtml"`，且后端生成的 HTML 未转义（见 B4.3）
2. **前端 escHtml 函数未被广泛使用** — `useUtils.js` 定义了 `escHtml` 但大多数地方未调用
3. **输入校验不一致** — 电话号码做了正则过滤（`NewQuoteView.vue:311`），但其他字段无校验
4. **产品名称 maxlength=20** — 前端限制了，但后端也有检查，这是好的

### C5. UI/UX 问题

1. **密码重置使用 prompt()** — `AdminView.vue:91` — 体验差且不安全，浏览器可记住输入
2. **删除确认使用 confirm()** — 原生对话框，无法自定义样式
3. **无空状态引导** — DashboardView 在无数据时缺少引导
4. **IME 处理** — 拼音搜索有 IME composition 事件处理，这是好的
5. **分页器逻辑重复** — QuotesView、ProductsView、AdminView 各自实现了几乎相同的分页逻辑
6. **ProductsView per-page 500="全部"** — 可能加载大量数据

---

## D) 部署与运维

### D1. systemd 服务配置

```ini
[Service]
ExecStart=/opt/quote-system/venv/bin/gunicorn ...
WorkingDirectory=/opt/quote-system
```
- **问题：** 无 `Restart=always` 或 `Restart=on-failure`
- 无 `StandardOutput` / `StandardError` 日志配置
- 无资源限制（MemoryMax, CPUQuota）

### D2. CI/CD

- **test.yml 引用不存在的测试文件** — `tests/test_auth.py` 等 6 个文件不存在，CI 必定失败
- 无构建/部署步骤，仅测试
- 无前端构建验证

### D3. 数据库迁移

- **无迁移工具** — 使用 `db.create_all()` 无法处理 schema 变更
- 生产环境任何模型修改都需要手动 `sqlite3` 执行 ALTER TABLE
- 无备份策略

### D4. 日志与监控

- 无结构化日志
- `_debug_log()` 硬编码写文件到特定路径
- 无健康检查端点
- 无 Prometheus/OpenTelemetry 指标
- 无 Sentry 等错误追踪

---

## E) 按严重程度列出所有问题

### Critical（5个）

| # | 问题 | 位置 |
|---|------|------|
| 1 | 密码哈希使用 SHA256，无工作因子 | auth.py:18-21 |
| 2 | SSRF — /api/download-image 无内网过滤 | app.py:705-758 |
| 3 | XSS — 报价单 HTML 预览拼接未转义 | app.py:2429-2443, QuotePreviewModal.vue:120 |
| 4 | Token 通过 URL 参数传递（CSRF + 泄露） | app.py:323 |
| 5 | CORS 完全开放 | app.py:34 |

### High（10个）

| # | 问题 | 位置 |
|---|------|------|
| 6 | 产品图片端点无需认证，可遍历 | app.py:525-531 |
| 7 | 管理员密码重置用 prompt()，最小3位 | AdminView.vue:91, app.py:285 |
| 8 | 注册无密码强度要求 | auth.py:103 |
| 9 | 用户名无长度/格式校验 | auth.py:105 |
| 10 | JWT Secret 重启后变化，所有用户登出 | app.py:48 |
| 11 | SQLite 并发写锁（多 worker） | app.py + gunicorn |
| 12 | per_page 无上限校验（OOM 风险） | app.py:381 |
| 13 | Excel 生成代码重复120行 | app.py:1966-2173 vs 2232-2353 |
| 14 | 下载日志用 user_name 字符串而非 user_id | models.py:148 |
| 15 | QuoteItem 缺 discount_rate 字段 | models.py:103-116 |

### Medium（15个）

| # | 问题 | 位置 |
|---|------|------|
| 16 | 无数据库迁移工具 | 全局 |
| 17 | 拼音搜索全表内存过滤 | app.py:413-441, 1714-1740 |
| 18 | 图片 BLOB 存数据库影响性能 | models.py:20 |
| 19 | 2974 行单体 app.py | app.py |
| 20 | before_request 白名单认证脆弱 | app.py:310-335 |
| 21 | Product.to_dict() N+1 查询 creator | models.py:29-31 |
| 22 | bare except 无日志 | app.py:334, 2924 |
| 23 | datetime.now vs utcnow 混用 | models.py:24-25 |
| 24 | 前端无全局状态管理 | 全局前端 |
| 25 | ProductsView 897 行过于庞大 | ProductsView.vue |
| 26 | 分页逻辑在3个组件中重复 | QuotesView/ProductsView/AdminView |
| 27 | 测试目录不存在，CI 必定失败 | tests/ |
| 28 | OCR API key 硬编码 'helloworld' | app.py:800 |
| 29 | 无健康检查端点 | 全局 |
| 30 | 无请求/响应日志 | 全局 |

### Low（10个）

| # | 问题 | 位置 |
|---|------|------|
| 31 | _ocr_fallback() dead code | app.py:820-840 |
| 32 | import 语句散布函数内部 | 多处 |
| 33 | 硬编码 /opt/quote-system 路径 | app.py:958 |
| 34 | 前端无请求取消机制 | useApi.js |
| 35 | 删除确认使用原生 confirm() | 多个组件 |
| 36 | API 错误格式不统一 | 全局后端 |
| 37 | 前端无前端测试 | 全局前端 |
| 38 | package.json 无 lock 文件 | frontend/ |
| 39 | test.yml 无前端构建步骤 | .github/ |
| 40 | 无 API 版本化 | 全局后端 |

---

## F) 优化建议（按优先级排序）

### P0 — 立即修复（安全）

1. **替换密码哈希为 bcrypt/argon2** — 安装 `bcrypt` 包，修改 `hash_password()` 和 `verify_password()`
2. **修复 SSRF** — 在 `/api/download-image` 中过滤内网 IP（127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16），或使用白名单域名
3. **修复 XSS** — 后端 `preview_quote_html()` 必须对所有用户输入做 `html.escape()`，前端对 v-html 内容做sanitize
4. **移除 URL token 参数** — 改用短期下载 ticket 或设置 httpOnly cookie
5. **限制 CORS** — `CORS(app, origins=['https://your-domain.com'])`
6. **JWT Secret 持久化** — 确保通过环境变量设置固定值，或在启动时生成并写入文件

### P1 — 短期修复（1-2周）

7. **启用 SQLite WAL 模式** — 在 db 初始化后执行 `PRAGMA journal_mode=WAL`
8. **添加 per_page 上限** — `per_page = min(per_page, 200)`
9. **用户名/密码加强校验** — 用户名3-30字符字母数字，密码至少8位含字母数字
10. **合并重复的 Excel 生成代码** — 提取 `_build_excel()` 为唯一实现
11. **拆分 app.py** — products_bp, quotes_bp, admin_bp, ai_bp 四个 Blueprint
12. **添加 QuoteItem.discount_rate 字段** — 数据库迁移 + API 支持
13. **添加 Flask-Migrate** — `flask db init/migrate/upgrade`
14. **产品图片端点添加认证** — 或改用签名 URL

### P2 — 中期优化（1-2月）

15. **拼音搜索优化** — 预计算拼音字段存入数据库，或使用 FTS5 全文搜索
16. **图片 BLOB 改为纯文件系统存储** — 删除数据库中的 image_data 列，仅存 URL
17. **添加全局错误处理器** — `@app.errorhandler(404)` 等
18. **添加请求日志中间件** — 记录 method/path/status/elapsed
19. **前端提取分页 composable** — `usePagination()` 复用逻辑
20. **前端拆分 ProductsView** — 提取 ProductFormModal、ProductDetailModal 为独立组件
21. **添加健康检查端点** — `/api/health` 返回 DB 连接状态
22. **编写实际测试** — 补全 tests/ 目录下的测试文件
23. **修复 CI** — 确保测试能运行

### P3 — 长期演进

24. **考虑 PostgreSQL 替换 SQLite** — 如果并发用户 > 10
25. **添加 Pinia 状态管理** — 替代 useApi 中的模块级 ref
26. **token 存储改为 httpOnly cookie** — 减少 XSS 窃取风险
27. **添加 API 限流** — Flask-Limiter 防止暴力破解
28. **添加审计日志** — 关键操作（删除、权限变更）记录
29. **结构化日志** — 使用 structlog 替代 print/手写文件
30. **前端添加 E2E 测试** — Playwright/Cypress

---

**总结：** 该系统功能完整，代码可运行，但存在多个 Critical 安全问题（弱密码哈希、SSRF、XSS、Token 泄露），以及单体架构导致的可维护性差。建议按 P0→P1→P2 顺序修复，尤其是安全漏洞应立即处理。
