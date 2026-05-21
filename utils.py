"""共享工具函数 — 多个 Blueprint 共用"""
import json
import re
from datetime import datetime
from pathlib import Path

from extensions import db
from models import AIUsageLog, SystemSetting

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / 'uploads'
EXPORT_DIR = BASE_DIR / 'exports'
UPLOAD_DIR.mkdir(exist_ok=True)
EXPORT_DIR.mkdir(exist_ok=True)


def _debug_log(msg):
    """写调试日志到 gunicorn error log 文件"""
    try:
        with open(BASE_DIR / 'gunicorn-error.log', 'a') as f:
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


def get_setting(key, default=''):
    """读取单个系统设置"""
    s = SystemSetting.query.filter_by(key=key).first()
    return s.value if s else default


def get_all_settings():
    """读取所有系统设置 (返回dict)"""
    return {s.key: s.value for s in SystemSetting.query.all()}


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


# ─── 字段可见性缓存 ───
_field_cache = None
_field_cache_time = None


def get_field_visibility():
    global _field_cache, _field_cache_time
    from models import FieldSetting
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


def check_quote_owner(quote_id):
    """非管理员只能操作自己的报价单。返回 (quote_or_error, status_code)."""
    from models import Quote
    from flask import g, jsonify
    quote = db.session.get(Quote, quote_id)
    if not quote:
        return None, jsonify({'error': '报价单不存在'}), 404
    if g.current_user.role != 'admin' and quote.created_by != g.current_user.id:
        return None, jsonify({'error': '无权操作此报价单'}), 403
    return quote, None, None


def preload_products_for_quote(quote):
    """批量加载报价单所有明细关联的产品，返回 {product_id: Product}"""
    from models import Product
    pids = [item.product_id for item in quote.items if item.product_id]
    if not pids:
        return {}
    products = Product.query.filter(Product.id.in_(pids)).all()
    return {p.id: p for p in products}


# ─── 下载 Ticket 机制 ───
_download_tickets = {}  # {ticket_str: {'user_id': int, 'exp': float}}
_TICKET_TTL = 120  # 秒


def create_download_ticket_entry(user_id):
    """创建下载ticket，返回ticket字符串"""
    import secrets
    ticket = secrets.token_urlsafe(32)
    _download_tickets[ticket] = {
        'user_id': user_id,
        'exp': datetime.utcnow().timestamp() + _TICKET_TTL,
    }
    # 清理过期ticket
    now = datetime.utcnow().timestamp()
    expired = [k for k, v in _download_tickets.items() if v['exp'] < now]
    for k in expired: del _download_tickets[k]
    return ticket


def _validate_download_ticket(ticket_str):
    """验证下载ticket，返回 user_id 或 None"""
    entry = _download_tickets.get(ticket_str)
    if not entry: return None
    if datetime.utcnow().timestamp() > entry['exp']:
        _download_tickets.pop(ticket_str, None)
        return None
    return entry['user_id']


# ─── 数字转中文大写 ───
CN_NUM = ['零', '壹', '贰', '叁', '肆', '伍', '陆', '柒', '捌', '玖']
CN_UNIT = ['', '拾', '佰', '仟']
CN_BIG_UNIT = ['', '万', '亿', '万亿']


def number_to_cn(num):
    """数字转中文大写金额"""
    if num == 0:
        return '零圆整'
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
            pass
        num //= 10000
        unit_idx += 1

    while '零零' in result:
        result = result.replace('零零', '零')
    if result.endswith('零'):
        result = result[:-1]

    return result + '圆整'
