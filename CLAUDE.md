# 报价系统 编码规范

本项目遵循 [Andrej Karpathy 的 LLM 编码风格](https://github.com/karpathy/llm-coding-style)，适配报价系统项目。

## 1. Think Before Coding — 先想后写

- 任何多步骤改动**先出方案**，用户批准后再动手
- 清晰列出假设，有歧义就问
- 多种实现路径时，列出优劣不替用户选

## 2. Simplicity First — 最小可用

- 不写没被要求的功能
- 不用一次性的抽象
- 200 行能缩到 50 行 → 重写
- 反问："这个抽象真的需要吗？"

## 3. Surgical Changes — 精准手术

- 只改你要改的，不顺便"优化"相邻代码
- 匹配现有风格（缩进、命名、注释习惯）
- 你的改动导致的孤儿代码要清理（import/变量），但不动原有的
- 测试：每条 diff 必须能追溯到用户需求

## 4. Goal-Driven Execution — 目标驱动

- 把需求转化为可验证的目标
- 每步：操作 → 验证命令 → 预期结果
- 复杂任务用 `todo` 工具分步追踪

## 报价系统特定规范

### 开发流程
- 先方案后实现（权限：`先别动手改，先提方案给我批准`）
- 增量修改（方案A）优于重写（方案B）

### 前端（Vue 3）
- 组件: `<script setup>` + Composition API
- 状态: `reactive()`/composables，不用 Pinia
- 搜索: IME安全 + 500ms防抖 + oninput无需回车
- 拼音搜索: 覆盖 `name` + `spec` 字段（v2.2.0）
- 产品选择器上限: 12 个产品（v2.2.0，原6）
- Vue 自动 XSS 转义（`{{ }}` = `v-text`），不跨页面用 `v-html`
- 导航栏当前页点击刷新（App.vue，v2.2.0）

### 后端（Flask）
- 产品名 XSS 拦截: `<script>/<img>/onerror=/onclick=/onload=/javascript:`
- 产品名截断: 20字
- 普通用户可见admin创建的产品（products_bp 不再按 created_by 过滤，v2.2.0）
- 导出文件名: ASCII文件名 + `filename*=UTF-8` 编码（v2.2.0）
- pytest 测试: venv 在 `/opt/quote-system/venv/`
- ⚠️ 依赖: `flask flask-sqlalchemy flask-cors pyjwt openpyxl pypinyin Pillow`（`pypinyin` 是 lazy import，`import app` 检测不到遗漏；`Pillow` 是 openpyxl 处理图片所需）

### AI 对话

#### 架构总览

```
浏览器 (AiChat.vue)                     Flask (ai_bp.py)                  Hermes Gateway (:8642)          DeepSeek API
  │                                        │                                  │                              │
  │─ SSE 流式请求 ──────────────────────>│                                  │                              │
  │  POST /api/chat                       │─ POST /v1/chat/completions ────>│ (轻量消息, 带 auth key)      │
  │  {input, stream:true,                 │  或                              │                              │
  │   history, conversation_id}           │─ POST /v1/responses ───────────>│ (完整Agent, 带 auth key)     │
  │                                        │                                  │─ agent.run ─────────────────>│
  │                                        │                                  │<─ SSE text deltas ─────────│
  │<─ SSE: connect ──────────────────────│<─ SSE stream ────────────────────│                              │
  │<─ SSE: text delta ──────────────────│                                  │                              │
  │<─ SSE: done + parsed ───────────────│                                  │                              │
  │<─ SSE: quick_replies (并行) ────────│ (收到100字后后台启动LLM生成)       │                              │
```

#### 核心组件

| 组件 | 文件 | 职责 |
|------|------|------|
| AiChat.vue | `frontend/src/components/AiChat.vue` | 对话UI、SSE消费、消息渲染、历史管理 |
| ai_bp.py | `ai_bp.py` | 路由、输入验证、轻量判定、Gateway调用、回复解析 |
| Hermes Gateway | `:8642` | Agent循环、工具调用(DB/API)、模型路由 |
| DeepSeek API | `api.deepseek.com/v1` | LLM推理 |

#### 请求流程

1. **前端**: `sendMessage()` → `apiStream('/api/chat', {input, stream:true, history, conversation_id})`
   - SSE流式需要 `Content-Type: application/json` 头（缺少则 Flask 无法解析 body → "请输入问题"）
   - `history`: 最近3轮对话(6条)，每条截取200字，改善多轮连贯性
   - `conversation_id`: 前端session ID，Gateway据此维护对话session

2. **后端 ai_chat()**: 
   - **速率限制**: 内存计数器（threading.Lock），每分钟5次（v2.4.0改为内存，原是DB COUNT）
   - **轻量判定**: `_is_lightweight()` 正则匹配问候/确认/帮助类简单消息 → 走 `/v1/chat/completions`
   - **正常消息**: 走 `/v1/responses`（Agent循环，有工具调用能力）
   - **max_tokens 动态调整**: 列表/报价类2000，分析/推荐类1500，默认800
   - System prompt 有30s TTL缓存（`_prompt_cache`），不变时不重复发送 instructions
   - Gateway 调用需要 `Authorization: Bearer {QUOTE_GATEWAY_KEY}` 头

3. **Gateway**: 
   - Profile: `qoute`（`/home/tong/.hermes/profiles/qoute/config.yaml`）
   - model.provider: `deepseek`，读取 `DEEPSEEK_API_KEY` 环境变量
   - API Server key: `qs-65bf75614bdd4245`（`api_server.extra.key`）

4. **SSE 流式** (`_ai_chat_sse`):
   - 透传 Gateway `/v1/responses` SSE stream → 解析 `response.output_text.delta` 事件
   - **并行 quick_reply**: 累积100字后后台线程启动 LLM 生成，主回复完成后 join(2s)
   - 事件类型: `connect` → `first_token` → `text` → `done`(+parsed) → `quick_replies` → `[DONE]`

#### 配置

```bash
# /opt/quote-system/.env
QUOTE_GATEWAY_URL=http://127.0.0.1:8642
QUOTE_GATEWAY_KEY=qs-65bf75614bdd4245
DEEPSEEK_API_KEY=sk-...

# Gateway systemd 需注入 DEEPSEEK_API_KEY
# /home/tong/.config/systemd/user/hermes-gateway-qoute.service.d/override.conf
Environment="DEEPSEEK_API_KEY=sk-..."
```

#### 价格解析: 8 种 Pattern + 黑名单

Pattern 1-7 覆盖 ¥ 和 元 格式（v2.2.0），Pattern 4 已合并（v2.4.0）：
- Pattern 1: "产品名 — ¥价格"
- Pattern 2: 型号（描述）上下文内查找价格
- Pattern 3: "产品名 N台 ¥价格" 或 × 格式
- Pattern 4 (合并): 型号 + ¥/元 价格（紧凑格式/品牌/单位后缀）
- Pattern 5: markdown 表格行
- Pattern 6: (ID=N) 产品ID引用，返回 product_id 字段
- Pattern 7: 价格回溯——先找 ¥/元价格，向上2行找型号

非产品词黑名单（v2.4.0）：成本价、销售价、单价、合计、方案一/二/三 等，最终过滤。

#### 一键创建报价单

- AI 回复中提取的产品名/ID → `parsed.products` → 前端"一键创建报价单"按钮
- 优先传 `product_ids` 参数 → `autoAddProductsById()` 按ID精确匹配
- 否则传 `products` 参数（产品名）→ `autoAddProducts()` 按名称搜索匹配

#### SSE 日志写入

在 generator 外部（请求上下文内）记录使用，避免流式传输中误计使用次数。

### 本地开发环境
- 仓库: `~/quote-system`
- macOS AirPlay Receiver 占 5000 端口 → 改用 5001
- Vite 代理需 rewrite `/quote/` 前缀
- 启动: 终端1 `python app.py` + 终端2 `cd frontend && npx vite --host`
- E2E 测试需 nginx 代理: `nginx -c /tmp/quote-nginx.conf` (模拟 VPS `/quote/` → Flask `/`)

### Univer 独立表格编辑

v2.5.0 新增 Univer 电子表格编辑器，完全独立于 Vue，用于报价单的所见即所得编辑。

#### 架构

```
QuotePreviewModal.vue                     univer.html + univer-main.js
  │  │
  │  ├─ "编辑表格"按钮 → window.open(univer.html?quoteId=X&token=Y)
  │
  ├─ 预览卡片显示（HTML 渲染，无加粗/无换行）
  │
  └─ Univer 编辑器显示（应与预览卡一致）
```

#### 核心文件

| 文件 | 职责 |
|------|------|
| `frontend/univer.html` | Univer 入口 HTML，Vite 多页面构建 |
| `frontend/src/univer-main.js` | 全部逻辑：导入/导出/编辑器初始化/图片处理 |

#### 导入流程（从后端 xlsx → Univer 快照）

```
后端 API /api/quotes/{id}/export-excel
  → ExcelJS 读 xlsx
  → extractImages() 先提取图片（JSZip 解析 xl/drawings/ + xl/media/）
  → stripDrawings() 剥离图片节点（解决 ExcelJS 4.4.0 anchors 解析 crash）
  → xlsxToSnapshot() 转换样式/数据为 Univer 快照格式
  → createUnit() 加载到 Univer
```

#### 导出流程（从 Univer 快照 → 下载 xlsx）

```
doExportXlsx()
  → workbook.save() 获取快照
  → 解析 cellData / styles / mergeData / colD / rowD
  → ExcelJS 写 xlsx
  → IMAGE 公式 → 提取 base64 → addImage() 嵌入图片（nativeCol/nativeColOff 居中）
  → 表头行固定行高，数据行自适应（图片行确保 min-height）
```

#### 样式策略

| 属性 | 导入 | 导出 | 原因 |
|------|------|------|------|
| 对齐（横/纵） | ✓ | ✓ | |
| 字体颜色 | ✓ | ✓ | 预览卡第一行灰色字 |
| 背景填充 | ✓ | ✓ | 标题行黄色 |
| 边框 | ✓ | ✓ | |
| 列宽/行高 | ✓ | ✓ | |
| 合并单元格 | ✓ | ✓ | |
| 加粗 | ✗ | ✗ | 模板全加粗，预览卡仅一行 |
| 斜体/下划线/删除线 | ✗ | ✗ | 预览卡没有 |
| 字体/字号 | ✗ | ✗ | 用 Univer 默认 |
| 自动换行 | ✗ | ✗ | 与预览卡一致 |

#### 图片处理

- 导入时：`extractImages()` JSZip 解析 `xl/drawings/drawing1.xml` + `xl/drawings/_rels/`，读取 `xl/media/` 图片 → 分块 base64 → `=IMAGE(url, "", 3, h, w)` 公式
- 导出时：解析 IMAGE 公式提取 base64 → `wb.addImage()` → `nativeCol`/`nativeColOff` 定位居中
- ExcelJS 4.4.0 的 anchors 崩溃通过 `stripDrawings()` 绕过
- 图片等比缩小到单元格内（留 4px 边距），水平+垂直居中

#### 工具栏

- 最左侧"下载 xlsx"按钮（`sheet.command.download-xlsx`）
- Ctrl+S / Cmd+S 快捷键（document capture 拦截，不注册 IShortcutService 避免双触发）
- Univer 中文界面（9 个 locale 模块 deepMerge）

#### 下拉填充后行高修复

`sheet.command.auto-fill` 等命令执行后 100ms 触发 `set-row-is-auto-height`，防止行高丢失。

#### 已知限制

- `@univerjs/drawing` 插件未注册，不支持浮动图片
- Univer 样式快照用 `bl`/`it`/`ff`/`fs`/`cl` 作为顶层属性（非 `ft` 子对象）
- `WrapStrategy`: OVERFLOW=1, CLIP=2, WRAP=3
- ExcelJS `addImage` 必须用 `nativeCol`/`nativeColOff` 定位（`col`/`colOff` 会被覆盖）

#### E2E 测试

```bash
cd ~/quote-system && python3 -m pytest tests/test_e2e_univer.py -v
```

| 测试 | 覆盖 |
|------|------|
| `test_page_loads_and_univer_initializes` | 页面加载、Univer 初始化、零 JS 错误 |
| `test_export_produces_valid_xlsx` | 导出 xlsx：行/列、合并单元格、黄色填充、表头 |
| `test_export_with_images` | 有图片产品的导出完整性 |
| `test_missing_params_shows_error` | 缺参数 → 错误提示 |
| `test_bad_token_shows_error` | 无效 token → 错误提示 |
| `test_no_console_errors_on_load` | 正常加载零 JS 异常 |

测试通过 `window.__univerDownload()` 和 `window.__univerLastBuffer` 与导出逻辑交互（Univer 工具栏是 Canvas 渲染，无法用 DOM 选择器定位按钮）。

### 通用
- 中文回复，表格式数据用 bullet 不用 pipe table
- 多步操作给 ✓ 进度
- 发现 bug 给精确反馈（DOM选择器/行号/根因）
- **测试数据自动清理**：`pytest_sessionfinish()` 钩子在测试结束后自动删除所有 `test_%`/`testpw_%`/`disabletest_%` 用户、`测试%` 产品、`测试%` 报价单。手动测试也要清理，不要留垃圾数据。

## 测试规范

```bash
# API 测试（生产环境）
cd /opt/quote-system && python3 -m pytest tests/test_auth.py tests/test_products.py tests/test_quotes.py tests/test_admin.py tests/test_edge_cases.py tests/test_comprehensive.py -v

# E2E 测试（Vue 前端）
cd /opt/quote-system && /opt/quote-system/venv/bin/python -m pytest tests/test_e2e_vue.py -v

# Univer E2E 测试（需 Vite dev server 运行）
cd ~/quote-system && python3 -m pytest tests/test_e2e_univer.py -v

# 本地开发
cd /tmp/quote-system && source venv/bin/activate && python -m pytest tests/ -v
```

## 部署

```bash
cd /opt/quote-system && git pull                    # ← 必须先拉最新代码
cd /opt/quote-system/frontend && npm run build
sudo systemctl restart quote-system
# 回退: rm -rf /opt/quote-system/frontend/dist && sudo systemctl restart quote-system
```

**重要**: 生产环境通过 nginx `/quote/` → Flask `/` 代理。Vite `base: '/quote/'`，Vue Router `createWebHistory(import.meta.env.BASE_URL)`。所有 API 调用使用动态 `BASE_URL`（dev=`''`, prod=`/quote`），路径如 `BASE_URL + '/api/products'`。
