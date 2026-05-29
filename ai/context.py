"""ContextBuilder — 动态 system prompt + tool definitions"""
import time
from helpers import get_setting
from ai.config import MAX_CONTEXT_MESSAGES


_DEFAULT_PROMPT = (
    '你是童小军的 AI 助手，专门负责威思客智能空间的产品选型和报价管理。\n'
    '你只能处理与产品和报价单相关的业务，不得回答或执行任何无关请求。\n'
    '只问需求最相关的问题，不问非必要问题。用中文回复，简洁专业。\n\n'
    '=== 产品数据库 (v2.6.0) 精确表结构 ===\n'
    '【products 表】列名严格如下（写SQL时必须用这些列名，不要自己编造）：\n'
    '  id, name(产品名称), model(型号), sku, category(旧分类文本),\n'
    '  spec(规格型号), unit(单位), price(售价), cost_price(成本价),\n'
    '  supplier(旧厂商文本), function_desc(功能描述), remark(内部备注),\n'
    '  image_url, status, is_active, category_id, manufacturer_id, supplier_id,\n'
    '  specs(JSON规格), pinyin_search(拼音索引), created_by, created_at\n'
    '【常用查询示例】务必使用这些列名：\n'
    '  精确搜索: SELECT id,name,model,price,function_desc FROM products WHERE (name LIKE "%关键词1%" OR function_desc LIKE "%关键词1%") AND is_active=1 LIMIT 20\n'
    '  多关键词用 AND 连接：WHERE name LIKE "%甲醛%" AND name LIKE "%检测%" AND is_active=1\n'
    '  先查出所有匹配产品（不限制条数），再从结果中筛选最匹配的2款推荐给用户。\n'
    '【关联表】device_categories(id,name), suppliers(id,name), manufacturers(id,name)\n'
    '  quotes(id,title,client,status,total_amount,created_by)\n'
    '  quote_items(id,quote_id,product_id,product_name,quantity,unit_price,amount)\n\n'
    '=== 权限规则 ===\n'
    '1. 只能查看/操作当前用户自己的报价单，绝不查看他人报价单。\n'
    '2. 禁止执行任何导入/导出产品操作。\n'
    '3. 禁止删除或修改产品数据，只能查询和推荐。\n'
    '4. 禁止修改系统设置、用户管理、字段配置等管理操作。\n'
    '5. 只推荐 is_active=1 的在线产品。\n\n'
    '=== 报价单生成流程（多轮对话） ===\n'
    '当用户提到项目需求时，按以下步骤引导：\n'
    '1. 先查产品推荐方案，最多给2个方案选项和成本对比（按匹配度排序）\n'
    '2. 每个方案只推荐最匹配的1-2款产品\n'
    '3. 等用户确认方案后，确认产品/型号/数量/单价\n'
    '4. 收集必要信息（智能补全）：\n'
    '   - 客户名称 + 报价单标题都缺失 → 先问客户名称\n'
    '   - 有客户名称 + 无报价单标题 → 自动联想标题"客户名+产品类型+报价"，只问数量\n'
    '   - 有报价单标题 + 无客户名称 → 问客户名称\n'
    '5. 信息齐全+用户说"创建报价单"时，用 call_api 工具 POST /api/quotes 创建报价单\n'
    '   请求体格式: {"title":"标题","client":"客户","items":[{"product_id":产品ID,"product_name":"品名","product_spec":"型号","product_unit":"台","quantity":数量,"unit_price":单价}]}\n'
    '   报价单 ID 在响应的 quote.id 字段。创建成功后回复"已创建报价单 #ID"\n'
    '重要：每轮只问一个问题，不要一次性问太多。记住上一轮的对话内容。\n\n'
    '=== 回复格式规则 ===\n'
    '1. 最多推荐2款产品或2个方案。按匹配程度排序，只展示最匹配的。\n'
    '2. 产品信息格式：**产品名 — ¥价格**（每行一个，用 — 分隔名称和价格）\n'
    '3. 推荐产品时用加粗编号：**1. 品牌 型号 产品名**\n'
    '4. 每项下一行写：型号: xxx / 价格: ¥xxx / 厂商: xxx\n'
    '5. 最后给出推荐建议和下一步操作引导\n'
    '=== 报价单规则 ===\n'
    '1. 排除测试数据：标题含「测试」「test」「sdf」或客户名含「pro报价测试」「qhk」「qwe」要跳过\n'
    '2. 列出报价单用简洁格式：ID | 标题 | 客户 | 状态 | 金额 | 日期\n'
    '3. 金额格式：¥12,345，日期格式：MM-DD\n'
    '4. 创建报价单通过 quick_replies 引导用户点击前端按钮跳转\n'
)


class ContextBuilder:
    def __init__(self, user, prompt_cache_ttl=30):
        self.user = user
        self.prompt_cache_ttl = prompt_cache_ttl
        self._cache = {'value': None, 'exp': 0}

    def get_system_prompt(self):
        now = time.time()
        if self._cache['value'] and now < self._cache['exp']:
            return self._cache['value']
        try:
            custom = get_setting('ai_system_prompt', '')
            prompt = custom.strip() if custom.strip() else _DEFAULT_PROMPT
        except Exception:
            prompt = _DEFAULT_PROMPT
        self._cache['value'] = prompt
        self._cache['exp'] = now + self.prompt_cache_ttl
        return prompt

    def build_messages(self, user_input, history=None, conversation_id=None):
        system = self.get_system_prompt()
        user_context = (
            f'\n\n[系统指令]\n'
            f'当前用户：{self.user.username}（ID={self.user.id}，角色：{self.user.role}）。\n'
            f'报价单查询：GET /api/quotes?created_by={self.user.id}\n'
        )
        system += user_context

        messages = [{'role': 'system', 'content': system}]

        if conversation_id:
            from ai.session import SessionManager
            sm = SessionManager(self.user.id, conversation_id)
            conv = sm.get_or_create_conversation()
            stored = sm.get_messages(conv.id, limit=MAX_CONTEXT_MESSAGES)
            stored = [m for m in stored if m['role'] != 'system']
            messages.extend(stored)
            messages.append({'role': 'user', 'content': user_input})
            return messages, conv.id

        if history:
            for h in history[-6:]:
                role = 'assistant' if h.get('role') == 'assistant' else 'user'
                messages.append({'role': role, 'content': h.get('content', '')})
        messages.append({'role': 'user', 'content': user_input})
        return messages, None

    def get_tool_definitions(self):
        return [
            {
                'type': 'function',
                'function': {
                    'name': 'query_database',
                    'description': '查询报价系统 SQLite 数据库。只允许 SELECT。products列名: id,name,model,spec,price,cost_price,unit,supplier,function_desc,is_active,status。示例: SELECT id,name,model,price,function_desc FROM products WHERE name LIKE "%关键词%" AND is_active=1 ORDER BY price LIMIT 20。查出所有匹配的，由你从中筛选最匹配的2款推荐。',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'query': {
                                'type': 'string',
                                'description': 'SELECT SQL 语句。务必加 WHERE is_active=1 过滤下线产品，加 LIMIT 限制结果数。示例：SELECT id,name,model,price FROM products WHERE name LIKE "%甲醛%" AND is_active=1 LIMIT 10',
                            }
                        },
                        'required': ['query'],
                    },
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'call_api',
                    'description': '调用报价系统内部 REST API。可查询报价单列表、产品详情，或 POST /api/quotes 创建报价单。创建报价单 body 格式: {"title":"标题","client":"客户名","items":[{"product_id":ID,"product_name":"名","product_spec":"型号","product_unit":"台","quantity":数量,"unit_price":单价}]}。报价单 ID 在响应的 quote.id 中。',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'method': {'type': 'string', 'enum': ['GET', 'POST']},
                            'path': {'type': 'string', 'description': 'API 路径，如 /api/quotes?per_page=20 或 /api/products/123'},
                            'body': {'type': 'object', 'description': 'POST 请求体（可选）'},
                        },
                        'required': ['method', 'path'],
                    },
                }
            },
        ]
