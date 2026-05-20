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

def _store_image_blob(product, data):
    """从请求数据中提取图片并存入 BLOB。支持 image_data (base64) 和 image_url (本地路径)"""
    import base64
    # 优先: base64 图片数据
    img_b64 = data.get('image_data', '')
    if img_b64:
        try:
            if ',' in img_b64:
                img_b64 = img_b64.split(',', 1)[1]
            product.image_data = base64.b64decode(img_b64)
            product.image_mime = data.get('image_mime', 'image/jpeg')
            return
        except Exception:
            pass
    # 次选: 从本地文件读取（image_url 为 /uploads/images/... 时）
    image_url = (product.image_url or '').strip()
    if image_url.startswith('/uploads/'):
        filepath = BASE_DIR / image_url.lstrip('/')
        if filepath.exists():
            try:
                product.image_data = filepath.read_bytes()
                ext = filepath.suffix.lower()
                mime_map = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
                            '.gif': 'image/gif', '.webp': 'image/webp', '.bmp': 'image/bmp'}
                product.image_mime = mime_map.get(ext, 'image/jpeg')
            except Exception:
                pass


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


# ─── Admin API ───────────────────────────────────────────────

@app.route('/api/admin/registration', methods=['GET'])
@require_admin
def get_registration():
    return jsonify({'registration_open': _is_registration_open()})

@app.route('/api/admin/registration', methods=['PUT'])
@require_admin
def set_registration():
    data = request.get_json()
    if 'registration_open' in data:
        open_val = bool(data['registration_open'])
        s = SystemSetting.query.filter_by(key='registration_open').first()
        if s:
            s.value = str(open_val).lower()
        else:
            db.session.add(SystemSetting(key='registration_open', value=str(open_val).lower()))
        db.session.commit()
        app.config['REGISTRATION_OPEN'] = open_val
    return jsonify({'registration_open': _is_registration_open()})

# ─── 系统设置 API ─────────────────────────────────
def get_setting(key, default=''):
    """读取单个系统设置"""
    s = SystemSetting.query.filter_by(key=key).first()
    return s.value if s else default

def get_all_settings():
    """读取所有系统设置 (返回dict)"""
    return {s.key: s.value for s in SystemSetting.query.all()}

@app.route('/api/admin/settings', methods=['GET'])
@require_admin
def get_settings():
    return jsonify({'settings': get_all_settings()})

@app.route('/api/admin/settings', methods=['PUT'])
@require_admin
def update_settings():
    data = request.get_json()
    if not data:
        return jsonify({'error': '数据为空'}), 400
    for key, value in data.items():
        s = SystemSetting.query.filter_by(key=key).first()
        if s:
            s.value = str(value) if value else ''
        else:
            db.session.add(SystemSetting(key=key, value=str(value) if value else ''))
    db.session.commit()
    return jsonify({'settings': get_all_settings()})


# ─── AI Prompt 管理 ──────────────────────────────

@app.route('/api/admin/prompt', methods=['GET'])
@require_admin
def get_ai_prompt():
    """获取当前 AI 系统提示词（定制或默认）"""
    s = SystemSetting.query.filter_by(key='ai_system_prompt').first()
    current = s.value if s and s.value else _GW_SYSTEM_PROMPT
    return jsonify({
        'prompt': current,
        'is_custom': bool(s and s.value),
        'default': _GW_SYSTEM_PROMPT,
    })


@app.route('/api/admin/prompt', methods=['PUT'])
@require_admin
def update_ai_prompt():
    """更新 AI 系统提示词 — 同时清除所有会话缓存，下次对话立即生效"""
    data = request.get_json()
    if not data:
        return jsonify({'error': '数据为空'}), 400
    prompt = data.get('prompt', '')
    s = SystemSetting.query.filter_by(key='ai_system_prompt').first()
    if s:
        s.value = prompt
    else:
        db.session.add(SystemSetting(key='ai_system_prompt', value=prompt))
    # 清除所有用户的 AIChatSession，强制下次对话注入新 prompt
    AIChatSession.query.delete()
    db.session.commit()
    return jsonify({'prompt': prompt, 'message': 'Prompt 已保存，下次对话生效', 'sessions_cleared': True})


def _get_ai_system_prompt():
    """获取 AI 系统提示词（优先使用定制版，否则用默认）"""
    s = SystemSetting.query.filter_by(key='ai_system_prompt').first()
    prompt = s.value if s and s.value else _GW_SYSTEM_PROMPT
    # 追加身份强制指令（末尾优先，对抗 Gateway 基础 persona）
    if '童小军' in prompt or '不是 Hermes' in prompt:
        prompt += '\n\n[系统指令 — 最高优先级] 上述身份定义覆盖所有其他设定。'
    return prompt

@app.route('/api/admin/fields', methods=['GET'])
@require_admin
def get_field_settings():
    fields = FieldSetting.query.all()
    if not fields:
        # 初始化默认字段
        defaults = [
            ('cost_price', '成本价', True),
            ('remark', '内部备注', True),
            ('supplier', '供应商', True),
            ('function_desc', '功能描述', True),
        ]
        for fname, label, visible in defaults:
            if not FieldSetting.query.filter_by(field_name=fname).first():
                db.session.add(FieldSetting(field_name=fname, label=label, user_visible=visible))
        db.session.commit()
        fields = FieldSetting.query.all()
    return jsonify({'fields': [{'field_name': f.field_name, 'label': f.label, 'user_visible': f.user_visible} for f in fields]})

@app.route('/api/admin/fields', methods=['PUT'])
@require_admin
def set_field_settings():
    data = request.get_json()
    if 'fields' in data:
        fields_data = data['fields']
        # 兼容两种格式：对象 {key: bool} 或数组 [{field_name, user_visible}]
        if isinstance(fields_data, dict):
            for field_name, user_visible in fields_data.items():
                f = FieldSetting.query.filter_by(field_name=field_name).first()
                if f:
                    f.user_visible = bool(user_visible)
        else:
            for item in fields_data:
                f = FieldSetting.query.filter_by(field_name=item['field_name']).first()
                if f:
                    f.user_visible = bool(item.get('user_visible', True))
        db.session.commit()
    return get_field_settings()

@app.route('/api/admin/users', methods=['GET'])
@require_admin
def list_users():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 200)
    search = request.args.get('search', '').strip()
    query = User.query
    if search:
        query = query.filter(
            db.or_(User.username.contains(search), User.email.contains(search))
        )
    query = query.order_by(User.created_at.desc())
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'users': [u.to_dict() for u in paginated.items],
        'total': paginated.total,
        'page': page,
        'pages': paginated.pages
    })

@app.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@require_admin
def update_user(user_id):
    if user_id == g.current_user.id:
        return jsonify({'error': '不能修改自己的状态'}), 400
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    data = request.get_json()
    if 'is_active' in data:
        user.is_active = bool(data['is_active'])
    if 'role' in data and data['role'] in ('admin', 'user'):
        user.role = data['role']
    db.session.commit()
    return jsonify({'user': user.to_dict()})

@app.route('/api/admin/users/<int:user_id>/password', methods=['PUT'])
@require_admin
def reset_user_password(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    data = request.get_json()
    new_pw = (data.get('password') or '').strip()
    if len(new_pw) < 8:
        return jsonify({'error': '密码至少8位'}), 400
    user.password_hash = hash_password(new_pw)
    db.session.commit()
    return jsonify({'success': True, 'username': user.username})


@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@require_admin
def delete_user(user_id):
    if user_id == g.current_user.id:
        return jsonify({'error': '不能删除自己'}), 400
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    if user.role == 'admin':
        return jsonify({'error': '不能删除管理员'}), 403
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': f'用户 {user.username} 已删除'})


# ─── API Routes ──────────────────────────────────────────────

# ─── 下载 Ticket 机制（替代 URL token，防泄露/CSRF） ───
_download_tickets = {}  # {ticket_str: {'user_id': int, 'exp': float}}
_TICKET_TTL = 120  # 秒

@app.route('/api/download-ticket', methods=['POST'])
def create_download_ticket():
    """已认证用户获取短期下载ticket（2分钟有效）"""
    # 复用已有的认证逻辑：g.current_user 必须已设置
    if not hasattr(g, 'current_user') or not g.current_user:
        return jsonify({'error': '请先登录'}), 401
    ticket = secrets.token_urlsafe(32)
    _download_tickets[ticket] = {
        'user_id': g.current_user.id,
        'exp': datetime.utcnow().timestamp() + _TICKET_TTL,
    }
    # 清理过期ticket
    now = datetime.utcnow().timestamp()
    expired = [k for k, v in _download_tickets.items() if v['exp'] < now]
    for k in expired: del _download_tickets[k]
    return jsonify({'ticket': ticket})

def _validate_download_ticket(ticket_str):
    """验证下载ticket，返回 user_id 或 None"""
    entry = _download_tickets.get(ticket_str)
    if not entry: return None
    if datetime.utcnow().timestamp() > entry['exp']:
        _download_tickets.pop(ticket_str, None)
        return None
    return entry['user_id']

# 公开路由（无需登录）
PUBLIC_ROUTES = {'auth.auth_login', 'auth.auth_register', 'auth.auth_registration_status', 'get_version', 'health_check', 'index', 'serve_upload', 'export_product_template'}

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
    if not request.path.startswith('/api/'):
        return None
    # 提取路由名
    endpoint = request.endpoint
    if endpoint in PUBLIC_ROUTES or (endpoint and endpoint.startswith('static')):
        return None
    # 鉴权：优先 Bearer Token，其次 download_ticket（短期一次性）
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
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
    now = datetime.utcnow()
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

# ----- Products -----

def add_pinyin_field(p_dict):
    """给产品字典添加 _py 字段（全拼+首字母），供前端拼音搜索用。"""
    from pypinyin import pinyin, Style
    texts = [p_dict.get('name',''), p_dict.get('spec',''), p_dict.get('supplier',''), p_dict.get('function_desc','')]
    py_parts = []
    initials_parts = []
    for t in texts:
        if t:
            py_list = pinyin(t, style=Style.NORMAL, heteronym=False)
            py_parts.append(''.join(p[0] for p in py_list).lower())
            initials_parts.append(''.join(p[0][0] for p in py_list).lower())
    p_dict['_py'] = ' '.join(py_parts)
    p_dict['_py_initials'] = ' '.join(initials_parts)
    return p_dict

@app.route('/api/products', methods=['GET'])
def list_products():
    """产品列表，支持搜索（含拼音）和分类筛选"""
    import re
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    supplier = request.args.get('supplier', '').strip()

    # 排序
    sort_by = request.args.get('sort_by', 'id')
    sort_order = request.args.get('sort_order', 'desc')
    if sort_by == 'name':
        col = Product.name
    elif sort_by == 'price':
        col = Product.price
    elif sort_by == 'category':
        col = Product.category
    else:
        col = Product.id

    query = Product.query
    is_admin = hasattr(g, 'current_user') and g.current_user and g.current_user.role == 'admin'
    if not is_admin:
        # 普通用户：只看管理员创建的(None) + 自己创建的
        uid = g.current_user.id if hasattr(g, 'current_user') and g.current_user else None
        query = query.filter(
            db.or_(Product.created_by.is_(None), Product.created_by == uid)
        )
    if category:
        query = query.filter(Product.category.ilike(f'%{category}%'))
    if supplier:
        query = query.filter(Product.supplier == supplier)

    # 拼音搜索：纯ASCII（无汉字）时启用
    is_pinyin = search and not re.search(r'[\u4e00-\u9fff]', search)
    if is_pinyin:
        from pypinyin import pinyin, Style
        q_lower = search.lower().strip()
        all_products = query.order_by(col.asc() if sort_order == 'asc' else col.desc()).all()

        def pinyin_match(prod):
            """匹配产品名/规格/厂商/功能描述中的拼音"""
            texts = [prod.name, prod.spec or '', prod.supplier or '', prod.function_desc or '']
            for text in texts:
                if not text:
                    continue
                # 全拼匹配
                py_list = pinyin(text, style=Style.NORMAL, heteronym=False)
                full_py = ''.join(p[0] for p in py_list).lower()
                if q_lower in full_py:
                    return True
                # 首字母匹配
                initials = ''.join(p[0][0] for p in py_list).lower()
                if q_lower in initials:
                    return True
                # 模糊：逐字首字母子串（如 "hwsb" 匹配 "华为设备"）
                if len(q_lower) >= 2 and len(initials) >= 2:
                    if q_lower in initials:
                        return True
            return False

        filtered = [p for p in all_products if pinyin_match(p)]
        total = len(filtered)
        products = filtered[(page - 1) * per_page: page * per_page]
    else:
        query = query.order_by(col.asc() if sort_order == 'asc' else col.desc())
        if search:
            like = f'%{search}%'
            query = query.filter(
                db.or_(Product.name.ilike(like), Product.spec.ilike(like),
                        Product.supplier.ilike(like), Product.function_desc.ilike(like))
            )
        total = query.count()
        products = query.offset((page - 1) * per_page).limit(per_page).all()

    # 获取所有分类标签（支持逗号分隔的多标签）
    raw_cats = [r[0] for r in db.session.query(Product.category).filter(Product.category.isnot(None)).all() if r[0]]
    cat_set = set()
    for c in raw_cats:
        for tag in c.split(','):
            tag = tag.strip()
            if tag:
                cat_set.add(tag)
    categories = sorted(cat_set)

    suppliers_list = sorted([r[0] for r in db.session.query(Product.supplier).distinct().filter(Product.supplier.isnot(None)).all() if r[0]])
    latest = db.session.query(func.max(Product.updated_at)).scalar()
    total_all = Product.query.count()

    return jsonify({
        'products': [add_pinyin_field(p.to_dict()) for p in products],
        'total': total,
        'page': page,
        'per_page': per_page,
        'categories': sorted(categories),
        'suppliers': sorted(suppliers_list),
        'version': {'count': total_all, 'max_updated_at': latest.isoformat() if latest else None},
    })


@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': '产品名称不能为空'}), 400

    name = str(data['name']).strip()
    if not name:
        return jsonify({'error': '产品名称不能为空'}), 400
    # Reject XSS vectors in product name
    xss_patterns = ['<script', '<img', 'onerror=', 'onclick=', 'onload=', 'javascript:']
    if any(p in name.lower() for p in xss_patterns):
        return jsonify({'error': '产品名称包含非法字符'}), 400
    # Enforce 20-char limit on product name
    if len(name) > 20:
        return jsonify({'error': '产品名称不能超过20个字'}), 400

    # 规格型号统一：spec 为主，同时填充 sku
    spec = data.get('spec', '')
    product = Product(
        name=name,
        sku=spec,
        category=data.get('category', ''),
        spec=spec,
        unit=data.get('unit', ''),
        price=round(float(data.get('price', 0)), 2),
        cost_price=round(float(data.get('cost_price', 0)), 2),
        supplier=data.get('supplier', ''),
        function_desc=data.get('function_desc', ''),
        remark=data.get('remark', ''),
        image_url=data.get('image_url', ''),
        created_by=g.current_user.id if hasattr(g, 'current_user') and g.current_user else None,
    )
    _store_image_blob(product, data)
    db.session.add(product)
    db.session.commit()
    return jsonify({'product': product.to_dict()}), 201


@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({'error': '产品不存在'}), 404
    return jsonify({'product': product.to_dict()})


@app.route('/api/products/<int:product_id>/image', methods=['GET'])
@require_auth
def get_product_image(product_id):
    """返回产品图片二进制数据"""
    product = db.session.get(Product, product_id)
    if not product or not product.image_data:
        return '', 404
    return Response(product.image_data, mimetype=product.image_mime or 'image/jpeg')


@app.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({'error': '产品不存在'}), 404
    # 权限检查：管理员可编辑全部，普通用户只能编辑自己创建的
    is_admin = hasattr(g, 'current_user') and g.current_user and g.current_user.role == 'admin'
    if not is_admin and product.created_by != g.current_user.id:
        return jsonify({'error': '只能编辑自己创建的产品'}), 403
    data = request.get_json()
    for field in ['name', 'sku', 'category', 'spec', 'unit', 'supplier', 'function_desc', 'remark', 'image_url']:
        if field in data:
            val = data[field]
            if field == 'name':
                val = str(val).strip()
                if not val:
                    return jsonify({'error': '产品名称不能为空'}), 400
                xss_patterns = ['<script', '<img', 'onerror=', 'onclick=', 'onload=', 'javascript:']
                if any(p in val.lower() for p in xss_patterns):
                    return jsonify({'error': '产品名称包含非法字符'}), 400
                if len(val) > 20:
                    return jsonify({'error': '产品名称不能超过20个字'}), 400
            setattr(product, field, val)
    # 规格型号统一
    if product.spec and product.sku != product.spec:
        product.sku = product.spec
    if not product.spec and product.sku:
        product.spec = product.sku
    if 'price' in data:
        product.price = round(float(data['price']), 2)
    if 'cost_price' in data:
        product.cost_price = round(float(data['cost_price']), 2)
    _store_image_blob(product, data)
    db.session.commit()
    return jsonify({'product': product.to_dict()})


@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({'error': '产品不存在'}), 404
    # 权限检查：管理员可删除全部，普通用户只能删除自己创建的
    is_admin = hasattr(g, 'current_user') and g.current_user and g.current_user.role == 'admin'
    if not is_admin and product.created_by != g.current_user.id:
        return jsonify({'error': '只能删除自己创建的产品'}), 403
    db.session.delete(product)
    db.session.commit()
    return jsonify({'message': '已删除'})


@app.route('/api/products/batch-delete', methods=['POST'])
def batch_delete_products():
    data = request.get_json()
    ids = data.get('ids', [])
    if not ids:
        return jsonify({'error': '请选择要删除的产品'}), 400
    is_admin = hasattr(g, 'current_user') and g.current_user and g.current_user.role == 'admin'
    if not is_admin:
        # 普通用户：只允许删除自己创建的产品，过滤掉非自己的
        uid = g.current_user.id
        own_ids = [p.id for p in Product.query.filter(
            Product.id.in_(ids), Product.created_by == uid
        ).all()]
        if not own_ids:
            return jsonify({'error': '没有可以删除的产品'}), 403
        Product.query.filter(Product.id.in_(own_ids)).delete(synchronize_session=False)
        db.session.commit()
        skipped = len(ids) - len(own_ids)
        msg = f'已删除 {len(own_ids)} 个产品'
        if skipped > 0:
            msg += f'（跳过 {skipped} 个非自己创建的产品）'
        return jsonify({'message': msg})
    Product.query.filter(Product.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'message': f'已删除 {len(ids)} 个产品'})


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


@app.route('/api/upload/image', methods=['POST'])
def upload_image():
    """上传产品图片"""
    file = request.files.get('file')
    if not file:
        return jsonify({'error': '请选择图片文件'}), 400

    # 校验文件类型
    allowed = {'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp'}
    if file.content_type not in allowed and not file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')):
        return jsonify({'error': '仅支持 JPG/PNG/GIF/WebP/BMP 格式'}), 400

    # 生成文件名
    ext = os.path.splitext(file.filename)[1] if '.' in file.filename else '.jpg'
    fname = f'prod_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{random.randint(1000,9999)}{ext}'
    save_dir = UPLOAD_DIR / 'images'
    save_dir.mkdir(parents=True, exist_ok=True)
    filepath = save_dir / fname
    file.save(str(filepath))

    # 限制文件大小
    size = os.path.getsize(filepath)
    if size > 10 * 1024 * 1024:
        os.remove(filepath)
        return jsonify({'error': '图片不能超过10MB'}), 400

    # 压缩到 100KB 以内
    compressed_path, compressed_fname = compress_image_if_needed(str(filepath))
    if compressed_fname != fname:
        fname = compressed_fname

    # 返回相对URL（后面通过nginx /quote/uploads/images/ 访问）
    image_url = f'/uploads/images/{fname}'
    # 读取压缩后的图片返回 base64，方便前端直接存入 BLOB
    import base64
    with open(save_dir / fname, 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode('utf-8')
    return jsonify({'url': image_url, 'filename': fname, 'image_data': img_b64, 'image_mime': 'image/jpeg'})


@app.route('/api/download-image', methods=['POST'])
def download_image():
    """从URL下载图片并保存到本地（防SSRF）"""
    import ipaddress
    import socket
    import urllib.request
    import base64

    data = request.get_json()
    url = (data.get('url') or '').strip()
    if not url:
        return jsonify({'error': '请提供图片URL'}), 400
    # 只允许 http/https
    if not url.startswith(('http://', 'https://')):
        return jsonify({'error': '仅支持 http/https 链接'}), 400

    # ── SSRF 防护：解析域名，拒绝内网/保留IP ──
    try:
        from urllib.parse import urlparse
        hostname = urlparse(url).hostname
        if not hostname:
            return jsonify({'error': 'URL格式无效'}), 400
        resolved_ip = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for family, _, _, _, sockaddr in resolved_ip:
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return jsonify({'error': '不允许访问内网或保留地址'}), 400
    except socket.gaierror:
        return jsonify({'error': '域名解析失败'}), 400
    except Exception:
        return jsonify({'error': 'URL校验失败'}), 400

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()
            content_type = resp.headers.get('Content-Type', '')
    except Exception as e:
        return jsonify({'error': f'下载失败: {str(e)}'}), 400

    # 校验类型
    allowed_types = {'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp'}
    if content_type.split(';')[0].strip() not in allowed_types:
        return jsonify({'error': '仅支持 JPG/PNG/GIF/WebP/BMP 格式'}), 400

    # 推断扩展名
    ext_map = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/gif': '.gif',
               'image/webp': '.webp', 'image/bmp': '.bmp'}
    ext = ext_map.get(content_type.split(';')[0].strip(), '.jpg')
    # 也检查 URL 扩展名
    url_path = url.split('?')[0]
    if '.' in url_path.rsplit('/', 1)[-1]:
        url_ext = os.path.splitext(url_path.rsplit('/', 1)[-1])[1].lower()
        if url_ext in {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}:
            ext = url_ext

    fname = f'prod_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{random.randint(1000,9999)}{ext}'
    save_dir = UPLOAD_DIR / 'images'
    save_dir.mkdir(parents=True, exist_ok=True)
    filepath = save_dir / fname
    with open(filepath, 'wb') as f:
        f.write(content)

    # 压缩到 100KB 以内
    compressed_path, compressed_fname = compress_image_if_needed(str(filepath))
    if compressed_fname != fname:
        fname = compressed_fname

    image_url = f'/uploads/images/{fname}'
    # 读取压缩后的图片返回 base64，方便前端直接存入 BLOB
    import base64
    with open(save_dir / fname, 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode('utf-8')
    return jsonify({'url': image_url, 'filename': fname, 'image_data': img_b64, 'image_mime': 'image/jpeg'})


# 产品库版本信息（用于前端缓存判断）
@app.route('/api/products/version', methods=['GET'])
def products_version():
    count = Product.query.count()
    latest = db.session.query(func.max(Product.updated_at)).scalar()
    return jsonify({
        'count': count,
        'max_updated_at': latest.isoformat() if latest else None
    })


# 图片OCR识别接口（使用OCR.space免费API）
@app.route('/api/products/ocr', methods=['POST'])
def ocr_image():
    """上传图片进行OCR识别，返回识别文本"""
    file = request.files.get('file')
    if not file:
        return jsonify({'error': '请上传图片文件'}), 400

    tmp_path = UPLOAD_DIR / f'_ocr_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
    try:
        # 保存临时文件
        file.save(str(tmp_path))
        size = os.path.getsize(tmp_path)
        if size > 5 * 1024 * 1024:
            return jsonify({'error': '图片不能超过5MB'}), 400

        # 调用OCR.space免费API
        import requests as http_req
        with open(tmp_path, 'rb') as fp:
            r = http_req.post(
                'https://api.ocr.space/parse/image',
                files={'file': fp},
                data={
                    'language': 'chs',
                    'isOverlayRequired': False,
                    'detectOrientation': True,
                    'scale': True,
                    'apikey': os.environ.get('OCR_SPACE_API_KEY', 'helloworld'),
                },
                timeout=30,
            )

        if r.status_code != 200:
            return jsonify({'error': 'OCR服务暂时不可用'}), 502

        result = r.json()
        if result.get('OCRExitCode') == 1:
            text = result.get('ParsedResults', [{}])[0].get('ParsedText', '')
            return jsonify({'text': text.strip()})
        else:
            err = result.get('ErrorMessage', ['识别失败'])[0]
            return jsonify({'error': f'OCR识别失败: {err}'}), 400
    except Exception as e:
        return jsonify({'error': f'OCR处理失败: {str(e)}'}), 500
    finally:
        try: os.remove(tmp_path)
        except: pass


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
        except: pass


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


@app.route('/api/products/recognize', methods=['POST'])
def recognize_product():
    """智能识别粘贴内容（文字或图片），提取产品信息。
    每次只识别1个产品。
    图片用豆包 Vision；OCR/文字用 DeepSeek v4 Flash 解析（regex 降级）。
    请求体：{"text": "..."} 或上传 file 字段的图片
    返回：{"products": [...], "source": "...", "raw_text": "..."}
    """
    import time as _time
    _t0 = _time.time()
    _user_id = getattr(g, 'current_user', None)
    _user_id = _user_id.id if _user_id else 0

    data = request.get_json(silent=True) or {}
    uploaded_file = request.files.get('file')

    def _respond(product, source):
        raw = product.pop('_raw', '') if product else ''
        elapsed = _time.time() - _t0
        _log_ai_usage(user_id=_user_id, action='recognize', model=source, elapsed=elapsed, success=bool(product))
        return jsonify({'products': [product] if product else [], 'source': source, 'raw_text': raw[:3000]})

    text = None

    # 模式1: 图片文件上传 → 豆包 Vision
    if uploaded_file:
        tmp_path = UPLOAD_DIR / f'_smart_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
        try:
            uploaded_file.save(str(tmp_path))
            size = os.path.getsize(tmp_path)
            if size > 5 * 1024 * 1024:
                return jsonify({'error': '图片不能超过5MB'}), 400

            import base64
            with open(tmp_path, 'rb') as fp:
                image_b64 = base64.b64encode(fp.read()).decode('utf-8')

            product = doubao_vision_recognize(image_b64)
            if product:
                return _respond(product, 'doubao-vision')

            # 降级：OCR.space → DeepSeek 解析
            text = _ocr_fallback(str(tmp_path))
            if text:
                product = deepseek_parse_product(text)
                if product:
                    return _respond(product, 'deepseek-parse')
                # DeepSeek 失败 → regex 兜底
                product = smart_parse_product(text)
                if product:
                    return _respond(product, 'regex-parse')
            return jsonify({'products': [], 'error': '未能从图片中识别出产品信息，请检查图片清晰度'})
        except Exception as e:
            return jsonify({'error': f'图片处理失败: {str(e)}'}), 500
        finally:
            try: os.remove(tmp_path)
            except: pass

    # 模式2: base64图片 → 豆包 Vision
    elif data.get('image'):
        try:
            import base64
            img_data = data['image']
            if ',' in img_data:
                img_data = img_data.split(',', 1)[1]

            product = doubao_vision_recognize(img_data, mime_type=data.get('mime_type', 'image/png'))
            if product:
                return _respond(product, 'doubao-vision')
            return jsonify({'products': [], 'error': '未能从图片中识别出产品信息，请检查图片清晰度'})
        except Exception as e:
            return jsonify({'error': f'图片处理失败: {str(e)}'}), 500

    # 模式3: 纯文本 → DeepSeek 解析（regex 降级）
    elif data.get('text', '').strip():
        text = data['text'].strip()
    else:
        return jsonify({'error': '请粘贴文字或图片'}), 400

    if not text:
        return jsonify({'products': [], 'error': '未能识别出文字内容'})

    # DeepSeek v4 Flash 优先
    product = deepseek_parse_product(text)
    if product:
        return _respond(product, 'deepseek-parse')

    # regex 降级
    product = smart_parse_product(text)
    if product:
        return _respond(product, 'regex-parse')
    return jsonify({'products': [], 'error': '未能从内容中识别出产品信息，请检查粘贴内容'})


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


# ─── 发票OCR → 成本价匹配 ───
@app.route('/api/products/ocr-costs', methods=['POST'])
@require_admin
def ocr_costs():
    """上传进货发票图片，OCR识别 + 自动匹配产品成本价"""
    file = request.files.get('file')
    if not file:
        return jsonify({'error': '请上传发票图片'}), 400

    tmp_path = UPLOAD_DIR / f'_ocr_cost_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
    try:
        file.save(str(tmp_path))
        if os.path.getsize(tmp_path) > 5 * 1024 * 1024:
            return jsonify({'error': '图片不能超过5MB'}), 400

        import requests as http_req
        with open(tmp_path, 'rb') as fp:
            r = http_req.post(
                'https://api.ocr.space/parse/image',
                files={'file': fp},
                data={'language': 'chs', 'isOverlayRequired': False, 'detectOrientation': True, 'scale': True, 'apikey': os.environ.get('OCR_SPACE_API_KEY', 'helloworld')},
                timeout=30,
            )
        if r.status_code != 200:
            return jsonify({'error': 'OCR服务暂时不可用'}), 502

        result = r.json()
        if result.get('OCRExitCode') != 1:
            err = result.get('ErrorMessage', ['识别失败'])[0]
            return jsonify({'error': f'OCR失败: {err}'}), 400

        raw_text = result.get('ParsedResults', [{}])[0].get('ParsedText', '').strip()
        lines = [l.strip() for l in raw_text.split('\n') if l.strip()]

        # 解析每行：最后数字=成本价，前面=产品名
        products = Product.query.filter_by(is_active=True).all()
        matches = []
        import re
        for line in lines:
            # 找最后一个数字（可能带 ¥ 符号）
            m = re.findall(r'[¥￥]?\s*(\d+\.?\d*)\s*[元]?\s*$', line)
            if not m:
                continue
            try:
                cost_price = round(float(m[-1]), 2)
            except ValueError:
                continue
            # 去掉价格部分，剩余为产品描述
            name_part = re.sub(r'[¥￥]?\s*\d+\.?\d*\s*[元]?\s*$', '', line).strip()
            if not name_part or cost_price <= 0:
                continue

            # 模糊匹配产品
            candidates = []
            name_lower = name_part.lower()
            for p in products:
                score = 0
                p_name = (p.name or '').lower()
                p_spec = (p.spec or '').lower()
                p_supplier = (p.supplier or '').lower()
                if name_lower in p_name or p_name in name_lower:
                    score += 50
                if name_lower in p_spec or p_spec in name_lower:
                    score += 30
                if name_lower in p_supplier or p_supplier in name_lower:
                    score += 10
                # 检查空格分割的token匹配
                for token in name_lower.split():
                    if len(token) >= 2 and token in p_name:
                        score += 5
                    if len(token) >= 2 and token in p_spec:
                        score += 3
                if score > 0:
                    candidates.append({'id': p.id, 'name': p.name, 'spec': p.spec or '', 'cost_price': p.cost_price or 0, 'price': p.price or 0, 'supplier': p.supplier or '', 'score': score})
            candidates.sort(key=lambda x: -x['score'])
            matches.append({
                'line': line,
                'name_part': name_part,
                'cost_price': cost_price,
                'candidates': candidates[:3],
            })

        return jsonify({'raw_text': raw_text, 'matches': matches})

    except Exception as e:
        return jsonify({'error': f'处理失败: {str(e)}'}), 500
    finally:
        try: os.remove(tmp_path)
        except: pass


@app.route('/api/products/batch-costs', methods=['POST'])
@require_admin
def batch_update_costs():
    """批量更新产品成本价 {updates: [{id, cost_price}, ...]}"""
    data = request.get_json()
    if not data or not data.get('updates'):
        return jsonify({'error': '缺少更新数据'}), 400
    updated = 0
    for item in data['updates']:
        pid = item.get('id')
        cost = item.get('cost_price')
        if pid and cost is not None:
            product = db.session.get(Product, int(pid))
            if product:
                product.cost_price = round(float(cost), 2)
                updated += 1
    db.session.commit()
    return jsonify({'updated': updated, 'message': f'已更新{updated}个产品成本价'})


@app.route('/api/products/<int:product_id>/toggle-active', methods=['PUT'])
@require_admin
def toggle_product_active(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({'error': '产品不存在'}), 404
    product.is_active = not product.is_active
    product.updated_at = datetime.now()
    db.session.commit()
    return jsonify({'id': product.id, 'is_active': product.is_active})

@app.route('/api/products/import', methods=['POST'])
def import_products():
    """从Excel导入产品 — 支持多Sheet、自动识别分类、提取嵌入图片"""
    file = request.files.get('file')
    if not file:
        return jsonify({'error': '请上传Excel文件'}), 400

    try:
        wb = openpyxl.load_workbook(file, data_only=True)

        field_map = {
            'name': ['产品名称', '名称', '品名', 'name', 'product'],
            'sku': ['编号', 'sku', '编码', '货号', '产品编号', '料号'],
            'spec': ['规格', '型号', '规格型号', 'spec', 'model', '功能/型号'],
            'unit': ['单位', 'unit'],
            'price': ['单价', '价格', '售价', '销售价', 'price', 'unit price'],
            'cost_price': ['成本价', '成本', '进价', '采购价', 'cost'],
            'supplier': ['供应商', '厂商', 'supplier'],
            'function_desc': ['功能描述'],
            'remark': ['备注', '说明', 'remark'],
            'image_url': ['图片', 'image', 'image_url', '产品图片'],
        }

        def find_col(header, names):
            for i, h in enumerate(header):
                if not h:  # 跳过空表头
                    continue
                for n in names:
                    if n in h or h in n:
                        return i
            return -1

        def safe_float(val):
            if val is None:
                return 0
            if isinstance(val, (int, float)):
                return round(float(val) if val else 0, 2)
            try:
                return round(float(val), 2)
            except (ValueError, TypeError):
                return 0

        imported = 0
        errors = []
        total_sheets = len(wb.sheetnames)

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))
            if not rows or len(rows) < 2:
                continue

            # 检测表头行：第一行只有一个非空值(标题行)，表头在第二行
            first_nonempty = [v for v in rows[0] if v is not None and str(v).strip()]
            second_nonempty = [v for v in rows[1] if v is not None and str(v).strip()] if len(rows) > 1 else []
            header_row_idx = 0
            if len(first_nonempty) <= 2 and len(second_nonempty) >= 3:
                header_row_idx = 1

            header = [str(h).strip().lower() if h else '' for h in rows[header_row_idx]]

            col_idx = {}
            for key, names in field_map.items():
                col_idx[key] = find_col(header, names)

            # ── 智能解析：备注 vs 内部备注 vs 图片 ──
            inner_remark_col = find_col(header, ['内部备注'])
            if inner_remark_col >= 0 and col_idx.get('remark', -1) >= 0:
                # 模板同时有「备注」和「内部备注」→ 备注=图片, 内部备注=remark
                if col_idx.get('image_url', -1) < 0:
                    col_idx['image_url'] = col_idx['remark']
                col_idx['remark'] = inner_remark_col
            elif col_idx.get('image_url', -1) >= 0 and col_idx.get('remark', -1) < 0:
                pass  # 专用图片列，remark 另行处理
            elif col_idx.get('image_url', -1) < 0 and col_idx.get('remark', -1) >= 0:
                # 仅有一个备注列 → 优先检查是否含嵌入图片，无则保持为 remark
                pass

            # ── 构建嵌入图片索引 ──
            image_map = {}
            if hasattr(ws, '_images'):
                for img in ws._images:
                    try:
                        anc = img.anchor
                        if hasattr(anc, '_from'):
                            image_map[(anc._from.col, anc._from.row)] = img
                    except Exception:
                        pass

            # 没有找到名称列则跳过此sheet
            if col_idx.get('name', -1) < 0:
                continue

            # 供应商列回退：若表头未匹配到，尝试扫描数据行定位
            if col_idx.get('supplier', -1) < 0:
                data_start2 = header_row_idx + 1
                candidate_cols = [11, 12, 13]  # 常见位置（0-indexed: 12→11）
                for cc in candidate_cols:
                    if cc >= len(rows[header_row_idx]):
                        continue
                    # 检查该列在数据行中是否有非空值
                    sample_count = 0
                    for dr in rows[data_start2:data_start2+10]:
                        if dr and cc < len(dr) and dr[cc] and str(dr[cc]).strip():
                            sample_count += 1
                    if sample_count >= 2:
                        col_idx['supplier'] = cc
                        break

            data_start = header_row_idx + 1
            sheet_count = 0
            sheet_supplier = ''
            for row_idx, row in enumerate(rows[data_start:], data_start + 1):
                if all(c is None or str(c).strip() == '' for c in row):
                    continue
                first_col = str(row[0]).strip().lower() if row[0] else ''
                if first_col in ('小计', '合计', '总计', 'subtotal', 'total', '注', '备注'):
                    continue

                try:
                    name_idx = col_idx['name']
                    name = str(row[name_idx]).strip() if name_idx >= 0 and name_idx < len(row) and row[name_idx] else ''
                    if not name:
                        # 名称为空时，用规格型号作为名称
                        spec_idx = col_idx.get('spec', -1)
                        if spec_idx >= 0 and spec_idx < len(row) and row[spec_idx]:
                            name = str(row[spec_idx]).strip()
                    if not name:
                        continue

                    sup_val = str(row[col_idx['supplier']]).strip() if col_idx.get('supplier', -1) >= 0 and col_idx['supplier'] < len(row) and row[col_idx['supplier']] else ''
                    if not sup_val and sheet_supplier:
                        sup_val = sheet_supplier  # 空供应商继承上行
                    else:
                        sheet_supplier = sup_val

                    sku_val = str(row[col_idx['sku']]).strip() if col_idx.get('sku', -1) >= 0 and col_idx['sku'] < len(row) and row[col_idx['sku']] else ''
                    spec_val = str(row[col_idx['spec']]).strip() if col_idx.get('spec', -1) >= 0 and col_idx['spec'] < len(row) and row[col_idx['spec']] else ''
                    # 规格型号统一：spec 优先，无 spec 时用 sku 填充
                    if spec_val:
                        sku_val = spec_val
                    else:
                        spec_val = sku_val
                    product = Product(
                        name=name,
                        category=sheet_name,  # 用sheet名作为分类
                        sku=sku_val or spec_val,
                        spec=spec_val,
                        unit=str(row[col_idx['unit']]).strip() if col_idx.get('unit', -1) >= 0 and col_idx['unit'] < len(row) and row[col_idx['unit']] else '',
                        price=safe_float(row[col_idx['price']]) if col_idx.get('price', -1) >= 0 and col_idx['price'] < len(row) else 0,
                        cost_price=safe_float(row[col_idx['cost_price']]) if col_idx.get('cost_price', -1) >= 0 and col_idx['cost_price'] < len(row) else 0,
                        supplier=sup_val,
                        function_desc=str(row[col_idx['function_desc']]).strip() if col_idx.get('function_desc', -1) >= 0 and col_idx['function_desc'] < len(row) and row[col_idx['function_desc']] else '',
                        remark=str(row[col_idx['remark']]).strip() if col_idx.get('remark', -1) >= 0 and col_idx['remark'] < len(row) and row[col_idx['remark']] else '',
                        created_by=g.current_user.id if hasattr(g, 'current_user') and g.current_user else None,
                    )

                    # ── 提取图片：嵌入图片优先，URL 文本次之 ──
                    if col_idx.get('image_url', -1) >= 0:
                        img_col_0 = col_idx['image_url']
                        # 1) 检查嵌入图片
                        emb_img = image_map.get((img_col_0, row_idx - 1))
                        if emb_img is not None:
                            try:
                                img_bytes = emb_img._data()
                                ext = (emb_img.format or 'png').lower()
                                if ext == 'jpeg':
                                    ext = 'jpg'
                                fname = f'prod_{int(datetime.now().timestamp())}_{random.randint(1000, 9999)}.{ext}'
                                img_dir = UPLOAD_DIR / 'images'
                                img_dir.mkdir(parents=True, exist_ok=True)
                                save_path = img_dir / fname
                                save_path.write_bytes(img_bytes)
                                _, compressed_fname = compress_image_if_needed(str(save_path))
                                product.image_url = f'/uploads/images/{compressed_fname}'
                            except Exception:
                                pass
                        # 2) 没有嵌入图片时，检查 URL 文本
                        if not product.image_url and img_col_0 < len(row) and row[img_col_0]:
                            txt = str(row[img_col_0]).strip()
                            if txt and (txt.startswith('http') or txt.startswith('/uploads/')):
                                product.image_url = txt[:500]

                    _store_image_blob(product, {'image_url': product.image_url or ''})

                    db.session.add(product)
                    imported += 1
                    sheet_count += 1
                except Exception as e:
                    errors.append(f'[{sheet_name}] 第{row_idx}行: {str(e)}')

        db.session.commit()
        return jsonify({
            'message': f'成功导入 {imported} 个产品（共{total_sheets}个Sheet）',
            'imported': imported,
            'errors': errors,
        })
    except Exception as e:
        return jsonify({'error': f'导入失败: {str(e)}'}), 400


@app.route('/api/products/export-template', methods=['GET'])
def export_product_template():
    """下载原始报价规格库模板（包含所有分类Sheet）"""
    template_path = BASE_DIR / 'template.xlsx'
    if template_path.exists():
        return send_file(str(template_path), download_name='硬件报价规格库（成本）.xlsx', as_attachment=True)
    # 兜底：生成简易模板
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '产品模板'
    headers = ['序号', '名称', '规格型号', '功能/型号', '功能描述', '单价', '数量', '合计', '折扣率', '成交价', '备注', '供应商', '供应商型号', '成本', '指导价', '最低零售价', '备注']
    ws.append(headers)
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = Font(bold=True, size=11)
        cell.alignment = Alignment(horizontal='center')
    for col in range(1, 18):
        ws.column_dimensions[get_column_letter(col)].width = 15
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, download_name='产品导入模板.xlsx', as_attachment=True)


# ----- Quotes -----

@app.route('/api/quotes', methods=['GET'])
def list_quotes():
    """报价单列表，支持分页、状态筛选、关键词搜索（含拼音）"""
    import re
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 200)
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()

    query = Quote.query
    # 非管理员只看自己的报价单
    if hasattr(g, 'current_user') and g.current_user and g.current_user.role != 'admin':
        query = query.filter(Quote.created_by == g.current_user.id)
    if status_filter:
        query = query.filter(Quote.status == status_filter)

    # 拼音搜索：纯ASCII（无汉字）时启用
    is_pinyin = search and not re.search(r'[\u4e00-\u9fff]', search)
    if is_pinyin:
        from pypinyin import pinyin, Style
        q_lower = search.lower().strip()
        all_quotes = query.order_by(Quote.id.desc()).all()

        def pinyin_match(q):
            texts = [q.title or '', q.client or '']
            for text in texts:
                if not text:
                    continue
                py_list = pinyin(text, style=Style.NORMAL, heteronym=False)
                full_py = ''.join(p[0] for p in py_list).lower()
                if q_lower in full_py:
                    return True
                initials = ''.join(p[0][0] for p in py_list).lower()
                if q_lower in initials:
                    return True
                if len(q_lower) >= 2 and len(initials) >= 2:
                    if q_lower in initials:
                        return True
            return False

        filtered = [q for q in all_quotes if pinyin_match(q)]
        total = len(filtered)
        quotes = filtered[(page - 1) * per_page: page * per_page]
    else:
        query = query.order_by(Quote.id.desc())
        if search:
            like = f'%{search}%'
            query = query.filter(
                db.or_(Quote.title.ilike(like), Quote.client.ilike(like))
            )
        total = query.count()
        quotes = query.offset((page - 1) * per_page).limit(per_page).all()

    # 预加载所有创建者用户名，避免 N+1 查询
    creator_ids = list(set(q.created_by for q in quotes if q.created_by))
    users_map = {}
    if creator_ids:
        users = User.query.filter(User.id.in_(creator_ids)).all()
        users_map = {u.id: u.username for u in users}

    return jsonify({
        'quotes': [q.to_dict(users_map=users_map) for q in quotes],
        'total': total,
        'page': page,
        'per_page': per_page,
    })


@app.route('/api/quotes/stats', methods=['GET'])
def quote_stats():
    """按客户统计报价单（客户维度聚合）"""
    qf = Quote.client.isnot(None), Quote.client != ''
    if hasattr(g, 'current_user') and g.current_user and g.current_user.role != 'admin':
        qf = qf + (Quote.created_by == g.current_user.id,)
    rows = db.session.query(
        Quote.client, Quote.id, Quote.title, Quote.total_amount,
        Quote.status, Quote.quote_date, Quote.download_count
    ).filter(*qf)\
     .order_by(Quote.client, Quote.id.desc()).all()

    customers = {}
    for client, qid, title, amt, status, qdate, dl in rows:
        if client not in customers:
            customers[client] = {'client': client, 'quotes': [], 'total_amount': 0, 'quote_count': 0}
        customers[client]['quotes'].append({
            'id': qid, 'title': title, 'total_amount': amt or 0,
            'status': status, 'quote_date': qdate, 'download_count': dl or 0
        })
        customers[client]['total_amount'] += (amt or 0)
        customers[client]['quote_count'] += 1

    return jsonify({'customers': sorted(customers.values(), key=lambda x: x['total_amount'], reverse=True)})


@app.route('/api/quotes/<int:quote_id>/status', methods=['PATCH'])
def update_quote_status(quote_id):
    """修改报价单状态"""
    quote, err, status = check_quote_owner(quote_id)
    if not quote:
        return err, status
    data = request.get_json()
    new_status = data.get('status', '')
    valid_statuses = ['draft', 'sent', 'confirmed', 'rejected', 'expired']
    if new_status not in valid_statuses:
        return jsonify({'error': f'无效状态，可选: {valid_statuses}'}), 400
    quote.status = new_status
    db.session.commit()
    return jsonify({'quote': quote.to_dict()})


@app.route('/api/quotes', methods=['POST'])
def create_quote():
    data = request.get_json()
    if not data:
        return jsonify({'error': '缺少数据'}), 400

    quote = Quote(
        title=data.get('title', ''),
        client=data.get('client', ''),
        contact=data.get('contact', ''),
        phone=data.get('phone', ''),
        quote_date=data.get('quote_date', datetime.now().strftime('%Y-%m-%d')),
        valid_days=int(data.get('valid_days', 15)),
        tax_rate=round(float(data.get('tax_rate', 0)), 2),
        remark=data.get('remark', ''),
        created_by=g.current_user.id if hasattr(g, 'current_user') and g.current_user else None,
    )

    items_data = data.get('items', [])
    total = 0
    # 预加载产品信息以填充 name/spec/unit/sku
    pids = [it.get('product_id') for it in items_data if it.get('product_id')]
    pmap = {}
    if pids:
        products = Product.query.filter(Product.id.in_(pids)).all()
        pmap = {p.id: p for p in products}
    for i, item in enumerate(items_data):
        qty = int(item.get('quantity', 1))
        up = round(float(item.get('unit_price', 0)), 2)
        amt = round(qty * up, 2)
        pid = item.get('product_id')
        prod = pmap.get(pid) if pid else None
        qi = QuoteItem(
            product_id=pid,
            product_name=item.get('product_name') or (prod.name if prod else ''),
            product_sku=item.get('product_sku') or (prod.sku if prod else ''),
            product_spec=item.get('product_spec') or (prod.spec if prod else ''),
            product_unit=item.get('product_unit') or (prod.unit if prod else ''),
            quantity=qty,
            unit_price=up,
            amount=amt,
            remark=item.get('remark', ''),
            sort_order=i,
        )
        quote.items.append(qi)
        total += amt

    quote.total_amount = round(total, 2)
    db.session.add(quote)
    db.session.commit()
    return jsonify({'quote': quote.to_dict()}), 201


@app.route('/api/quotes/<int:quote_id>', methods=['GET'])
def get_quote(quote_id):
    quote, err, status = check_quote_owner(quote_id)
    if not quote:
        return err, status
    pmap = preload_products_for_quote(quote)
    return jsonify({'quote': quote.to_dict(pmap)})


@app.route('/api/quotes/<int:quote_id>', methods=['PUT'])
def update_quote(quote_id):
    quote, err, status = check_quote_owner(quote_id)
    if not quote:
        return err, status
    data = request.get_json()
    if data.get('title') is not None: quote.title = data['title']
    if data.get('client') is not None: quote.client = data['client']
    if data.get('contact') is not None: quote.contact = data['contact']
    if data.get('phone') is not None: quote.phone = data['phone']
    if data.get('quote_date') is not None: quote.quote_date = data['quote_date']
    if data.get('valid_days') is not None: quote.valid_days = int(data['valid_days'])
    if data.get('tax_rate') is not None: quote.tax_rate = round(float(data['tax_rate']), 2)
    if data.get('remark') is not None: quote.remark = data['remark']
    if data.get('status') is not None: quote.status = data['status']

    if 'items' in data:
        QuoteItem.query.filter_by(quote_id=quote_id).delete()
        total = 0
        # 预加载产品信息以填充 name/spec/unit/sku
        pids = [it.get('product_id') for it in data['items'] if it.get('product_id')]
        pmap = {}
        if pids:
            products = Product.query.filter(Product.id.in_(pids)).all()
            pmap = {p.id: p for p in products}
        for i, item in enumerate(data['items']):
            qty = int(item.get('quantity', 1))
            up = round(float(item.get('unit_price', 0)), 2)
            amt = round(qty * up, 2)
            pid = item.get('product_id')
            prod = pmap.get(pid) if pid else None
            qi = QuoteItem(
                quote_id=quote_id,
                product_id=pid,
                product_name=item.get('product_name') or (prod.name if prod else ''),
                product_sku=item.get('product_sku') or (prod.sku if prod else ''),
                product_spec=item.get('product_spec') or (prod.spec if prod else ''),
                product_unit=item.get('product_unit') or (prod.unit if prod else ''),
                quantity=qty,
                unit_price=up,
                amount=amt,
                remark=item.get('remark', ''),
                sort_order=i,
            )
            db.session.add(qi)
            total += amt
        quote.total_amount = round(total, 2)

    db.session.commit()
    return jsonify({'quote': quote.to_dict()})


@app.route('/api/quotes/<int:quote_id>', methods=['DELETE'])
def delete_quote(quote_id):
    quote, err, status = check_quote_owner(quote_id)
    if not quote:
        return err, status
    db.session.delete(quote)
    db.session.commit()
    return jsonify({'message': '已删除'})


@app.route('/api/quotes/batch', methods=['DELETE'])
@require_auth
def batch_delete_quotes():
    """批量删除报价单（仅限自己创建的或管理员删除全部）"""
    data = request.get_json(silent=True) or {}
    ids = data.get('ids', [])
    if not isinstance(ids, list) or not ids:
        return jsonify({'error': '请提供要删除的报价单 ID 列表'}), 400
    if len(ids) > 100:
        return jsonify({'error': '单次最多删除 100 条'}), 400

    user = g.current_user
    is_admin = user.role == 'admin'

    quotes = Quote.query.filter(Quote.id.in_(ids)).all()
    deletable = []
    forbidden = []
    for q in quotes:
        if is_admin or q.created_by == user.id:
            deletable.append(q)
        else:
            forbidden.append(q.id)

    for q in deletable:
        db.session.delete(q)
    db.session.commit()

    return jsonify({
        'deleted': len(deletable),
        'total': len(ids),
        'forbidden': forbidden,
    })


@app.route('/api/quotes/<int:quote_id>/export-excel', methods=['GET'])
def export_quote_excel(quote_id):
    """导出报价单 — 样式精确克隆模板.xlsx"""
    quote, err, status = check_quote_owner(quote_id)
    if not quote:
        return err, status

    # 记录下载次数
    quote.download_count = (quote.download_count or 0) + 1
    db.session.commit()

    pmap = preload_products_for_quote(quote)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = quote.title or '报价单'

    # ── 样式（精确匹配模板） ──
    YELLOW_FILL = PatternFill(start_color='FFFF00', end_color='FFFF00', fill_type='solid')
    title_font = Font(name='微软雅黑', size=10, bold=True)
    header_font = Font(name='微软雅黑', size=10, bold=True)
    data_font = Font(name='微软雅黑', size=11, bold=True)
    total_font = Font(name='微软雅黑', size=10, bold=True)
    note_font = Font(name='微软雅黑', size=10, bold=False)

    thin = Side(style='thin')
    thin_border = Border(left=thin, right=thin, top=thin, bottom=thin)

    ca = Alignment(horizontal='center', vertical='center', wrap_text=True)
    money_fmt = '#,##0.00'
    pct_fmt = '0%'

    # ── 列宽（精确匹配模板） ──
    col_widths = [9.66, 27.16, 18.83, 20.16, 60.16, 13.33, 7.5, 11.33, 6.5, 12.16, 18.16, 16.0]
    headers = ['序号', '名称', '规格型号', '型号', '功能描述', '单价', '数量', '合计', '折扣率', '成交价', '备注', '图片']
    COL_COUNT = len(headers)

    for ci, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(ci)].width = w

    # ── 第1行：公司名 + 客户信息 ──
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=COL_COUNT)
    company = get_setting('company_name', '').strip()
    parts = [f'公司：{company}'] if company else []
    if quote.client: parts.append(f'客户：{quote.client}')
    if quote.contact: parts.append(f'联系人：{quote.contact}')
    if quote.phone: parts.append(f'电话：{quote.phone}')
    if quote.tax_rate and quote.tax_rate > 0: parts.append(f'税率：{quote.tax_rate}%')
    if quote.quote_date: parts.append(f'日期：{quote.quote_date}')
    info = '  |  '.join(parts) if parts else ''
    c1 = ws.cell(row=1, column=1, value=info)
    c1.font = Font(name='微软雅黑', size=9, color='666666')
    c1.alignment = Alignment(horizontal='left', vertical='center')
    for ci in range(1, COL_COUNT + 1):
        ws.cell(row=1, column=ci).border = thin_border
    ws.row_dimensions[1].height = 17

    # ── 第2行：黄色标题 ──
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=COL_COUNT)
    t = ws.cell(row=2, column=1, value=quote.title or '报价单')
    t.font = title_font; t.fill = YELLOW_FILL; t.alignment = ca
    for ci in range(1, COL_COUNT + 1):
        ws.cell(row=2, column=ci).border = thin_border
    ws.row_dimensions[2].height = 18

    # ── 第3行：表头 ──
    HEAD = 3
    ws.row_dimensions[HEAD].height = 17
    for ci, h in enumerate(headers, 1):
        cell = ws.cell(row=HEAD, column=ci, value=h)
        cell.font = header_font; cell.alignment = ca
        cell.border = thin_border
    ws.cell(row=HEAD, column=1).border = thin_border
    ws.cell(row=HEAD, column=COL_COUNT).border = thin_border

    # ── 数据行 ──
    row = HEAD
    for i, item in enumerate(quote.items, 1):
        row += 1
        ws.row_dimensions[row].height = 54

        qty = item.quantity if item.quantity else 1
        up = item.unit_price if item.unit_price else 0
        subtotal = round(qty * up, 2)

        # 取产品 function_desc 作为功能描述
        product_function_desc = ''
        image_url = None
        if item.product_id:
            product = pmap.get(item.product_id)
            if product:
                product_function_desc = product.function_desc or ''
                image_url = product.image_url

        desc = product_function_desc

        vals = [i, item.product_name, item.product_spec or '',
                item.product_spec or item.product_sku or '', desc,
                up, qty, subtotal, 0, subtotal, item.remark or '', '']

        for ci, val in enumerate(vals, 1):
            cell = ws.cell(row=row, column=ci, value=val)
            cell.font = data_font; cell.alignment = ca; cell.border = thin_border
            if ci in (6, 8, 10): cell.number_format = money_fmt
            elif ci == 9: cell.number_format = pct_fmt

        ws.cell(row=row, column=1).border = thin_border
        ws.cell(row=row, column=COL_COUNT).border = thin_border

        # 嵌入产品图片到图片列（L列）— 从 BLOB 读取
        if image_url:
            try:
                img_bytes = None
                if product and hasattr(product, 'image_data') and product.image_data:
                    img_bytes = product.image_data
                if not img_bytes:
                    img_path = BASE_DIR / image_url.lstrip('/')
                    if img_path.exists():
                        img_bytes = img_path.read_bytes()
                if img_bytes:
                    img = XLImage(io.BytesIO(img_bytes))
                    # 限制尺寸适配图片列：宽≈80px, 高≤48px
                    w, h = img.width, img.height
                    max_w, max_h = 80, 48
                    ratio = min(max_w / w, max_h / h, 1)
                    img.width = int(w * ratio)
                    img.height = int(h * ratio)
                    # 图片单元格内居中
                    col_l = get_column_letter(12)
                    col_w_px = (ws.column_dimensions[col_l].width or 10) * 7
                    row_h_pt = ws.row_dimensions[row].height or 60
                    x_emu = int(max(0, (col_w_px - img.width) / 2) * 9525)
                    y_emu = int(max(0, (row_h_pt - img.height) / 2) * 9525)
                    img.anchor = TwoCellAnchor(
                        _from=AnchorMarker(col=11, colOff=x_emu, row=row-1, rowOff=y_emu),
                        to=AnchorMarker(col=11, colOff=x_emu + img.width * 9525, row=row-1, rowOff=y_emu + img.height * 9525)
                    )
                    ws.add_image(img)
            except Exception:
                pass

    # ── 合计行 ──
    row += 1
    ws.row_dimensions[row].height = 22
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=10)

    total_amt = quote.total_amount or 0
    tlabel = ws.cell(row=row, column=1, value=f'合计（大写）：{number_to_cn(total_amt)}')
    tlabel.font = total_font
    tlabel.alignment = Alignment(horizontal='right', vertical='center')
    tlabel.border = thin_border

    for ci in range(2, 11):
        c = ws.cell(row=row, column=ci)
        c.font = total_font; c.border = thin_border

    tc = ws.cell(row=row, column=11, value=total_amt)
    tc.font = total_font; tc.number_format = money_fmt; tc.alignment = ca
    tc.border = thin_border

    ws.cell(row=row, column=12).border = thin_border
    ws.cell(row=row, column=12).font = total_font

    # ── 备注行 ──
    row += 1
    ws.row_dimensions[row].height = 18
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=COL_COUNT)
    nc = ws.cell(row=row, column=1, value=quote.remark or '注：硬件默认自验收日起维保1年，硬件1年内享受免费寄修服务。')
    nc.font = note_font
    nc.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
    for ci in range(1, COL_COUNT + 1):
        ws.cell(row=row, column=ci).border = thin_border

    # ── 页脚行（公司自定义） ──
    footer = get_setting('footer_text', '').strip()
    if footer:
        row += 1
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=COL_COUNT)
        fc = ws.cell(row=row, column=1, value=footer)
        fc.font = Font(name='微软雅黑', size=9, color='888888')
        fc.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
        ws.row_dimensions[row].height = 30
        for ci in range(1, COL_COUNT + 1):
            ws.cell(row=row, column=ci).border = Border()

    # ── 打印：纵向 ──
    ws.page_setup.orientation = 'portrait'
    ws.page_setup.fitToWidth = 1
    ws.page_margins.left = 0.4; ws.page_margins.right = 0.4

    filepath = EXPORT_DIR / f'报价单_{quote.id}.xlsx'
    wb.save(filepath)
    # 优先使用前端传来的浏览器本地日期，兜底用服务器日期
    download_date = request.args.get('download_date', '').strip()
    if download_date:
        date_str = download_date
    else:
        date_str = datetime.now().strftime('%Y%m%d')
    dl_name = f'{quote.client or ""}_{quote.title or ""}_{quote.contact or ""}_{date_str}'.strip('_').replace(' ','') + '.xlsx'

    # 记录下载日志
    user_name = g.current_user.username if hasattr(g, 'current_user') and g.current_user else request.args.get('user_name', '').strip()
    if user_name:
        log = DownloadLog(quote_id=quote_id, user_name=user_name)
        db.session.add(log)
        db.session.commit()

    return send_file(str(filepath), download_name=dl_name, as_attachment=True)


# ─── 邮件发送 (v1.4.0) ───
@app.route('/api/quotes/<int:quote_id>/send-email', methods=['POST'])
def send_quote_email(quote_id):
    quote, err, status = check_quote_owner(quote_id)
    if not quote:
        return err, status
    data = request.get_json(silent=True) or {}
    to_email = data.get('to_email', '').strip()
    if not to_email:
        return jsonify({'error': '请填写收件人邮箱'}), 400
    subject = data.get('subject', '').strip()
    body_text = data.get('body', '').strip()
    smtp_host = get_setting('smtp_host', '')
    if not smtp_host:
        return jsonify({'error': 'SMTP未配置'}), 400
    smtp_port = int(get_setting('smtp_port', '587'))
    smtp_user = get_setting('smtp_user', '')
    smtp_password = get_setting('smtp_password', '')
    smtp_from = get_setting('smtp_from', smtp_user)
    smtp_use_tls = get_setting('smtp_use_tls', 'true').lower() == 'true'

    # 生成附件
    filepath = EXPORT_DIR / f'报价单_{quote_id}.xlsx'
    pmap = preload_products_for_quote(quote)
    _build_excel(quote, pmap, str(filepath))

    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders
    msg = MIMEMultipart()
    msg['From'] = smtp_from
    msg['To'] = to_email
    msg['Subject'] = subject or f'{quote.title or quote.client or ""}'
    msg.attach(MIMEText(body_text or f'{quote.title or ""}\n{quote.client or ""}\n{quote.quote_date or ""}', 'plain', 'utf-8'))
    with open(filepath, 'rb') as f:
        part = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment', filename=f'{quote.client or ""}_{quote.title or ""}.xlsx')
        msg.attach(part)
    try:
        if smtp_use_tls:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()
        return jsonify({'success': True, 'message': f'{to_email}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _build_excel(quote, pmap, filepath):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = quote.title or ''
    YELLOW_FILL = PatternFill(start_color='FFFF00', end_color='FFFF00', fill_type='solid')
    title_font = Font(name='微软雅黑', size=10, bold=True)
    header_font = Font(name='微软雅黑', size=10, bold=True)
    data_font = Font(name='微软雅黑', size=11, bold=True)
    total_font = Font(name='微软雅黑', size=10, bold=True)
    note_font = Font(name='微软雅黑', size=10, bold=False)
    thin = Side(style='thin')
    thin_border = Border(left=thin, right=thin, top=thin, bottom=thin)
    ca = Alignment(horizontal='center', vertical='center', wrap_text=True)
    money_fmt = '#,##0.00'
    col_widths = [9.66, 27.16, 18.83, 20.16, 60.16, 13.33, 7.5, 11.33, 6.5, 12.16, 18.16, 16.0]
    headers = ['序号', '名称', '规格型号', '型号', '功能描述', '单价', '数量', '合计', '折扣率', '成交价', '备注', '图片']
    COL_COUNT = len(headers)
    for ci, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(ci)].width = w
    # ── 第1行：公司名 + 客户信息 ──
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=COL_COUNT)
    company = get_setting('company_name', '').strip()
    parts = [f'公司：{company}'] if company else []
    if quote.client: parts.append(f'客户：{quote.client}')
    if quote.contact: parts.append(f'联系人：{quote.contact}')
    if quote.phone: parts.append(f'电话：{quote.phone}')
    if quote.tax_rate and quote.tax_rate > 0: parts.append(f'税率：{quote.tax_rate}%')
    if quote.quote_date: parts.append(f'日期：{quote.quote_date}')
    info = '  |  '.join(parts) if parts else ''
    c1 = ws.cell(row=1, column=1, value=info)
    c1.font = Font(name='微软雅黑', size=9, color='666666'); c1.alignment = Alignment(horizontal='left', vertical='center')
    for ci in range(1, COL_COUNT + 1):
        ws.cell(row=1, column=ci).border = thin_border
    ws.row_dimensions[1].height = 17
    # ── 第2行：黄色标题 ──
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=COL_COUNT)
    t = ws.cell(row=2, column=1, value=quote.title or '')
    t.font = title_font; t.fill = YELLOW_FILL; t.alignment = ca
    for ci in range(1, COL_COUNT + 1):
        ws.cell(row=2, column=ci).border = thin_border
    ws.row_dimensions[2].height = 18
    HEAD = 3
    ws.row_dimensions[HEAD].height = 17
    for ci, h in enumerate(headers, 1):
        cell = ws.cell(row=HEAD, column=ci, value=h)
        cell.font = header_font; cell.alignment = ca; cell.border = thin_border
    row = HEAD
    for i, item in enumerate(quote.items, 1):
        row += 1
        ws.row_dimensions[row].height = 54
        qty = item.quantity if item.quantity else 1
        up = item.unit_price if item.unit_price else 0
        subtotal = round(qty * up, 2)
        product_function_desc = ''; image_url = ''
        if item.product_id:
            product = pmap.get(item.product_id)
            if product:
                product_function_desc = product.function_desc or ''
                image_url = product.image_url
        vals = [i, item.product_name, item.product_spec or '', item.product_spec or item.product_sku or '', product_function_desc, up, qty, subtotal, 0, subtotal, item.remark or '', '']
        for ci, val in enumerate(vals, 1):
            cell = ws.cell(row=row, column=ci, value=val)
            cell.font = data_font; cell.alignment = ca; cell.border = thin_border
        # 嵌入产品图片到图片列（L列）— 从 BLOB 读取
        if image_url:
            try:
                img_bytes = None
                if product and hasattr(product, 'image_data') and product.image_data:
                    img_bytes = product.image_data
                if not img_bytes:
                    img_path = BASE_DIR / image_url.lstrip('/')
                    if img_path.exists():
                        img_bytes = img_path.read_bytes()
                if img_bytes:
                    img = XLImage(io.BytesIO(img_bytes))
                    w, h = img.width, img.height
                    max_w, max_h = 80, 48
                    ratio = min(max_w / w, max_h / h, 1)
                    img.width = int(w * ratio)
                    img.height = int(h * ratio)
                    # 图片单元格内居中
                    col_l = get_column_letter(12)
                    col_w_px = (ws.column_dimensions[col_l].width or 10) * 7
                    row_h_pt = ws.row_dimensions[row].height or 60
                    x_emu = int(max(0, (col_w_px - img.width) / 2) * 9525)
                    y_emu = int(max(0, (row_h_pt - img.height) / 2) * 9525)
                    img.anchor = TwoCellAnchor(
                        _from=AnchorMarker(col=11, colOff=x_emu, row=row-1, rowOff=y_emu),
                        to=AnchorMarker(col=11, colOff=x_emu + img.width * 9525, row=row-1, rowOff=y_emu + img.height * 9525)
                    )
                    ws.add_image(img)
            except Exception:
                pass
    row += 1
    ws.row_dimensions[row].height = 22
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=10)
    total_amt = quote.total_amount or 0
    tlabel = ws.cell(row=row, column=1, value=f'合计（大写）：{number_to_cn(total_amt)}')
    tlabel.font = total_font; tlabel.alignment = Alignment(horizontal='right', vertical='center'); tlabel.border = thin_border
    for ci in range(2, 11):
        c = ws.cell(row=row, column=ci); c.font = total_font; c.border = thin_border
    tc = ws.cell(row=row, column=11, value=total_amt)
    tc.font = total_font; tc.number_format = money_fmt; tc.alignment = ca; tc.border = thin_border
    ws.cell(row=row, column=12).border = thin_border; ws.cell(row=row, column=12).font = total_font
    row += 1
    ws.row_dimensions[row].height = 18
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=COL_COUNT)
    nc = ws.cell(row=row, column=1, value=quote.remark or '注：硬件默认自验收日起维保1年，硬件1年内享受免费寄修服务。')
    nc.font = note_font; nc.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
    for ci in range(1, COL_COUNT + 1):
        ws.cell(row=row, column=ci).border = thin_border
    footer = get_setting('footer_text', '').strip()
    if footer:
        row += 1
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=COL_COUNT)
        fc = ws.cell(row=row, column=1, value=footer)
        fc.font = Font(name='微软雅黑', size=9, color='888888')
        fc.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
        ws.row_dimensions[row].height = 30
        for ci in range(1, COL_COUNT + 1):
            ws.cell(row=row, column=ci).border = Border()
    wb.save(filepath)


# ─── 下载日志 API ───
@app.route('/api/download-logs', methods=['GET'])
def list_download_logs():
    logs = DownloadLog.query.order_by(DownloadLog.downloaded_at.desc()).limit(200).all()
    return jsonify({'logs': [log.to_dict() for log in logs]})


@app.route('/api/download-logs/stats', methods=['GET'])
def download_logs_stats():
    """按用户汇总下载次数"""
    rows = db.session.query(
        DownloadLog.user_name, func.count(DownloadLog.id)
    ).group_by(DownloadLog.user_name).order_by(func.count(DownloadLog.id).desc()).all()
    return jsonify({'users': [{'user_name': name, 'count': cnt} for name, cnt in rows]})


# ─── 报价单 HTML 预览 ───
@app.route('/api/quotes/<int:quote_id>/preview', methods=['GET'])
def preview_quote_html(quote_id):
    """返回报价单的HTML预览（17列格式匹配原模板）"""
    import html as _html  # 用于转义用户输入防XSS

    quote, err, status = check_quote_owner(quote_id)
    if not quote:
        return err, status

    pmap = preload_products_for_quote(quote)

    def fmt(n):
        if n is None: return '0.00'
        return f'{n:,.2f}'

    def fmt_int(n):
        if n is None: return ''
        try: return f'{int(float(n))}'
        except: return str(n)

    def e(s):
        """html.escape shorthand — 防止用户输入中的HTML/JS注入"""
        return _html.escape(str(s)) if s else ''

    info_parts = []
    company = get_setting('company_name', '').strip()
    if company: info_parts.append(f'公司：{e(company)}')
    if quote.client: info_parts.append(f'客户：{e(quote.client)}')
    if quote.contact: info_parts.append(f'联系人：{e(quote.contact)}')
    if quote.phone: info_parts.append(f'电话：{e(quote.phone)}')
    if quote.quote_date: info_parts.append(f'日期：{e(quote.quote_date)}')
    if quote.valid_days: info_parts.append(f'有效期：{quote.valid_days}天')
    if quote.tax_rate and quote.tax_rate > 0: info_parts.append(f'税率：{quote.tax_rate}%')
    info_line = '  |  '.join(info_parts) if info_parts else ''

    items_html = ''
    for i, item in enumerate(quote.items, 1):
        supplier = ''; supplier_sku = ''; cost = 0; prod_function_desc = ''; image_url = ''
        if item.product_id:
            prod = pmap.get(item.product_id)
            if prod:
                supplier = prod.supplier or ''
                supplier_sku = prod.spec or prod.sku or ''
                cost = prod.cost_price or 0
                prod_function_desc = prod.function_desc or ''
                image_url = prod.image_url or ''

        qty = item.quantity if item.quantity else 1
        up = item.unit_price if item.unit_price else 0
        subtotal = round(qty * up, 2)
        deal_price = subtotal
        guide_price = round(cost * 1.5, 2) if cost else 0
        min_retail = round(cost * 1.15, 2) if cost else 0

        # 图片列：使用 /api/products/<id>/image 端点
        img_cell = ''
        if image_url:
            src = f'/quote/api/products/{item.product_id}/image'
            img_cell = f'<img src="{src}" style="max-width:100px;max-height:48px;object-fit:contain;display:block;margin:0 auto">'
        else:
            img_cell = '—'

        items_html += f'''
        <tr>
            <td>{i}</td>
            <td><strong>{e(item.product_name)}</strong></td>
            <td>{e(item.product_spec or '')}</td>
            <td>{e(item.product_sku or supplier_sku)}</td>
            <td>{e(prod_function_desc or '')}</td>
            <td>{fmt(up)}</td>
            <td>{fmt_int(qty)}</td>
            <td>{fmt(subtotal)}</td>
            <td>0%</td>
            <td>{fmt(deal_price)}</td>
            <td>{e(item.remark or '')}</td>
            <td style="text-align:center;vertical-align:middle">{img_cell}</td>
        </tr>'''

    html = f'''<style>
.pv-table{{width:100%;border-collapse:collapse;font-size:11pt;font-weight:bold}}
.pv-table th{{font-size:10pt;font-weight:bold;padding:3px 2px;border:1px solid #ccc;text-align:center;background:#fff}}
.pv-table td{{padding:3px 2px;border:1px solid #ccc;vertical-align:middle;text-align:center}}
.pv-table td:first-child{{border-left:1px solid #ccc}}
.pv-table td:last-child{{border-right:1px solid #ccc}}
.pv-table tr:hover td{{background:#fffbe6}}
.pv-table .total-row td{{font-size:10pt;font-weight:bold;border-top:1px solid #ccc;border-bottom:1px solid #ccc;padding:4px 2px;background:#fafafa}}
.pv-table .total-row td:first-child{{border-left:1px solid #ccc}}
.pv-table .total-row td:last-child{{border-right:1px solid #ccc}}
.pv-table .total-amount{{font-size:10pt}}
.pv-note{{font-size:10pt;padding:3px 8px;border:1px solid #ccc;border-top:none}}
</style>
<div style="overflow-x:auto">
<table class="pv-table">
  <thead>
    <tr>
      <td colspan="12" style="font-size:9pt;color:#666;padding:4px 8px;text-align:left;font-weight:normal">{info_line}</td>
    </tr>
    <tr>
      <th colspan="12" style="background:#FFFF00;font-size:10pt;font-weight:bold;text-align:center;padding:4px">{e(quote.title or '报价单')}</th>
    </tr>
    <tr>
      <th style="width:50px">序号</th>
      <th style="width:170px">名称</th>
      <th style="width:100px">规格型号</th>
      <th style="width:110px">型号</th>
      <th style="width:300px">功能描述</th>
      <th style="width:75px">单价</th>
      <th style="width:45px">数量</th>
      <th style="width:70px">合计</th>
      <th style="width:42px">折扣率</th>
      <th style="width:75px">成交价</th>
      <th style="width:90px">备注</th>
      <th style="width:80px">图片</th>
    </tr>
  </thead>
  <tbody>
    {items_html}
  </tbody>
  <tfoot>
    <tr class="total-row">
      <td colspan="11" style="text-align:right">合计（大写）：<strong>{number_to_cn(quote.total_amount or 0)}</strong></td>
      <td class="total-amount">¥{fmt(quote.total_amount or 0)}</td>
    </tr>
  </tfoot>
</table>
</div>
<div class="pv-note">{e(quote.remark or '注：硬件默认自验收日起维保1年，硬件1年内享受免费寄修服务。')}</div>'''
    return html


CN_NUM = ['零', '壹', '贰', '叁', '肆', '伍', '陆', '柒', '捌', '玖']
CN_UNIT = ['', '拾', '佰', '仟']
CN_BIG_UNIT = ['', '万', '亿', '万亿']


def number_to_cn(num):
    """数字转中文大写金额"""
    if num == 0:
        return '零圆整'
    # 只处理整数部分
    num = int(num)
    if num < 0:
        return '负数'

    def _section(n):
        result = ''
        for i in range(4):
            digit = n % 10
            if digit != 0:
                result = CN_NUM[digit] + CN_UNIT[i] + result
            else:
                if result and result[0] != '零':
                    result = '零' + result
            n //= 10
        # 去掉开头多余的零
        while result.startswith('零'):
            result = result[1:]
        return result

    if num == 0:
        return '零圆整'

    result = ''
    unit_idx = 0
    while num > 0:
        section = num % 10000
        if section != 0:
            section_str = _section(section)
            if unit_idx > 0 and section < 1000:
                section_str = '零' + section_str
            result = section_str + CN_BIG_UNIT[unit_idx] + result
        elif result and result[0] not in ('零', '万', '亿'):
            # 中间有零
            pass
        num //= 10000
        unit_idx += 1

    # 处理连续的零
    while '零零' in result:
        result = result.replace('零零', '零')
    if result.endswith('零'):
        result = result[:-1]

    return result + '圆整'


# ─── AI Token ────────────────

@app.route('/api/ai/token', methods=['GET'])
@require_auth
def ai_token():
    """AI 助手获取当前用户的 JWT token（用于 API 操作）。"""
    token = create_token(g.current_user, app)
    return jsonify({'token': token, 'username': g.current_user.username, 'user_id': g.current_user.id})


# ─── AI Chat (通过 Hermes Gateway Responses API + SSE 流式) ─────

_ai_model = os.environ.get('QUOTE_AI_MODEL', 'deepseek-v4-pro')

# Hermes Gateway API Server（一个端口，通过 model 字段区分模型）
_gateway_url = os.environ.get('QUOTE_GATEWAY_URL', 'http://127.0.0.1:8643')

_AVAILABLE_MODELS = [
    {'id': 'deepseek-v4-pro', 'name': 'DeepSeek V4 Pro', 'desc': '深度推理，适合复杂分析'},
    {'id': 'deepseek-v4-flash', 'name': 'DeepSeek V4 Flash', 'desc': '快速响应，适合日常问答'},
]


@app.route('/api/chat/models', methods=['GET'])
def get_chat_models():
    """返回可用 AI 模型列表"""
    return jsonify({'models': _AVAILABLE_MODELS, 'default': _ai_model})


@app.route('/api/admin/ai-usage', methods=['GET'])
@require_admin
def ai_usage_stats():
    """AI 使用统计 — 管理员查看"""
    from sqlalchemy import func
    days = min(int(request.args.get('days', 7)), 90)
    since = datetime.now() - __import__('datetime').timedelta(days=days)

    # 总览
    total = AIUsageLog.query.filter(AIUsageLog.created_at >= since).count()
    success = AIUsageLog.query.filter(AIUsageLog.created_at >= since, AIUsageLog.success == True).count()
    avg_elapsed = db.session.query(func.avg(AIUsageLog.elapsed)).filter(
        AIUsageLog.created_at >= since, AIUsageLog.success == True
    ).scalar() or 0

    # 按 action 分组
    by_action = db.session.query(
        AIUsageLog.action, func.count(), func.avg(AIUsageLog.elapsed)
    ).filter(AIUsageLog.created_at >= since).group_by(AIUsageLog.action).all()

    # 按用户分组 (Top 10)
    by_user = db.session.query(
        AIUsageLog.user_id, User.username, func.count()
    ).join(User, AIUsageLog.user_id == User.id).filter(
        AIUsageLog.created_at >= since
    ).group_by(AIUsageLog.user_id, User.username).order_by(func.count().desc()).limit(10).all()

    # 按日期分组
    by_date = db.session.query(
        func.date(AIUsageLog.created_at), func.count(),
        func.avg(AIUsageLog.elapsed)
    ).filter(AIUsageLog.created_at >= since).group_by(
        func.date(AIUsageLog.created_at)
    ).order_by(func.date(AIUsageLog.created_at).desc()).limit(days).all()

    # 最近50条明细
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


@app.route('/api/ai/my-usage', methods=['GET'])
@require_auth
def my_ai_usage():
    """当前用户的AI使用次数（首页卡片用）"""
    from sqlalchemy import func
    my_count = AIUsageLog.query.filter_by(user_id=g.current_user.id).count()
    total_count = AIUsageLog.query.count()
    return jsonify({'my_count': my_count, 'total_count': total_count})


_GW_SYSTEM_PROMPT = (
    '你是报价管理系统（/opt/quote-system）的 AI 助手。'
    '你可以用工具直接操作系统：\n'
    '- 数据库：/opt/quote-system/quote.db (SQLite)\n'
    '  产品表 products(id, name, sku, category, spec, unit, price, cost_price, supplier, function_desc, is_active, created_by)\n'
    '  报价单 quotes(id, title, client, contact, phone, quote_date, valid_days, status, total_amount, created_by)\n'
    '  报价明细 quote_items(id, quote_id, product_id, product_name, product_sku, quantity, unit_price, amount)\n'
    '- API：127.0.0.1:5001，JWT token 从 DB 获取\n'
    '  创建报价：POST /api/quotes  导出Excel：GET /api/quotes/<id>/export-excel\n'
    '- 产品搜索：sqlite3 /opt/quote-system/quote.db 查询时务必加上 AND is_active=1 过滤下线产品\n'
    '    "SELECT name,price FROM products WHERE name LIKE \'%关键词%\' AND is_active=1 ORDER BY price"\n\n'
    '规则：\n'
    '1. 只推荐 is_active=1 的在线产品，不推荐已下线产品（is_active=0）。\n'
    '2. 查询报价单时，用 curl 调用 API 而非 sqlite3 直查（API 会自动按用户权限过滤）：\n'
    '   curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:5001/api/quotes?per_page=50\n'
    '   如果必须用 sqlite3，务必加 AND created_by=<当前用户ID> 过滤，只能查看当前用户自己的报价单。\n'
    '3. 列出/统计报价单时，排除测试垃圾数据——满足以下任一条件视为测试数据需要跳过不展示：\n'
    '   - 标题包含「测试」「test」「sdf」「asdf」或全是随机字符\n'
    '   - 客户名或联系人是「pro报价测试」「qhk」「qwe」「asdf」等无意义字符串\n'
    '   - 标题长度 ≤ 3 且不含中文\n'
    '4. 生成报价单前，先检查对话上下文：如果之前已创建过报价单，主动询问用户沿用还是新客户。\n'
    '5. 导出后给用户下载链接：https://bwh.ddns.mobi/quote/api/quotes/{id}/export-excel，不要报本地路径。\n'
    '6. 每个用户的对话完全独立，不要使用或查询任何全局记忆/历史中的用户信息。'
    '如果不知道用户信息，就说不知道，不要从记忆里猜测。'
)


def _extract_choices_via_llm(text):
    """用 LLM 从「是A还是B」问句中提取两个选项。返回 [a, b] 或 []。"""
    import urllib.request, json as _json
    # 快速预检：必须包含「还是」
    if '还是' not in text:
        return []
    # 截取最后一句问句（约200字）
    sentences = re.split(r'[。！\n]', text)
    question = sentences[-1] if sentences[-1].strip() else (sentences[-2] if len(sentences) > 1 else text)
    question = question.strip()[-300:]
    if '还是' not in question:
        question = text.strip()[-300:]

    prompt = (
        '从这句话中提取「还是」前后两个选项。返回纯JSON数组如["A","B"]，不要markdown、不要解释。\n'
        '去掉「这是/是要/是/用/选/给」等前缀词和「的/呢/吗/啊」等后缀词，只留核心5-15字。\n'
        '例：「继续用威发西安还是新建客户？」→ ["继续用威发西安","新建客户"]\n'
        '例：「要改方案还是新项目？」→ ["改方案","新项目"]\n'
        f'提取："{question}"'
    )
    try:
        body = _json.dumps({
            'model': 'deepseek-v4-flash',
            'input': prompt,
            'max_output_tokens': 100,
        })
        req = urllib.request.Request(
            f'{_gateway_url}/v1/responses',
            data=body.encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        resp = urllib.request.urlopen(req, timeout=5)
        result = _json.loads(resp.read())
        reply = ''
        for o in result.get('output', []):
            if o.get('type') == 'message':
                content = o.get('content', [])
                if content:
                    reply = content[0].get('text', '')
                break
        # 尝试解析 JSON
        reply = reply.strip()
        if reply.startswith('['):
            arr = _json.loads(reply)
            if isinstance(arr, list) and len(arr) == 2:
                a, b = str(arr[0]).strip(), str(arr[1]).strip()
                if 1 <= len(a) <= 30 and 1 <= len(b) <= 30:
                    return [a, b]
    except Exception:
        pass
    return []


def _parse_reply_actions(reply_text):
    """解析 AI 回复，提取结构化数据：产品、报价引用、快捷操作"""
    # 过滤敏感路径，防止内部架构泄露
    reply_text = reply_text.replace('/opt/quote-system', '[系统路径]')
    reply_text = re.sub(r'127\.0\.0\.1:\d+', '[内部地址]', reply_text)
    reply_text = reply_text.replace('quote.db', '[数据库]')

    result = {'products': [], 'quote_refs': [], 'quick_replies': []}

    # 提取报价单引用 #N
    for m in re.finditer(r'(?:报价单|#)\s*(\d{1,5})', reply_text):
        result['quote_refs'].append(int(m.group(1)))

    # 检测问句 → 生成快捷回复
    question_patterns = [
        (r'沿用.*还是.*新.*', ['沿用上一份', '新建报价单']),
        (r'新建.*还是.*合并', ['新建报价单', '合并到已有']),
        (r'需要我(?:帮[您你])?.*吗[？?]', ['好的，开始吧', '先不用']),
        (r'哪个[？?]', []),  # 不生成快捷回复的产品选择题
    ]
    # 「是A还是B」→ LLM 提取实际选项
    if '还是' in reply_text:
        choices = _extract_choices_via_llm(reply_text)
        if choices:
            result['quick_replies'] = choices

    # 回退到固定模式
    if not result['quick_replies']:
        for pat, replies in question_patterns:
            if re.search(pat, reply_text) and replies:
                result['quick_replies'] = replies
                break

    # 检测推荐了产品 → 提取产品名+价格
    # 格式: "AI热电堆人数统计传感器 - ¥429"
    # 关键：逐行匹配，不跨行；分隔符前后必须有空格
    prod_pattern1 = re.findall(
        r'(?:\d+[.、．]\s*)?([A-Za-z\u4e00-\u9fff][A-Za-z0-9\u4e00-\u9fff\-+ ]{3,50}?)[ ]+[-–—][ ]+(?:¥|￥|[Rr][Mm][Bb])?\s*([\d,]+\.?\d*)',
        reply_text
    )
    seen = set()
    for name, price in prod_pattern1[:6]:
        name = name.strip()
        if name in seen or len(name) < 4:
            continue
        if re.match(r'^[\d\s\-+.,]+$', name):
            continue
        seen.add(name)
        try:
            result['products'].append({
                'name': name,
                'price': float(price.replace(',', '')),
            })
        except ValueError:
            pass

    # 多产品选型场景 → 每个产品一个快捷按钮
    if not result['quick_replies'] and len(result['products']) >= 2:
        if re.search(r'(选哪个|选哪|哪个更|哪款|推荐哪个|推荐哪|挑一个|选一款)', reply_text):
            result['quick_replies'] = [p['name'] for p in result['products'][:6]]

    # 提取已创建报价单 → 前端渲染预览/下载按钮
    dl_match = re.search(r'(https://bwh\.ddns\.mobi/quote/api/quotes/(\d+)/export-excel)', reply_text)
    if dl_match:
        result['created_quote'] = {'id': int(dl_match.group(2)), 'download_url': dl_match.group(1)}

    return result


# ─── AI 速率限制 ───
_ai_rate_limit = {}  # {user_id: [timestamp, ...]}
_AI_RATE_LIMIT = 5  # 每分钟最多5次

@app.route('/api/chat', methods=['POST'])
@require_auth
def ai_chat():
    """AI 对话 — 通过 Hermes Gateway Responses API。支持 SSE 流式。"""
    import time, urllib.request, json as _json
    t0 = time.time()

    # 速率限制
    uid = g.current_user.id
    now = time.time()
    _ai_rate_limit.setdefault(uid, [])
    _ai_rate_limit[uid] = [t for t in _ai_rate_limit[uid] if now - t < 60]
    if len(_ai_rate_limit[uid]) >= _AI_RATE_LIMIT:
        return jsonify({'error': f'请求过快，每分钟最多{_AI_RATE_LIMIT}次，请稍后再试'}), 429
    _ai_rate_limit[uid].append(now)

    data = request.get_json(silent=True) or {}
    user_input = (data.get('input', '') or '').strip()
    if not user_input:
        return jsonify({'error': '请输入问题'}), 400

    # 注入身份指令到用户消息头部（对抗 Gateway 基础 persona）
    prompt = _get_ai_system_prompt()
    for line in prompt.split('\n')[:3]:
        if '童小军' in line or '不是 Hermes' in line:
            user_input = f'[{line.strip()}] {user_input}'
            break

    stream = data.get('stream', False)

    user = g.current_user
    conversation = f'quote-user-{user.id}'

    body = {
        'model': data.get('model') or _ai_model,
        'input': user_input,
        'conversation': conversation,
        'max_output_tokens': 2000,
    }

    import hashlib
    prompt = _get_ai_system_prompt()
    prompt_h = hashlib.sha256(prompt.encode()).hexdigest()[:16]

    session = AIChatSession.query.filter_by(user_id=user.id).first()
    if not session or session.prompt_hash != prompt_h:
        body['instructions'] = (
            prompt + '\n'
            f'当前用户：{user.username}（ID={user.id}，角色：{user.role}）。\n'
            f'查询/列出报价单：用 curl 调 API 或 sqlite3 直查均可。\n'
            f'  curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:5001/api/quotes?per_page=50\n'
            f'  sqlite3: SELECT id,title,client,status,total_amount,quote_date FROM quotes WHERE created_by={user.id} ORDER BY id DESC LIMIT 30;\n'
            f'创建报价：curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d \'...\' http://127.0.0.1:5001/api/quotes\n'
            f'报价单自动归属到当前用户 ID={user.id}（{user.username}）。\n'
            f'列出报价单时：\n'
            f'  1) 排除测试数据：标题含「测试」「test」「sdf」或客户名含「pro报价测试」「qhk」「qwe」的要跳过\n'
            f'  2) 用 pipe table 格式列出，必须包含这6列：ID | 标题 | 客户 | 状态 | 金额 | 日期\n'
            f'  3) 金额格式：¥12,345，日期格式：MM-DD\n'
            f'  4) 先统计总数再列出表格，最后给用户一段可选操作提示'
        )
        if session:
            session.prompt_hash = prompt_h
        else:
            db.session.add(AIChatSession(user_id=user.id, prompt_hash=prompt_h))
        db.session.commit()

    # ─── SSE 流式模式 ───
    if stream:
        body['stream'] = True
        return _ai_chat_sse(body, t0, user_id=user.id)

    # ─── 非流式模式 ───
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

        # 记录AI使用
        _log_ai_usage(user_id=user.id, action='chat', model=body.get('model', ''), elapsed=t2-t0)

        return jsonify({
            'reply': reply,
            'parsed': parsed,
            'model': 'hermes-gateway',
            'timings': {'Gateway': f'{t2 - t1:.1f}s', '总耗时': f'{t2 - t0:.1f}s'}
        })
    except Exception as e:
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

            # 先发连接时间（Flask→Gateway 网络 + Gateway 内部处理）
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
                # Skip response.output_item.done — carries full text, duplicates deltas

                if delta_text:
                    if first_token:
                        first_token = False
                        ttft = time.time() - t_connected
                        yield f'data: {_json.dumps({"type": "first_token", "ttft": f"{ttft:.1f}s"})}\n\n'
                    accumulated += delta_text
                    yield f'data: {_json.dumps({"type": "text", "text": delta_text})}\n\n'

                # 工具调用阶段
                if event_type and 'tool' in event_type.lower():
                    yield f'data: {_json.dumps({"type": "tool"})}\n\n'

            # 完成 — 发送解析结果
            parsed = _parse_reply_actions(accumulated)
            _log_ai_usage(user_id=user_id, action='chat', model=body.get('model', ''), elapsed=time.time()-t0)
            yield f'data: {_json.dumps({"type": "done", "parsed": parsed, "elapsed": f"{time.time() - t0:.1f}s"})}\n\n'

        except Exception as e:
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


# ─── Frontend ────────────────────────────────────────────────

# Vue production build static files
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
    except:
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
    # 初始化默认系统设置
    defaults = {'company_name': '', 'footer_text': ''}
    for k, v in defaults.items():
        if not SystemSetting.query.filter_by(key=k).first():
            db.session.add(SystemSetting(key=k, value=v))
    db.session.commit()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
