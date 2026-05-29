"""
AI Blueprint — AI 对话、使用统计相关 API 路由
v3.0: 自研 AI Engine 替代 Hermes Gateway
"""
import os
import re
import json as _json
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path

from flask import Blueprint, request, jsonify, g, Response, current_app
from auth import require_auth, require_admin, create_token
from extensions import db
from models import User, AIUsageLog, AIChatSession

# ─── Blueprint ──────────────────────────────────────────────
ai_bp = Blueprint('ai', __name__)
BASE_DIR = Path(__file__).parent

# ─── 配置 ──────────────────────────────────────────────────
_ai_model = os.environ.get('QUOTE_AI_MODEL', 'deepseek-v4-flash')
_AI_RATE_LIMIT = 5  # 每分钟
_rate_limit_cache = {}
_rate_lock = threading.Lock()

from ai.config import AVAILABLE_MODELS as _AVAILABLE_MODELS

# ─── AI Engine ─────────────────────────────────────────────
from ai.engine import LlmEngine
from ai.session import SessionManager
from ai.context import ContextBuilder
from ai.tools import ToolRegistry
from ai.agent import Agent
from ai.reply_parser import parse_reply_actions, generate_quick_replies

_engine = None

def _get_engine():
    global _engine
    if _engine is None:
        _engine = LlmEngine()
    return _engine

def _build_agent(user):
    ctx = ContextBuilder(user)
    tools = ToolRegistry(user_context={
        'db_path': str(BASE_DIR / 'quote.db'),
        'base_url': 'http://127.0.0.1:5001',
        'auth_token': create_token(user, current_app),
    })
    return Agent(_get_engine(), tools), ctx

def _quick_reply_llm(model_id, system_msg, user_msg, max_tokens):
    try:
        resp = _get_engine().chat(model_id, [
            {'role': 'system', 'content': system_msg},
            {'role': 'user', 'content': user_msg},
        ], max_tokens=max_tokens)
        return resp['choices'][0]['message'].get('content', '')
    except Exception:
        return None

# ─── AI Token ──────────────────────────────────────────────
@ai_bp.route('/api/ai/token', methods=['GET'])
@require_auth
def ai_token():
    return jsonify({'token': create_token(g.current_user, current_app)})

# ─── Chat Models ───────────────────────────────────────────
@ai_bp.route('/api/chat/models', methods=['GET'])
def get_chat_models():
    return jsonify({'models': _AVAILABLE_MODELS, 'default': 'deepseek-v4-flash'})

# ─── My AI Usage ───────────────────────────────────────────
@ai_bp.route('/api/ai/my-usage', methods=['GET'])
@require_auth
def my_ai_usage():
    uid = g.current_user.id
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = AIUsageLog.query.filter_by(user_id=uid).order_by(AIUsageLog.created_at.desc())
    total = query.count()
    logs = query.offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({
        'logs': [l.to_dict() for l in logs],
        'total': total, 'page': page, 'per_page': per_page,
    })

# ─── Rate Limiting ─────────────────────────────────────────
def _check_ai_rate_limit(user_id):
    now = datetime.now()
    cutoff = now - timedelta(minutes=1)
    with _rate_lock:
        timestamps = [t for t in _rate_limit_cache.get(user_id, []) if t > cutoff]
        _rate_limit_cache[user_id] = timestamps
        if len(timestamps) >= _AI_RATE_LIMIT:
            return True
        timestamps.append(now)
        _rate_limit_cache[user_id] = timestamps
        return False

# ─── Lightweight Detection ─────────────────────────────────
_LIGHT_PATTERNS = re.compile(
    r'^(你好|hi|hello|嗨|在吗|在不在|早上好|下午好|晚上好|晚安|'
    r'好的|ok|行|可以|对|是的|没错|嗯|哦|明白了|懂了|收到|'
    r'谢谢|多谢|thank|thanks|辛苦了|'
    r'你是谁|你叫什么|帮助|help|怎么用|使用说明|'
    r'再见|拜拜|bye|回头见)[！!。.,，?？\s]*$',
    re.IGNORECASE
)

def _is_lightweight(text):
    return bool(_LIGHT_PATTERNS.match(text.strip()))

# ─── Lightweight Chat Handler ──────────────────────────────
def _handle_lightweight_chat(user_input, stream, t0, user, model_id='deepseek-v4-flash'):
    messages = [
        {'role': 'system', 'content': '你是童小军的 AI 助手，只处理产品和报价相关业务。请用中文简洁回复。'},
        {'role': 'user', 'content': user_input},
    ]

    if stream:
        def generate():
            yield f'data: {_json.dumps({"type": "connect", "elapsed": f"{time.time()-t0:.1f}s"})}\n\n'
            full = ''
            first = True
            try:
                for chunk in _get_engine().chat_stream(model_id, messages, max_tokens=200, temperature=0.7):
                    delta = (chunk.get('choices') or [{}])[0].get('delta', {}).get('content', '')
                    if delta:
                        if first:
                            yield f'data: {_json.dumps({"type": "first_token", "ttft": f"{time.time()-t0:.1f}s"})}\n\n'
                            first = False
                        full += delta
                        yield f'data: {_json.dumps({"type": "text", "text": delta}, ensure_ascii=False)}\n\n'
                parsed = parse_reply_actions(full)
                yield f'data: {_json.dumps({"type": "done", "parsed": parsed, "elapsed": f"{time.time()-t0:.1f}s"}, ensure_ascii=False)}\n\n'
            except Exception as e:
                yield f'data: {_json.dumps({"type": "error", "error": str(e)})}\n\n'
            finally:
                yield 'data: [DONE]\n\n'

        from utils import _log_ai_usage
        _log_ai_usage(user_id=user.id, action='chat', model=model_id, elapsed=0, success=True)
        return Response(generate(), mimetype='text/event-stream',
                        headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'X-Accel-Buffering': 'no'})

    try:
        resp = _get_engine().chat(model_id, messages, max_tokens=200, temperature=0.7)
        reply = resp['choices'][0]['message'].get('content', '') or '好的。'
        parsed = parse_reply_actions(reply)
        from utils import _log_ai_usage
        _log_ai_usage(user_id=user.id, action='chat', model=model_id, elapsed=time.time()-t0)
        return jsonify({'reply': reply, 'parsed': parsed, 'model': 'ai-engine', 'timings': {'总耗时': f'{time.time()-t0:.1f}s'}})
    except Exception as e:
        from utils import _log_ai_usage
        _log_ai_usage(user_id=user.id, action='chat', model=model_id, elapsed=time.time()-t0, success=False, error=str(e)[:200])
        return jsonify({'error': f'AI 服务异常: {str(e)}'}), 503

# ─── Main Chat Endpoint ────────────────────────────────────
@ai_bp.route('/api/chat', methods=['POST'])
@require_auth
def ai_chat():
    """AI 对话 — 自研 AI Engine (v3.0)"""
    t0 = time.time()
    uid = g.current_user.id

    if _check_ai_rate_limit(uid):
        return jsonify({'error': f'请求过快，每分钟最多{_AI_RATE_LIMIT}次，请稍后再试'}), 429

    data = request.get_json(silent=True) or {}
    user_input = (data.get('input', '') or '').strip()
    if not user_input:
        return jsonify({'error': '请输入问题'}), 400

    stream = data.get('stream', False)
    user = g.current_user
    conv_id = data.get('conversation_id', '') or ''
    history = data.get('history') or []
    model_id = data.get('model') or _ai_model

    if _is_lightweight(user_input):
        return _handle_lightweight_chat(user_input, stream, t0, user, model_id)

    agent, ctx = _build_agent(user)
    messages, _ = ctx.build_messages(user_input, history=history, conversation_id=conv_id)
    tool_defs = ctx.get_tool_definitions()

    sm = SessionManager(uid, conv_id)
    conv_pk = sm.get_or_create_conversation().id
    sm.add_message(conv_pk, 'user', user_input)

    if stream:
        def generate():
            try:
                engine = _get_engine()
                yield f'data: {_json.dumps({"type": "connect", "elapsed": f"{time.time()-t0:.1f}s"})}\n\n'

                loop_messages = list(messages)
                for turn in range(3):
                    resp = engine.chat('deepseek-v4-flash', loop_messages, tools=tool_defs, max_tokens=2000)
                    msg = resp['choices'][0]['message']

                    if not msg.get('tool_calls'):
                        reply = msg.get('content', '')
                        if reply:
                            yield f'data: {_json.dumps({"type": "first_token", "ttft": f"{time.time()-t0:.1f}s"})}\n\n'
                            for i in range(0, len(reply), 3):
                                yield f'data: {_json.dumps({"type": "text", "text": reply[i:i+3]}, ensure_ascii=False)}\n\n'
                        if turn > 0:
                            yield f'data: {_json.dumps({"type": "tool"})}\n\n'
                        parsed = parse_reply_actions(reply)
                        yield f'data: {_json.dumps({"type": "done", "parsed": parsed, "elapsed": f"{time.time()-t0:.1f}s"}, ensure_ascii=False)}\n\n'
                        return

                    yield f'data: {_json.dumps({"type": "tool"})}\n\n'
                    loop_messages.append({'role': 'assistant', 'content': msg.get('content'), 'tool_calls': msg['tool_calls']})
                    for tc in msg['tool_calls']:
                        fn = tc['function']
                        try:
                            args = _json.loads(fn['arguments'])
                        except Exception:
                            args = {}
                        result = agent.tools.execute(fn['name'], args)
                        loop_messages.append({'role': 'tool', 'tool_call_id': tc.get('id', ''), 'name': fn['name'], 'content': _json.dumps(result, ensure_ascii=False)})

                yield f'data: {_json.dumps({"type": "done", "parsed": {}, "elapsed": f"{time.time()-t0:.1f}s"})}\n\n'
            except Exception as e:
                import traceback
                err_msg = str(e)[:200]
                yield f'data: {_json.dumps({"type": "error", "error": err_msg})}\n\n'
            finally:
                yield 'data: [DONE]\n\n'

        from utils import _log_ai_usage
        _log_ai_usage(user_id=uid, action='chat', model=model_id, elapsed=0, success=True)
        return Response(generate(), mimetype='text/event-stream',
                        headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'X-Accel-Buffering': 'no'})

    try:
        resp = _get_engine().chat('deepseek-v4-flash', messages, tools=tool_defs, max_tokens=2000)
        msg = resp['choices'][0]['message']
        reply = msg.get('content', '') or '抱歉，AI 暂时无法回答。'
        parsed = parse_reply_actions(reply)
        elapsed = time.time() - t0

        from utils import _log_ai_usage
        _log_ai_usage(user_id=uid, action='chat', model=model_id, elapsed=elapsed)
        return jsonify({'reply': reply, 'parsed': parsed, 'model': 'ai-engine', 'timings': {'总耗时': f'{elapsed:.1f}s'}})
    except Exception as e:
        from utils import _log_ai_usage
        _log_ai_usage(user_id=uid, action='chat', model=model_id, elapsed=time.time()-t0, success=False, error=str(e)[:200])
        return jsonify({'error': f'AI 服务异常: {str(e)}'}), 503
