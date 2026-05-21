# 报价系统自动化测试套件

> 基于 pytest 的 REST API 端到端测试，覆盖报价管理系统的全部功能模块。

## 快速开始

```bash
# 安装依赖
cd /opt/quote-system
./venv/bin/pip install pytest requests

# 运行全部 API 测试
./venv/bin/python -m pytest tests/ --ignore=tests/test_e2e_vue.py --ignore=tests/test_e2e_all.py -v

# 简洁输出
./venv/bin/python -m pytest tests/ --ignore=tests/test_e2e_vue.py --ignore=tests/test_e2e_all.py -v --tb=short

# 仅运行特定模块
./venv/bin/python -m pytest tests/test_auth.py -v
./venv/bin/python -m pytest tests/test_products.py -v
./venv/bin/python -m pytest tests/test_quotes.py -v
./venv/bin/python -m pytest tests/test_admin.py -v
./venv/bin/python -m pytest tests/test_edge_cases.py -v
./venv/bin/python -m pytest tests/test_comprehensive.py -v
./venv/bin/python -m pytest tests/test_audit_fixes.py -v

# 运行特定测试类/方法
./venv/bin/python -m pytest tests/test_auth.py::TestLogin -v
./venv/bin/python -m pytest tests/test_products.py::TestProductSearch::test_pinyin_search_full -v

# 生成 HTML 报告（需安装 pytest-html）
./venv/bin/pip install pytest-html
./venv/bin/python -m pytest tests/ --ignore=tests/test_e2e_vue.py --ignore=tests/test_e2e_all.py --html=report.html --self-contained-html

# Vue E2E 测试（需 Playwright + Chromium）
./venv/bin/python -m pytest tests/test_e2e_vue.py -v
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `QUOTE_TEST_URL` | `http://127.0.0.1:5000` | 测试目标 URL |
| `QUOTE_TEST_ADMIN` | `admin` | 管理员用户名 |
| `QUOTE_TEST_PASS` | `admin123` | 管理员密码 |

## 测试覆盖一览

### 认证系统 (test_auth.py) — 16 项
| # | 测试 | 验证点 |
|---|------|--------|
| 1 | 管理员登录 | 200 + token 非空 |
| 2 | 错误密码 | 401 "用户名或密码错误" |
| 3 | 空字段登录 | 400 |
| 4 | 缺少字段 | 400 |
| 5 | 不存在用户 | 401 |
| 6 | 重复注册 | 409 |
| 7 | 空字段注册 | 400 |
| 8 | 短密码注册 | 记录行为 |
| 9 | 有效 token session | 200 + user 信息 |
| 10 | 无 token session | 401 |
| 11 | 无效 token | 401 |
| 12 | 过期 token | 401 |
| 13 | 自动续签 | 200 正常 |
| 14 | 更新邮箱 | 200 |
| 15 | 空 body 更新 | 400 |
| 16 | 无认证更新 | 401 |

### 产品管理 (test_products.py) — 25 项
| # | 测试 | 验证点 |
|---|------|--------|
| 1 | 产品列表 | 200 + products/total/categories/suppliers/version |
| 2 | 分页 | page=1&per_page=5 → ≤5 条 |
| 3 | 产品详情 | 200 + name 匹配 |
| 4 | 创建产品 | 201 + sku 自动同步 spec |
| 5 | 最小字段创建 | 仅名称 → 201 |
| 6 | 空名称创建 | 400 |
| 7 | 更新产品 | 200 + 字段变更验证 |
| 8 | 更新不存在产品 | 404 |
| 9 | 删除产品 | 200 → 404 确认 |
| 10 | 删除不存在产品 | 404 |
| 11 | 名称搜索 | total ≥ 1 |
| 12 | 规格搜索 | 200 |
| 13 | 无结果搜索 | total=0 |
| 14 | 拼音全拼搜索 | _py/_py_initials 字段 |
| 15 | 拼音首字母搜索 | 200 |
| 16 | 分类筛选 | 200 |
| 17 | 厂商筛选 | 200 |
| 18 | 排序 | price desc |
| 19 | 版本端点 | 200 + count/max_updated_at |
| 20 | 版本变化检测 | count 或 updated_at 变化 |
| 21 | 批量删除 | 200 → 404 |
| 22 | 空列表批量删除 | 400 |
| 23-25 | 未登录拦截 | 列表/创建/删除 → 401 |

### 报价单管理 (test_quotes.py) — 19 项
| # | 测试 | 验证点 |
|---|------|--------|
| 1 | 报价单列表 | 200 + quotes |
| 2 | 报价单详情 | 200 + items 含 profit/profit_rate |
| 3 | 最小字段创建 | 201 + status=draft |
| 4 | 完整报价单创建 | 201 + total_amount=1100 + items=2 + tax_rate=5 |
| 5 | 更新报价单 | 200 + 字段变更 |
| 6 | 更新不存在 | 404 |
| 7 | 删除报价单 | 200 → 404 |
| 8 | 默认状态 draft | 201 + status=draft |
| 9 | draft→sent | 200 |
| 10 | →confirmed/completed | 200 |
| 11 | 无效状态 | 400 |
| 12 | HTML 预览 | 200 + 含 <table> |
| 13 | Excel 导出 | 200 + Content-Type |
| 14 | 下载计数递增 | download_count +1 |
| 15 | 报价统计 | 200 + 客户维度聚合 |
| 16-19 | 无认证/非所有者 | 401/403 |

### 管理后台 (test_admin.py) — 17 项
| # | 测试 | 验证点 |
|---|------|--------|
| 1-3 | 用户列表 | 管理员→200 / 普通用户→403 / 未登录→401 |
| 4 | 修改角色 | 200 + 角色变更 |
| 5 | 启用/禁用 | is_active 切换 |
| 6 | 重置密码 | success=True |
| 7 | 密码过短 | 400 |
| 8 | 不能修改自己 | 400 |
| 9 | 字段可见性获取 | 200 |
| 10 | 字段可见性更新 | 200 + 验证 |
| 11 | 注册开关读取 | 200 |
| 12 | 关闭注册 | 200 |
| 13 | 关闭后注册拦截 | 403(多worker宽松) |
| 14 | 系统设置获取 | 200 |
| 15 | 更新系统设置 | 200 + 验证 |
| 16 | 非管理员拦截 | 403 |
| 17 | 产品上下线 | is_active 切换 |

### 边界&安全 (test_edge_cases.py) — 22 项
| # | 测试 | 验证点 |
|---|------|--------|
| 1 | 公开版本号 | 200（无需认证） |
| 2 | 静态文件 | 200 |
| 3 | 不存在路由 | 401/404 |
| 4 | SQL 注入搜索 | 200（参数化防护） |
| 5 | JSON 注入 | 201（正常创建） |
| 6 | 分类注入 | 200 |
| 7-8 | XSS 产品名/搜索 | 200（前端转义） |
| 9 | 超长产品名(200字符) | 201 |
| 10 | 超过长度(300字符) | 记录行为 |
| 11 | 特殊 Unicode | 201 |
| 12 | 负价格 | 201（不校验） |
| 13 | 数量0报价单 | 201 + total=0 |
| 14 | 错误 HTTP 方法 | 401/405 |
| 15 | 畸形 JSON | 400/415 |
| 16 | 缺少 Content-Type | 400/415 |
| 17 | 顺序创建多个产品 | 不崩溃 |
| 18 | SKU-spec 同步 | 创建+更新均同步 |
| 19 | 价格类型 | int/float |
| 20 | 禁用用户登录 | 401/403 |
| 21 | 禁用后 token 失效 | 401/403 |
| 22 | 多次错误登录 | 不崩溃 |

### 补全覆盖 (test_comprehensive.py) — 28 项
| # | 测试 | 验证点 |
|---|------|--------|
| 1-3 | Excel 导入 | 有文件/无文件/无认证 |
| 4-5 | 导出模板 | 200 / 无认证 |
| 6-8 | 图片上传 | 有文件/无文件/无认证 |
| 9-11 | 文本识别 | 单行/空行/无认证 |
| 12-14 | OCR 识别 | 有图/无文件/无认证 |
| 15-17 | 邮件发送 | 无SMTP配置/无效报价/无认证 |
| 18-20 | 下载日志 | 列表/统计/无认证 |
| 21 | 版本端点 | 200 |
| 22 | 系统页面加载 | 200 |
| 23-25 | OCR 成本 | 无文件/非管理员/无认证 |
| 26-28 | 批量成本更新 | 有产品/空列表/非管理员 |

### 审计修复 (test_audit_fixes.py) — 34 项
| 全量审计修复覆盖，含 admin_bp 拆分后验证 |
