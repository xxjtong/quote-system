# 报价管理系统 (Quote Management System)

> Flask + SQLite + Vue 3 SPA — 产品管理、报价单生成、Excel 导入导出、火山引擎豆包智能识别、AI 对话助手、多用户认证、拼音搜索

[![Version](https://img.shields.io/badge/version-2.1.0-blue)](version.txt)
[![Python](https://img.shields.io/badge/python-3.11+-green)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-orange)](LICENSE)

---

## 目录

- [功能概览](#功能概览)
- [技术架构](#技术架构)
- [数据模型](#数据模型)
- [前提条件](#前提条件)
- [安装步骤](#安装步骤)
- [版本号管理](#版本号管理)
- [REST API](#rest-api)
- [AI 对话](#ai-对话)
- [前端功能详解](#前端功能详解)
- [前端架构](#前端架构)
- [Excel 导入导出](#excel-导入导出)
- [智能识别](#智能识别)
- [项目结构](#项目结构)
- [开发约定](#开发约定)

---

## 功能概览

| 模块 | 功能 |
|------|------|
| 🔐 **认证系统** | JWT 登录/注册、管理员面板、字段可见性控制、注册开关、个人信息修改、全站鉴权门 |
| 📦 **产品管理** | CRUD、拼音/缩写智能搜索、分类/厂商筛选、批量删除、图片上传预览、产品上线/下线、图片 Blob 内嵌存储 |
| 📊 **概览仪表盘** | 产品总数/报价单/下载/总金额统计卡片、最近报价单、快速操作 |
| 📝 **报价单** | 创建/编辑/删除、搜索过滤、分页、批量删除、状态流转、每行备注、利润概览、客户聚合、台湾税率支持、折扣率 |
| 📥 **Excel 导入** | 多 Sheet 导入、列名智能映射、嵌入图片提取、自动同步 SKU/规格、6 子函数低耦合实现 |
| 📤 **Excel 导出** | 格式化报价单导出、图片嵌入、自定义公司名/页脚、下载计数统计 |
| 👁️ **预览** | HTML 预览报价单（Blob URL + token 鉴权） |
| 📧 **邮件** | SMTP 配置，一键发送报价单 Excel 附件 |
| 🔍 **智能识别** | 粘贴文本自动解析产品信息、豆包 Vision 图片识别、DeepSeek V4 Flash 文本解析、可编辑识别结果、发票 OCR → 批量更新成本价 |
| 🤖 **AI 助手** | Dashboard 内嵌 AI 产品助手，SSE 流式输出、快捷回复（规则+LLM 异步补发）、产品卡片、对比表、一键创建报价单（含产品条目自动填入）、对话历史、模型选择与切换、自定义 Prompt |
| 🎨 **UI** | 统一页面风格、组件化架构（5 个独立子组件）、一致样式体系 |
| ⚡ **性能优化** | 缓存优先渲染、产品选择器版本指纹、前端本地拼音过滤、DB-based 速率限制（多 worker 共享） |

---

## 技术架构

```
┌──────────────┐     ┌──────────┐     ┌──────────────┐     ┌────────────────┐
│   浏览器      │────▶│  nginx   │────▶│   Gunicorn   │     │ Hermes Gateway │
│  Bootstrap 5  │     │  :443    │     │  2 workers   │     │    :8642        │
│  Vue 3 SPA    │     │  proxy   │     │  :5001       │     │  AI 会话池      │
└──────────────┘     └──────────┘     └──────┬───────┘     └──────┬─────────┘
                                             │                    │
                                        ┌────▼───────┐     ┌─────▼─────────┐
                                        │   Flask     │────▶│ Responses API  │
                                        │ 4 Blueprints│     │ 会话存储       │
                                        │ JWT Auth    │     │ 工具调用过滤    │
                                        │ SQLAlchemy  │     └───────────────┘
                                        │ Migrate     │
                                        └────┬───────┘
                                             │
                                        ┌────▼───────┐
                                        │  SQLite     │
                                        │ quote.db    │
                                        └────────────┘
```

| 层 | 技术 | 说明 |
|---|------|------|
| Web 服务器 | nginx | 反向代理，TLS 终端，路径 `/quote/` → Gunicorn |
| 应用服务器 | Gunicorn | 2 worker 进程（`--preload`），绑定 `127.0.0.1:5001` |
| 后端框架 | Flask + SQLAlchemy | 4 Blueprint 拆分（products / quotes / admin / ai）+ auth 独立模块 |
| DB 迁移 | Flask-Migrate (Alembic) | 替代手动 ALTER TABLE，版本化 schema 变更 |
| AI 引擎 | Hermes Gateway | Responses API（`/v1/responses`），服务端会话存储，工具调用过滤 |
| 认证 | JWT (PyJWT) | 无状态 token，bcrypt 密码哈希，自动续签 |
| 数据库 | SQLite | 单文件，零配置 |
| 前端 | Vue 3 SPA | Composition API + Vite 构建 + Vue Router 历史模式 + Bootstrap 5 CSS |
| 拼音 | pypinyin | 后端拼音搜索（DB LIKE）+ 前端本地拼音过滤 |
| Excel | openpyxl | 读写 `.xlsx`，含格式化 |
| 视觉识别 | 火山引擎豆包 | Seed Lite 视觉模型，直出 JSON |
| 降级 OCR | OCR.space API | 免费 tier 兜底 |

---

## 数据模型

### User（用户）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增主键 |
| `username` | VARCHAR(50) | 用户名（唯一，必填） |
| `password_hash` | VARCHAR(128) | bcrypt 密码哈希 |
| `email` | VARCHAR(200) | 邮箱（选填） |
| `role` | VARCHAR(10) | 角色：`admin` / `user` |
| `is_active` | BOOLEAN | 账户启用状态，默认 True |
| `created_at` | DATETIME | 注册时间 |
| `last_login` | DATETIME | 最后登录时间 |

### Product（产品）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增主键 |
| `name` | VARCHAR(200) | 产品名称（必填，索引） |
| `sku` | VARCHAR(100) | SKU 编码，自动同步 `spec` |
| `category` | VARCHAR(100) | 分类标签（索引） |
| `spec` | VARCHAR(500) | 规格型号（主型号字段） |
| `unit` | VARCHAR(20) | 计量单位 |
| `price` | FLOAT | 销售单价 |
| `cost_price` | FLOAT | 成本价 |
| `supplier` | VARCHAR(200) | 供应商/厂商 |
| `function_desc` | TEXT | 功能描述（对客户可见，导出） |
| `remark` | TEXT | 内部备注（仅内部可见，不导出） |
| `image_url` | VARCHAR(500) | 产品图片路径 |
| `image_data` | BLOB | 图片二进制数据（Blob 内嵌存储） |
| `image_mime` | VARCHAR(30) | 图片 MIME 类型 |
| `is_active` | BOOLEAN | 上下线状态，默认 True |
| `pinyin_search` | TEXT | 预计算拼音索引（全拼+首字母，DB LIKE） |
| `created_by` | INTEGER FK | 创建者 User ID |
| `created_at` | DATETIME | 创建时间 |
| `updated_at` | DATETIME | 更新时间（自动刷新） |

### Quote（报价单）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 主键 |
| `title` | VARCHAR(200) | 报价单标题 |
| `client` | VARCHAR(200) | 客户名称 |
| `contact` | VARCHAR(100) | 联系人 |
| `phone` | VARCHAR(50) | 联系电话 |
| `quote_date` | VARCHAR(20) | 报价日期 |
| `valid_days` | INTEGER | 有效期（天），默认 15 |
| `tax_rate` | FLOAT | 税率(%)，默认 0 |
| `status` | VARCHAR(20) | 状态：draft/sent/confirmed/rejected |
| `total_amount` | FLOAT | 合计金额 |
| `download_count` | INTEGER | 导出下载次数 |
| `created_by` | FK → User | 创建者 |
| `remark` | TEXT | 备注 |
| `items` | relationship | 一对多 → QuoteItem |

### QuoteItem（报价单明细行）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 主键 |
| `quote_id` | FK → Quote | 所属报价单，级联删除 |
| `product_id` | FK → Product | 关联产品（可选） |
| `product_name` | VARCHAR(200) | 产品名称快照 |
| `product_sku` | VARCHAR(100) | SKU 快照 |
| `product_spec` | VARCHAR(500) | 规格型号快照 |
| `product_unit` | VARCHAR(20) | 单位快照 |
| `quantity` | INTEGER | 数量，默认 1 |
| `unit_price` | FLOAT | 单价 |
| `amount` | FLOAT | 小计 = 数量 × 单价 |
| `discount_rate` | FLOAT | 折扣率（%） |
| `remark` | VARCHAR(500) | 行备注 |
| `sort_order` | INTEGER | 排序序号 |

### FieldSetting（字段可见性）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 主键 |
| `field_name` | VARCHAR(50) | 字段名 |
| `label` | VARCHAR(100) | 显示标签 |
| `user_visible` | BOOLEAN | 普通用户是否可见 |

### SystemSetting（系统设置）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 主键 |
| `key` | VARCHAR(100) UNIQUE | 设置键 |
| `value` | TEXT | 设置值 |

### DownloadLog / DownloadTicket / AIChatSession / AIUsageLog

| 模型 | 用途 |
|------|------|
| `DownloadLog` | 下载记录（quote_id, user_name, downloaded_at） |
| `DownloadTicket` | 一次性下载凭证（ticket, user_id, expires_at） |
| `AIChatSession` | AI 会话持久化（user_id, prompt_hash） |
| `AIUsageLog` | AI 使用记录（user_id, action, model, elapsed, success, error）— 也用于速率限制 |

---

## 前提条件

- Python 3.11+
- Node.js 18+（前端构建）
- nginx（生产环境反向代理）
- systemd（用于服务管理）
- Hermes Gateway（AI 对话功能，可选）

---

## 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/xxjtong/quote-system.git /opt/quote-system
cd /opt/quote-system

# 2. 安装 Python 依赖
pip3 install --user --break-system-packages -r requirements.txt

# 3. 生成 JWT Secret
python3 -c "import secrets; print(secrets.token_hex(32))"
# 将输出填入 step 6 的 QUOTE_JWT_SECRET

# 4. 初始化数据库 + 运行迁移
export QUOTE_JWT_SECRET="你生成的secret"
export QUOTE_ADMIN_PASSWORD="你的管理员密码"   # 留空则自动生成随机密码写入.admin_password
python3 -c "
from app import app, db
with app.app_context():
    db.create_all()
    print('数据库已创建')
"
# 标记当前 schema 为最新迁移版本
export FLASK_APP=app.py
python3 -m flask db stamp head

# 5. 构建前端
cd frontend
npm install
npm run build
cd ..

# 6. 创建上传/导出目录
mkdir -p uploads/images exports

# 7. 安装 systemd 服务（编辑 Environment 填入 JWT secret 和管理员密码）
sudo cp quote-system.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now quote-system

# 8. 配置 nginx（示例）
# location /quote/ {
#     proxy_pass http://127.0.0.1:5001/;
#     proxy_set_header Host $host;
#     client_max_body_size 50m;
# }
# sudo systemctl reload nginx
```

---

## 版本号管理

```bash
echo "2.1.0" > version.txt
sudo systemctl restart quote-system
```

版本号存储在 `version.txt`，通过 `GET /api/version` 公开读取。

---

## REST API

Base URL: `http://127.0.0.1:5001`

> ⚠️ 除公开路由外，所有 API 需 `Authorization: Bearer ***` 请求头。

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/auth/login` | 登录 `{username, password}` → `{token, user}` |
| `POST` | `/api/auth/register` | 注册 `{username, password, email?}` |
| `GET` | `/api/auth/registration-status` | 注册开关状态 |
| `GET` | `/api/session` | 验签/续签 token（自动返回 `X-New-Token`） |
| `PUT` | `/api/auth/profile` | 修改个人信息 `{email?, current_password?, new_password?}` |
| `GET` | `/api/auth/me` | 当前用户信息 |

### 产品

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/products` | 列表（`page`, `per_page`, `search`, `category`, `supplier`, `sort_by`, `sort_order`） |
| `GET` | `/api/products/<id>` | 详情 |
| `GET` | `/api/products/<id>/image` | 产品图片（支持 `?token=` query param 鉴权） |
| `POST` | `/api/products` | 新增 |
| `PUT` | `/api/products/<id>` | 编辑 |
| `DELETE` | `/api/products/<id>` | 删除 |
| `POST` | `/api/products/batch-delete` | 批量删除 `{ids: [1,2]}` |
| `PUT` | `/api/products/<id>/toggle-active` | 产品上下线切换 |
| `POST` | `/api/products/import` | 导入 Excel（multipart） |
| `GET` | `/api/products/export-template` | 下载导入模板 |
| `POST` | `/api/products/upload-image` | 上传图片（自动压缩 ≤100KB） |
| `POST` | `/api/products/ocr` | 图片 OCR 识别（降级兜底） |
| `POST` | `/api/products/recognize` | 文本智能解析 + 图片豆包 Vision 识别 |
| `POST` | `/api/download-image` | 从 URL 下载图片并压缩保存 |
| `POST` | `/api/products/ocr-costs` | 发票 OCR 识别 |
| `POST` | `/api/products/batch-costs` | 批量更新成本价（管理员） |
| `GET` | `/api/products/version` | 产品数据版本指纹 |

### 报价单

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/quotes` | 列表（含 `search`, `status` 筛选） |
| `GET` | `/api/quotes/<id>` | 详情（含 items + 利润 + `tax_rate`） |
| `POST` | `/api/quotes` | 新建（含 `tax_rate`, 行 `remark`, `discount_rate`） |
| `PUT` | `/api/quotes/<id>` | 编辑 |
| `DELETE` | `/api/quotes/<id>` | 删除 |
| `DELETE` | `/api/quotes/batch` | 批量删除 |
| `PATCH` | `/api/quotes/<id>/status` | 切换状态 |
| `GET` | `/api/quotes/<id>/export-excel` | 导出 Excel（递增下载计数） |
| `GET` | `/api/quotes/<id>/preview` | HTML 预览 |
| `POST` | `/api/quotes/<id>/send-email` | 发送邮件 |
| `GET` | `/api/quotes/stats` | 客户维度聚合统计 |

### 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/admin/users` | 用户列表（管理员） |
| `PUT` | `/api/admin/users/<id>` | 修改用户 |
| `DELETE` | `/api/admin/users/<id>` | 删除用户 |
| `PUT` | `/api/admin/users/<id>/password` | 修改用户密码（管理员） |
| `GET` / `PUT` | `/api/admin/fields` | 字段可见性配置 |
| `GET` / `PUT` | `/api/admin/registration` | 注册开关 |
| `GET` / `PUT` | `/api/admin/settings` | 系统设置 |
| `GET` / `PUT` | `/api/admin/prompt` | AI 系统提示词 |
| `GET` | `/api/download-logs` | 下载记录列表 |
| `GET` | `/api/download-logs/stats` | 下载统计 |

### 通用

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/version` | 系统版本号（公开） |
| `GET` | `/api/health` | 健康检查（公开，含 DB 状态） |

---

## AI 对话

### API

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/chat` | AI 对话 — `{input, stream: true/false, model?}`，SSE 流式输出 |
| `GET` | `/api/ai/token` | 获取当前用户 JWT token（AI 代理用） |
| `GET` | `/api/ai/my-usage` | 当前用户 AI 使用统计 |
| `GET` | `/api/admin/prompt` | 获取 AI 系统提示词（管理员） |
| `PUT` | `/api/admin/prompt` | 更新提示词 + 清除会话缓存 |

### 架构

Flask `/api/chat` → Hermes Gateway `POST /v1/responses`（按用户隔离会话）。

**流式模式：** `stream: true` → SSE 透传 Gateway 事件流，前端逐字渲染。

**身份注入：** Prompt 第一行身份声明自动注入每条用户消息头部。Prompt 变更时 hash 对比 → 清空 AIChatSession → 重新注入。

**速率限制：** 基于 AIUsageLog DB 查询（非进程级变量），多 worker 共享，默认每用户每分钟 5 次。

### 快捷回复（quick_replies）

AI 回复底部自动生成快捷回复按钮，两层策略：

1. **规则提取（同步）**：正则匹配「方案A/B/C」格式、"还是"关键词、问句 pattern
2. **LLM 异步补发**：规则未提取到时，调用 LLM 生成选项，通过 SSE `quick_replies` 事件补发

### 一键创建报价单

AI 对话中提及产品时，前端提取 `product_ids`，底部出现「一键创建报价单」按钮：

- **有产品条目** → 跳转新建报价单页面并自动填入匹配产品作为 items
- **无产品条目** → 跳转空白新建报价单页面（无产品添加）

条件：AI 回复中必须包含可提取的产品引用（`product_id` 在系统中存在），否则跳转后无条目。

---

## 前端功能详解

### 认证系统

- **登录页**：用户名 + 密码，支持注册开关
- **注册页**：用户名 + 密码 + 邮箱（选填）
- **Token 管理**：`useApi` composable 统一管理，自动附带 `Authorization` 头
- **自动续签**：`/api/session` 返回新 token 时自动更新
- **401 处理**：token 过期自动跳转登录页
- **管理员面板**：用户管理、角色切换、改密、字段可见性、注册开关
- **个人信息**：右上角下拉 → 修改邮箱/密码

### 概览仪表盘

- **统计卡片**：产品总数、报价单总数、总下载次数
- **最近报价单**：最新 10 条
- **AI 产品助手**：独立 AiChat 组件（660 行），SSE 流式逐字渲染、快捷回复、产品卡片、对比表、一键创建报价单、对话历史、模型选择/切换
- **快捷操作**：新建报价单、导入产品

### 产品管理

**列表页（ProductTable 组件）：** 表格 + 搜索 + 分类/厂商筛选 + 分页 + 排序 + 批量删除 + 图片预览

**新增/编辑（ProductFormModal 组件）：** 完整表单 + 内嵌 SmartRecognition 组件 + 图片上传/粘贴

**智能识别（SmartRecognition 组件）：** 文本/图片粘贴识别 → 可编辑结果 → 确认填入表单

**详情弹窗（ProductDetailModal 组件）：** 全字段展示 + 图片查看

### 报价单管理

**列表页：** 表格 + 状态切换 + 预览/导出/编辑/删除/批量删除

**新建/编辑：** 头部信息 + 产品选择器 + 明细行（数量/单价/金额/折扣率/备注）+ 利润概览

**预览（QuotePreviewModal 组件）：** HTML 渲染 + 图片嵌入 + 导出/邮件

**产品选择器：** 模态框 + 即时搜索 + 分类过滤 + 智能缓存（版本指纹）

---

## 前端架构

```
frontend/src/
├── App.vue              # 根组件 + 导航 + 路由守卫
├── router/index.js      # Vue Router 历史模式
├── style.css            # 全局样式
├── composables/
│   ├── useApi.js        # 统一 API 调用 + BASE_URL + authToken + isAdmin
│   ├── usePagination.js # 分页 composable（解构 totalItems）
│   └── useUtils.js      # 工具函数（formatMoney 等）
├── components/
│   ├── AiChat.vue           # AI 对话（660行）SSE流式/快捷回复/历史/对比/一键报价
│   ├── ProductTable.vue     # 产品表格（350行）搜索/分页/排序/批量操作
│   ├── ProductFormModal.vue # 产品表单（302行）新增/编辑+SmartRecognition
│   ├── SmartRecognition.vue # 智能识别（292行）文本/图片解析+可编辑结果
│   ├── QuotePreviewModal.vue# 报价单预览（169行）HTML渲染+导出+邮件
│   ├── ProductDetailModal.vue#产品详情（71行）全字段+图片
│   └── ToastMessage.vue     # Toast 通知（44行）
└── views/
    ├── DashboardView.vue    # 仪表盘（138行）统计卡片+AiChat
    ├── ProductsView.vue     # 产品管理（110行）编排4个子组件
    ├── QuotesView.vue       # 报价单列表（330行）
    ├── NewQuoteView.vue     # 新建/编辑报价单（506行）
    ├── AdminView.vue        # 管理面板（367行）
    ├── LoginView.vue        # 登录/注册（132行）
    └── ImportView.vue       # Excel 导入（84行）
```

- `<script setup>` + Composition API，状态用 `reactive()`/composables
- Vite 开发服务器（HMR），`base: '/quote/'`
- API 调用统一通过 `useApi.js` 的 `api()` 封装（自动 token/401 拦截/JSON 解析）
- SSE 流式和 blob 下载保留裸 fetch（非 JSON 响应）

---

## Excel 导入导出

### 导入列名映射

| Excel 表头 | 数据库字段 | 备注 |
|-----------|-----------|------|
| 产品名称 / 名称 / 品名 | `name` | |
| 规格型号 / 规格 / 型号 / SKU | `spec` | `sku` 自动同步 |
| 功能描述 | `function_desc` | |
| 备注 / 说明 | `remark` | 内部备注 |
| 供应商 / 厂商 | `supplier` | |
| 单价 / 价格 / 售价 | `price` | |
| 成本价 / 成本 / 进价 | `cost_price` | |
| 单位 | `unit` | |

### 导入功能实现（6 子函数）

| 函数 | 职责 |
|------|------|
| `import_products()` | 路由入口，加载 workbook |
| `_import_all_sheets(wb)` | 遍历 Sheet 编排 |
| `_parse_excel_header(ws, rows, header_row_idx)` | 表头解析 + 嵌入图片索引 |
| `_detect_supplier_col(rows, header_row_idx)` | 供应商列回退检测 |
| `_extract_embedded_image(emb_img)` | Excel 嵌入图片提取+压缩 |
| `_process_import_row(row, row_idx, col_idx, ...)` | 单行→Product 对象 |

- 支持多 Sheet 导入（Sheet 名 = 分类）
- 嵌入图片自动提取、压缩、保存
- 供应商空值继承上行
- 规格型号自动同步 SKU

### 导出模板

`GET /api/products/export-template` — 下载含标准表头的空 `.xlsx`

### 报价单导出

`GET /api/quotes/<id>/export-excel` — 格式化 Excel，含报价头、明细表、合计行、产品图片、下载计数

---

## 智能识别

### 三层识别管道

`POST /api/products/recognize` — 支持粘贴图片或文字，自动提取产品信息。

```
图片 ──→ 豆包 Vision ──────────→ source: doubao-vision
              │ 失败
              ▼
        OCR.space ──→ DeepSeek V4 Flash ──→ source: deepseek-parse
                          │ 失败
                          ▼
                    正则解析 ──→ source: regex-parse

文字 ──→ DeepSeek V4 Flash ──→ source: deepseek-parse
              │ 失败
              ▼
        正则解析 ──→ source: regex-parse
```

| 层级 | 组件 | 位置 | 说明 |
|------|------|------|------|
| 1 | 豆包 Vision | product_utils.py | 火山引擎视觉模型，图片直出 JSON |
| 2 | DeepSeek V4 Flash | product_utils.py | LLM 文本解析（via Gateway） |
| 3 | 正则解析 | product_utils.py | 规则兜底，7 步流水线 |

### 识别结果

- 可编辑输入框呈现（8 个字段）
- 来源标签：`豆包 Vision` / `DeepSeek V4 Flash` / `正则解析`
- 可折叠"模型返回原始数据"区域
- 修正后确认填入表单

### 环境变量

| 变量 | 说明 |
|------|------|
| `VOLCENGINE_API_KEY` | 火山引擎豆包 API Key |
| (Gateway :8643) | Hermes Gateway 提供 DeepSeek 推理 |

---

## 项目结构

```
/opt/quote-system/
├── app.py                     # Flask 应用（387行）4 Blueprint 注册 + DB 初始化
├── extensions.py              # db = SQLAlchemy() 单例
├── models.py                  # 10 个数据模型（243行）
├── products_bp.py             # 产品 Blueprint（971行）CRUD + 导入 + 识别
├── quotes_bp.py               # 报价单 Blueprint（886行）CRUD + 导出 + 预览 + 邮件
├── ai_bp.py                   # AI Blueprint（568行）SSE 对话 + 速率限制
├── admin_bp.py                # 管理 Blueprint（273行）用户/设置/Prompt
├── auth.py                    # 认证模块（219行）JWT 登录/注册/续签
├── utils.py                   # 通用工具（64行）debug_log/log_ai_usage/safe_number/pinyin
├── product_utils.py           # 产品工具（516行）识别/图片/解析/压缩
├── migrations/                # Flask-Migrate (Alembic) 迁移目录
├── frontend/                  # Vue 3 SPA
│   ├── src/                   # 源码
│   │   ├── views/             # 7 个页面组件
│   │   ├── components/        # 7 个独立子组件
│   │   ├── composables/       # 3 个 composable
│   │   └── router/            # Vue Router
│   ├── dist/                  # Vite 构建产物
│   └── vite.config.js         # Vite 配置
├── tests/                     # pytest 测试套件（208 项，138 API + 70 边界）
│   ├── conftest.py            # fixtures
│   ├── test_auth.py           # 认证
│   ├── test_products.py       # 产品
│   ├── test_quotes.py         # 报价单
│   ├── test_admin.py          # 管理
│   └── ...
├── quote-system.service       # systemd 服务配置
├── version.txt                # 版本号
├── requirements.txt           # Python 依赖
├── CHANGELOG.md               # 更新日志
├── README.md                  # 本文件
├── uploads/images/            # 产品图片
├── exports/                   # 导出的 Excel
└── quote.db                   # SQLite 数据库（不入版本控制）
```

---

## 开发约定

| 约定 | 说明 |
|------|------|
| `function_desc` ≠ `remark` | 前者对客户可见（导出），后者仅内部 |
| `sku` = `spec` | 写入时自动同步 |
| 搜索匹配 | `name` + `spec` + `supplier` + `function_desc` + 拼音（DB LIKE `pinyin_search`） |
| 搜索防抖 | 500ms，IME 组字中不触发 |
| API 调用 | 统一通过 `useApi.js` 的 `api()` 封装 |
| 修改 Vue 组件 | `cd frontend && npm run build && sudo systemctl restart quote-system` |
| 修改后端 Python | `sudo systemctl restart quote-system` |
| DB schema 变更 | 使用 `flask db migrate` + `flask db upgrade` |
| 版本号 | `echo "x.x.x" > version.txt` + 重启 |
| 图片压缩 | PIL 自动 ≤100KB，透明 PNG 贴白底转 JPG |
| 速率限制 | 基于 AIUsageLog DB 查询，多 worker 共享 |
| 管理员密码 | 环境变量 `QUOTE_ADMIN_PASSWORD`，空值则随机生成写入 `.admin_password` |
| AI prompt | 变更后 hash 对比 → 自动清空会话 → 重新注入 |

### 常用命令

```bash
# 服务管理
sudo systemctl restart quote-system
sudo systemctl status quote-system

# 数据库迁移
export FLASK_APP=app.py
flask db migrate -m "add new column"
flask db upgrade

# 更新版本号
echo "2.1.0" > version.txt && sudo systemctl restart quote-system

# 推送到 GitHub
cd /opt/quote-system
git add -A && git commit -m "描述" && git push
```

---

## License

MIT
