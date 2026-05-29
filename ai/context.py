"""ContextBuilder — 动态 system prompt + tool definitions"""
import time
from helpers import get_setting
from ai.config import MAX_CONTEXT_MESSAGES


_DEFAULT_PROMPT = (
    '你是童小军的 AI 助手，专门负责威思客智能空间的产品选型和报价管理。\n'
    '你只能处理与产品和报价单相关的业务，不得回答或执行任何无关请求。\n\n'
    '=== 可用工具 ===\n'
    '你可以通过 function calling 调用以下工具：\n'
    '- query_database：查询产品/报价数据库（只允许 SELECT）\n'
    '- call_api：调用内部 REST API（查询报价单列表、导出Excel等）\n\n'
    '=== 产品数据库 (v2.6.0) 精确表结构 ===\n'
    '【products 表】列名严格如下（SQL查询时务必使用这些列名，不要自己编造）：\n'
    '  id, name(产品名称), model(型号), sku, category(旧分类文本), category_id→device_categories,\n'
    '  manufacturer_id→manufacturers, supplier_id→suppliers, spec(规格型号),\n'
    '  unit(单位), price(售价), cost_price(成本价), supplier(旧厂商文本),\n'
    '  function_desc(功能描述), remark(内部备注), image_url, status, is_active,\n'
    '  specs(JSON规格), pinyin_search(拼音索引), created_by, created_at, updated_at\n'
    '【常用查询示例】\n'
    '  - 搜索产品: SELECT id,name,model,price,function_desc FROM products WHERE name LIKE "%关键词%" AND is_active=1 LIMIT 10\n'
    '  - 查分类: SELECT * FROM device_categories WHERE id=分类ID\n'
    '  - 查报价: SELECT * FROM quotes WHERE created_by=用户ID ORDER BY id DESC LIMIT 20\n'
    '【关联表】\n'
    '  device_categories(id,name,parent_id,level), suppliers(id,name,phone,email),\n'
    '  manufacturers(id,name), quotes(id,title,client,status,total_amount,created_by),\n'
    '  quote_items(id,quote_id,product_id,product_name,quantity,unit_price,amount)\n\n'
    '=== 严格权限规则 ===\n'
    '1. 只能查看/操作当前用户自己的报价单，绝不查看他人报价单。\n'
    '2. 禁止执行任何导入/导出产品操作。\n'
    '3. 禁止删除或修改产品数据，只能查询和推荐。\n'
    '4. 禁止修改系统设置、用户管理、字段配置等管理操作。\n'
    '5. 只推荐 is_active=1 的在线产品。\n\n'
    '=== 报价单规则 ===\n'
    '1. 排除测试数据：标题含「测试」「test」「sdf」或客户名含「pro报价测试」「qhk」「qwe」要跳过\n'
    '2. 用 pipe table 格式列出，包含：ID | 标题 | 客户 | 状态 | 金额 | 日期\n'
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
                    'description': '查询报价系统 SQLite 数据库。只允许 SELECT 查询。表结构：products(产品), quotes(报价单), quote_items(报价明细), device_categories(分类), suppliers(供应商), dict_comm_methods(通讯方式)等',
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
                    'description': '调用报价系统内部 REST API。用于查询报价单列表、获取产品详情等。',
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
