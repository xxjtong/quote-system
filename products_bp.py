"""
Products Blueprint — 产品相关 API 路由
从 app.py 拆分出的所有 /api/products/* 路由及 /api/upload/image、/api/download-image
"""

import os
import io
import re
import random
from datetime import datetime
from pathlib import Path

from flask import Blueprint, request, jsonify, g, Response, send_file
from sqlalchemy import func

from extensions import db
from models import Product, AIUsageLog
from auth import require_auth, require_admin

from utils import _debug_log, _log_ai_usage, _safe_number, _compute_pinyin_search
from product_utils import (
    compress_image_if_needed, _ocr_fallback, doubao_vision_recognize,
    _parse_json_reply, _product_from_parsed, deepseek_parse_product,
    smart_parse_product, parse_product_line,
)

# ─── Blueprint 定义 ──────────────────────────────────────────
products_bp = Blueprint('products', __name__, url_prefix='/api/products')

# 独立前缀的路由需要单独 Blueprint
upload_bp = Blueprint('upload', __name__)
download_bp = Blueprint('download_img', __name__)

# 项目根目录（用于文件操作）
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / 'uploads'
UPLOAD_DIR.mkdir(exist_ok=True)

# Gateway URL（deepseek_parse_product 用）
_gateway_url = os.environ.get('QUOTE_GATEWAY_URL', 'http://127.0.0.1:8642')


# ─── Lazy imports（避免循环依赖） ─────────────────────────────

def _get_setting(key, default=''):
    """读取单个系统设置（本地包装，指向 app.py 的实现）"""
    from app import get_setting
    return get_setting(key, default)


def _filter_fields_for_user(data_dict, is_admin):
    """过滤非管理员不可见字段（指向 app.py 的实现）"""
    from app import filter_fields_for_user
    return filter_fields_for_user(data_dict, is_admin)


def _get_field_visibility():
    """获取字段可见性（指向 app.py 的实现）"""
    from app import get_field_visibility
    return get_field_visibility()


# ─── 辅助函数 ────────────────────────────────────────────────

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


# ─── 产品路由 ────────────────────────────────────────────────

@products_bp.route('', methods=['GET'])
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
        q_lower = search.lower().strip()
        like = f'%{q_lower}%'
        query = query.filter(Product.pinyin_search.like(like))
        query = query.order_by(col.asc() if sort_order == 'asc' else col.desc())
        total = query.count()
        products = query.offset((page - 1) * per_page).limit(per_page).all()
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


@products_bp.route('', methods=['POST'])
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
    product.pinyin_search = _compute_pinyin_search(name, spec, data.get('category', ''), data.get('supplier', ''))
    db.session.add(product)
    db.session.commit()
    return jsonify({'product': product.to_dict()}), 201


@products_bp.route('/<int:product_id>', methods=['GET'])
def get_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({'error': '产品不存在'}), 404
    return jsonify({'product': product.to_dict()})


@products_bp.route('/<int:product_id>/image', methods=['GET'])
def get_product_image(product_id):
    """返回产品图片二进制数据（支持 query param token 认证）"""
    # 不用 @require_auth，手动验证（img 标签无法设 header）
    from flask import request as _req
    token = _req.headers.get('Authorization', '').replace('Bearer ', '') or _req.args.get('token', '')
    if not token:
        return '', 401
    try:
        import jwt as _jwt
        from flask import current_app
        data = _jwt.decode(token, current_app.config['JWT_SECRET'], algorithms=['HS256'])
        from models import User
        user = db.session.get(User, data['user_id'])
        if not user or not user.is_active:
            return '', 403
    except Exception:
        return '', 401
    product = db.session.get(Product, product_id)
    if not product or not product.image_data:
        return '', 404
    return Response(product.image_data, mimetype=product.image_mime or 'image/jpeg')


@products_bp.route('/<int:product_id>', methods=['PUT'])
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
    product.pinyin_search = _compute_pinyin_search(product.name, product.spec or '', product.category or '', product.supplier or '')
    db.session.commit()
    return jsonify({'product': product.to_dict()})


@products_bp.route('/<int:product_id>', methods=['DELETE'])
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


@products_bp.route('/batch-delete', methods=['POST'])
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


@products_bp.route('/version', methods=['GET'])
def products_version():
    count = Product.query.count()
    latest = db.session.query(func.max(Product.updated_at)).scalar()
    return jsonify({
        'count': count,
        'max_updated_at': latest.isoformat() if latest else None
    })


# ─── 图片OCR识别接口 ─────────────────────────────────────────

@products_bp.route('/ocr', methods=['POST'])
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
        except Exception: pass


@products_bp.route('/recognize', methods=['POST'])
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
            except Exception: pass

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


# ─── 发票OCR → 成本价匹配 ─────────────────────────────────────

@products_bp.route('/ocr-costs', methods=['POST'])
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
        except Exception: pass


@products_bp.route('/batch-costs', methods=['POST'])
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


@products_bp.route('/<int:product_id>/toggle-active', methods=['PUT'])
@require_admin
def toggle_product_active(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({'error': '产品不存在'}), 404
    product.is_active = not product.is_active
    product.updated_at = datetime.now()
    db.session.commit()
    return jsonify({'id': product.id, 'is_active': product.is_active})


@products_bp.route('/import', methods=['POST'])
def import_products():
    """从Excel导入产品 — 支持多Sheet、自动识别分类、提取嵌入图片"""
    import openpyxl

    file = request.files.get('file')
    if not file:
        return jsonify({'error': '请上传Excel文件'}), 400

    try:
        wb = openpyxl.load_workbook(file, data_only=True)
        imported, errors = _import_all_sheets(wb)
        db.session.commit()
        return jsonify({
            'message': f'成功导入 {imported} 个产品（共{len(wb.sheetnames)}个Sheet）',
            'imported': imported,
            'errors': errors,
        })
    except Exception as e:
        return jsonify({'error': f'导入失败: {str(e)}'}), 400


# ─── import_products 子函数 ────────────────────────────────────

_FIELD_MAP = {
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


def _find_col(header, names):
    """在表头中查找包含指定名称的列索引"""
    for i, h in enumerate(header):
        if not h:
            continue
        for n in names:
            if n in h or h in n:
                return i
    return -1


def _parse_excel_header(ws, rows, header_row_idx):
    """解析Excel表头，返回列索引映射 + 嵌入图片索引"""
    header = [str(h).strip().lower() if h else '' for h in rows[header_row_idx]]
    col_idx = {}
    for key, names in _FIELD_MAP.items():
        col_idx[key] = _find_col(header, names)

    # 智能解析：备注 vs 内部备注 vs 图片
    inner_remark_col = _find_col(header, ['内部备注'])
    if inner_remark_col >= 0 and col_idx.get('remark', -1) >= 0:
        if col_idx.get('image_url', -1) < 0:
            col_idx['image_url'] = col_idx['remark']
        col_idx['remark'] = inner_remark_col
    elif col_idx.get('image_url', -1) < 0 and col_idx.get('remark', -1) >= 0:
        pass  # 仅有一个备注列，保持为 remark

    # 构建嵌入图片索引
    image_map = {}
    if hasattr(ws, '_images'):
        for img in ws._images:
            try:
                anc = img.anchor
                if hasattr(anc, '_from'):
                    image_map[(anc._from.col, anc._from.row)] = img
            except Exception:
                pass

    return col_idx, image_map


def _detect_supplier_col(rows, header_row_idx):
    """供应商列回退：扫描数据行定位常见位置"""
    data_start2 = header_row_idx + 1
    for cc in [11, 12, 13]:
        if cc >= len(rows[header_row_idx]):
            continue
        sample_count = 0
        for dr in rows[data_start2:data_start2 + 10]:
            if dr and cc < len(dr) and dr[cc] and str(dr[cc]).strip():
                sample_count += 1
        if sample_count >= 2:
            return cc
    return -1


def _extract_embedded_image(emb_img):
    """从Excel嵌入图片提取并保存，返回 image_url 路径或空字符串"""
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
        return f'/uploads/images/{compressed_fname}'
    except Exception:
        return ''


def _process_import_row(row, row_idx, col_idx, image_map, sheet_name, sheet_supplier_ref):
    """处理单行数据，返回 (Product对象, error_string_or_None)"""
    name_idx = col_idx['name']
    name = str(row[name_idx]).strip() if name_idx >= 0 and name_idx < len(row) and row[name_idx] else ''
    if not name:
        spec_idx = col_idx.get('spec', -1)
        if spec_idx >= 0 and spec_idx < len(row) and row[spec_idx]:
            name = str(row[spec_idx]).strip()
    if not name:
        return None, None

    sup_val = str(row[col_idx['supplier']]).strip() if col_idx.get('supplier', -1) >= 0 and col_idx['supplier'] < len(row) and row[col_idx['supplier']] else ''
    if not sup_val and sheet_supplier_ref[0]:
        sup_val = sheet_supplier_ref[0]
    else:
        sheet_supplier_ref[0] = sup_val

    sku_val = str(row[col_idx['sku']]).strip() if col_idx.get('sku', -1) >= 0 and col_idx['sku'] < len(row) and row[col_idx['sku']] else ''
    spec_val = str(row[col_idx['spec']]).strip() if col_idx.get('spec', -1) >= 0 and col_idx['spec'] < len(row) and row[col_idx['spec']] else ''
    if spec_val:
        sku_val = spec_val
    else:
        spec_val = sku_val

    product = Product(
        name=name,
        category=sheet_name,
        sku=sku_val or spec_val,
        spec=spec_val,
        unit=str(row[col_idx['unit']]).strip() if col_idx.get('unit', -1) >= 0 and col_idx['unit'] < len(row) and row[col_idx['unit']] else '',
        price=_safe_number(row[col_idx['price']]) if col_idx.get('price', -1) >= 0 and col_idx['price'] < len(row) else 0,
        cost_price=_safe_number(row[col_idx['cost_price']]) if col_idx.get('cost_price', -1) >= 0 and col_idx['cost_price'] < len(row) else 0,
        supplier=sup_val,
        function_desc=str(row[col_idx['function_desc']]).strip() if col_idx.get('function_desc', -1) >= 0 and col_idx['function_desc'] < len(row) and row[col_idx['function_desc']] else '',
        remark=str(row[col_idx['remark']]).strip() if col_idx.get('remark', -1) >= 0 and col_idx['remark'] < len(row) and row[col_idx['remark']] else '',
        created_by=g.current_user.id if hasattr(g, 'current_user') and g.current_user else None,
    )

    # 提取图片：嵌入图片优先，URL 文本次之
    if col_idx.get('image_url', -1) >= 0:
        img_col_0 = col_idx['image_url']
        emb_img = image_map.get((img_col_0, row_idx - 1))
        if emb_img is not None:
            product.image_url = _extract_embedded_image(emb_img)
        if not product.image_url and img_col_0 < len(row) and row[img_col_0]:
            txt = str(row[img_col_0]).strip()
            if txt and (txt.startswith('http') or txt.startswith('/uploads/')):
                product.image_url = txt[:500]

    _store_image_blob(product, {'image_url': product.image_url or ''})
    return product, None


def _import_all_sheets(wb):
    """遍历所有Sheet导入产品，返回 (imported_count, errors_list)"""
    imported = 0
    errors = []

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if not rows or len(rows) < 2:
            continue

        # 检测表头行
        first_nonempty = [v for v in rows[0] if v is not None and str(v).strip()]
        second_nonempty = [v for v in rows[1] if v is not None and str(v).strip()] if len(rows) > 1 else []
        header_row_idx = 1 if len(first_nonempty) <= 2 and len(second_nonempty) >= 3 else 0

        col_idx, image_map = _parse_excel_header(ws, rows, header_row_idx)
        if col_idx.get('name', -1) < 0:
            continue

        if col_idx.get('supplier', -1) < 0:
            col_idx['supplier'] = _detect_supplier_col(rows, header_row_idx)

        sheet_supplier_ref = ['']  # 用list以便在_process_import_row中修改
        data_start = header_row_idx + 1
        for row_idx, row in enumerate(rows[data_start:], data_start + 1):
            if all(c is None or str(c).strip() == '' for c in row):
                continue
            first_col = str(row[0]).strip().lower() if row[0] else ''
            if first_col in ('小计', '合计', '总计', 'subtotal', 'total', '注', '备注'):
                continue
            try:
                product, err = _process_import_row(row, row_idx, col_idx, image_map, sheet_name, sheet_supplier_ref)
                if product:
                    db.session.add(product)
                    imported += 1
            except Exception as e:
                errors.append(f'[{sheet_name}] 第{row_idx}行: {str(e)}')

    return imported, errors


@products_bp.route('/export-all', methods=['GET'])
@require_auth
def export_all_products():
    """导出全部产品为 Excel（按模板格式，管理员增加创建者列）"""
    import openpyxl
    from openpyxl.styles import Font, Alignment
    from openpyxl.utils import get_column_letter

    is_admin = g.current_user.role == 'admin'
    uid = g.current_user.id

    # 权限过滤：普通用户只导出自己创建的产品
    query = Product.query
    if not is_admin:
        query = query.filter(Product.created_by == uid)
    products = query.order_by(Product.id.asc()).all()

    wb = openpyxl.Workbook()
    # 按 category 分 Sheet，未分类放「未分类」
    sheet_map = {}
    for p in products:
        cats = [c.strip() for c in (p.category or '').split(',') if c.strip()] or ['未分类']
        for cat in cats:
            if cat not in sheet_map:
                sheet_map[cat] = []
            sheet_map[cat].append(p)

    header_font = Font(bold=True, size=11)
    center_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    data_align = Alignment(vertical='center', wrap_text=True)

    for sheet_name, prods in sheet_map.items():
        ws = wb.create_sheet(title=sheet_name[:31])
        headers = ['产品名称', '规格型号', '功能描述', '备注', '供应商', '单价', '成本价', '单位']
        if is_admin:
            headers.append('创建者')
        ws.append(headers)
        for col in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col)
            cell.font = header_font
            cell.alignment = center_align
        widths = [20, 25, 30, 20, 15, 10, 10, 8]
        if is_admin:
            widths.append(10)
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

        for p in prods:
            row_data = [
                p.name or '',
                p.spec or '',
                p.function_desc or '',
                p.remark or '',
                p.supplier or '',
                p.price or 0,
                p.cost_price or 0,
                p.unit or '',
            ]
            if is_admin:
                creator = ''
                if p.created_by:
                    from models import User
                    u = db.session.get(User, p.created_by)
                    creator = u.username if u else str(p.created_by)
                row_data.append(creator)
            ws.append(row_data)

    # 删除默认空 Sheet
    if 'Sheet' in wb.sheetnames and len(wb.sheetnames) > 1:
        del wb['Sheet']

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    fname = 'products_export.xlsx' if is_admin else 'my_products_export.xlsx'
    return send_file(output, download_name=fname, as_attachment=True)


@products_bp.route('/export-template', methods=['GET'])
def export_product_template():
    """下载原始报价规格库模板（包含所有分类Sheet）"""
    from openpyxl.styles import Font, Alignment
    from openpyxl.utils import get_column_letter

    template_path = BASE_DIR / 'template.xlsx'
    if template_path.exists():
        return send_file(str(template_path), download_name='硬件报价规格库（成本）.xlsx', as_attachment=True)
    # 兜底：生成简易模板
    import openpyxl
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


# ─── 独立前缀路由（不在 /api/products 下） ────────────────────

@upload_bp.route('/api/upload/image', methods=['POST'])
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


@download_bp.route('/api/download-image', methods=['POST'])
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
