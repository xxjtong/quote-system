# 报价管理系统 (Quote Management System)

> Flask + SQLite + Bootstrap SPA — 产品管理、报价单生成、Excel 导入导出、OCR 智能识别

[![Version](https://img.shields.io/badge/version-1.2.21-blue)](version.txt)
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
| 📦 **产品管理** | CRUD、多条件搜索、分类/厂商筛选、批量删除、图片上传预览 |
| 📊 **概览仪表盘** | 产品总数、报价单统计、下载量、最近报价单列表 |
| 📝 **报价单** | 创建/编辑/删除、产品多选添加、数量/价格行内编辑、排序 |
| 📥 **Excel 导入** | 多 Sheet 导入、列名智能映射、自动同步 SKU/规格 |
| 📤 **Excel 导出** | 格式化报价单导出、图片嵌入、下载计数统计 |
| 👁️ **预览** | HTML 预览报价单，功能描述与备注分离 |
| 🔍 **智能识别** | 粘贴文本自动解析产品信息、图片 OCR 识别 |
| ⚡ **性能优化** | 缓存优先渲染、产品选择器版本指纹智能缓存 |

---

## 技术架构

```
┌──────────────┐     ┌──────────┐     ┌──────────────┐
│   浏览器      │────▶│  nginx   │────▶│   Gunicorn   │
│  Bootstrap 5  │     │  :443    │     │  4 workers   │
│  SPA (原生JS) │     │  proxy   │     │  :5000       │
└──────────────┘     └──────────┘     └──────┬───────┘
                                             │
                                        ┌────▼───────┐
                                        │   Flask     │
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
| 应用服务器 | Gunicorn | 4 worker 进程，绑定 `127.0.0.1:5000` |
| 后端框架 | Flask + SQLAlchemy | RESTful JSON API |
| 数据库 | SQLite | 单文件，零配置 |
| 前端 | 原生 JavaScript SPA | Bootstrap 5 UI，无框架依赖 |
| Excel | openpyxl | 读写 `.xlsx`，含格式化 |
| OCR | OCR.space API | 免费 tier 图片文字识别 |

---

## 数据模型

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
| `status` | VARCHAR(20) | 状态，默认 `draft` |
| `total_amount` | FLOAT | 合计金额 |
| `download_count` | INTEGER | 导出下载次数 |
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
| `quantity` | FLOAT | 数量，默认 1 |
| `unit_price` | FLOAT | 单价 |
| `amount` | FLOAT | 小计 = 数量 × 单价 |
| `remark` | VARCHAR(500) | 行备注 |
| `sort_order` | INTEGER | 排序序号 |

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
pip install flask flask-sqlalchemy flask-cors gunicorn openpyxl

# 3. 初始化数据库
python3 -c "
from app import app, db
with app.app_context():
    db.create_all()
    print('数据库已创建')
"

# 4. 创建上传/导出目录
mkdir -p uploads/images exports

# 5. 安装 systemd 服务
sudo cp quote-system.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now quote-system

# 6. 配置 nginx（示例）
# location /quote/ {
#     proxy_pass http://127.0.0.1:5000/;
#     proxy_set_header Host $host;
#     client_max_body_size 50m;
# }
# sudo systemctl reload nginx
```

### 版本号管理

```bash
echo "1.2.22" > version.txt
sudo systemctl restart quote-system
```

---

## REST API

Base URL: `http://127.0.0.1:5000`

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
| `GET` | `/api/products/version` | 版本检查 `{count, max_updated_at}` |
| `POST` | `/api/products/upload-image` | 上传图片 |
| `POST` | `/api/products/ocr` | 图片 OCR 识别 |
| `POST` | `/api/products/recognize` | 文本智能解析 |

**搜索匹配字段：** `name`、`spec`、`supplier`、`function_desc`（ILIKE 模糊匹配）

**响应格式：**
```json
{
  "products": [{...}],
  "total": 392,
  "page": 1,
  "per_page": 20,
  "categories": ["网络设备", "安防监控", ...],
  "suppliers": ["华为", "海康", ...],
  "version": {"count": 392, "max_updated_at": "2026-05-14T08:12:09"}
}
```

### 报价单

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/quotes` | 列表 |
| `GET` | `/api/quotes/<id>` | 详情（含 items） |
| `POST` | `/api/quotes` | 新建 |
| `PUT` | `/api/quotes/<id>` | 编辑 |
| `DELETE` | `/api/quotes/<id>` | 删除 |
| `GET` | `/api/quotes/<id>/export-excel` | 导出 Excel（递增下载计数） |
| `GET` | `/api/quotes/<id>/preview` | HTML 预览 |

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

### 通用

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/version` | 系统版本号 |
| `GET` | `/api/stats` | 统计数据 |

---

## 前端功能详解

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
- 搜索框：Enter 触发（避免中文输入法干扰），匹配名称/规格/功能描述/厂商
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
- 编辑、预览、导出 Excel、删除

**新建/编辑报价单：**
- 头部信息：标题、客户、联系人、电话、日期、有效期、备注
- 明细行表格：产品名称、规格型号、数量、单价、金额、备注
- 行内编辑：数量/单价修改即算金额
- 产品选择器（详见下方）
- 删除行、拖拽排序

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
2. 搜索框：即时客户端过滤（`oninput`），匹配名称/规格/功能描述/厂商
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

## 智能识别 (OCR)

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

### 图片 OCR

`POST /api/products/ocr` — 上传图片 → OCR.space API → 返回文字。

依赖：OCR.space 免费 API（apikey: `helloworld`）

---

## 项目结构

```
/opt/quote-system/
├── app.py                  # Flask 应用主文件（后端全部逻辑）
├── templates/
│   └── index.html          # 前端 SPA（全部 HTML/CSS/JS）
├── quote-system.service    # systemd 服务配置
├── version.txt             # 版本号
├── REQUIREMENTS.md         # 完整需求规格书
├── README.md               # 本文件
├── template.xlsx           # 导入模板
├── uploads/
│   └── images/             # 产品图片
├── exports/                # 导出的报价单 Excel
└── quote.db                # SQLite 数据库（不加入版本控制）
```

---

## 开发约定

| 约定 | 说明 |
|------|------|
| `function_desc` ≠ `remark` | 前者对客户可见（导出），后者仅内部 |
| `sku` = `spec` | 写入时自动同步 |
| 搜索匹配 | `name` + `spec` + `supplier` + `function_desc` |
| 中文搜索用 Enter | 不用 `oninput`，避免拼音干扰 |
| 修改模板必重启 | `sudo systemctl restart quote-system` |
| 修改 JS 必强刷 | 提示用户 `Ctrl+Shift+R` |
| 版本号手动递增 | `echo "x.x.x" > version.txt` + 重启 |
| 图片预览白底 | 防透明 PNG 背景透字 |
| 新增产品清空图片 | `window._pfImageUrl = ''` |

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
echo "1.2.22" > version.txt && sudo systemctl restart quote-system

# 推送到 GitHub
cd /opt/quote-system
git add -A && git commit -m "描述" && git push
```

---

## License

MIT
