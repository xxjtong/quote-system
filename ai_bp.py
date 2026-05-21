"""
AI Blueprint — AI 对话、使用统计相关 API 路由
"""

import os
import re
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, g, Response
from auth import require_auth, require_admin, create_token
from extensions import db
from models import User, AIUsageLog, AIChatSession

# ─── Blueprint 定义 ──────────────────────────────────────────
ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')
chat_bp = Blueprint('chat', __name__)  # /api/chat 不在 /api/ai 前缀下
admin_ai_bp = Blueprint('admin_ai', __name__)  # /api/admin/ai-usage

# ─── 配置 ──────────────────────────────────────────────────
_ai_model = os.environ.get('QUOTE_AI_MODEL', 'deepseek-v4-flash')
_gateway_url = os.environ.get('QUOTE_GATEWAY_URL', 'http://127.0.0.1:8643')

_AVAILABLE_MODELS = [
    {'id': 'deepseek-v4-flash', 'name': 'DeepSeek V4 Flash', 'desc': '快速响应，适合日常问答'},
    {'id': 'deepseek-v4-pro', 'name': 'DeepSeek V4 Pro', 'desc': '深度推理，适合复杂分析'},
]


# ─── AI Token ────────────────────────────────────────────────
@ai_bp.route('/token', methods=['GET'])
@require_auth
def ai_token():
    """AI 助手获取当前用户的 JWT token（用于 API 操作）。"""
    from flask import current_app
    token = create_token(g.current_user, current_app)
    return jsonify({'token': token, 'username': g.current_user.username, 'user_id': g.current_user.id})


# ─── Chat Models ─────────────────────────────────────────────
@chat_bp.route('/api/chat/models', methods=['GET'])
def get_chat_models():
    """返回可用 AI 模型列表"""
    return jsonify({'models': _AVAILABLE_MODELS, 'default': _ai_model})


# ─── Admin AI Usage ─────────────────────────────────────────
@admin_ai_bp.route('/api/admin/ai-usage', methods=['GET'])
@require_admin
def ai_usage_stats():
    """AI 使用统计 — 管理员查看"""
    from sqlalchemy import func
    days = min(int(request.args.get('days', 7)), 90)
    since = datetime.now() - __import__('datetime').timedelta(days=days)

    total = AIUsageLog.query.filter(AIUsageLog.created_at >= since).count()
    success = AIUsageLog.query.filter(AIUsageLog.created_at >= since, AIUsageLog.success == True).count()
    avg_elapsed = db.session.query(func.avg(AIUsageLog.elapsed)).filter(
        AIUsageLog.created_at >= since, AIUsageLog.success == True
    ).scalar() or 0

    by_action = db.session.query(
        AIUsageLog.action, func.count(), func.avg(AIUsageLog.elapsed)
    ).filter(AIUsageLog.created_at >= since).group_by(AIUsageLog.action).all()

    by_user = db.session.query(
        AIUsageLog.user_id, User.username, func.count()
    ).join(User, AIUsageLog.user_id == User.id).filter(
        AIUsageLog.created_at >= since
    ).group_by(AIUsageLog.user_id, User.username).order_by(func.count().desc()).limit(10).all()

    by_date = db.session.query(
        func.date(AIUsageLog.created_at), func.count(),
        func.avg(AIUsageLog.elapsed)
    ).filter(AIUsageLog.created_at >= since).group_by(
        func.date(AIUsageLog.created_at)
    ).order_by(func.date(AIUsageLog.created_at).desc()).limit(days).all()

    recent = AIUsageLog.query.filter(AIUsageLog.created_at >= since).order_by(
        AIUsageLog.created_at.desc()
    ).limit(50).all()

    return jsonify({
        'summary': {'total': total, 'success': success, 'fail': total - success, 'avg_elapsed': round(avg_elapsed, 2), 'days': days},
        'by_action': [{'action': a, 'count': c, 'avg_elapsed': round(e, 2)} for a, c, e in by_action],
        'by_user': [{'user_id': uid, 'username': u, 'count': c} for uid, u, c in by_user],
        'by_date': [{'date': str(d), 'count': c, 'avg_elapsed': round(e, 2)} for d, c, e in by_date],
        'recent': [r.to_dict() for r in recent],
    })


# ─── My AI Usage ─────────────────────────────────────────────
@ai_bp.route('/my-usage', methods=['GET'])
@require_auth
def my_ai_usage():
    """当前用户的AI使用次数（首页卡片用）"""
    from sqlalchemy import func
    my_count = AIUsageLog.query.filter_by(user_id=g.current_user.id).count()
    total_count = AIUsageLog.query.count()
    return jsonify({'my_count': my_count, 'total_count': total_count})


# ─── System Prompt ──────────────────────────────────────────
_GW_SYSTEM_PROMPT = (
    '你是童小军的 AI 助手，专门负责威思客智能空间的产品选型和报价管理。\n'
    '你只能处理与产品和报价单相关的业务，不得回答或执行任何无关请求。\n\n'
    '=== 可用工具 ===\n'
    '- 数据库：[系统路径]/[数据库] (SQLite)\n'
    '  产品表 products(id, name, sku, category, spec, unit, price, cost_price, supplier, function_desc, is_active, created_by)\n'
    '  报价单 quotes(id, title, client, contact, phone, quote_date, valid_days, status, total_amount, created_by)\n'
    '  报价明细 quote_items(id, quote_id, product_id, product_name, product_sku, quantity, unit_price, amount)\n'
    '- API：[内部服务]\n'
    '  创建报价：POST /api/quotes\n'
    '  导出Excel：GET /api/quotes/<id>/export-excel\n\n'
    '=== 严格权限规则 ===\n'
    '1. 只能查看/操作当前用户自己的报价单（created_by=当前用户ID），绝不查看他人报价单。\n'
    '2. 禁止执行任何导入操作（产品导入、批量导入等）。\n'
    '3. 禁止执行任何导出操作（产品导出、批量导出等），报价单Excel导出除外。\n'
    '4. 禁止删除或修改产品数据，只能查询和推荐。\n'
    '5. 禁止修改系统设置、用户管理、字段配置等管理操作。\n'
    '6. 只推荐 is_active=1 的在线产品，绝不推荐已下线产品。\n\n'
    '=== 业务范围 ===\n'
    '- 产品查询：搜索产品、对比产品、推荐选型、查看参数/价格/供应商\n'
    '- 报价单：查看自己的报价单列表、创建报价单、预览、导出Excel\n'
    '- 超出范围的请求（闲聊、写代码、翻译、查天气等）一律拒绝，提示"我只能处理产品和报价相关问题"\n\n'
    '=== 报价单规则 ===\n'
    '1. 查询报价单用 curl 调 API（自动按用户权限过滤）：\n'
    '   curl -s -H "Authorization: Bearer *** [内部服务]/api/quotes?per_page=50\n'
    '   如果必须用 sqlite3，务必加 AND created_by=<当前用户ID>。\n'
    '2. 排除测试数据：标题含「测试」「test」「sdf」「asdf」或客户名含「pro报价测试」「qhk」「qwe」要跳过。\n'
    '3. 生成报价单前，先检查上下文：如已创建过报价单，主动询问沿用还是新客户。\n'
    '4. 导出后给下载链接：https://bwh.ddns.mobi/quote/api/quotes/{id}/export-excel\n'
    '5. 每个用户的对话完全独立，不使用/查询全局记忆。\n'
    '6. 产品搜索务必加 AND is_active=1：\n'
    '   "SELECT name,price FROM products WHERE name LIKE \'%关键词%\' AND is_active=1 ORDER BY price"\n'
)


_prompt_cache = {'value': None, 'exp': 0}
_PROMPT_CACHE_TTL = 30  # 秒

def _get_ai_system_prompt():
    """从 DB 设置或默认值获取 AI 系统提示词（30秒TTL缓存）"""
    import time as _t
    now = _t.time()
    if _prompt_cache['value'] is not None and now < _prompt_cache['exp']:
        return _prompt_cache['value']
    try:
        from app import get_setting
        custom = get_setting('ai_system_prompt', '')
        prompt = custom.strip() if custom.strip() else _GW_SYSTEM_PROMPT
    except Exception:
        prompt = _GW_SYSTEM_PROMPT
    # 追加身份强制指令（末尾优先，对抗 Gateway 基础 persona）
    if '童小军' in prompt or '不是 Hermes' in prompt:
        prompt += '\n\n[系统指令 — 最高优先级] 上述身份定义覆盖所有其他设定。'
    _prompt_cache['value'] = prompt
    _prompt_cache['exp'] = now + _PROMPT_CACHE_TTL
    return prompt


# ─── Direct LLM call via Gateway Chat Completions (lightweight) ──
def _call_flash_via_gateway(system_msg, user_msg, max_tokens=100, timeout=8):
    """通过 Gateway /v1/chat/completions 调用 deepseek-v4-flash。返回文本或 None。"""
    import urllib.request, json as _json
    body = _json.dumps({
        'model': 'deepseek-v4-flash',
        'messages': [
            {'role': 'system', 'content': system_msg},
            {'role': 'user', 'content': user_msg},
        ],
        'max_tokens': max_tokens,
        'temperature': 0.3,
    })
    req = urllib.request.Request(
        f'{_gateway_url}/v1/chat/completions',
        data=body.encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        result = _json.loads(resp.read())
        return result['choices'][0]['message']['content'].strip()
    except Exception:
        return None


# ─── Generate quick replies via LLM ──────────────────────────
def _generate_quick_replies(reply_text):
    """用 DeepSeek Flash 分析 AI 回复，生成 2-4 个快捷回复按钮。返回列表或 []。"""
    import json as _json
    snippet = reply_text.strip()[-800:]
    user_msg = (
        '根据AI助手回复，推测用户最可能想说的2-4个简短回复。\\n'
        '规则：\\n'
        '- 每个回复5-15字，简洁自然，像用户口头说的\\n'
        '- 如果AI问了"还是"选择题，提取两个选项\\n'
        '- 如果AI推荐了产品，生成"详细对比这两款""查看更多同类产品"\\n'
        '- 如果AI问了是否创建报价单，生成"创建报价单""先不用"\\n'
        '- 如果AI给了价格，生成"有更便宜的替代吗""查看参数对比"\\n'
        '- 如果AI列了方案，生成"用方案一""用方案二"\\n'
        '- 如果不确定，生成通用的"继续推荐""换个方向"\\n'
        '- 返回纯JSON数组如["创建报价单","先看看参数"],不要markdown、不要解释\\n'
        f'AI回复摘要："""{snippet}"""'
    )
    text = _call_flash_via_gateway(
        '你是快捷回复生成器，只返回JSON数组，不要任何解释。',
        user_msg, max_tokens=100, timeout=8,
    )
    if not text:
        return []
    try:
        if text.startswith('['):
            arr = _json.loads(text)
            if isinstance(arr, list) and 1 <= len(arr) <= 6:
                return [str(x).strip() for x in arr if 2 <= len(str(x).strip()) <= 30][:4]
    except Exception:
        pass
    return []


# ─── Extract choices via LLM ────────────────────────────────
def _extract_choices_via_llm(text):
    """用 LLM 从「是A还是B」问句中提取两个选项。返回 [a, b] 或 []。"""
    import json as _json
    if '还是' not in text:
        return []
    sentences = re.split(r'[。！\n]', text)
    question = sentences[-1] if sentences[-1].strip() else (sentences[-2] if len(sentences) > 1 else text)
    question = question.strip()[-300:]
    if '还是' not in question:
        question = text.strip()[-300:]

    user_msg = (
        '从这句话中提取「还是」前后两个选项。返回纯JSON数组如["A","B"]，不要markdown、不要解释。\n'
        '去掉「这是/是要/是/用/选/给」等前缀词和「的/呢/吗/啊」等后缀词，只留核心5-15字。\n'
        '例：「继续用威发西安还是新建客户？」→ ["继续用威发西安","新建客户"]\n'
        '例：「要改方案还是新项目？」→ ["改方案","新项目"]\n'
        f'提取："{question}"'
    )
    text = _call_flash_via_gateway(
        '你是选项提取器，只返回JSON数组，不要任何解释。',
        user_msg, max_tokens=50, timeout=5,
    )
    if not text:
        return []
    try:
        if text.startswith('['):
            arr = _json.loads(text)
            if isinstance(arr, list) and len(arr) == 2:
                a, b = str(arr[0]).strip(), str(arr[1]).strip()
                if 1 <= len(a) <= 30 and 1 <= len(b) <= 30:
                    return [a, b]
    except Exception:
        pass
    return []


# ─── Parse reply actions ────────────────────────────────────
def _parse_reply_actions(reply_text):
    """解析 AI 回复，提取结构化数据：产品、报价引用、快捷操作"""
    reply_text = reply_text.replace('/opt/quote-system', '[系统路径]')
    reply_text = re.sub(r'127\.0\.0\.1:\d+', '[内部地址]', reply_text)
    reply_text = reply_text.replace('quote.db', '[数据库]')

    result = {'products': [], 'quote_refs': [], 'quick_replies': []}

    for m in re.finditer(r'(?:报价单|#)\s*(\d{1,5})', reply_text):
        result['quote_refs'].append(int(m.group(1)))

    question_patterns = [
        (r'沿用.*还是.*新.*', ['沿用上一份', '新建报价单']),
        (r'新建.*还是.*合并', ['新建报价单', '合并到已有']),
        (r'需要我(?:帮[您你])?.*吗[？?]', ['好的，开始吧', '先不用']),
        (r'选哪种[？?]', []),
        (r'选哪个[？?]', []),
        (r'哪个方案[？?]', []),
        (r'哪种方案[？?]', []),
        (r'选哪[个种款][？?]', []),
    ]
    if '还是' in reply_text:
        choices = _extract_choices_via_llm(reply_text)
        if choices:
            result['quick_replies'] = choices

    # 检测多方案选择（"方案A/方案B/方案C"）并自动生成快捷按钮
    if not result['quick_replies']:
        scheme_re = re.findall(r'方案([A-Z])[：:）)]\s*(.{2,30}?)(?:[（(]|$)', reply_text, re.MULTILINE)
        if len(scheme_re) >= 2:
            result['quick_replies'] = [f'方案{letter}（{desc.strip()}）' for letter, desc in scheme_re]

    if not result['quick_replies']:
        for pat, replies in question_patterns:
            if re.search(pat, reply_text) and replies:
                result['quick_replies'] = replies
                break

    prod_pattern1 = re.findall(
        r'(?:\d+[.、．]\s*)?([A-Za-z\u4e00-\u9fff][A-Za-z0-9\u4e00-\u9fff\-+ ]{3,50}?)[ ]+[-–—][ ]+(?:¥|￥|[Rr][Mm][Bb])?\s*([\d,]+\.?\d*)',
        reply_text
    )
    seen = set()
    for name, price in prod_pattern1[:6]:
        name = name.strip()
        norm = name.replace(' ', '')
        if norm in seen or len(name) < 4:
            continue
        if re.match(r'^[\d\s\-+.,]+$', name):
            continue
        seen.add(norm)
        try:
            result['products'].append({
                'name': name,
                'price': float(price.replace(',', '')),
            })
        except ValueError:
            pass

    # Pattern 2: 产品型号（描述）—— 方案行中的产品名
    if len(result['products']) < 6:
        for m in re.finditer(r'(?:^|[\s>：:）)])\s*([A-Z][A-Z0-9\-/]{2,20})[（(]', reply_text, re.MULTILINE):
            name = m.group(1).strip()
            norm = name.replace(' ', '')
            if norm not in seen and len(name) >= 3:
                seen.add(norm)
                result['products'].append({'name': name, 'price': 0})

    # Pattern 3: "产品名 N台/个 ¥价格" 或 "产品名 N台/个 × ¥价格"
    if len(result['products']) < 6:
        for m in re.finditer(r'([A-Za-z\u4e00-\u9fff][A-Za-z0-9\u4e00-\u9fff\- ]{2,30}?)\s*\d+\s*[台个只套件]\s*[×x]?\s*(?:¥|￥)\s*([\d,]+\.?\d*)', reply_text):
            name = m.group(1).strip()
            price_str = m.group(2)
            norm = name.replace(' ', '')
            if norm not in seen and len(name) >= 3:
                seen.add(norm)
                try:
                    result['products'].append({'name': name, 'price': float(price_str.replace(',', ''))})
                except ValueError:
                    result['products'].append({'name': name, 'price': 0})

    # Pattern 4: 型号 + ¥价格 紧凑格式（如 "UG63 ¥990"）
    if len(result['products']) < 6:
        for m in re.finditer(r'([A-Z][A-Z0-9\-/]{2,20})\s+(?:¥|￥)\s*([\d,]+\.?\d*)', reply_text):
            name = m.group(1).strip()
            price_str = m.group(2)
            norm = name.replace(' ', '')
            if norm not in seen and len(name) >= 3:
                seen.add(norm)
                try:
                    result['products'].append({'name': name, 'price': float(price_str.replace(',', ''))})
                except ValueError:
                    result['products'].append({'name': name, 'price': 0})

    if not result['quick_replies'] and len(result['products']) >= 2:
        if re.search(r'(选哪个|选哪|哪个更|哪款|推荐哪个|推荐哪|挑一个|选一款)', reply_text):
            result['quick_replies'] = [p['name'] for p in result['products'][:6]]

    # 注意：LLM兜底生成quick_replies已移到SSE层异步执行，不阻塞_parse_reply_actions

    dl_match = re.search(r'(https://bwh\.ddns\.mobi/quote/api/quotes/(\d+)/export-excel)', reply_text)
    if dl_match:
        result['created_quote'] = {'id': int(dl_match.group(2)), 'download_url': dl_match.group(1)}

    return result


# ─── AI 速率限制 ────────────────────────────────────────────
_AI_RATE_LIMIT = 5  # 每分钟最多5次

def _check_ai_rate_limit(user_id):
    """DB-based rate limit — works across gunicorn workers. Returns True if rate limited."""
    from sqlalchemy import func as _func
    cutoff = datetime.now() - timedelta(minutes=1)
    recent = AIUsageLog.query.filter(
        AIUsageLog.user_id == user_id,
        AIUsageLog.action == 'chat',
        AIUsageLog.created_at >= cutoff
    ).count()
    return recent >= _AI_RATE_LIMIT


# ─── Chat endpoint ──────────────────────────────────────────
@chat_bp.route('/api/chat', methods=['POST'])
@require_auth
def ai_chat():
    """AI 对话 — 通过 Hermes Gateway Responses API。支持 SSE 流式。"""
    import time, urllib.request, json as _json
    t0 = time.time()

    uid = g.current_user.id
    if _check_ai_rate_limit(uid):
        return jsonify({'error': f'请求过快，每分钟最多{_AI_RATE_LIMIT}次，请稍后再试'}), 429

    data = request.get_json(silent=True) or {}
    user_input = (data.get('input', '') or '').strip()
    if not user_input:
        return jsonify({'error': '请输入问题'}), 400

    prompt = _get_ai_system_prompt()
    for line in prompt.split('\n')[:3]:
        if '童小军' in line or '不是 Hermes' in line:
            user_input = f'[{line.strip()}] {user_input}'
            break

    stream = data.get('stream', False)
    user = g.current_user
    conv_id = data.get('conversation_id', '') or ''
    # 每个前端session独立conversation，+号新建时conversation_id变化
    conversation = f'quote-user-{user.id}-{conv_id}' if conv_id else f'quote-user-{user.id}'

    body = {
        'model': data.get('model') or _ai_model,
        'input': user_input,
        'conversation': conversation,
        'max_output_tokens': 800,
    }

    import hashlib
    prompt = _get_ai_system_prompt()
    prompt_h = hashlib.sha256(prompt.encode()).hexdigest()[:16]

    session = AIChatSession.query.filter_by(user_id=user.id).first()
    if not session or session.prompt_hash != prompt_h:
        body['instructions'] = (
            prompt + '\n'
            f'当前用户：{user.username}（ID={user.id}，角色：{user.role}）。\n'
            f'查询报价单：curl -s -H "Authorization: Bearer *** [内部服务]/api/quotes?per_page=50\n'
            f'  sqlite3: SELECT id,title,client,status,total_amount,quote_date FROM quotes WHERE created_by={user.id} ORDER BY id DESC LIMIT 30;\n'
            f'创建报价：curl -X POST -H "Authorization: Bearer *** -H "Content-Type: application/json" -d \'...\' [内部服务]/api/quotes\n'
            f'报价单自动归属到当前用户 ID={user.id}（{user.username}）。\n'
            f'列出报价单时：\n'
            f'  1) 排除测试数据：标题含「测试」「test」「sdf」或客户名含「pro报价测试」「qhk」「qwe」的要跳过\n'
            f'  2) 用 pipe table 格式列出，包含这6列：ID | 标题 | 客户 | 状态 | 金额 | 日期\n'
            f'  3) 金额格式：¥12,345，日期格式：MM-DD\n'
            f'  4) 先统计总数再列出表格\n'
            f'【权限提醒】禁止导入/导出产品、禁止修改系统设置、禁止操作他人报价单'
        )
        if session:
            session.prompt_hash = prompt_h
        else:
            db.session.add(AIChatSession(user_id=user.id, prompt_hash=prompt_h))
        db.session.commit()

    if stream:
        body['stream'] = True
        return _ai_chat_sse(body, t0, user_id=user.id)

    t1 = time.time()
    try:
        req = urllib.request.Request(
            f'{_gateway_url}/v1/responses',
            data=_json.dumps(body).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        resp = urllib.request.urlopen(req, timeout=60)
        t2 = time.time()

        result = _json.loads(resp.read())
        reply = ''
        for o in result.get('output', []):
            if o.get('type') == 'message':
                content = o.get('content', [])
                if content:
                    reply = content[0].get('text', '')
                break
        if not reply:
            reply = '抱歉，AI 暂时无法回答，请稍后再试。'

        parsed = _parse_reply_actions(reply)

        # Lazy import _log_ai_usage from app
        from app import _log_ai_usage
        _log_ai_usage(user_id=user.id, action='chat', model=body.get('model', ''), elapsed=t2-t0)

        return jsonify({
            'reply': reply,
            'parsed': parsed,
            'model': 'hermes-gateway',
            'timings': {'Gateway': f'{t2 - t1:.1f}s', '总耗时': f'{t2 - t0:.1f}s'}
        })
    except Exception as e:
        from app import _log_ai_usage
        _log_ai_usage(user_id=user.id, action='chat', model=body.get('model', ''), elapsed=time.time()-t0, success=False, error=str(e)[:200])
        return jsonify({
            'error': f'AI 服务异常: {str(e)}',
            'timings': {'总耗时': f'{time.time() - t0:.1f}s'}
        }), 503


def _ai_chat_sse(body, t0, user_id=None):
    """SSE 流式 — 透传 Gateway stream，前端 EventSource 接收"""
    import time, urllib.request, json as _json

    def generate():
        t_connect = time.time()
        accumulated = ''
        try:
            req = urllib.request.Request(
                f'{_gateway_url}/v1/responses',
                data=_json.dumps(body).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            resp = urllib.request.urlopen(req, timeout=60)
            t_connected = time.time()

            yield f'data: {_json.dumps({"type": "connect", "elapsed": f"{t_connected - t0:.1f}s"})}\n\n'

            first_token = True
            for line_bytes in resp:
                line = line_bytes.decode('utf-8', errors='replace').strip()
                if not line or not line.startswith('data: '):
                    continue
                data_str = line[6:]
                if data_str == '[DONE]':
                    break
                try:
                    chunk = _json.loads(data_str)
                except _json.JSONDecodeError:
                    continue

                delta_text = ''
                event_type = chunk.get('type', '')
                if event_type == 'response.output_text.delta':
                    delta_text = chunk.get('delta', '')

                if delta_text:
                    if first_token:
                        first_token = False
                        ttft = time.time() - t_connected
                        yield f'data: {_json.dumps({"type": "first_token", "ttft": f"{ttft:.1f}s"})}\n\n'
                    accumulated += delta_text
                    yield f'data: {_json.dumps({"type": "text", "text": delta_text})}\n\n'

                if event_type and 'tool' in event_type.lower():
                    yield f'data: {_json.dumps({"type": "tool"})}\n\n'

            parsed = _parse_reply_actions(accumulated)
            from app import _log_ai_usage
            _log_ai_usage(user_id=user_id, action='chat', model=body.get('model', ''), elapsed=time.time()-t0)
            # 先发 done（含规则提取的 quick_replies），不阻塞等 LLM
            yield f'data: {_json.dumps({"type": "done", "parsed": parsed, "elapsed": f"{time.time() - t0:.1f}s"})}\n\n'
            # 异步：如果规则没提取到 quick_replies，用 LLM 生成后补发
            if not parsed.get('quick_replies'):
                try:
                    llm_replies = _generate_quick_replies(accumulated)
                    if llm_replies:
                        yield f'data: {_json.dumps({"type": "quick_replies", "items": llm_replies})}\n\n'
                except Exception:
                    pass

        except Exception as e:
            from app import _log_ai_usage
            _log_ai_usage(user_id=user_id, action='chat', model=body.get('model', ''), elapsed=time.time()-t0, success=False, error=str(e)[:200])
            yield f'data: {_json.dumps({"type": "error", "error": f"AI 服务异常: {str(e)}"})}\n\n'

        yield f'data: [DONE]\n\n'

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )
