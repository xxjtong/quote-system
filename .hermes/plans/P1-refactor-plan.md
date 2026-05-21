# P1 架构级重构方案 (1/2/3/4)

## P1-1: 消除12个重复函数

### 现状
app.py 和 products_bp.py 有12个完全重复的函数：

| 函数 | app.py行 | products_bp.py行 | 分类 |
|------|---------|-----------------|------|
| _compute_pinyin_search | 412 | 179 | 产品工具 |
| _debug_log | 389 | 156 | 通用工具 |
| _log_ai_usage | 399 | 166 | 通用工具 |
| _ocr_fallback | 292 | 292 | 识别工具 |
| _parse_json_reply | 442 | 209 | 识别工具 |
| _product_from_parsed | 479 | 246 | 识别工具 |
| _safe_number | 430 | 197 | 通用工具 |
| compress_image_if_needed | 239 | 103 | 图片工具 |
| deepseek_parse_product | 498 | 391 | 识别核心 |
| doubao_vision_recognize | 315 | 315 | 识别核心 |
| parse_product_line | 688 | 590 | 识别核心 |
| smart_parse_product | 544 | 446 | 识别核心 |

### 方案

新建3个模块，按职责拆分：

```
utils.py          ← 通用工具 (4个函数)
  _debug_log, _log_ai_usage, _safe_number, _compute_pinyin_search

product_utils.py  ← 产品+识别工具 (8个函数)
  compress_image_if_needed, _ocr_fallback, doubao_vision_recognize,
  _parse_json_reply, _product_from_parsed, deepseek_parse_product,
  smart_parse_product, parse_product_line

app.py 和 products_bp.py 中的12个函数全部删除，改为 import
```

### 影响范围
- app.py: 删除12个函数 (~500行)，仅保留17个app-only函数
- products_bp.py: 删除12个函数 (~500行)，改为 import
- 新增 utils.py (~80行) + product_utils.py (~450行)
- 净减 ~500行重复代码

### 风险
低。纯函数搬移，无逻辑变更。需确保 import 路径正确，特别是循环引用——utils.py 和 product_utils.py 不依赖 app.py，所以无循环。

---

## P1-2: 拆分 import_products (CC=83)

### 现状
- 位置: products_bp.py L1170-L1374 (204行)
- 68个分支点，圈复杂度83
- 单一函数处理：文件上传 → Excel解析 → 列头智能识别 → 行遍历 → 产品创建/更新 → 图片提取

### 方案

拆为5个子函数 + 1个编排函数：

```
import_products()           ← 编排函数 (30行)
  ├── _parse_excel_header()   ← 识别列头映射 (40行)
  ├── _find_supplier_col()    ← 供应商列智能检测 (25行)
  ├── _extract_images()       ← Excel内嵌图片提取 (20行)
  ├── _process_import_row()   ← 单行→产品dict (40行)
  └── _save_import_products() ← 批量create/update (50行)
```

### 影响范围
- products_bp.py: import_products 204行 → 6个函数合计 ~205行 (总行数不变，但每个函数CC<15)
- 无外部API变更

### 风险
中。import_products是核心导入逻辑，修改需仔细测试Excel各种格式(有表头/无表头/图片/供应商列)。

---

## P1-3: 引入 Flask-Migrate

### 现状
- app.py L830-849: 手动 ALTER TABLE，需在 _auto_migrate_columns 列表里硬编码每个新列
- db.create_all() 只创建新表，不添加新列
- 已有2个手动迁移项: quote_items.discount_rate, products.pinyin_search
- 无迁移历史记录，无法回滚

### 方案

**轻量方案**（推荐）：

引入 Flask-Migrate (Alembic)，但保留 `_auto_migrate_columns` 作为过渡期兜底。

```
1. pip install Flask-Migrate
2. app.py: 初始化 Migrate(app, db)
3. flask db init → 生成 migrations/ 目录
4. flask db migrate -m "initial" → 从当前schema生成基线迁移
5. flask db stamp head → 标记当前DB为最新，不执行任何SQL
6. 未来新列: flask db migrate -m "add xxx" + flask db upgrade
7. 过渡期(1-2个月): 保留_auto_migrate_columns，新列同时加两边
8. 过渡期后: 删除_auto_migrate_columns
```

### 影响范围
- app.py: +2行 (init Migrate)，后期 -20行 (删除_auto_migrate)
- 新增 migrations/ 目录
- 部署流程: VPS需 pip3 install Flask-Migrate --user
- 首次迁移: 在VPS执行 flask db stamp head（一次性）

### 风险
中。Alembic与SQLite兼容性有限（不支持ALTER COLUMN/DROP COLUMN），但ADD COLUMN没问题。当前项目只用ADD COLUMN，所以OK。

---

## P1-4: 拆分巨型前端组件

### 现状

| 组件 | 行数 | 功能域 |
|------|------|--------|
| ProductsView | 981 | 产品表格 + 表单弹窗 + 智能识别 + 图片管理 + 详情弹窗 |
| DashboardView | 765 | 仪表盘概览 + AI聊天(SSE流) + 产品对比 |

### 方案

**ProductsView → 4个子组件**:

```
ProductsView.vue (200行) ← 编排组件
  ├── ProductTable.vue (180行)     ← 表格 + 分页 + 批量操作
  ├── ProductFormModal.vue (250行) ← 新增/编辑表单 + 图片URL
  ├── SmartRecognition.vue (200行) ← 智能识别(文本粘贴/图片粘贴/OCR)
  └── ProductDetailModal.vue (150行) ← 详情弹窗 + 图片
```

**DashboardView → 2个子组件**:

```
DashboardView.vue (200行) ← 概览卡片 + 最近报价
  └── AiChat.vue (400行)  ← 完整聊天: 消息列表 + SSE流 + 对比 + 快捷回复 + 历史管理
```

### 影响范围
- 前端新增5个 .vue 文件
- ProductsView.vue 和 DashboardView.vue 各缩减 70-75%
- 路由不变，仅内部组件拆分
- 需通过 props/emits 或 inject 传递状态

### 风险
高。这是改动量最大的项，涉及大量状态传递重构。建议：
- 每次只拆1个子组件，拆完测试再拆下一个
- 先拆最独立的 ProductDetailModal (最少依赖)
- SmartRecognition 最复杂，最后拆

---

## 执行顺序建议

```
P1-1 (重复函数)  →  风险最低，立即做，净减500行
P1-3 (Migrate)   →  风险中低，VPS一次性操作
P1-2 (拆函数)    →  风险中，需测试多种Excel格式
P1-4 (拆组件)    →  风险最高，逐个拆分，每次验证
```

P1-1 和 P1-3 可以并行做。P1-2 依赖 P1-1 完成（因为 import_products 在 products_bp.py，拆完重复函数后文件更清晰）。P1-4 独立于后端改动。

## 工作量估计

| 项目 | 代码改动 | 测试 | 总时间 |
|------|----------|------|--------|
| P1-1 | 新建2文件 + 2文件删import | 全量pytest | 30min |
| P1-2 | 1文件内重构 | Excel导入E2E | 45min |
| P1-3 | +Migrate配置 | VPS迁移验证 | 30min |
| P1-4 | 新建5组件 + 重构2组件 | 前端全功能验证 | 2-3h |
