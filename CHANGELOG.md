# 更新日志

## v3.0.0 (2026-05-29) — AI 引擎自研

### 自研 AI Engine 替代 Hermes Gateway

- **新 `ai/` 包**: engine(LlmEngine), context(ContextBuilder), tools(ToolRegistry), session(SessionManager), sse(SseAdapter), reply_parser, agent
- DeepSeek API 直连，OpenAI-compatible 格式，支持 function calling
- 服务端对话持久化（AIConversation + AIMessage 表），每轮加载完整上下文
- 流式 SSE 使用 `stream_with_context`，支持 GenUI `component` 事件
- 模型选择: flash(快速)/pro(深度推理) 前端下拉框切换

### GenUI 渲染池

- `componentRegistry` + `<component :is>` 动态组件渲染
- ProductCompareCard: 勾选对比 + 创建报价单
- QuoteDraftCard: 预览 + 下载，tool 结果直接提取 created_quote
- SSE `component` 事件自动触发

### v2.6.0 产品高级功能

- 15 张新表: 字典(4)、M2M(5)、分类树、规格定义、供应商、制造商、产品图片、产品依赖
- Product 扩展 10 字段: model, category_id, manufacturer_id, supplier_id, specs(JSON), status 等
- 分类管理 + 字典管理 前端页面
- 导入导出适配新表结构
- 生产数据迁移（456 产品 → 新表）

### 前端重构

- 统一 UI 风格: `.page-header`, `.card-modern`, `.table-modern`, `.btn-modern`
- 产品数据库页面（product-db 移植）
- AiChat SSE 超时处理（30s）、错误恢复
- 快捷按钮黑名单过滤

### 测试

- Backend: 138/138 通过
- UI: 15/15 页面渲染 + 17/17 功能流程

---

## v2.3.0 (2026-05-24)

### 后端重构 — 消除循环依赖 + Blueprint 合并

- 新建 `helpers.py`：提取 `get_setting`/`get_all_settings`/`get_field_visibility`/`filter_fields_for_user`/`preload_products_for_quote`/`check_quote_owner`，`app.py` 不再被任何模块 import
- Blueprint 从 11 个合并为 5 个（auth/products/quotes/admin/ai），消除 `download_bp` 命名冲突
- 修复硬编码 `helloworld` OCR API Key 默认值（3 处）
- Float → `Numeric(asdecimal=False)` 迁移（7 个货币字段），保持 jsonify 兼容
- `Product.to_dict()` N+1 查询修复：`users_map` 预加载
- `DownloadLog.quote` 级联删除修复：审计日志不再随报价单删除
- 新增 DB 索引：`products.sku`、`products.supplier`、`ai_usage_logs(user_id, created_at)` 复合索引

### 前端优化

- API 调用统一：`useApi.js` 新增 `apiRaw`/`apiStream`，消除 6 处原生 `fetch()` 调用，401 自动处理覆盖率 100%
- XSS 防护：`AiChat.vue` `renderContent` 输出加 `DOMPurify.sanitize`
- 新增 `useFocusTrap` composable：3 个模态框支持焦点锁定 + Esc 关闭
- 死代码清理：删除 `static/js/`（2089 行）、删除未用 import/export
- E2E 测试选择器更新：测试适配当前 UI（nginx 代理模式）

### 测试

- API 测试：138/138 通过
- E2E 测试：34/34 通过

---

## v2.2.0 (2026-05-22)
### 🔧 功能增强 + Bug 修复

**产品管理：**
- 产品列表添加创建人列（ProductTable.vue）
- 普通用户可见 admin 创建的产品（products_bp.py 查询不再按 created_by 过滤）
- 拼音搜索覆盖 spec 字段（pinyin_search 索引含 spec 内容）
- 产品选择器上限 6 → 12

**导出/预览文件名修复：**
- 导出文件名 xlsx.xlsx 修复：后端使用 ASCII 文件名 + 前端优先解析 filename*=UTF-8
- 预览下载文件名双下划线修复：优先 filename* 解码 + title 以 client 开头时去重
- AI 下载 Excel 文件名公司名重复修复：title 包含 client 时去重

**AI 对话增强：**
- AI 对比列表价格提取全面支持 ¥ 和 元 格式（Pattern 1b/1c/2/3b/4b/4c/5/6/7）
- Pattern 6：(ID=N) 产品 ID 引用，返回 product_id 字段
- Pattern 7：价格回溯——先找 ¥/元 价格，向上 2 行找型号（支持中文括号/星号/破折号格式）
- 一键创建报价单：前端优先传 product_ids 参数，NewQuoteView 直接用 ID 查产品（autoAddProductsById）
- 方案 quick_replies：支持「方案A（描述）」格式，去掉重复括号
- AI 对话框试试问我按钮文案：甲醛空气质量检测仪 / 张经理创客空间项目200个共享工位要占用检测 / 华为的任总需要园区能耗分析方案
- AI 使用次数不变：SSE 日志改在 generator 外部写入（请求上下文内），避免流式传输中误计

**报价单预览：**
- 备注移入表格内，总价行下一行，9pt 左对齐固定文案

**导航：**
- 导航栏当前页点击刷新（App.vue）

## v2.1.0 (2026-05-22)
### 🏗️ 架构重构 v2.1 — Blueprint 拆分 + 安全修复 + 组件化

**P0 安全/运维修复：**
- XSS 修复：`renderTable` 使用 `escHtml` 转义
- 管理员密码脱硬编码：空值 → 随机生成写入 `.admin_password`
- AI prompt 脱敏：系统路径/内部服务替换为 `[系统路径]/[内部服务]`
- SQLite 备份 crontab 03:00 UTC（Python `sqlite3.backup()`）
- logrotate crontab 03:15 UTC

**P1-1: 12 个重复函数提取：**
- 新建 `utils.py`（64 行）：`_debug_log`, `_log_ai_usage`, `_safe_number`, `_compute_pinyin_search`
- 新建 `product_utils.py`（516 行）：8 个识别/图片/解析/压缩函数
- app.py 净减 ~500 行，products_bp.py 净减 ~500 行

**P1-2: import_products 拆分（CC=83 → 6 个子函数，各 CC<15）：**
- `_FIELD_MAP` + `_find_col`、`_parse_excel_header`、`_detect_supplier_col`、`_extract_embedded_image`、`_process_import_row`、`_import_all_sheets`

**P1-3: Flask-Migrate 替代手动 ALTER TABLE：**
- `Migrate(app, db)` 初始化 + migrations/ 目录
- 过渡期保留 `_auto_migrate_columns` 兜底

**P1-4: 前端巨型组件拆分：**
- ProductsView 981→110 行 → 4 子组件：ProductTable(350) + ProductFormModal(302) + SmartRecognition(292) + ProductDetailModal(71)
- DashboardView 765→138 行 → 1 子组件：AiChat(660)

**P1-5~8: 短期改进：**
- BASE_URL 提取到 useApi.js 统一导出（消除 8 处重复）
- 裸 fetch 统一为 api() 封装，localStorage.getItem→authToken.value
- 拼音搜索删除死代码回退路径，移除回填 limit 500
- AI 速率限制从进程级变量改为 DB 查询（AIUsageLog，多 worker 共享）

**依赖：** requirements.txt 新增 `flask-migrate>=4.0`

## v1.7.9 (2026-05-21)
### 📝 文档全面更新 + 测试增强
- **全量文档同步**：README、REQUIREMENTS、TEST_REPORT、tests/README 全部更新至当前 API 196 项测试覆盖
- **测试覆盖增长**：127 → 161 API 测试（+34 项），Vue E2E 34 项保持
- **智能识别字段排序优化**：表单字段智能排序
- **原始数据展示区**：完整 API 响应展示
- **移除豆包入口调试日志**
- **Gateway 调用简化**：移除 endpoint 逻辑，直接用标准 model 名

## v1.7.8 (2026-05-20)
### 🔍 智能识别管道重构 + 功能增强
- **三层管道**：豆包 Vision → DeepSeek V4 Flash → 正则解析（图片和文字均覆盖）
- **DeepSeek 文本解析**：新增 `deepseek_parse_product()`，调用 Gateway DeepSeek V4 Flash 从非结构化文本提取结构化 JSON，作为 OCR 和文字粘贴的主力解析器
- **可编辑识别结果**：红框识别区域改为 9 个可编辑输入框（含功能描述），用户可手动修正 OCR/LLM 错误后再填入表单
- **识别来源标签**：标题右侧显示 `豆包 Vision` / `DeepSeek V4 Flash` / `正则解析` 灰色标签
- **原始数据展示**：可折叠区域显示模型返回的原始 JSON/文本，方便复制粘贴
- **成本价全用户可见**：新增/编辑产品表单中成本价字段不再仅管理员可见
- **弹窗关闭保护**：新增/编辑产品弹窗取消点击空白处关闭，仅通过 X 或取消按钮关闭
- **修复**：豆包 API Key 格式错误导致 401 → 更换正确 Key；DeepSeek 超时 15s → 30s

## v1.7.7 (2026-05-20)
### 🎨 分页统一样式 & 用户管理增强
- **报价单页**：顶栏新增总数「共 X 条」+ 每页条数选择器（10/20/50/100）
- **管理页用户列表**：完整分页支持（总数 + 每页条数选择器 + 上一页/下一页导航），搜索改为服务端分页
- **三页分页样式统一**：报价单、产品、管理页使用相同的分页栏（首页/上一页/页码/下一页/末页）
- **用户"上次登录"列**：新增 `last_login` 字段，登录时自动更新，管理页显示（从未登录 → 灰色提示）
- **下载统计卡片**：样式对齐报价单卡片（上方大数字 + 下方「共 X 次」）
- **修复 502**：误将 `last_login` 加到 Product/Quote 模型导致启动崩溃，已移除并在 User 模型正确添加
- **用户计数防换行**：「共 X 个用户」加 `white-space:nowrap` 防止折行
- **新建报价底部保存按钮**：长表单底部增加操作栏
- **产品表格文案修正**：「产品信息」→「产品名称」，规格型号列 hover tooltip
- **下载列格式**：显示「5次」而非「5」
- **注册控制**：紧凑化布局 + 说明文字
- **AI Prompt 编辑器**：保存按钮移至卡片标题栏


## v1.7.6 (2026-05-19)
### 🛡️ AI 身份注入修复
- **身份指令注入用户消息**：自定义 Prompt 第一行身份声明（你是童小军的 AI 助手...）自动注入到每条用户消息头部，对抗 Gateway 基础 persona 覆盖
- **Prompt 变更自动注入**：hash 对比机制，Prompt 变更时清空 AIChatSession、重新发送 instructions 到 Gateway
- **三层兜底**：Prompt instructions → `[系统指令 — 最高优先级]` 追加 → 用户消息头部注入
- **修复验证**：`你是谁` / `介绍一下你` / 产品搜索等任意消息均正确返回「童小军的 AI 助手」身份，不出现 Hermes / Nous Research

## v1.7.5 (2026-05-19)
### 🔧 交互优化与 Bug 修复
- **导航精简**：产品管理 / 报价管理 / 导入导出，+ 号移至报价管理右侧
- **管理页 AI Prompt 编辑器**：管理员可在线编辑系统提示词，保存即时生效，支持恢复默认
- **加载状态重构**：进度条 + 4 阶段列表 → 单行状态条（图标 + 文字 + 计时器），流式中与消息底部栏合并显示
- **SSE 流式修复**：token key 从 `token` 改为 `quote_token`，修复认证失败；跳过 `response.output_item.done` 解决回复重复
- **TTFT 计时**：SSE 增加 `first_token` 事件，前端阶段精简为连接→思考→生成回复
- **历史记录面板**：Teleport 到 body 层 + 按钮下方自动定位 + 遮罩层关闭，修复点击无反应
- **购物车跳转**：AI 产品卡片购物车按钮 → 新建报价单自动搜索并填入产品（多策略回退：全名→分词→型号）
- **产品解析优化**：正则支持编号列表格式，空格分隔避免型号横杠误匹配，不跨行匹配
- **首页布局**：最近报价卡片移至 AI 产品助手下方

## v1.7.4 (2026-05-19)
### 🤖 AI 聊天全面升级
- **SSE 流式输出**：后端 `/api/chat` 支持 `stream: true`，Gateway Responses API 透传 SSE，前端 EventSource 接收，进度条反映真实 token 生成
- **快捷回复按钮**：AI 问"沿用还是新建？"时自动渲染可点击按钮，一键回复
- **产品卡片渲染**：AI 推荐产品时提取产品名+价格，显示为卡片（可点击加入对比）
- **产品对比表**：勾选 2+ 产品后弹出对比表，可一键创建含对比产品的报价单
- **一键创建报价单**：AI 消息底部固定「一键创建报价单」按钮，直接跳转 NewQuote 页面
- **上下文引用**：AI 回复中的 `#N` / `报价单 N` 自动转为可点击链接，跳转报价单列表
- **消息操作**：每条 AI 回复底部加入复制/重新生成/赞/踩按钮
- **对话历史**：localStorage 存储对话历史，右上角面板可切换/新建对话
- **后端解析**：`_parse_reply_actions()` 自动提取产品+报价引用+快捷回复，接口返回 `parsed` 字段

## v1.7.3 (2026-05-19)
### 🎨 7 项设计与架构优化
- **AI 聊天高度**：400px → 60vh，自适应窗口
- **表格斑马纹**：`.table-modern > tbody > tr:nth-child(even)` 交替背景色
- **移动端侧边栏**：已有 hamburger toggle + overlay + 动画
- **进度条说明**：当前前端模拟阶段进度，Gateway 需 SSE 支持才能实现真实进度
- **邮件模态框**：`prompt()` → 专用 Modal（邮箱输入 + Enter 发送）
- **下载错误反馈**：`<a>` 标签盲点 → `fetch` + blob + toast 错误提示
- **auth 模块提取**：auth.py (Blueprint)，app.py 2898 → 2545 行

## v1.7.2 (2026-05-19)
### 🔧 优化与架构改进
- **多 worker 安全修复**：`_initialized_convos` 内存 set → `AIChatSession` 表，Gunicorn 多进程下不会重复注入 AI instructions
- **批量删除 API**：新增 `DELETE /api/quotes/batch`，N 次请求 → 1 次，前端接入
- **模块拆分**：提取 `models.py`（8 个模型类）+ `extensions.py`（db 独立模块），app.py 2898 → 2705 行
- **模型配置化**：AI 模型从 `QUOTE_AI_MODEL` 环境变量读取，默认 `deepseek-v4-flash`
- **分页边界简化**：`pageNumbers` 逻辑重写，去掉 `totalPages - 6` 歧义计算

## v1.7.1 (2026-05-19)
### 🤖 AI 对话升级 — Hermes Gateway Responses API
- **Chat Completions → Responses API**：`POST /v1/chat/completions` → `POST /v1/responses`
- **服务端会话存储**：`conversation=quote-user-{id}` 按用户隔离，页面刷新不丢对话
- **前端极简化**：从 `{messages: [全部历史]}` → `{input: "一句话"}`，3 行代码变 1 行
- **instructions 自动复用**：system prompt 首轮注入，无需每轮重发（省 ~1K token/轮）
- **工具调用过滤**：Flask 只返回最终文本，用户看不到内部 SQL/终端命令
- **用户身份注入**：AI 首轮知晓当前用户，通过 `/api/ai/token` 以正确身份操作报价
- **truncation: auto**：自动截断超长对话（100 条历史）

### 🏗️ 架构简化
- Flask 不直接 import Hermes（去掉 `run_agent`、`httpx`、`websockets`、`openai` 等依赖）
- AI 会话池由 Gateway 独立管理（`systemd Restart=always`），gunicorn 重启不丢
- Flask 代码从 ~90 行减至 ~40 行

### 🧪 测试
- 127/127 API 测试通过

## v1.7.0 (2026-05-17)
### 🔍 报价单管理增强
- **搜索过滤**：报价单列表新增搜索框（标题/客户），支持拼音+中文，500ms 防抖，IME 安全
- **分页控件**：底部页码导航（首页/上页/页码/下页/末页），显示「共 N 条，第 X/Y 页」
- **批量删除**：表头全选框 + 行复选框，批量删除确认弹窗，删除后计数反馈
- **筛选修复**：状态「已接受」(accepted → confirmed) 修复、创建者列 `created_by_name` 显示修复

### 🛠 管理员功能
- **删除用户**：新增 `DELETE /api/admin/users/<id>` 端点，管理员可删除普通用户（不可删自己/管理员）

### ✨ 新建报价单增强
- **产品选择器修复**：搜索过滤后选中产品不丢失（Picker map 缓存完整产品数据）
- **分类标签筛选**：产品选择器搜索框上方新增分类标签行，点击快速筛选
- **电话验证**：输入框 `type="tel"`，自动过滤非数字字符
- **邮箱验证**：`type="email"` + 保存时格式校验

## v1.6.0 (2026-05-16)
### 🎨 Vue 3 前端重构
- **全站 Vue 3 SPA** 替换旧版原生 JS SPA
- Composition API + `<script setup>` + `reactive()` 状态管理
- Vue Router 历史模式 (`createWebHistory('/quote/')`)
- CDN 加载，零构建工具依赖（仅 Vite 打包生产环境）
- 文件拆分：`ProductsView` / `QuotesView` / `NewQuoteView` / `LoginView` / `AdminView` / `ImportView` / `DashboardView`

### 🧠 火山引擎豆包视觉识别
- **主力模型**：`doubao-seed-1-6-lite-250815`（火山引擎豆包 Seed Lite）
- 替换 OCR.space → 豆包直出结构化 JSON（名称/规格/厂商/价格/分类/功能描述/备注）
- 支持降级兜底：豆包失败 → OCR.space → smart_parse_product
- 模型可切换：支持 `doubao-seed-2-0-mini-260215` / `doubao-seed-2-0-lite-260215`
- 图片智能识别无需压缩 — 原图直传豆包 Vision API

### 🖼 产品图片全面增强
- **图片压缩**：PIL 压缩到 ≤100KB，透明 PNG 自动贴白底转 JPG
- **URL 下载**：新增 `POST /api/download-image`，从 URL 下载图片并保存
- **Excel 嵌入**：报价单导出新增第 12 列「图片」，产品图片嵌入单元格内居中
- **预览嵌入**：报价单预览新增图片列，`max-width:100px` 内嵌
- **Excel 列布局**：11 列 → 12 列（+图片列），合并单元格范围修正

### ✨ 智能识别增强
- **prompt 拆分**：`remark` 拆为 `function_desc`（功能描述）+ `remark`（内部备注）
- 识别结果自动填入对应字段（功能描述→功能描述框，备注→备注框）
- 文字解析保留全部 5 字段定位置解析能力

### 🐛 Bug 修复
- **全选复选框**：`toggleAll()` 逻辑修复，根据当前状态切换而非依赖传参
- **字段可见性 API**：兼容 dict `{key: bool}` 和数组 `[{field_name, user_visible}]` 两种格式
- **Token URL 参数兜底**：`check_auth()` 支持 `?token=` URL 参数（用于 `<a>` 标签下载）
- **下载记录 cascade**：`DownloadLog.quote` backref 增加 `cascade='all, delete-orphan'`
- **金额精度**：全站 `price` / `cost_price` / `unit_price` / `tax_rate` 统一 `round(,2)`
- **XSS 防护**：产品名 `<script>` / `onerror=` 等拦截返回 400（非 201）

### 🎨 UI 优化
- **Toast 位置**：右下角 → 右上角，不再遮挡产品列表操作按钮
- **预览/导出表头**：公司名+客户信息行 → 黄色标题行 → 表头行的三行结构

### 🏗️ 架构变更
- **Vue SPA** 构建产物通过 Flask `send_file` / `send_from_directory` 托管
- **SPA catch-all** 路由：所有非 API 路径返回 `index.html`（Vue Router 接管）
- **Nginx 反向代理**：`/quote/` → Flask `/`，Vite `base: '/quote/'`
- **开发/生产兼容**：前端 `BASE_URL` 动态判断（dev=`''`, prod=`/quote`）

## v1.5.6 (2026-05-15)
### 🐛 预览/导出 5 项修复
- **预览**：`info_parts` 补全税率 `税率：5%`，备注行改为 `quote.remark`（有备注时显示备注，无备注时回退默认提示）
- **Excel**：
  - `YELLOW_FILL` 颜色值修正：`FFFFFF00` (白) → `FFFF00` (黄)
  - `export_quote_excel` 行序修正：Row1=黄色标题 / Row2=公司+客户信息（与 `_build_excel` 统一）
  - info 行补全税率 `税率：5%`
- **测试**：新增预览/导出 openpyxl 验证脚本，E2E 全覆盖

## v1.5.5 (2026-05-15)
### 🐛 修复编辑报价单毛利始终为 0
- **根因**：`productsCache` 只缓存产品列表第 1 页（20 条），编辑报价时产品不在缓存中 → 找不到 `cost_price` → 毛利为 0
- **修复**：双重回退机制 — 优先用缓存 `cost_price` 实时计算，缓存未命中则用后端存储的 `item.profit` × 数量

## v1.5.4 (2026-05-15)
### 🎨 UI 统一重构
- **概览页** → 上下布局（统计卡片 → 最近报价（全宽）→ 快速操作（全宽））
- **导入页** → 上下布局（上传卡片 → 说明卡片）
- **CSS 重构**：350 行 → ~310 行，新 Token 变量（`--card-radius`, `--card-padding`, `--card-gap`, `--btn-radius`, `--transition-*`）
- **新增 CSS 类**：`.page-header`（统一页面标题）、`.form-label-modern`（统一表单标签）
- 按区块重组：Tokens / Sidebar / Layout / Header / Cards / Tables / Forms / Buttons / Components / Animations / Responsive

## v1.5.3 (2026-05-15)
### 🎨 管理页面 → 上下布局
- 旧布局（左右分割）：用户管理(左) + 字段可见/注册设置(右) / 系统设置(左) + SMTP(右)
- 新布局（上下分割）：用户管理 → 字段可见\|注册设置(并排) → 系统设置\|SMTP(并排) → 发票OCR → 下载记录

## v1.5.2 (2026-05-15)
### 🧾 发票 OCR 成本更新
- 新增 `POST /api/products/ocr-cost` + `POST /api/products/update-costs` 端点
- 上传进货单/采购单图片 → OCR 识别产品名+成本价 → 模糊匹配产品库 → 批量更新 `cost_price`
- 模糊匹配算法：发票名包含产品名(+50)、包含规格(+30)、包含厂商(+10)、token 命中(+5/token)
- 管理页面新增「发票OCR → 更新成本价」卡片（管理员可见）
- 使用 `@require_admin` 保护端点

## v1.5.1 (2026-05-15)
### 📊 合计行简化
- 去掉成本列，毛利/毛利率用绿盈红亏颜色区分（`var(--success)` / `var(--danger)`）
- 每行毛利颜色与合计行一致

## v1.5.0 (2026-05-15)
### 🇹🇼 台湾税率支持
- **逻辑**：单价 = 含税价 → 算毛利时 `税前价 = 单价 / (1 + 税率/100)` → `(税前价 - 成本) × 数量`
- **模型**：`Quote.tax_rate` (Float, 默认 0)
- **界面**：基本信息区新增 `税率(%)` 输入框（0~100, 步长 0.1），改税率实时刷新毛利
- **合计行**：`¥总价 | ¥总毛利 | 利率% | 税额 ¥XXX`
- 税率=0 时：税前价=含税价，税额隐藏，行为不变

## v1.4.6 (2026-05-15)
### 📊 合计行增加毛利率
- Footer: `合计 | ¥total | ¥profit | rate% | 税额 ¥tax` 5列

## v1.4.5 (2026-05-15)
### 🐛 修复毛利 = (售价-成本) × 数量
- 之前每行毛利只显示单件毛利，不随数量变化
- 修复后改数量实时刷新每行毛利
- 备注显示在预览/导出中

## v1.4.4 (2026-05-15)
### 🐛 修复保存必填校验 + onclick 安全
- 标题/客户/联系人/电话四项必填，精确提示缺哪个
- 修复 `escJs()` 处理产品名中的换行符

## v1.4.3 (2026-05-15)
### 📝 每行备注 + 布局重构
- 报价明细每行新增备注输入框
- 基本信息区域移到上方（全宽），明细表在下
- 保存/返回按钮移至表格下方

## v1.4.2 (2026-05-15)
### 🔐 全站鉴权门
- `renderPage()` 入口统一拦截未登录用户
- 修复 `showLoginPage()` 不隐藏 mainWrapper

## v1.4.1 (2026-05-15)
### 🔢 数量强制整数
- 前端 `type="number" min="1"` + `parseInt()` + `oninput` 过滤
- 后端 `db.Integer` + `int()`

## v1.4.0 (2026-05-14)
### ✨ 7 项需求
- **#5 报价预览修复**：iframe 改 Blob URL + token
- **#6 Excel 页脚修复**：仅 bank_account 非空时显示
- **#7 Excel 第一行格式**：项目名称黄底 + 公司/客户第二行
- **#4 OCR 单产品**：一次识别仅取一个产品，自动填入表单
- **#2 产品上线/下线**：`is_active` 字段 + toggle API + 管理员下线按钮
- **#3 邮件发送**：SMTP 配置 + `POST /api/quotes/<id>/send-email`
- **#1 用户权限精细化**：标记待做

### 🐛 数量小数问题修复

## v1.3.9 (2026-05-14)
### 📋 系统设置自定义导出
- 新增 `SystemSetting` 模型（key-value）
- 公司名称 + 页脚文字可在导出中使用

## v1.3.8 (2026-05-14)
### 🔄 拖拽排序
- HTML5 Drag and Drop，`⋮⋮` 手柄
- `sort_order` 字段，保存时自动设置

### ⚡ N+1 查询修复
- `Quote.to_dict(users_map=)` 预加载用户名

## v1.3.7 (2026-05-14)
### 🏗️ 前端架构拆分
- 单文件 2285 行拆分为 app.js (292) + auth.js (153) + products.js (1357)

### 🔍 搜索统一增强
- 所有搜索框支持拼音/缩写 + IME 适配
- 防抖统一 500ms

### 🐛 修复
- `searchDelay` 缺少结尾 `}` 导致 JS 崩溃
- `pinyin()` 返回类型索引错误

## v1.3.6 (2026-05-14)
- 拼音搜索：全拼 `hongwai` → 红外，首字母 `hw` → 红外/华为

## v1.3.5 ~ v1.3.2
- 多用户 JWT 认证 + SHA256
- 权限分权、字段可见性控制
- 管理员面板：用户管理、改密、注册开关

## v1.3.1
- 修复 Gunicorn 多 worker JWT secret 不一致

## v1.3.0
- 完整认证系统

## v1.2.x
- 产品 CRUD、报价单 CRUD、Excel 导入导出
- 多 Sheet 导入、图片上传粘贴
- 报价单下载、状态流转、客户聚合、利润概览
