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
- 价格解析: 7 种 Pattern 全面支持 ¥ 和 元 格式（v2.2.0）
- Pattern 6: (ID=N) 产品 ID 引用，返回 product_id 字段
- Pattern 7: 价格回溯——先找 ¥/元价格，向上 2 行找型号
- 一键创建报价单: 前端优先传 product_ids 参数，autoAddProductsById
- 方案 quick_replies: 支持「方案A（描述）」格式，去掉重复括号
- SSE 日志写入: 在 generator 外部（请求上下文内），避免流式传输中误计使用次数

### 本地开发环境
- 仓库: `~/quote-system`
- macOS AirPlay Receiver 占 5000 端口 → 改用 5001
- Vite 代理需 rewrite `/quote/` 前缀
- 启动: 终端1 `python app.py` + 终端2 `cd frontend && npx vite --host`
- E2E 测试需 nginx 代理: `nginx -c /tmp/quote-nginx.conf` (模拟 VPS `/quote/` → Flask `/`)

### 通用
- 中文回复，表格式数据用 bullet 不用 pipe table
- 多步操作给 ✓ 进度
- 发现 bug 给精确反馈（DOM选择器/行号/根因）
- **测试数据自动清理**：`pytest_sessionfinish()` 钩子在测试结束后自动删除所有 `test_%`/`testpw_%`/`disabletest_%` 用户、`测试%` 产品、`测试%` 报价单。手动测试也要清理，不要留垃圾数据。

## 测试规范

```bash
# API 测试（生产环境）
cd /opt/quote-system && python3 -m pytest tests/test_auth.py tests/test_products.py tests/test_quotes.py tests/test_admin.py tests/test_edge_cases.py tests/test_comprehensive.py -v

# E2E 测试
cd /opt/quote-system && /opt/quote-system/venv/bin/python -m pytest tests/test_e2e_vue.py -v

# 本地开发（/tmp/quote-system）
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
