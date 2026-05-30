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
from helpers import get_setting, get_all_settings, get_field_visibility, filter_fields_for_user, preload_products_for_quote, check_quote_owner

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

# Register all blueprints
app.register_blueprint(auth_bp)
from products_bp import products_bp
app.register_blueprint(products_bp)
from quotes_bp import quotes_bp
app.register_blueprint(quotes_bp)
from admin_bp import admin_bp
app.register_blueprint(admin_bp)
from ai_bp import ai_bp
app.register_blueprint(ai_bp)
from dict_bp import dict_bp
app.register_blueprint(dict_bp)
from category_bp import category_bp
app.register_blueprint(category_bp)
from product_advanced_bp import product_advanced_bp
app.register_blueprint(product_advanced_bp)

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
app.config['DEFAULT_ADMIN_PASSWORD'] = os.environ.get('QUOTE_ADMIN_PASSWORD', '')  # 空值=首次启动自动生成随机密码
app.config['REGISTRATION_OPEN'] = os.environ.get('QUOTE_REGISTRATION', 'true').lower() == 'true'

db.init_app(app)

# Flask-Migrate (Alembic) — 替代手动 ALTER TABLE
from flask_migrate import Migrate
migrate = Migrate(app, db)

def _get_ai_system_prompt():
    """获取 AI 系统提示词 — 委托给 ai_bp 实现（单一来源）"""
    from ai_bp import _get_ai_system_prompt as _ai_bp_get_prompt
    return _ai_bp_get_prompt()


# ─── API Routes ──────────────────────────────────────────────

# ─── 下载 Ticket 机制已移至 admin_bp.py ────────────────────
# _validate_download_ticket 在 check_auth() 中延迟导入，避免循环依赖

# 公开路由（无需登录）
PUBLIC_ROUTES = {'auth.auth_login', 'auth.auth_register', 'auth.auth_registration_status', 'get_version', 'health_check', 'index', 'products.export_product_template', 'products.get_product_image'}

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
    # 放行 CORS preflight (OPTIONS) 请求
    if request.method == 'OPTIONS':
        return None
    if not request.path.startswith('/api/') and not request.path.startswith('/uploads/'):
        return None
    if request.path.startswith('/uploads/'):
        return None  # 静态上传文件无需认证
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

# 字段可见性缓存 — 已移至 helpers.py（from helpers import get_field_visibility, filter_fields_for_user）

# ----- Products (moved to products_bp.py) -----
# All product route handlers have been moved to products_bp.py
# Helper functions below extracted to utils.py and product_utils.py

from utils import _debug_log, _log_ai_usage, _safe_number, _compute_pinyin_search
from product_utils import (
    compress_image_if_needed, _ocr_fallback, doubao_vision_recognize,
    _parse_json_reply, _product_from_parsed, deepseek_parse_product,
    smart_parse_product, parse_product_line,
)


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


# ─── Univer 独立页面（Vite 多页面构建产物） ──────
# Flask 仅在生产环境（_has_vue_build）提供构建后的 univer.html
# 开发环境由 Vite dev server 直接提供 univer.html


# ─── SPA catch-all (must be LAST route) ──────
@app.route('/<path:path>')
def spa_catch_all(path):
    """所有非 API/静态文件路径 → 返回 Vue SPA；univer.html 返回独立 Univer 页面"""
    if _has_vue_build:
        # Univer 独立页面
        if path == 'univer.html':
            univer_html = os.path.join(_dist_dir, 'univer.html')
            if os.path.isfile(univer_html):
                return send_file(univer_html)
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
        # v2.6.0 Product 扩展字段
        ('products', 'model', 'VARCHAR(100)'),
        ('products', 'category_id', 'INTEGER'),
        ('products', 'manufacturer_id', 'INTEGER'),
        ('products', 'supplier_id', 'INTEGER'),
        ('products', 'product_url', 'VARCHAR(500)'),
        ('products', 'status', "VARCHAR(20) DEFAULT 'active'"),
        ('products', 'parent_id', 'INTEGER'),
        ('products', 'specs', 'TEXT'),
        ('products', 'urls', 'TEXT'),
        ('products', 'custom_fields', 'TEXT'),
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
        _admin_pwd = app.config['DEFAULT_ADMIN_PASSWORD']
        if not _admin_pwd:
            # 未设环境变量时，生成随机密码并写入文件，避免硬编码弱密码
            _admin_pwd = secrets.token_urlsafe(12)
            _pwd_file = Path(BASE_DIR) / '.admin_password'
            _pwd_file.write_text(_admin_pwd)
            _pwd_file.chmod(0o600)
            print(f'[Init] 随机密码已写入 {_pwd_file}（请妥善保管）')
        admin = User(
            username='admin',
            password_hash=hash_password(_admin_pwd),
            role='admin', is_active=True
        )
        db.session.add(admin)
        db.session.commit()
        print(f'[Init] 已创建管理员: admin / [密码已设]')
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
    ).all()
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

    # v2.6.0 种子数据: 字典表默认值
    from models import (
        DictCommMethod, DictCommProtocol, DictPowerSupply, DictSensorMetric
    )

    # 通讯方式种子
    _comm_methods = [
        ('wired', 'Ethernet'), ('wired', 'RS485'), ('wired', 'RS232'),
        ('wired', 'DryContact'), ('wired', 'KNX'), ('wired', 'M-BUS'), ('wired', 'USB'),
        ('wireless', 'LoRaWAN'), ('wireless', 'WiFi'), ('wireless', '4G'),
        ('wireless', '5G'), ('wireless', 'NB-IoT'), ('wireless', 'Zigbee'),
        ('wireless', 'BLE'), ('wireless', 'NFC'), ('wireless', 'GNSS'), ('wireless', 'D2D'),
    ]
    for _type, _name in _comm_methods:
        if not DictCommMethod.query.filter_by(name=_name).first():
            db.session.add(DictCommMethod(method_type=_type, name=_name))

    # 通讯协议种子
    _protocols = [
        'HTTP', 'HTTPS', 'MQTT', 'MQTTS', 'ModbusRTU', 'ModbusTCP',
        'BACnet/IP', 'BACnet/MS-TP', 'TCP', 'UDP', 'SNMP', 'SSH', 'VPN', 'RTSP', 'NTP',
    ]
    for _name in _protocols:
        if not DictCommProtocol.query.filter_by(name=_name).first():
            db.session.add(DictCommProtocol(name=_name))

    # 供电方式种子
    _supplies = [
        ('外接电源', 'DC'), ('外接电源', 'PoE'), ('内置电池', 'Battery'),
        ('外接电源', 'USB-C'), ('外接电源', 'AC'), ('外接电源', 'Solar'),
    ]
    for _cat, _name in _supplies:
        if not DictPowerSupply.query.filter_by(name=_name).first():
            db.session.add(DictPowerSupply(supply_category=_cat, name=_name))

    # 传感指标种子
    _metrics = [
        ('温度', '℃'), ('湿度', '%RH'), ('CO2', 'ppm'), ('TVOC', 'ppb'),
        ('PM2.5', 'μg/m³'), ('PM10', 'μg/m³'), ('气压', 'hPa'), ('光照', 'lux'),
        ('噪声', 'dB'), ('水浸', None), ('门磁', None), ('倾斜', None),
        ('液位', None), ('压力', None), ('距离', 'm'), ('人数', None),
        ('人体存在', None), ('CO', 'ppm'), ('O3', 'ppm'), ('HCHO', 'mg/m³'),
        ('电流', 'A'),
    ]
    for _name, _unit in _metrics:
        if not DictSensorMetric.query.filter_by(name=_name).first():
            db.session.add(DictSensorMetric(name=_name, unit=_unit))

    db.session.commit()
    print('[Init] v2.6.0 字典种子数据已初始化')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)

