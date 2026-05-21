#!/usr/bin/env python3
"""
报价管理系统 - Quote Management System
Flask + SQLite + REST API + Web UI
"""

import os
import sys
import json
import io
import re
import random
import secrets
import threading
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, request, jsonify, send_file, send_from_directory, render_template, g, Response
from flask_cors import CORS
from sqlalchemy import func
import jwt
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.drawing.image import Image as XLImage
from openpyxl.drawing.spreadsheet_drawing import AnchorMarker, TwoCellAnchor
from openpyxl.utils import get_column_letter

from extensions import db
from models import Product, Quote, QuoteItem, User, DownloadLog, FieldSetting, SystemSetting, AIChatSession, AIUsageLog
from auth import auth_bp, hash_password, verify_password, create_token, require_auth, require_admin, _is_registration_open

app = Flask(__name__)
# CORS 限制：仅允许同源和已知域名
_cors_origins = os.environ.get('QUOTE_CORS_ORIGINS', '').strip()
cors_kwargs = {}
if _cors_origins:
    cors_kwargs['origins'] = [o.strip() for o in _cors_origins.split(',') if o.strip()]
else:
    # 默认仅允许同源（生产环境应设置 QUOTE_CORS_ORIGINS）
    cors_kwargs['origins'] = [
        'https://bwh.ddns.mobi',
        'http://localhost:5173',  # Vite dev
    ]
CORS(app, **cors_kwargs)

# Register auth blueprint
app.register_blueprint(auth_bp)
# Admin + download blueprints (lazy import to avoid circular dependency)
import admin_bp as _admin_bp_mod
app.register_blueprint(_admin_bp_mod.admin_bp)
app.register_blueprint(_admin_bp_mod.download_bp)
# Products + upload + download_img blueprints
import products_bp as _products_bp_mod
app.register_blueprint(_products_bp_mod.products_bp)
app.register_blueprint(_products_bp_mod.upload_bp)
app.register_blueprint(_products_bp_mod.download_bp)
# Quotes + download_logs blueprints
import quotes_bp as _quotes_bp_mod
app.register_blueprint(_quotes_bp_mod.quotes_bp)
app.register_blueprint(_quotes_bp_mod.download_logs_bp)
# AI + chat blueprints
import ai_bp as _ai_bp_mod
app.register_blueprint(_ai_bp_mod.ai_bp)
app.register_blueprint(_ai_bp_mod.chat_bp)
app.register_blueprint(_ai_bp_mod.admin_ai_bp)

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / 'uploads'
EXPORT_DIR = BASE_DIR / 'exports'
UPLOAD_DIR.mkdir(exist_ok=True)
EXPORT_DIR.mkdir(exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{BASE_DIR}/quote.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB
app.config['JWT_SECRET'] = os.environ.get('QUOTE_JWT_SECRET', '')
if not app.config['JWT_SECRET']:
    # 尝试从文件加载（多worker共享同一secret）
    _secret_file = BASE_DIR / '.jwt_secret'
    if _secret_file.exists():
        app.config['JWT_SECRET'] = _secret_file.read_text().strip()
    if not app.config['JWT_SECRET']:
        app.config['JWT_SECRET'] = secrets.token_hex(32)
        _secret_file.write_text(app.config['JWT_SECRET'])
app.config['JWT_EXPIRY_HOURS'] = 72
app.config['DEFAULT_ADMIN_PASSWORD'] = os.environ.get('QUOTE_ADMIN_PASSWORD', 'admin123')
app.config['REGISTRATION_OPEN'] = os.environ.get('QUOTE_REGISTRATION', 'true').lower() == 'true'

db.init_app(app)

# ─── Helpers ─────────────────────────────────────────────────────
# _store_image_blob, add_pinyin_field, compress_image_if_needed,
# _debug_log, _log_ai_usage, _compute_pinyin_search, _safe_number,
# _parse_json_reply, _product_from_parsed, deepseek_parse_product,
# _ocr_fallback, doubao_vision_recognize, smart_parse_product,
# parse_product_line — 已移至 products_bp.py


def preload_products_for_quote(quote):
    """批量加载报价单所有明细关联的产品，返回 {product_id: Product}"""
    pids = [item.product_id for item in quote.items if item.product_id]
    if not pids:
        return {}
    products = Product.query.filter(Product.id.in_(pids)).all()
    return {p.id: p for p in products}

# ─── JWT & Auth Helpers (moved to auth.py) ──────────────────

def check_quote_owner(quote_id):
    """非管理员只能操作自己的报价单。返回 (quote_or_error, status_code)."""
    quote = db.session.get(Quote, quote_id)
    if not quote:
        return None, jsonify({'error': '报价单不存在'}), 404
    if g.current_user.role != 'admin' and quote.created_by != g.current_user.id:
        return None, jsonify({'error': '无权操作此报价单'}), 403
    return quote, None, None


# ─── Admin API (moved to admin_bp.py) ───────────────────────
# Admin routes are now in admin_bp.py; register blueprint below.

# ─── 系统设置 Helper（仍被 app.py 其他路由使用） ───────
def get_setting(key, default=''):
    """读取单个系统设置"""
    s = SystemSetting.query.filter_by(key=key).first()
    return s.value if s else default

def get_all_settings():
    """读取所有系统设置 (返回dict)"""
    return {s.key: s.value for s in SystemSetting.query.all()}

def _get_ai_system_prompt():
    """获取 AI 系统提示词 — 委托给 ai_bp 实现（单一来源）"""
    from ai_bp import _get_ai_system_prompt as _ai_bp_get_prompt
    return _ai_bp_get_prompt()


# ─── API Routes ──────────────────────────────────────────────

# ─── 下载 Ticket 机制已移至 admin_bp.py ────────────────────
# _validate_download_ticket 在 check_auth() 中延迟导入，避免循环依赖

# 公开路由（无需登录）
PUBLIC_ROUTES = {'auth.auth_login', 'auth.auth_register', 'auth.auth_registration_status', 'get_version', 'health_check', 'index', 'products.export_product_template', 'download.create_download_ticket'}

# ─── 全局错误处理 ───
@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(405)
@app.errorhandler(500)
def _handle_error(e):
    return jsonify({'error': e.description if hasattr(e, 'description') else str(e)}), e.code if hasattr(e, 'code') else 500

# ─── 请求日志中间件 ───
import time as _req_time

@app.after_request
def _log_request(response):
    if request.path.startswith('/api/') and not request.path.startswith('/api/assets'):
        elapsed = (int((_req_time.time() - g.get('_req_start', _req_time.time())) * 1000))
        user = getattr(g, 'current_user', None)
        username = user.username if user else '-'
        method = request.method
        status = response.status_code
        if status >= 400 or elapsed > 3000:  # 只记慢请求和错误
            _debug_log(f'{method} {request.path} {status} {elapsed}ms user={username}')
    return response

@app.before_request
def _mark_req_start():
    g._req_start = _req_time.time()

@app.before_request
def check_auth():
    if not request.path.startswith('/api/') and not request.path.startswith('/uploads/'):
        return None
    # 提取路由名
    endpoint = request.endpoint
    if endpoint in PUBLIC_ROUTES or (endpoint and endpoint.startswith('static')):
        return None
    # 鉴权：优先 Bearer Token，其次 query param token（图片等场景），最后 download_ticket
    token = request.headers.get('Authorization', '').replace('Bearer ', '') or request.args.get('token', '')
    if token:
        try:
            data = jwt.decode(token, app.config['JWT_SECRET'], algorithms=['HS256'])
            user = db.session.get(User, data['user_id'])
            if not user or not user.is_active:
                return jsonify({'error': '账号无效或已停用'}), 403
            g.current_user = user
            return None
        except jwt.ExpiredSignatureError:
            return jsonify({'error': '登录已过期，请重新登录'}), 401
        except Exception:
            return jsonify({'error': '认证失败'}), 401
    # 下载 ticket 兜底（仅用于文件下载场景，短期2分钟有效）
    dlt = request.args.get('download_ticket', '')
    if dlt:
        from admin_bp import _validate_download_ticket
        uid = _validate_download_ticket(dlt)
        if uid:
            user = db.session.get(User, uid)
            if user and user.is_active:
                g.current_user = user
                return None
        return jsonify({'error': '下载凭证无效或已过期'}), 401
    return jsonify({'error': '请先登录'}), 401

# 字段可见性缓存
_field_cache = None
_field_cache_time = None

def get_field_visibility():
    global _field_cache, _field_cache_time
    now = datetime.now()
    if _field_cache and _field_cache_time and (now - _field_cache_time).seconds < 300:
        return _field_cache
    _field_cache = {f.field_name: f.user_visible for f in FieldSetting.query.all()}
    _field_cache_time = now
    return _field_cache

def filter_fields_for_user(data_dict, is_admin):
    if is_admin:
        return data_dict
    visibility = get_field_visibility()
    for field in ['cost_price', 'remark', 'supplier', 'function_desc']:
        if field in data_dict and not visibility.get(field, True):
            data_dict[field] = '(无权限查看)'
    return data_dict

# ----- Products (moved to products_bp.py) -----
# All product route handlers have been moved to products_bp.py
# Helper functions below are kept here as they are also used by quotes/ai routes


def compress_image_if_needed(filepath, max_kb=95, max_dim=800):
    """压缩图片到指定大小以内，返回最终路径和文件名。
    透明PNG自动贴白底转JPG。"""
    from PIL import Image
    filepath = Path(filepath)
    img = Image.open(str(filepath))
    orig_w, orig_h = img.size
    orig_kb = filepath.stat().st_size / 1024

    # 尺寸过大的先缩小
    if orig_w > max_dim or orig_h > max_dim:
        ratio = min(max_dim / orig_w, max_dim / orig_h)
        new_w = max(1, int(orig_w * ratio))
        new_h = max(1, int(orig_h * ratio))
        img = img.resize((new_w, new_h), Image.LANCZOS)

    # 透明 PNG → 贴白底转 JPG（无论是否需要压缩都做）
    needs_white_bg = img.mode in ('RGBA', 'P')
    if needs_white_bg:
        if img.mode == 'P':
            img = img.convert('RGBA')
        alpha = img.split()[-1]
        has_alpha = img.mode == 'RGBA' and alpha.getextrema()[0] < 255
        if has_alpha:
            bg = Image.new('RGB', img.size, (255, 255, 255))
            bg.paste(img, mask=alpha)
            img = bg
        else:
            img = img.convert('RGB')

    # 若已有白底且小于阈值且不是透明格式，不处理
    if orig_kb <= max_kb and not needs_white_bg and filepath.suffix in ('.jpg', '.jpeg'):
        return str(filepath), filepath.name

    # 保存为 JPG
    out_path = filepath.with_suffix('.jpg')
    if orig_kb <= max_kb and needs_white_bg:
        # 小文件但已贴白底，高质量保存
        img.save(str(out_path), 'JPEG', quality=85, optimize=True)
    else:
        # 渐进降质量
        for quality in [75, 65, 55, 45, 35, 25]:
            img.save(str(out_path), 'JPEG', quality=quality, optimize=True)
            if out_path.stat().st_size / 1024 <= max_kb:
                break

    # 删除原始文件（如果扩展名变了）
    if out_path.suffix != filepath.suffix:
        filepath.unlink(missing_ok=True)

    return str(out_path), out_path.name


def _ocr_fallback(image_path):
    """OCR.space 作为降级方案，返回识别文本或 None。"""
    try:
        import requests as http_req
        with open(image_path, 'rb') as fp:
            r = http_req.post(
                'https://api.ocr.space/parse/image',
                files={'file': fp},
                data={'language': 'chs', 'isOverlayRequired': False,
                      'detectOrientation': True, 'scale': True,
                      'apikey': os.environ.get('OCR_SPACE_API_KEY', 'helloworld')},
                timeout=30,
            )
        if r.status_code != 200:
            return None
        result = r.json()
        if result.get('OCRExitCode') == 1:
            return result.get('ParsedResults', [{}])[0].get('ParsedText', '').strip()
    except Exception:
        pass
    return None


def doubao_vision_recognize(image_b64, mime_type='image/jpeg'):
    """使用火山引擎豆包 Seed Lite 从图片中提取产品信息，返回结构化 JSON dict。
    豆包直出纯 JSON，不需要额外解析。
    失败返回 None。
    """
    api_key = os.environ.get('VOLCENGINE_API_KEY', '')
    if not api_key:
        return None

    prompt = (
        '请仔细阅读图片中的产品信息，提取以下字段并以JSON格式返回（只返回JSON，不要其他文字）：\n'
        '{\n'
        '  "name": "产品名称（中文，不包括型号）",\n'
        '  "spec": "规格型号（如 ZQWL-GW2800NU-P12）",\n'
        '  "supplier": "厂商/品牌名",\n'
        '  "price": 售价数字（纯数字，没有则填 0）,\n'
        '  "cost_price": 成本价数字（纯数字，没有则填 0）,\n'
        '  "category": "分类（如 IO网关、传感器、门禁等，没有则填空字符串）",\n'
        '  "unit": "单位（台/个/套/件，默认台）",\n'
        '  "function_desc": "功能描述（核心功能、特性、参数亮点等）",\n'
        '  "remark": "其他备注（产地、认证、包装等次要信息，没有则填空字符串）"\n'
        '}\n'
        '注意：\n'
        '- 型号通常是大写字母+数字+横杠组合\n'
        '- 厂商从文字中直接提取，不要猜测\n'
        '- 价格只提取数字部分\n'
        '- function_desc 放主要功能特性，remark 放次要备注信息'
    )

    try:
        import requests as http_req
        r = http_req.post(
            'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': 'doubao-seed-2-0-lite-260215',
                'messages': [{
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': prompt},
                        {'type': 'image_url', 'image_url': {'url': f'data:{mime_type};base64,{image_b64}'}}
                    ]
                }],
                'max_tokens': 1000,
            },
            timeout=60,
        )
        if r.status_code != 200:
            _debug_log(f'[doubao_vision] API returned {r.status_code}: {r.text[:200]}')
            return None

        result = r.json()
        raw_text = result.get('choices', [{}])[0].get('message', {}).get('content', '')
        if not raw_text:
            _debug_log(f'[doubao_vision] Empty response content. Full: {str(result)[:300]}')
            return None

        # 解析 JSON（公共3层兜底）
        parsed = _parse_json_reply(raw_text)

        if parsed:
            product = _product_from_parsed(parsed, json.dumps(result, ensure_ascii=False))
            if product:
                return product
        _debug_log(f'[doubao_vision] Parsed but name empty. raw_text[:200]: {raw_text[:200]}')
        return None
    except Exception as e:
        _debug_log(f'[doubao_vision] Exception: {e}')
        return None


def _debug_log(msg):
    """写调试日志到 gunicorn error log 文件（相对于项目BASE_DIR）"""
    try:
        with open(BASE_DIR / 'gunicorn-error.log', 'a') as f:
            from datetime import datetime
            f.write(f'[{datetime.now().isoformat()}] {msg}\n')
    except Exception:
        pass


def _log_ai_usage(user_id, action, model='', elapsed=0, success=True, error=''):
    """记录AI调用到数据库（静默失败，不影响主流程）"""
    try:
        db.session.add(AIUsageLog(
            user_id=user_id, action=action, model=model[:50],
            elapsed=round(elapsed, 2), success=success, error=(error or '')[:200]
        ))
        db.session.commit()
    except Exception:
        try: db.session.rollback()
        except Exception: pass


def _compute_pinyin_search(name, sku='', category='', supplier=''):
    """预计算产品拼音搜索字段 — 所有字段拼音首字母+全拼拼接"""
    try:
        from pypinyin import pinyin, Style
        parts = [name or '', sku or '', category or '', supplier or '']
        all_py = []
        for text in parts:
            if text:
                py_list = pinyin(text, style=Style.NORMAL, heteronym=False)
                all_py.extend([p[0] for p in py_list])
                # 首字母
                first_letters = pinyin(text, style=Style.FIRST_LETTER, heteronym=False)
                all_py.extend([f[0] for f in first_letters])
        return ' '.join(all_py)
    except Exception:
        return ''


def _safe_number(val):
    """安全转换为 float，失败返回 0。"""
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return round(float(val), 2)
    try:
        return round(float(val), 2)
    except (ValueError, TypeError):
        return 0


def _parse_json_reply(text):
    """从LLM回复中提取JSON dict — 3层兜底：直接解析→代码块→正则。
    返回 dict 或 None。doubao_vision 和 deepseek_parse 共用。
    """
    import re, json
    parsed = None
    text = text.strip()

    # 策略1: 直接解析
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # 策略2: ```json ... ``` 代码块
    if not parsed:
        m = re.search(r'```(?:json)?\s*\n?(\{.+\})\s*```', text, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(1))
            except (json.JSONDecodeError, ValueError):
                pass

    # 策略3: 包含 "name" 字段的 JSON 对象（或任意 {...}）
    if not parsed:
        m = re.search(r'\{[^{}]*"name"\s*:\s*"[^"]*"[^{}]*\}', text, re.DOTALL)
        if not m:
            m = re.search(r'\{.+\}', text, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except (json.JSONDecodeError, ValueError):
                pass

    return parsed


def _product_from_parsed(parsed, raw=''):
    """从解析出的dict构建标准化产品dict，截断字段长度"""
    if not parsed:
        return None
    product = {
        'name': str(parsed.get('name', '')).strip()[:20],
        'spec': str(parsed.get('spec', '')).strip()[:100],
        'supplier': str(parsed.get('supplier', '')).strip()[:50],
        'price': _safe_number(parsed.get('price', 0)),
        'cost_price': _safe_number(parsed.get('cost_price', 0)),
        'unit': str(parsed.get('unit', '')).strip()[:10],
        'category': str(parsed.get('category', '')).strip()[:50],
        'function_desc': str(parsed.get('function_desc', '')).strip()[:500],
        'remark': str(parsed.get('remark', '')).strip()[:500],
        '_raw': raw,
    }
    return product if product['name'] else None


def deepseek_parse_product(text):
    """使用 DeepSeek v4 Flash（通过 Hermes Gateway）从非结构化文本中提取产品信息。
    返回结构化 dict 或 None。
    """
    import urllib.request, json as _json
    prompt = (
        '从以下产品文本中提取信息，返回纯JSON（只返回JSON，不要markdown、不要解释）：\n'
        '{"name":"产品名称（中文，不包括型号，截取前20字）","spec":"规格型号（大写字母+数字+横杠组合）","supplier":"厂商/品牌","price":售价数字,"cost_price":成本价数字,"category":"分类","unit":"单位","remark":"备注/功能描述"}\n'
        '规则：型号是大写字母+数字+横杠组合。厂商从文字中直接提取，不要猜测。价格只取数字。没有的字段填空字符串或0。\n'
        f'文本：\n{text[:3000]}'
    )
    try:
        body = _json.dumps({
            'model': 'deepseek-v4-flash',
            'input': prompt,
            'max_output_tokens': 500,
        })
        req = urllib.request.Request(
            f'{_gateway_url}/v1/responses',
            data=body.encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        resp = urllib.request.urlopen(req, timeout=30)
        result = _json.loads(resp.read())
        reply = ''
        for o in result.get('output', []):
            if o.get('type') == 'message':
                content = o.get('content', [])
                if content:
                    reply = content[0].get('text', '')
                break
        reply = reply.strip()
        # 解析 JSON（公共3层兜底）
        parsed = _parse_json_reply(reply)
        if parsed:
            product = _product_from_parsed(parsed, reply)
            if product:
                return product
        _debug_log(f'[deepseek_parse] Failed. reply[:200]: {reply[:200]}')
    except Exception as e:
        _debug_log(f'[deepseek_parse] Exception: {e}')
        pass
    return None


def smart_parse_product(text):
    """智能解析非结构化文本，按字段模式匹配提取产品信息。
    不依赖固定顺序/分隔符，支持任意格式粘贴。
    """
    import re

    result = {'name': '', 'sku': '', 'spec': '', 'unit': '',
              'price': 0, 'cost_price': 0, 'supplier': '', 'remark': ''}

    text = text.strip()
    if not text:
        return None

    # ── 1. 提取价格（支持：¥123.45 / 123元 / 价格:123 / 售价 ¥123）──
    price_patterns = [
        r'[¥￥]\s*(\d+\.?\d{0,2})\b',
        r'售价[：:\s]*[¥￥]?\s*(\d+\.?\d{0,2})\b',
        r'价格[：:\s]*[¥￥]?\s*(\d+\.?\d{0,2})\b',
        r'单价[：:\s]*[¥￥]?\s*(\d+\.?\d{0,2})\b',
        r'(\d+\.?\d{0,2})\s*元\b',
        r'\b(\d+\.?\d{0,2})\s*[元$]',
    ]
    prices_found = []
    for pat in price_patterns:
        for m in re.finditer(pat, text):
            val = float(m.group(1))
            if 0 < val < 100000000:
                prices_found.append((val, m.start(), m.end()))
    if prices_found:
        # 取最大金额作为售价
        prices_found.sort(key=lambda x: -x[0])
        result['price'] = round(prices_found[0][0], 2)

    # ── 2. 提取成本价 ──
    cost_patterns = [
        r'成本[：:\s]*[¥￥]?\s*(\d+\.?\d{0,2})\b',
        r'进价[：:\s]*[¥￥]?\s*(\d+\.?\d{0,2})\b',
        r'成本价[：:\s]*[¥￥]?\s*(\d+\.?\d{0,2})\b',
    ]
    for pat in cost_patterns:
        m = re.search(pat, text)
        if m:
            result['cost_price'] = round(float(m.group(1)), 2)
            break

    # ── 3. 提取型号（大写字母+数字+横杠组合）──
    sku_patterns = [
        r'\b([A-Z]{2,}[\dA-Z\-/\.\+]{1,30})\b',
        r'型号[：:\s]*([A-Z\d][\dA-Z\-/\.\+]{1,30})',
        r'规格型号[：:\s]*([A-Z\d][\dA-Z\-/\.\+]{1,30})',
        r'SKU[：:\s]*([A-Z\d][\dA-Z\-/\.\+]{1,30})',
    ]
    skus_found = []
    for pat in sku_patterns:
        for m in re.finditer(pat, text):
            v = m.group(1).strip()
            if len(v) >= 3 and re.search(r'[A-Z]', v) and re.search(r'\d', v):
                skus_found.append((v, m.start(), m.end()))
    if skus_found:
        # 最长型号优先
        skus_found.sort(key=lambda x: -len(x[0]))
        result['spec'] = skus_found[0][0]

    # ── 4. 熟悉厂商对照 ──
    known_suppliers = [
        '星纵', '绿米', '海康威视', '海康微影', '大华', '宇视', '汉朔',
        '京东方', 'BOE', '得力', '德生', '研华', '中弘', '亿联', '飞利浦',
        '树莓', '明纬', '杜亚', '欧孚', 'HID', 'QBIC', 'Temi', 'ELO',
        '智嵌', '智绘源', '宸展', '联智触控', '优良专显', '大唐', '大洋',
        '原点', '微光', '微耕', '西瑞智能', '苏州星途', '迪勤', '京仪北方',
        '汇尚', '海林', '百度', '中电', '迭代', '易乐看',
    ]
    for s in known_suppliers:
        if s in text:
            result['supplier'] = s
            break

    # ── 5. 熟悉分类对照 ──
    known_categories = [
        'IoT', '会议', '信发', '厕位', '工位', '星纵', '绿米', '门禁',
        '环境', '能耗照明环境', 'FM', 'IBMS', 'MTR', '访客',
    ]
    for c in known_categories:
        if c in text:
            result.setdefault('category', c)
            break

    # ── 6. 提取单位 ──
    unit_match = re.search(r'单位[：:\s]*([台个套件只条根米卷])', text)
    if unit_match:
        result['unit'] = unit_match.group(1)

    # ── 7. 剩余文字 → 产品名称 + 备注 ──
    # 去掉已匹配的价格、型号、厂商等
    clean = text
    for pat in price_patterns:
        clean = re.sub(pat, '', clean)
    for pat in sku_patterns:
        clean = re.sub(pat, '', clean, count=1)
    for pat in cost_patterns:
        clean = re.sub(pat, '', clean)
    clean = re.sub(r'[¥￥]', '', clean)
    clean = re.sub(r'售价|价格|单价|成本|进价|成本价|型号|规格型号|SKU|单位', '', clean)
    clean = re.sub(r'产品[：:\s]*|厂商[：:\s]*|功能[：:\s]*|描述[：:\s]*|说明[：:\s]*', '', clean)
    clean = re.sub(r'[：:\s]+', ' ', clean).strip()
    # 清理孤立的 "元"（价格提取残留）
    clean = re.sub(r'\b元\b', '', clean).strip()

    # 去掉已匹配的厂商名
    if result['supplier']:
        clean = clean.replace(result['supplier'], '').strip()

    # 清理多余空格和标点
    clean = re.sub(r'\s+', ' ', clean).strip(' ，,。.')
    clean = re.sub(r'^\d+[\\.\、\）\)]\s*', '', clean)  # 去掉序号前缀

    if clean:
        # 按常见中文标点/换行分段
        segments = [s.strip() for s in re.split(r'[，,。\\n]', clean) if s.strip()]
        if segments:
            # 第一段 → 产品名称（中文优先）
            chinese_name = ''
            for seg in segments:
                if re.search(r'[\u4e00-\u9fff]', seg):
                    chinese_name = seg
                    break
            if not chinese_name:
                chinese_name = segments[0]
            result['name'] = chinese_name[:20]

            # 剩余段 → 备注
            other = [s for s in segments if s != chinese_name]
            if other:
                result['remark'] = ' '.join(other)[:500]

    # ── 兜底：如果 name 为空，取正文第一行 ──
    if not result.get('name') and clean:
        first_line = clean.split('\n')[0].strip()[:20]
        if first_line:
            result['name'] = first_line

    return result if result.get('name') else None


def parse_product_line(line):
    """原始解析器，保留兼容（Tab/空格固定位置）"""
    import re

    # 先按tab分割（Excel粘贴）
    parts = [p.strip() for p in line.split('\t') if p.strip()]
    # 如果tab没分出来，尝试至少2个空格分割
    if len(parts) <= 1:
        parts = [p.strip() for p in re.split(r'\s{2,}', line) if p.strip()]
    # 仍然只有一个，尝试单空格分割
    if len(parts) <= 1:
        parts = [p.strip() for p in line.split() if p.strip()]

    if not parts:
        return None

    # 去掉可能的序号前缀（如 "1. " "2、"）
    parts = [re.sub(r'^\d+[\.\、\）\)](?!\d)', '', p).strip() for p in parts]
    parts = [p for p in parts if p]

    if not parts:
        return None

    result = {'name': '', 'sku': '', 'spec': '', 'unit': '', 'price': 0, 'supplier': '', 'remark': ''}

    # 检查最后一个是否像价格
    last = parts[-1]
    price_val = None
    price_match = re.match(r'^[¥￥]?\s*([\d]+\.?\d*)\s*[元]?$', last)
    if price_match:
        try:
            price_val = round(float(price_match.group(1)), 2)
            parts = parts[:-1]
        except ValueError:
            pass

    if not parts:
        return None

    # 第一个：产品名称
    result['name'] = parts[0]

    # 倒数第一个（价格之后的最后一个字段）：功能描述 → 备注
    if len(parts) >= 2:
        result['remark'] = parts[-1]
        parts = parts[:-1]

    # 倒数第二个（如有）：厂商
    if len(parts) >= 2:
        result['supplier'] = parts[-1]
        parts = parts[:-1]

    # 剩余中间部分：规格型号（合并）
    if len(parts) >= 2:
        spec_parts = parts[1:]
        result['spec'] = ' '.join(spec_parts)
        for sp in spec_parts:
            sku_match = re.match(r'^([A-Z]{2,}[\dA-Z\-/\.\+]*)$', sp)
            if sku_match:
                result['sku'] = sku_match.group(1)
                break

    if price_val is not None:
        result['price'] = price_val

    return result if result.get('name') else None


# ─── Quotes (moved to quotes_bp.py) ─────────────────────
# All quotes route handlers and helper functions have been moved to quotes_bp.py
# Helpers kept in app.py: check_quote_owner, preload_products_for_quote, get_setting

# ─── AI (moved to ai_bp.py) ───────────────────────
# All AI routes and helper functions have been moved to ai_bp.py

# ─── Frontend ────────────────────────────────────────────────
_dist_dir = os.path.join(os.path.dirname(__file__), 'frontend', 'dist')
_has_vue_build = os.path.isdir(_dist_dir)

@app.route('/')
def index():
    if _has_vue_build:
        return send_file(os.path.join(_dist_dir, 'index.html'))
    return render_template('index.html')

# Serve Vue build assets (JS/CSS) from /assets/ and /quote/assets/
@app.route('/assets/<path:filename>')
@app.route('/quote/assets/<path:filename>')
def vue_assets(filename):
    if _has_vue_build:
        return send_from_directory(os.path.join(_dist_dir, 'assets'), filename)
    return 'Not Found', 404


@app.route('/api/version', methods=['GET'])
def get_version():
    version_file = BASE_DIR / 'version.txt'
    try:
        ver = version_file.read_text().strip()
    except Exception:
        ver = '0.1.1'
    return jsonify({'version': ver})

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查 — 验证DB连通性"""
    try:
        db.session.execute(text('SELECT 1'))
        db_ok = True
    except Exception:
        db_ok = False
    status = 200 if db_ok else 503
    return jsonify({'status': 'ok' if db_ok else 'db_error', 'db': db_ok}), status

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """提供上传的图片等静态文件"""
    return send_from_directory(UPLOAD_DIR, filename)


# ─── SPA catch-all (must be LAST route) ──────
@app.route('/<path:path>')
def spa_catch_all(path):
    """所有非 API/静态文件路径 → 返回 Vue SPA"""
    if _has_vue_build:
        return send_file(os.path.join(_dist_dir, 'index.html'))
    return render_template('index.html')


# ─── Init DB ────────────────────────────────────────────────

with app.app_context():
    # 启用 SQLite WAL 模式（并发读写更安全）
    from sqlalchemy import text
    try:
        db.session.execute(text('PRAGMA journal_mode=WAL'))
        db.session.execute(text('PRAGMA busy_timeout=5000'))
        db.session.commit()
    except Exception:
        pass
    db.create_all()

    # 自动迁移：检测缺失列并ALTER TABLE（SQLite兼容）
    _auto_migrate_columns = [
        ('quote_items', 'discount_rate', 'REAL DEFAULT 100'),
        ('products', 'pinyin_search', 'TEXT'),
    ]
    import sqlite3 as _sqlite3
    _auto_db = _sqlite3.connect(str(BASE_DIR / 'quote.db'))
    _existing = _auto_db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    _existing_tables = {r[0] for r in _existing}
    for _tbl, _col, _col_type in _auto_migrate_columns:
        if _tbl in _existing_tables:
            _cols = [r[1] for r in _auto_db.execute(f'PRAGMA table_info({_tbl})').fetchall()]
            if _col not in _cols:
                try:
                    _auto_db.execute(f'ALTER TABLE {_tbl} ADD COLUMN {_col} {_col_type}')
                    _auto_db.commit()
                    print(f'[Migrate] 已添加 {_tbl}.{_col}')
                except Exception as e:
                    print(f'[Migrate] 添加 {_tbl}.{_col} 失败: {e}')
    _auto_db.close()

    # 预置管理员账号
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            password_hash=hash_password(app.config['DEFAULT_ADMIN_PASSWORD']),
            role='admin', is_active=True
        )
        db.session.add(admin)
        db.session.commit()
        print(f'[Init] 已创建管理员: admin / {app.config["DEFAULT_ADMIN_PASSWORD"]}')
    # 迁移：历史报价单 assign 给 admin (user_id=1)
    orphan_quotes = Quote.query.filter(Quote.created_by.is_(None)).all()
    if orphan_quotes:
        admin_user = User.query.filter_by(username='admin').first()
        if admin_user:
            for q in orphan_quotes:
                q.created_by = admin_user.id
            db.session.commit()
            print(f'[Init] 已为 {len(orphan_quotes)} 条历史报价单分配创建者: admin')

    # 回填：为旧产品计算拼音搜索字段
    missing_pinyin = Product.query.filter(
        (Product.pinyin_search.is_(None) | (Product.pinyin_search == ''))
    ).limit(500).all()
    if missing_pinyin:
        for p in missing_pinyin:
            p.pinyin_search = _compute_pinyin_search(p.name, p.spec or '', p.category or '', p.supplier or '')
        db.session.commit()
        print(f'[Init] 已回填 {len(missing_pinyin)} 个产品的拼音搜索字段')
    # 初始化默认系统设置
    defaults = {'company_name': '', 'footer_text': ''}
    for k, v in defaults.items():
        if not SystemSetting.query.filter_by(key=k).first():
            db.session.add(SystemSetting(key=k, value=v))
    db.session.commit()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
