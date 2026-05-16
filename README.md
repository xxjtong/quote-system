# 报价管理系统 (Quote Management System)

> Flask + SQLite + Vue 3 SPA — 产品管理、报价单生成、Excel 导入导出、火山引擎豆包智能识别、多用户认证、拼音搜索

[![Version](https://img.shields.io/badge/version-1.6.0-blue)](version.txt)
[![Python](https://img.shields.io/badge/python-3.11+-green)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-orange)](LICENSE)

---

## 目录

- [功能概览](#功能概览)
- [技术架构](#技术架构)
- [数据模型](#数据模型)
- [快速部署](#快速部署)
- [REST API](#rest-api)
- [前端功能详解](#前端功能详解)
- [Excel 导入导出](#excel-导入导出)
- [智能识别 (OCR)](#智能识别-ocr)
- [产品选择器](#产品选择器)
- [项目结构](#项目结构)
- [开发约定](#开发约定)

---

## 功能概览

| 模块 | 功能 |
|------|------|
| 🔐 **认证系统** | JWT 登录/注册、管理员面板、字段可见性控制、注册开关、个人信息修改、全站鉴权门 |
| 📦 **产品管理** | CRUD、拼音/缩写智能搜索、分类/厂商筛选、批量删除、图片上传预览、**产品上线/下线** |
| 📊 **概览仪表盘** | 产品总数/报价单/下载/总金额统计卡片、最近报价单、快速操作 |
| 📝 **报价单** | 创建/编辑/删除、状态流转、**拖拽排序**、**每行备注**、利润概览、客户聚合、**台湾税率支持** |
| 📥 **Excel 导入** | 多 Sheet 导入、列名智能映射、自动同步 SKU/规格 |
| 📤 **Excel 导出** | 格式化报价单导出、图片嵌入、**自定义公司名/页脚**、下载计数统计 |
| 👁️ **预览** | HTML 预览报价单（Blob URL + token 鉴权） |
| 📧 **邮件** | SMTP 配置，一键发送报价单 Excel 附件 |
| 🔍 **智能识别** | 粘贴文本自动解析产品信息、火山引擎豆包 Vision 图片识别、**发票 OCR → 批量更新成本价** |
| 🎨 **UI** | 统一页面风格、上下布局、`.page-header` / `.card-modern` / `.form-label-modern` 一致样式体系 |
| ⚡ **性能优化** | 缓存优先渲染、产品选择器版本指纹、前端本地拼音过滤 |

---

## 技术架构

```
┌──────────────┐     ┌──────────┐     ┌──────────────┐
│   浏览器      │────▶│  nginx   │────▶│   Gunicorn   │
│  Bootstrap 5  │     │  :443    │     │  2 workers   │
│  SPA (3 JS)   │     │  proxy   │     │  :5000       │
└──────────────┘     └──────────┘     └──────┬───────┘
                                             │
                                        ┌────▼───────┐
                                        │   Flask     │
                                        │ JWT Auth    │
                                        │ SQLAlchemy  │
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
| 应用服务器 | Gunicorn | 2 worker 进程（`--preload`），绑定 `127.0.0.1:5000` |
| 后端框架 | Flask + SQLAlchemy | RESTful JSON API，字段可见性控制 |
| 认证 | JWT (PyJWT) | 无状态 token，SHA256+盐密码，自动续签 |
| 数据库 | SQLite | 单文件，零配置 |
|| 前端 | Vue 3 SPA (CDN) | Composition API，Vite 构建，Vue Router 历史模式 |
|| 拼音 | pypinyin | 后端拼音搜索 + 前端本地拼音过滤 |
|| Excel | openpyxl | 读写 `.xlsx`，含格式化 |
|| 视觉识别 | 火山引擎豆包 | Seed Lite 视觉模型，直出 JSON (v1.6.0) |
|| 降级 OCR | OCR.space API | 免费 tier 兜底 |

---

## 数据模型

### User（用户）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增主键 |
| `username` | VARCHAR(80) | 用户名（唯一，必填） |
| `password_hash` | VARCHAR(128) | SHA256+盐密码哈希 |
| `email` | VARCHAR(120) | 邮箱（选填） |
| `role` | VARCHAR(20) | 角色：`admin` / `user` |
| `is_active` | BOOLEAN | 账户启用状态，默认 True |
| `created_at` | DATETIME | 注册时间 |

### Product（产品）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增主键 |
| `name` | VARCHAR(200) | 产品名称（必填，索引） |
| `sku` | VARCHAR(100) | SKU 编码，自动同步 `spec` |
| `category` | VARCHAR(100) | 分类标签，逗号分隔多标签（索引） |
| `spec` | VARCHAR(500) | 规格型号（主型号字段） |
| `unit` | VARCHAR(20) | 计量单位（台/套/个/米...） |
| `price` | FLOAT | 销售单价 |
| `cost_price` | FLOAT | 成本价 |
| `supplier` | VARCHAR(200) | 供应商/厂商 |
| `function_desc` | TEXT | **功能描述** — 出现在报价单 Excel 和预览中 |
| `remark` | TEXT | **内部备注** — 仅内部可见，不导出到报价单 |
| `image_url` | VARCHAR(500) | 产品图片路径 |
| `is_active` | BOOLEAN | 上下线状态，默认 True（v1.4.0） |
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
| `tax_rate` | FLOAT | 税率(%)，默认 0（v1.5.0）。`税前价 = 含税价 / (1 + 税率/100)` |
| `status` | VARCHAR(20) | 状态：draft/sent/confirmed/rejected |
| `total_amount` | FLOAT | 合计金额 |
| `download_count` | INTEGER | 导出下载次数 |
| `created_by` | FK → User | 创建者（可选） |
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
| `quantity` | INTEGER | 数量，默认 1（v1.4.1 改为整数） |
| `unit_price` | FLOAT | 单价 |
| `amount` | FLOAT | 小计 = 数量 × 单价 |
| `remark` | VARCHAR(500) | 行备注（v1.4.3） |
| `sort_order` | INTEGER | 排序序号（v1.3.8） |

### FieldSetting（字段可见性）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 主键 |
| `field_name` | VARCHAR(50) | 字段名 |
| `user_visible` | BOOLEAN | 普通用户是否可见 |

### DownloadLog（下载记录）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 主键 |
| `quote_id` | FK → Quote | 所属报价单 |
| `user_name` | VARCHAR(100) | 下载者用户名 |
| `downloaded_at` | DATETIME | 下载时间 |

### SystemSetting（系统设置，v1.3.9）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 主键 |
| `key` | VARCHAR(100) UNIQUE | 设置键（company_name, footer_text, smtp_* 等） |
| `value` | TEXT | 设置值 |

---

## 快速部署

### 前提条件

- Python 3.11+
- nginx
- systemd（用于服务管理）

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/xxjtong/quote-system.git /opt/quote-system
cd /opt/quote-system

# 2. 创建虚拟环境并安装依赖
python3 -m venv venv
source venv/bin/activate
pip install flask flask-sqlalchemy flask-cors gunicorn openpyxl pypinyin pyjwt

# 3. 生成 JWT Secret
python3 -c "import secrets; print(secrets.token_hex(32))"
# 将输出填入 step 5 的 QUOTE_JWT_SECRET

# 4. 初始化数据库
python3 -c "
from app import app, db
with app.app_context():
    db.create_all()
    print('数据库已创建')
"

# 5. 创建上传/导出目录
mkdir -p uploads/images exports

# 6. 安装 systemd 服务（编辑 Environment 填入 JWT secret）
sudo cp quote-system.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now quote-system

# 7. 配置 nginx（示例）
# location /quote/ {
#     proxy_pass http://127.0.0.1:5000/;
#     proxy_set_header Host $host;
#     client_max_body_size 50m;
# }
# sudo systemctl reload nginx
```

### 版本号管理

```bash
echo "1.3.8" > version.txt
sudo systemctl restart quote-system
```

---

## REST API

Base URL: `http://127.0.0.1:5000`

> ⚠️ 除公开路由外，所有 API 需 `Authorization: Bearer <token>` 请求头。

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/auth/login` | 登录 `{username, password}` → `{token, user}` |
| `POST` | `/api/auth/register` | 注册 `{username, password, email?}` |
| `GET` | `/api/session` | 验签/续签 token（自动返回 `X-New-Token`） |
| `PUT` | `/api/auth/profile` | 修改个人信息 `{email?, current_password?, new_password?}` |

### 产品

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/products` | 列表（`page`, `per_page`, `search`, `category`, `supplier`, `sort_by`, `sort_order`） |
| `GET` | `/api/products/<id>` | 详情 |
| `POST` | `/api/products` | 新增 |
| `PUT` | `/api/products/<id>` | 编辑 |
| `DELETE` | `/api/products/<id>` | 删除 |
| `POST` | `/api/products/batch-delete` | 批量删除 `{ids: [1,2]}` |
| `POST` | `/api/products/import` | 导入 Excel（multipart） |
| `GET` | `/api/products/export-template` | 下载导入模板 |
|| `POST` | `/api/products/upload-image` | 上传图片（自动压缩 ≤100KB） |
|| `POST` | `/api/products/ocr` | 图片 OCR 识别（降级兜底） |
|| `POST` | `/api/products/recognize` | 文本智能解析 + 图片豆包 Vision 识别（v1.6.0） |
|| `POST` | `/api/download-image` | 从 URL 下载图片并压缩保存（v1.6.0） |

**搜索匹配字段：** `name`、`spec`、`supplier`、`function_desc`（ILIKE）+ **拼音全拼+首字母**（无汉字输入时自动切换）

每个产品返回 `_py`（全拼）和 `_py_initials`（首字母）字段供前端本地过滤。

**响应格式：**
```json
{
  "products": [{"id":1, "name":"交换机", "_py":"jiaohuanji", "_py_initials":"jhj", ...}],
  "total": 392,
  "page": 1,
  "per_page": 20,
  "categories": ["网络设备", "安防监控", ...],
  "suppliers": ["华为", "海康", ...],
  "version": {"count": 392, "max_updated_at": "2026-05-15T03:17:42"}
}
```

### 报价单

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/quotes` | 列表（含 `search`, `status` 筛选） |
| `GET` | `/api/quotes/<id>` | 详情（含 items + 利润，含 `tax_rate`） |
| `POST` | `/api/quotes` | 新建（含 `tax_rate`, 行 `remark`） |
| `PUT` | `/api/quotes/<id>` | 编辑 |
| `DELETE` | `/api/quotes/<id>` | 删除 |
| `PATCH` | `/api/quotes/<id>/status` | 切换状态 `{status: "sent"}` |
| `GET` | `/api/quotes/<id>/export-excel` | 导出 Excel（递增下载计数） |
| `GET` | `/api/quotes/<id>/preview` | HTML 预览（含备注列） |
| `POST` | `/api/quotes/<id>/send-email` | 发送邮件（v1.4.0），body: `{to_email, subject?, body?}` |
| `GET` | `/api/quotes/stats` | 客户维度聚合统计 |

**新建报价单请求体：**
```json
{
  "title": "项目报价单",
  "client": "客户名称",
  "contact": "张三",
  "phone": "13800138000",
  "quote_date": "2026-05-14",
  "valid_days": 15,
  "remark": "备注",
  "items": [
    {
      "product_id": 1,
      "product_name": "交换机",
      "product_spec": "S6730-H48X6C",
      "product_sku": "S6730-H48X6C",
      "product_unit": "台",
      "quantity": 2,
      "unit_price": 3300.00,
      "remark": ""
    }
  ]
}
```

### 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/admin/users` | 用户列表（管理员） |
| `PUT` | `/api/admin/users/<id>` | 修改用户（启用/禁用/角色切换） |
| `PUT` | `/api/admin/users/<id>/password` | 修改用户密码（管理员） |
| `GET` | `/api/admin/fields` | 字段可见性配置 |
| `PUT` | `/api/admin/fields` | 更新字段可见性 |
| `GET` | `/api/admin/registration` | 注册开关状态 |
| `PUT` | `/api/admin/registration` | 设置注册开关 |
| `GET` | `/api/admin/settings` | 系统设置（公司名/页脚/SMTP） |
| `PUT` | `/api/admin/settings` | 更新系统设置 |
| `GET` | `/api/download-logs` | 下载记录列表 |
| `GET` | `/api/download-logs/stats` | 下载统计 |
| `POST` | `/api/products/ocr-cost` | 发票 OCR 识别（v1.5.2） |
| `POST` | `/api/products/update-costs` | 批量更新成本价（v1.5.2，管理员） |
| `PUT` | `/api/products/<id>/toggle-active` | 产品上下线切换（v1.4.0） |

### 通用

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/version` | 系统版本号（公开） |

---

## 前端功能详解

### 前端架构（v1.3.7+）

```
static/js/
├── app.js       # 状态管理 / 工具函数 / 导航 / Dashboard / Modal
├── auth.js      # 登录 / 注册 / 登出 / Session / 个人信息
└── products.js  # 产品 / 报价 / 导入 / 管理面板 / 初始化
```

三个模块通过全局变量共享状态，`index.html` 仅保留 HTML 结构和 CSS。

### 认证系统

- **登录页**：用户名 + 密码，支持注册开关
- **注册页**：用户名 + 密码 + 邮箱（选填）
- **Token 管理**：localStorage 存储，每次请求自动附带 `Authorization` 头
- **自动续签**：`/api/session` 返回新 token 时自动更新
- **401 处理**：token 过期自动跳转登录页
- **管理员面板**：用户管理、角色切换、改密、字段可见性、注册开关
- **个人信息**：右上角下拉 → 修改邮箱/密码

### 概览仪表盘

- **统计卡片**：产品总数、报价单总数、总下载次数
- **最近报价单**：最新 10 条，含客户、金额、状态、下载次数
- **快捷操作**：新建报价单、导入产品
- **性能**：缓存优先渲染，切换标签 <100ms

### 产品管理

**列表页：**
- 表格展示：复选框 | 缩略图 | 产品名称 | 分类 | 规格型号 | 厂商 | 单价 | 操作
- 图片悬浮预览（最大 300px，白底防透明 PNG 透字）
- 产品名称悬浮 tooltip（名称+规格+厂商+分类+价格+功能描述）
- **搜索框**：输入即搜（500ms 防抖），支持名称/规格/型号/功能/厂家/**拼音/缩写**
- IME 输入法适配：组字过程中不触发搜索，选字完成后自动搜索
- 搜索框右侧 ✕ 清除按钮（有内容时显示）
- 分类下拉 + 厂商下拉筛选
- 分页 + 排序（ID/名称/价格/分类）
- 批量删除

**新增/编辑产品：**
- 产品名称（必填）
- 规格型号
- 分类标签
- 厂商（**带自动补全**：输入时下拉匹配已有厂商，键盘 ↑↓ 导航，Enter 选中，匹配部分加粗）
- 单位
- 销售单价 / 成本价
- 功能描述（textarea，3 行）
- 内部备注（textarea，标签注明"内部备注"）
- 产品图片（支持粘贴上传）

**智能识别面板：**
- 文本域 + 「粘贴并识别」按钮
- 支持格式：`产品名称 ｜ 规格型号 ｜ 厂商 ｜ 功能描述 ｜ 售价`
- Tab / 多空格 / 单空格 / 换行分隔
- 识别结果列表，点击箭头填入表单
- 「识别图片」按钮上传图片 OCR
- 支持直接粘贴图片到文本域（自动上传 OCR → 解析全链路）

**产品详情弹窗：**
- 两列表格展示全部字段
- 图片悬浮预览
- 底部「编辑」按钮

### 报价单管理

**列表页：**
- 表格：ID、标题、客户、金额、状态、下载次数、日期、操作
- 状态颜色区分、一键循环切换状态
- 编辑、预览、导出 Excel、删除

**新建/编辑报价单：**
- 头部信息：标题、客户、联系人、电话、日期、有效期、备注
- 快速搜索栏：输入产品名/拼音即时匹配，支持拼音/缩写
- 明细行表格：产品名称、规格型号、数量、单价、金额、备注
- **利润概览**：毛利 / 毛利率列（绿色盈利、红色亏损）
- 行内编辑：数量/单价修改即算金额
- 产品选择器（详见下方）
- 删除行

**预览：**
- HTML 渲染报价单
- 功能描述列使用 `function_desc`（不含内部备注）
- 产品图片嵌入

**Excel 导出：**
- 格式化 `.xlsx`：边框、对齐、列宽
- 功能描述列使用 `function_desc`
- 内部备注（`remark`）**不导出**
- 产品图片嵌入
- 每次导出递增 `download_count`

### 产品选择器

报价单编辑时从产品库批量添加产品。

**交互：**
1. 点击「+从产品库选择」→ 模态框
2. 搜索框：即时客户端过滤，匹配名称/规格/功能描述/厂商 + **拼音全拼/首字母**
3. 分类快速过滤按钮（前 12 个分类）
4. 产品列表（最大高度 60vh 可滚动）
5. 每行：复选框 + 产品名称 + 厂商标签 + 分类标签 + 规格 + 价格
6. **点击产品名称 → 切换选中/取消**（反选）
7. 「全选/取消全选」按钮
8. 「添加选中」→ 批量加入报价单
9. 已在报价单的产品 → 数量 +1 而非重复

**智能缓存：**
- 首次打开：全量加载（`per_page=10000`）→ 缓存 `window._pickerData`
- 缓存版本指纹：`"${count}_${max_updated_at}"`
- 再次打开：先请求 `/api/products/version`（~50 字节）→ 版本一致则秒开缓存
- 产品增删改后版本号变化 → 自动重新全量加载

**全局输入框自动去空格：**
- 所有 `<input type="text">` 和 `<textarea>` 失焦时自动 `.trim()`
- 提交时再次 trim

---

## Excel 导入导出

### 导入列名映射

| Excel 表头 | 数据库字段 | 备注 |
|-----------|-----------|------|
| 产品名称 / 名称 / 品名 | `name` | |
| 规格型号 / 规格 / 型号 / SKU / Part Number | `spec` | `sku` 自动同步 |
| 功能描述 | `function_desc` | |
| 备注 / 说明 | `remark` | 内部备注 |
| 供应商 / 厂商 | `supplier` | |
| 单价 / 价格 / 售价 | `price` | |
| 成本价 / 成本 / 进价 | `cost_price` | |
| 单位 | `unit` | |

- 支持多 Sheet 导入
- 自动创建不存在的分类
- `sku` 自动同步 `spec` 值

### 导出模板

`GET /api/products/export-template` — 下载含标准表头的空 `.xlsx`

### 报价单导出

`GET /api/quotes/<id>/export-excel` — 格式化 Excel，含：
- 报价单头部信息（标题、客户、联系人、电话、日期、有效期）
- 明细表（序号、产品名称、规格型号、数量、单价、金额、功能描述）
- 合计行
- 产品图片嵌入功能描述列
- 下载计数 +1

---

## 智能识别（豆包 Vision + OCR）

### 火山引擎豆包视觉识别（v1.6.0 主力）

`POST /api/products/recognize` — 上传图片 → 火山引擎豆包 Seed Lite 视觉模型直出结构化 JSON。

- **模型**: `doubao-seed-1-6-lite-250815`（可切换至 `doubao-seed-2-0-lite-260215` / `doubao-seed-2-0-mini-260215`）
- **输出**: `{name, spec, supplier, price, cost_price, category, unit, function_desc, remark}`
- **降级**: 豆包失败 → OCR.space → smart_parse_product

### 文本解析

`POST /api/products/recognize` — 输入纯文本，输出结构化产品信息。

**分割策略（优先级）：**
1. Tab 字符 (`\t`)
2. ≥2 个连续空格
3. 单个空格
4. 换行（每行一个产品）

**字段映射（5 字段格式，从右向左提取）：**
1. **价格** — 最后一个可识别数值（支持 `¥123`、`123元`、`123.45`）
2. **功能描述** — 倒数第 2 个字段
3. **厂商** — 倒数第 3 个字段
4. **产品名称** — 第 1 个字段
5. **规格型号** — 剩余中间字段合并

### 图片 OCR（降级兜底）

`POST /api/products/ocr` — 上传图片 → OCR.space API → 返回文字。

依赖：OCR.space 免费 API（apikey: `helloworld`）

---

## 项目结构

```
/opt/quote-system/
├── app.py                     # Flask 应用主文件（~2572 行）
├── frontend/                  # Vue 3 SPA 前端（v1.6.0）
│   ├── src/                   # Vue 组件 / composables
│   │   ├── App.vue            # 根组件 + 导航
│   │   ├── router/            # Vue Router 配置
│   │   ├── views/             # 页面组件
│   │   │   ├── ProductsView   # 产品管理
│   │   │   ├── QuotesView / NewQuoteView  # 报价单
│   │   │   ├── DashboardView  # 概览仪表盘
│   │   │   ├── LoginView      # 登录/注册
│   │   │   ├── AdminView      # 管理面板
│   │   │   └── ImportView     # Excel 导入
│   │   └── components/        # 通用组件
│   ├── dist/                  # Vite 构建产物（生产）
│   └── vite.config.js         # Vite 配置
├── templates/
│   └── index.html             # 旧版 SPA 骨架（向下兼容）
├── static/js/                 # 旧版 JS 模块（向下兼容）
├── tests/                     # pytest 测试套件（127 项）
│   ├── conftest.py            # fixtures（登录、session）
│   ├── test_auth.py           # 认证
│   ├── test_products.py       # 产品
│   ├── test_quotes.py         # 报价单
│   ├── test_admin.py          # 管理
│   ├── test_edge_cases.py     # 边界&安全
│   ├── test_comprehensive.py  # 综合测试
│   └── test_e2e_vue.py        # Vue E2E 测试
├── quote-system.service       # systemd 服务配置
├── version.txt                # 版本号（手动递增）
├── CHANGELOG.md               # 更新日志
├── README.md                  # 本文件
├── REQUIREMENTS.md            # 需求规格书
├── CLAUDE.md                  # AI 编码规范
├── TEST_REPORT.md             # 测试报告
├── uploads/
│   └── images/                # 产品图片
├── exports/                   # 导出的报价单 Excel
└── quote.db                   # SQLite 数据库（不加入版本控制）
```

---

## 开发约定

| 约定 | 说明 |
|------|------|
| `function_desc` ≠ `remark` | 前者对客户可见（导出），后者仅内部 |
| `sku` = `spec` | 写入时自动同步 |
| 搜索匹配 | `name` + `spec` + `supplier` + `function_desc` + 拼音全拼 + 首字母 |
| 搜索防抖 | 500ms，IME 组字中不触发 |
| 修改 Vue 组件 | `cd frontend && npm run build && sudo systemctl restart quote-system` |
| 修改后端 Python | `sudo systemctl restart quote-system` |
| 修改 JS 必强刷 | 提示用户 `Ctrl+Shift+R` |
| 版本号手动递增 | `echo "x.x.x" > version.txt` + 重启 |
| 图片上传压缩 | PIL 自动压缩 ≤100KB，透明PNG贴白底转JPG |
| 图片预览白底 | 防透明 PNG 背景透字 |
| JWT Secret | 通过 systemd 环境变量固定，避免多 worker 不一致 |
| 视觉识别模型 | 火山引擎豆包 Seed Lite（环境变量 `VOLCENGINE_API_KEY`） |

### 常用命令

```bash
# 服务管理
sudo systemctl restart quote-system
sudo systemctl status quote-system

# 数据库直接操作（无需重启）
python3 -c "
import sqlite3
conn = sqlite3.connect('/opt/quote-system/quote.db')
c = conn.cursor()
c.execute(\"UPDATE products SET supplier='星纵' WHERE category='星纵'\")
conn.commit()
print(f'Updated: {c.rowcount}')
conn.close()
"

# 更新版本号
echo "1.6.0" > version.txt && sudo systemctl restart quote-system

# 推送到 GitHub
cd /opt/quote-system
git add -A && git commit -m "描述" && git push
```

---

## License

MIT
