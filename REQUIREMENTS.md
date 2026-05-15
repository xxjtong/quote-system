# 报价管理系统 — AI 重做需求规格书

> 写给 AI：本文档涵盖该报价系统的全部功能与交互细节。照着做就能复刻。

---

## 1. 系统架构

| 层 | 技术 | 说明 |
|---|------|------|
| Web 服务器 | nginx | 反向代理，`/quote/` → `127.0.0.1:5000/`，处理 TLS |
| 应用服务器 | Gunicorn | 4 worker，绑定 `127.0.0.1:5000` |
| 后端框架 | Flask + SQLAlchemy | REST JSON API |
| 数据库 | SQLite | 单文件 `/opt/quote-system/quote.db` |
| 前端 | 原生 JS SPA | Bootstrap 5 + 少量自定义 CSS，单页应用，所有 HTML 由 JS 模板字符串动态生成 |
| 部署 | systemd | 服务名 `quote-system`，用户 `tong` |

---

## 2. 数据模型

### 2.1 Product（产品）

| 字段 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `id` | Integer PK | 自增 | 主键 |
| `name` | String(200) | ✅ | 产品名称，有索引 |
| `sku` | String(100) | | SKU，**自动同步 spec 值** |
| `category` | String(100) | | 分类标签，逗号分隔多标签，有索引 |
| `spec` | String(500) | | 规格型号（主型号字段） |
| `unit` | String(20) | | 计量单位（台/套/个/米...） |
| `price` | Float | | 销售单价 |
| `cost_price` | Float | | 成本价 |
| `supplier` | String(200) | | 供应商/厂商 |
| `function_desc` | Text | | **功能描述** — 会出现在报价单 Excel 和预览中 |
| `remark` | Text | | **内部备注** — 仅内部可见，不导出到报价单 |
| `image_url` | String(500) | | 产品图片路径，如 `/uploads/images/xxx.jpg` |
| `created_at` | DateTime | 自动 | 创建时间 |
| `updated_at` | DateTime | 自动 | 更新时间，修改时自动刷新 |

**关键约定：**
- `sku` 始终等于 `spec`（创建/更新时自动同步）
- `function_desc` 和 `remark` 是独立字段：前者面向客户，后者内部使用
- 分类支持逗号分隔多标签，如 `"网络设备,交换机"`
- API 输出时空字段统一为空字符串，价格为 0 输出 `0`

### 2.2 Quote（报价单）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | 主键 |
| `title` | String(200) | 报价单标题 |
| `client` | String(200) | 客户名称 |
| `contact` | String(100) | 联系人 |
| `phone` | String(50) | 联系电话 |
| `quote_date` | String(20) | 报价日期 |
| `valid_days` | Integer | 有效期（天），默认 15 |
| `status` | String(20) | 状态，默认 `draft` |
| `total_amount` | Float | 合计金额 |
| `download_count` | Integer | 导出下载次数 |
| `remark` | Text | 备注 |
| `items` | relationship | 一对多关联 QuoteItem |

### 2.3 QuoteItem（报价单明细行）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | 主键 |
| `quote_id` | FK → Quote | 所属报价单 |
| `product_id` | FK → Product | 关联产品（可选） |
| `product_name` | String(200) | 产品名称快照 |
| `product_sku` | String(100) | SKU 快照 |
| `product_spec` | String(500) | 规格型号快照 |
| `product_unit` | String(20) | 单位快照 |
| `quantity` | Float | 数量，默认 1 |
| `unit_price` | Float | 单价 |
| `amount` | Float | 小计（数量×单价） |
| `remark` | String(500) | 行备注 |
| `sort_order` | Integer | 排序 |

---

## 3. REST API

Base: `http://127.0.0.1:5000` | 公网: `https://bwh.ddns.mobi/quote`

### 3.1 产品 API

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/products` | 列表，支持 `page`/`per_page`/`search`/`category`/`supplier`/`sort_by`/`sort_order` |
| `GET` | `/api/products/<id>` | 详情 |
| `POST` | `/api/products` | 新增产品 |
| `PUT` | `/api/products/<id>` | 编辑产品 |
| `DELETE` | `/api/products/<id>` | 删除产品 |
| `POST` | `/api/products/batch-delete` | 批量删除 `{ids: [1,2,3]}` |
| `POST` | `/api/products/import` | 导入 Excel（multipart） |
| `GET` | `/api/products/export-template` | 下载导入模板 |
| `GET` | `/api/products/version` | 轻量版本检查，返回 `{count, max_updated_at}` |
| `POST` | `/api/products/upload-image` | 上传图片 |
| `POST` | `/api/products/ocr` | 图片 OCR 识别 |
| `POST` | `/api/products/recognize` | 文本智能识别解析 |

**搜索行为：** `search` 参数模糊匹配 `name`、`spec`、`supplier`、`function_desc`（ILIKE）。
**响应包含：** `{products, total, page, per_page, categories, suppliers, version: {count, max_updated_at}}`

### 3.2 报价单 API

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/quotes` | 列表 |
| `GET` | `/api/quotes/<id>` | 详情（含 items） |
| `POST` | `/api/quotes` | 新建报价单 |
| `PUT` | `/api/quotes/<id>` | 编辑报价单 |
| `DELETE` | `/api/quotes/<id>` | 删除报价单 |
| `GET` | `/api/quotes/<id>/export-excel` | 导出 Excel（会递增 `download_count`） |
| `GET` | `/api/quotes/<id>/preview` | HTML 预览 |

### 3.3 通用 API

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/version` | 系统版本号 |
| `GET` | `/api/stats` | 统计数据（产品数、报价单数等） |

---

## 4. 前端功能需求

### 4.1 全局特性

#### 输入框自动去空格
所有 `<input type="text">` 和 `<textarea>` 失焦时自动 `.trim()`。提交时再次 trim。使用全局 `blur` 事件捕获（`addEventListener('blur', ..., true)`）。

#### 中文输入法处理
搜索框使用 `onkeydown` + `Enter` 键触发搜索，**不使用 `oninput`**——避免拼音组合输入期间触发搜索。

#### 版本号
页面底部显示系统版本号（独立文件 `/opt/quote-system/version.txt`），版本号由开发者手动递增，不随用户数据操作自动变化。

#### 模板缓存
Gunicorn 缓存 Jinja2 模板，每次修改 `index.html` 后需重启服务。修改 JS 后提示用户 `Ctrl+Shift+R` 强制刷新。

---

### 4.2 概览页（Dashboard）

- 顶部统计卡片：产品总数、报价单总数、总下载次数
- 最近报价单列表（最新 10 条），含客户名、金额、状态、下载次数
- 快捷操作区
- **缓存优先 + 后台刷新**：首次渲染用缓存数据（0ms），后台异步拉取新数据，有变化时静默更新 DOM

---

### 4.3 产品管理页

#### 产品列表
- 表格显示：复选框、图片缩略图、产品名称、分类、规格型号、厂商、单价、操作
- 分页，每页默认 20 条
- 支持排序（ID/名称/价格/分类，升序/降序）

#### 搜索与筛选
- **搜索框**：`onkeydown Enter` 触发搜索，匹配名称/规格/功能描述/厂商
- 搜索框右侧有 **✕ 清除按钮**：有内容时显示灰色圆形按钮，点击一键清空并刷新
- **分类下拉**：筛选分类
- **厂商下拉**：筛选厂商
- 搜索/筛选均重置到第一页

#### 新增/编辑产品
表单字段：
- 产品名称（必填）
- 规格型号
- 分类标签
- 厂商（**带自动补全下拉**，匹配已有厂商列表）
- 单位
- 销售单价
- 成本价
- 功能描述（textarea，3 行）
- 备注/内部备注（textarea，**标签注明"内部备注"**）
- 产品图片（支持粘贴图片自动上传）

**厂商自动补全细节：**
- `oninput`/`onfocus` 触发，过滤全局 `suppliers[]` 数组
- 子串匹配，不区分大小写，最多 8 条
- 匹配部分**加粗**
- 键盘 ↑↓ 导航，Enter 选中
- Blur 延时 200ms 收起（防止点击竞态）

#### 产品详情弹窗
- 两列表格显示全部字段（含功能描述、内部备注、图片）
- 图片悬浮预览：鼠标悬停弹出大图，最大 300px，白色背景，卡片自适应宽度
- 底部提供「编辑」按钮

#### 图片上传与预览
- 支持粘贴图片到图片 URL 输入框
- 上传限制 10MB
- 产品列表图片列悬浮显示大图预览（最大 300px）
- 产品名称列悬浮显示 tooltip（名称+规格+厂商+分类+价格+功能描述）
- 规格列无悬浮 tooltip

#### 智能识别（OCR + 文本解析）

**功能入口：** 产品表单中的「智能识别」区域

**格式提示：** 文本域下方显示：
> 产品名称 ｜ 规格型号 ｜ 厂商 ｜ 功能描述 ｜ 售价
> （Tab/空格/换行分隔，每行一个产品）

**文本解析（粘贴并识别）：**
- POST `/api/products/recognize`，body `{text}`
- 后端分割逻辑：先按换行分割，每行再按 Tab → ≥2 空格 → 单空格 优先分割
- 5 字段定位置解析（从右向左）：
  1. 价格（最后一个数值字段，支持 `¥123` / `123元` / `123.45`）
  2. 功能描述（倒数第 2）
  3. 厂商（倒数第 3）
  4. 产品名称（第 1 个）
  5. 规格型号（剩余中间字段合并）
- 识别结果列表显示，点击箭头填入表单

**图片 OCR：**
- `POST /api/products/ocr`，multipart 上传图片
- 后端调用 OCR.space API（free tier，apikey: `helloworld`）
- OCR 结果自动回填文本域并触发解析

**粘贴图片：**
- 文本域 `onpaste` 事件检测剪贴板图片
- 自动上传 OCR → 回填文本 → 触发解析（全自动链路）

#### Excel 导入
- `POST /api/products/import`，multipart 上传 `.xlsx`
- 支持多 Sheet
- 列名智能映射（别名）：

| Excel 列名 | 映射字段 |
|-----------|---------|
| 产品名称/名称/品名 | `name` |
| 规格型号/规格/型号/SKU/Part Number | `spec` |
| 功能描述 | `function_desc` |
| 备注/说明 | `remark` |
| 供应商/厂商 | `supplier` |
| 单价/价格/售价 | `price` |
| 成本价/成本/进价 | `cost_price` |
| 单位 | `unit` |

- `sku` 自动同步 `spec`
- 导入后自动刷新产品列表和全局分类/厂商数组

#### Excel 导出模板
- `GET /api/products/export-template` 下载带表头的空模板

#### 缓存策略
- `productsCache` 变量缓存产品列表数据
- 任何产品增/删/改/导入后调用 `clearCaches()` 失效缓存
- 切换标签时缓存优先渲染

---

### 4.4 报价单管理

#### 报价单列表
- 表格显示：ID、标题、客户、金额、状态、下载次数、日期、操作
- 支持编辑、预览、导出 Excel、删除

#### 新建/编辑报价单
**头部信息：**
- 报价单标题
- 客户名称
- 联系人
- 电话
- 报价日期
- 有效期（天）
- 备注

**明细行（产品列表）：**
- 每行：产品名称、规格型号、数量、单价、金额、备注
- 行内编辑：数量/单价修改后自动计算金额
- 支持删除行
- 支持拖拽排序（`sort_order`）

**产品选择器（"+从产品库选择"）：**

*交互流程：*
1. 点击按钮 → 弹出模态框，标题「选择产品（支持多选）」
2. 顶部搜索框（`oninput` 触发客户端即时过滤，回车不特殊处理）
3. 搜索框下方：**分类快速过滤按钮**（显示前 12 个分类，来自全局 `categories[]`）
4. 产品列表（最大高度 60vh，可滚动）
5. 每行：复选框 + 产品名称 + 厂商标签 + 分类标签 + 规格型号 + 价格/单位
6. 点击产品名称 → **切换复选框选中状态**（反选）
7. 底部「全选/取消全选」按钮
8. 底部「添加选中」→ 将选中的产品加入报价单明细
9. 已存在于报价单的产品 → 数量 +1 而非重复添加

*智能缓存：*
- **首次打开**：`GET /api/products?per_page=10000` 全量加载 → 缓存到 `window._pickerData`
- 同时缓存版本指纹：`window._pickerVersion = "${count}_${max_updated_at}"`
- **再次打开**：先 `GET /api/products/version`（~50 字节）→ 对比版本指纹
  - 一致 → 秒开缓存，无 spinner
  - 不一致 → 重新全量加载
- 产品增删改后 `updated_at` 或 `count` 变化 → 自动触发重新加载

*客户端过滤：*
- 搜索：匹配 `name`、`spec`、`function_desc`、`supplier`
- 分类：匹配 `category`（逗号分隔多标签）
- 搜索 + 分类可组合，纯客户端 200ms 防抖

*全选/取消全选：* 作用于当前可见列表

#### 报价单预览
- `GET /api/quotes/<id>/preview` 返回 HTML
- 功能描述列使用 `function_desc`（不是 `remark`）
- 产品图片嵌入预览中

#### Excel 导出
- `GET /api/quotes/<id>/export-excel`
- 格式化的 `.xlsx`，含边框、对齐、列宽调整
- 功能描述列使用 `function_desc`
- **不导出** `remark`（内部备注）
- 电话列包含在导出中
- 产品图片嵌入功能描述列
- 每次导出递增 `download_count`

---

### 4.5 UI/UX 细节

#### 对话框风格
所有模态框统一使用 Bootstrap 5 modal，自定义样式统一：
- 圆角、阴影
- 边框使用 `--gray-200` 色
- padding 一致

#### 产品选择器分类按钮
- 按钮列表显示前 12 个分类
- 加载时序：优先全局 `categories[]`，若为空则 fallback 到 `productsCache.categories`
- 点击切换激活态，再次点击取消过滤
- 选中态有明显视觉反馈（蓝色）

#### 搜索框清除按钮
- 产品管理页搜索框右侧圆形 ✕ 按钮
- 灰色背景 `--gray-300`
- 有内容时显示，无内容时隐藏
- 点击：清空搜索词 + 重置页码 + 刷新列表

#### Tooltip 规则
- 产品名称列：hover 显示名称+规格+厂商+分类+价格+功能描述
- 图片列：hover 显示大图（max 300px），`min-width:unset;max-width:unset;width:fit-content`，白色背景防止透明 PNG 透出底层文字
- 规格列：无 tooltip

#### 输入框 IME 处理
- 搜索类输入框使用 `onkeydown` + Enter，**不使用 `oninput`**
- 产品选择器内搜索使用 `oninput`（即时过滤，无服务端请求）

#### 全局 state 变量
- `window._pfImageUrl` — 当前编辑产品的图片 URL
- 打开「新增产品」时必须重置 `window._pfImageUrl = ''`，否则残留上次图片

---

## 5. 非功能性需求

### 5.1 性能
- 概览页和产品页切换必须 <100ms（缓存优先 + 后台刷新）
- 产品选择器首次打开加载 10000 条产品（当前 ~400 条）
- 产品选择器再次打开必须 <50ms（版本检查 ~50 字节 + 缓存渲染）

### 5.2 数据一致性
- `sku` 始终等于 `spec`
- Excel 导入时 SKU 映射到 spec
- 报价单明细中的 `product_sku` = `product_spec`

### 5.3 安全性
- 无认证（内网/代理使用）
- 图片上传限制 10MB
- 文件上传仅允许 `.xlsx`

### 5.4 部署
```bash
# 服务管理
sudo systemctl restart quote-system   # 修改模板后必须执行
sudo systemctl status quote-system

# 数据库直接操作（无需重启）
python3 -c "
import sqlite3
conn = sqlite3.connect('/opt/quote-system/quote.db')
# ... SQL ...
conn.commit()
conn.close()
"

# 版本号递增（手动）
echo "1.2.22" > /opt/quote-system/version.txt
sudo systemctl restart quote-system
```

### 5.5 浏览器兼容
- 用户使用 Chrome
- JS 修改后必须 `Ctrl+Shift+R` 强制刷新（否则缓存旧 JS）
- 这是部署后最常见的 bug 来源

---

## 6. 关键约定速查

| 约定 | 说明 |
|------|------|
| `function_desc` ≠ `remark` | 前者对客户可见（导出到报价单），后者仅内部可见 |
| `sku` = `spec` | 始终同步 |
| 搜索匹配字段 | `name` + `spec` + `supplier` + `function_desc` |
| 中文搜索用 Enter | 不用 `oninput`，避免拼音干扰 |
| 修改 HTML 必重启 | `sudo systemctl restart quote-system` |
| 修改 JS 必强制刷新 | 提示用户 `Ctrl+Shift+R` |
| 版本号手动递增 | 不随数据变更自动变化 |
| 图片预览白底 | `background:#fff`，防透明 PNG 显示异常 |
| `_pfImageUrl` 重置 | 新增产品时清空 |
| OCR 需要 apikey | `helloworld` |
| 产品选择器缓存 | 版本指纹对比，有变化才重新全量加载 |
