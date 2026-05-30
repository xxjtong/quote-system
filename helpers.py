"""共享辅助函数 — 从 app.py 提取，消除循环依赖"""
from datetime import datetime
from flask import g, jsonify
from extensions import db
from models import Product, Quote, FieldSetting, SystemSetting, User


def get_setting(key, default=''):
    """读取单个系统设置"""
    s = SystemSetting.query.filter_by(key=key).first()
    return s.value if s else default


def get_all_settings():
    """读取所有系统设置 (返回dict)"""
    return {s.key: s.value for s in SystemSetting.query.all()}


# 字段可见性缓存
_field_cache = None
_field_cache_time = None


def get_field_visibility():
    global _field_cache, _field_cache_time
    now = datetime.now()
    if _field_cache and _field_cache_time and (now - _field_cache_time).seconds < 30:
        return _field_cache
    _field_cache = {f.field_name: f.user_visible for f in FieldSetting.query.all()}
    _field_cache_time = now
    return _field_cache


def filter_fields_for_user(data_dict, is_admin):
    if is_admin:
        return data_dict
    visibility = get_field_visibility()
    for field in ['cost_price', 'remark', 'supplier', 'function_desc', 'manufacturer_name', 'supplier_name']:
        if field in data_dict and not visibility.get(field, True):
            data_dict[field] = None
    return data_dict


def preload_products_for_quote(quote):
    """批量加载报价单所有明细关联的产品，返回 {product_id: Product}"""
    pids = [item.product_id for item in quote.items if item.product_id]
    if not pids:
        return {}
    products = Product.query.filter(Product.id.in_(pids)).all()
    return {p.id: p for p in products}


def check_quote_owner(quote_id):
    """非管理员只能操作自己的报价单。返回 (quote_or_error, status_code)."""
    quote = db.session.get(Quote, quote_id)
    if not quote:
        return None, jsonify({'error': '报价单不存在'}), 404
    if g.current_user.role != 'admin' and quote.created_by != g.current_user.id:
        return None, jsonify({'error': '无权操作此报价单'}), 403
    return quote, None, None
