#!/usr/bin/env python3
"""
报价管理系统 - Quote Management System
Flask + SQLite + REST API + Web UI
"""

import os
import json
import io
import random
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, send_file, send_from_directory, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from sqlalchemy import func
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.drawing.image import Image as XLImage
from openpyxl.utils import get_column_letter

app = Flask(__name__)
CORS(app)

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / 'uploads'
EXPORT_DIR = BASE_DIR / 'exports'
UPLOAD_DIR.mkdir(exist_ok=True)
EXPORT_DIR.mkdir(exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{BASE_DIR}/quote.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

db = SQLAlchemy(app)

# ─── Models ───────────────────────────────────────────────────

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    sku = db.Column(db.String(100), nullable=True)
    category = db.Column(db.String(100), nullable=True, index=True)
    spec = db.Column(db.String(500), nullable=True)
    unit = db.Column(db.String(20), nullable=True)
    price = db.Column(db.Float, nullable=True)
    cost_price = db.Column(db.Float, nullable=True)
    supplier = db.Column(db.String(200), nullable=True)
    function_desc = db.Column(db.Text, nullable=True)
    remark = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'sku': self.sku or '',
            'category': self.category or '',
            'spec': self.spec or '',
            'unit': self.unit or '',
            'price': self.price or 0,
            'cost_price': self.cost_price or 0,
            'supplier': self.supplier or '',
            'function_desc': self.function_desc or '',
            'remark': self.remark or '',
            'image_url': self.image_url or '',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else '',
        }


class Quote(db.Model):
    __tablename__ = 'quotes'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=True)
    client = db.Column(db.String(200), nullable=True)
    contact = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    quote_date = db.Column(db.String(20), nullable=True)
    valid_days = db.Column(db.Integer, default=15)
    status = db.Column(db.String(20), default='draft')
    total_amount = db.Column(db.Float, default=0)
    download_count = db.Column(db.Integer, default=0)
    remark = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    items = db.relationship('QuoteItem', backref='quote', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title or '',
            'client': self.client or '',
            'contact': self.contact or '',
            'phone': self.phone or '',
            'quote_date': self.quote_date or '',
            'valid_days': self.valid_days,
            'status': self.status,
            'total_amount': self.total_amount or 0,
            'download_count': self.download_count or 0,
            'remark': self.remark or '',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else '',
            'items': [item.to_dict() for item in self.items],
        }


class QuoteItem(db.Model):
    __tablename__ = 'quote_items'
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey('quotes.id', ondelete='CASCADE'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    product_name = db.Column(db.String(200), nullable=False)
    product_sku = db.Column(db.String(100), nullable=True)
    product_spec = db.Column(db.String(500), nullable=True)
    product_unit = db.Column(db.String(20), nullable=True)
    quantity = db.Column(db.Float, default=1)
    unit_price = db.Column(db.Float, default=0)
    amount = db.Column(db.Float, default=0)
    remark = db.Column(db.String(500), nullable=True)
    sort_order = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'quote_id': self.quote_id,
            'product_id': self.product_id,
            'product_name': self.product_name,
            'product_sku': self.product_sku or '',
            'product_spec': self.product_spec or '',
            'product_unit': self.product_unit or '',
            'quantity': self.quantity,
            'unit_price': self.unit_price,
            'amount': self.amount,
            'remark': self.remark or '',
            'sort_order': self.sort_order,
        }


# ─── API Routes ──────────────────────────────────────────────

# ----- Products -----

@app.route('/api/products', methods=['GET'])
def list_products():
    """产品列表，支持搜索和分类筛选"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    supplier = request.args.get('supplier', '').strip()

    query = Product.query
    if search:
        like = f'%{search}%'
        query = query.filter(
            db.or_(Product.name.ilike(like), Product.spec.ilike(like),
                    Product.supplier.ilike(like), Product.function_desc.ilike(like))
        )
    if category:
        query = query.filter(Product.category.ilike(f'%{category}%'))
    if supplier:
        query = query.filter(Product.supplier == supplier)

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
    if sort_order == 'asc':
        query = query.order_by(col.asc())
    else:
        query = query.order_by(col.desc())

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
        'products': [p.to_dict() for p in products],
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

    # 规格型号统一：spec 为主，同时填充 sku
    spec = data.get('spec', '')
    product = Product(
        name=data['name'],
        sku=spec,
        category=data.get('category', ''),
        spec=spec,
        unit=data.get('unit', ''),
        price=float(data.get('price', 0)),
        cost_price=float(data.get('cost_price', 0)),
        supplier=data.get('supplier', ''),
        function_desc=data.get('function_desc', ''),
        remark=data.get('remark', ''),
        image_url=data.get('image_url', ''),
    )
    db.session.add(product)
    db.session.commit()
    return jsonify({'product': product.to_dict()}), 201


@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({'error': '产品不存在'}), 404
    return jsonify({'product': product.to_dict()})


@app.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({'error': '产品不存在'}), 404
    data = request.get_json()
    for field in ['name', 'sku', 'category', 'spec', 'unit', 'supplier', 'function_desc', 'remark', 'image_url']:
        if field in data:
            setattr(product, field, data[field])
    # 规格型号统一
    if product.spec and product.sku != product.spec:
        product.sku = product.spec
    if not product.spec and product.sku:
        product.spec = product.sku
    if 'price' in data:
        product.price = float(data['price'])
    if 'cost_price' in data:
        product.cost_price = float(data['cost_price'])
    db.session.commit()
    return jsonify({'product': product.to_dict()})


@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({'error': '产品不存在'}), 404
    db.session.delete(product)
    db.session.commit()
    return jsonify({'message': '已删除'})


@app.route('/api/products/batch-delete', methods=['POST'])
def batch_delete_products():
    data = request.get_json()
    ids = data.get('ids', [])
    if not ids:
        return jsonify({'error': '请选择要删除的产品'}), 400
    Product.query.filter(Product.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'message': f'已删除 {len(ids)} 个产品'})


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

    # 返回相对URL（后面通过nginx /quote/uploads/images/ 访问）
    image_url = f'/uploads/images/{fname}'
    return jsonify({'url': image_url, 'filename': fname})


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

    try:
        # 保存临时文件
        tmp_path = UPLOAD_DIR / f'_ocr_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
        file.save(str(tmp_path))
        size = os.path.getsize(tmp_path)
        if size > 5 * 1024 * 1024:
            os.remove(tmp_path)
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
                    'apikey': 'helloworld',
                },
                timeout=30,
            )
        os.remove(tmp_path)

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


@app.route('/api/products/recognize', methods=['POST'])
def recognize_product():
    """识别粘贴的文本，提取产品信息"""
    data = request.get_json()
    if not data or not data.get('text', '').strip():
        return jsonify({'error': '请粘贴要识别的内容'}), 400

    text = data['text'].strip()
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    results = []
    for line in lines:
        product = parse_product_line(line)
        if product:
            results.append(product)

    if results:
        return jsonify({'products': results})
    return jsonify({'products': [], 'error': '未能从内容中识别出产品信息，请检查粘贴格式'})


def parse_product_line(line):
    """解析一行文本为产品字段。
    格式：产品名称 [tab/空格] 规格型号 [tab/空格] 厂商 [tab/空格] 功能描述 [tab/空格] 售价
    - 第1个字段：产品名称
    - 最后1个字段如果是数字：售价
    - 倒数第2个字段：功能描述 → 填入备注
    - 倒数第3个字段（如有）：厂商
    - 其余中间字段：规格型号
    """
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
            price_val = float(price_match.group(1))
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

@app.route('/api/products/import', methods=['POST'])
def import_products():
    """从Excel导入产品 — 支持多Sheet、自动识别分类"""
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
                return float(val) if val else 0
            try:
                return float(val)
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
                    )
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
    quotes = Quote.query.order_by(Quote.id.desc()).all()
    return jsonify({'quotes': [q.to_dict() for q in quotes]})


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
        remark=data.get('remark', ''),
    )

    items_data = data.get('items', [])
    total = 0
    for i, item in enumerate(items_data):
        qty = float(item.get('quantity', 1))
        up = float(item.get('unit_price', 0))
        amt = round(qty * up, 2)
        qi = QuoteItem(
            product_id=item.get('product_id'),
            product_name=item.get('product_name', ''),
            product_sku=item.get('product_sku', ''),
            product_spec=item.get('product_spec', ''),
            product_unit=item.get('product_unit', ''),
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
    quote = db.session.get(Quote, quote_id)
    if not quote:
        return jsonify({'error': '报价单不存在'}), 404
    return jsonify({'quote': quote.to_dict()})


@app.route('/api/quotes/<int:quote_id>', methods=['PUT'])
def update_quote(quote_id):
    quote = db.session.get(Quote, quote_id)
    if not quote:
        return jsonify({'error': '报价单不存在'}), 404
    data = request.get_json()
    if data.get('title') is not None: quote.title = data['title']
    if data.get('client') is not None: quote.client = data['client']
    if data.get('contact') is not None: quote.contact = data['contact']
    if data.get('phone') is not None: quote.phone = data['phone']
    if data.get('quote_date') is not None: quote.quote_date = data['quote_date']
    if data.get('valid_days') is not None: quote.valid_days = int(data['valid_days'])
    if data.get('remark') is not None: quote.remark = data['remark']
    if data.get('status') is not None: quote.status = data['status']

    if 'items' in data:
        QuoteItem.query.filter_by(quote_id=quote_id).delete()
        total = 0
        for i, item in enumerate(data['items']):
            qty = float(item.get('quantity', 1))
            up = float(item.get('unit_price', 0))
            amt = round(qty * up, 2)
            qi = QuoteItem(
                quote_id=quote_id,
                product_id=item.get('product_id'),
                product_name=item.get('product_name', ''),
                product_sku=item.get('product_sku', ''),
                product_spec=item.get('product_spec', ''),
                product_unit=item.get('product_unit', ''),
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
    quote = db.session.get(Quote, quote_id)
    if not quote:
        return jsonify({'error': '报价单不存在'}), 404
    db.session.delete(quote)
    db.session.commit()
    return jsonify({'message': '已删除'})


@app.route('/api/quotes/<int:quote_id>/export-excel', methods=['GET'])
def export_quote_excel(quote_id):
    """导出报价单 — 样式精确克隆模板.xlsx"""
    quote = db.session.get(Quote, quote_id)
    if not quote:
        return jsonify({'error': '报价单不存在'}), 404

    # 记录下载次数
    quote.download_count = (quote.download_count or 0) + 1
    db.session.commit()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = quote.title or '报价单'

    # ── 样式（精确匹配模板） ──
    YELLOW_FILL = PatternFill(start_color='FFFFFF00', end_color='FFFFFF00', fill_type='solid')
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
    col_widths = [9.66, 27.16, 18.83, 20.16, 60.16, 13.33, 7.5, 11.33, 6.5, 12.16, 18.16]
    headers = ['序号', '名称', '规格型号', '型号', '功能描述', '单价', '数量', '合计', '折扣率', '成交价', '备注']
    COL_COUNT = len(headers)

    for ci, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(ci)].width = w

    # ── 第1行：客户信息（最上面） ──
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=COL_COUNT)
    parts = []
    if quote.client: parts.append(f'客户：{quote.client}')
    if quote.contact: parts.append(f'联系人：{quote.contact}')
    if quote.phone: parts.append(f'电话：{quote.phone}')
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
            product = db.session.get(Product, item.product_id)
            if product:
                product_function_desc = product.function_desc or ''
                image_url = product.image_url

        desc = product_function_desc

        vals = [i, item.product_name, item.product_spec or '',
                item.product_spec or item.product_sku or '', desc,
                up, qty, subtotal, 0, subtotal, '']

        for ci, val in enumerate(vals, 1):
            cell = ws.cell(row=row, column=ci, value=val)
            cell.font = data_font; cell.alignment = ca; cell.border = thin_border
            if ci in (6, 8, 10): cell.number_format = money_fmt
            elif ci == 9: cell.number_format = pct_fmt

        ws.cell(row=row, column=1).border = thin_border
        ws.cell(row=row, column=COL_COUNT).border = thin_border

        # 嵌入产品图片到功能描述列
        if image_url:
            try:
                img_path = BASE_DIR / image_url.lstrip('/')
                if img_path.exists():
                    img = XLImage(str(img_path))
                    # 限制尺寸不超过单元格：宽≈400px, 高≤48px（行高54-边距6）
                    w, h = img.width, img.height
                    max_w, max_h = 400, 48
                    ratio = min(max_w / w, max_h / h, 1)
                    img.width = int(w * ratio)
                    img.height = int(h * ratio)
                    img.anchor = get_column_letter(5) + str(row)
                    ws.add_image(img)
            except Exception:
                pass

    # ── 合计行 ──
    row += 1
    ws.row_dimensions[row].height = 22
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=8)

    total_amt = quote.total_amount or 0
    tlabel = ws.cell(row=row, column=1, value=f'合计（大写）：{number_to_cn(total_amt)}')
    tlabel.font = total_font
    tlabel.alignment = Alignment(horizontal='right', vertical='center')
    tlabel.border = thin_border

    for ci in range(2, 9):
        c = ws.cell(row=row, column=ci)
        c.font = total_font; c.border = thin_border

    tc = ws.cell(row=row, column=10, value=total_amt)
    tc.font = total_font; tc.number_format = money_fmt; tc.alignment = ca
    tc.border = thin_border

    ws.cell(row=row, column=9).font = total_font
    ws.cell(row=row, column=9).border = thin_border
    ws.cell(row=row, column=11).border = thin_border
    ws.cell(row=row, column=11).font = total_font

    # ── 备注行 ──
    row += 1
    ws.row_dimensions[row].height = 18
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=COL_COUNT)
    nc = ws.cell(row=row, column=1, value=quote.remark or '注：硬件默认自验收日起维保1年，硬件1年内享受免费寄修服务。')
    nc.font = note_font
    nc.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
    for ci in range(1, COL_COUNT + 1):
        ws.cell(row=row, column=ci).border = thin_border

    # ── 打印：纵向 ──
    ws.page_setup.orientation = 'portrait'
    ws.page_setup.fitToWidth = 1
    ws.page_margins.left = 0.4; ws.page_margins.right = 0.4

    filepath = EXPORT_DIR / f'报价单_{quote.id}.xlsx'
    wb.save(filepath)
    date_str = (quote.quote_date or '').replace('-','')
    dl_name = f'{quote.client or ""}_{quote.title or ""}_{quote.contact or ""}_{date_str}'.strip('_').replace(' ','') + '.xlsx'
    return send_file(filepath, download_name=dl_name, as_attachment=True)


# ─── 报价单 HTML 预览 ───
@app.route('/api/quotes/<int:quote_id>/preview', methods=['GET'])
def preview_quote_html(quote_id):
    """返回报价单的HTML预览（17列格式匹配原模板）"""
    quote = db.session.get(Quote, quote_id)
    if not quote:
        return jsonify({'error': '报价单不存在'}), 404

    def fmt(n):
        if n is None: return '0.00'
        return f'{n:,.2f}'

    def fmt_int(n):
        if n is None: return ''
        try: return f'{int(float(n))}'
        except: return str(n)

    info_parts = []
    if quote.client: info_parts.append(f'客户：{quote.client}')
    if quote.contact: info_parts.append(f'联系人：{quote.contact}')
    if quote.phone: info_parts.append(f'电话：{quote.phone}')
    if quote.quote_date: info_parts.append(f'日期：{quote.quote_date}')
    if quote.valid_days: info_parts.append(f'有效期：{quote.valid_days}天')

    items_html = ''
    for i, item in enumerate(quote.items, 1):
        supplier = ''; supplier_sku = ''; cost = 0; prod_function_desc = ''
        if item.product_id:
            prod = db.session.get(Product, item.product_id)
            if prod:
                supplier = prod.supplier or ''
                supplier_sku = prod.spec or prod.sku or ''
                cost = prod.cost_price or 0
                prod_function_desc = prod.function_desc or ''

        qty = item.quantity if item.quantity else 1
        up = item.unit_price if item.unit_price else 0
        subtotal = round(qty * up, 2)
        deal_price = subtotal
        guide_price = round(cost * 1.5, 2) if cost else 0
        min_retail = round(cost * 1.15, 2) if cost else 0

        items_html += f'''
        <tr>
            <td>{i}</td>
            <td><strong>{item.product_name}</strong></td>
            <td>{item.product_spec or ''}</td>
            <td>{item.product_sku or supplier_sku}</td>
            <td>{prod_function_desc or ''}</td>
            <td>{fmt(up)}</td>
            <td>{fmt_int(qty)}</td>
            <td>{fmt(subtotal)}</td>
            <td>0%</td>
            <td>{fmt(deal_price)}</td>
            <td></td>
        </tr>'''

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>报价单预览 — {quote.title or '报价单'}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:"Microsoft YaHei","微软雅黑",sans-serif;background:#f0f2f5;padding:20px}}
.container{{max-width:1300px;margin:0 auto;background:#fff;padding:20px;box-shadow:0 0 20px rgba(0,0,0,.05)}}
.title{{font-size:10pt;font-weight:bold;text-align:center;padding:4px;border:1px solid #ccc;border-bottom:none;background:#FFFF00}}
.info{{font-size:9pt;color:#666;padding:4px 8px 6px;border:1px solid #ccc;border-bottom:none}}
table{{width:100%;border-collapse:collapse;font-size:11pt;font-weight:bold}}
th{{font-size:10pt;font-weight:bold;padding:3px 2px;border:1px solid #ccc;text-align:center;background:#fff}}
td{{padding:3px 2px;border:1px solid #ccc;vertical-align:middle;text-align:center}}
td:first-child{{border-left:1px solid #ccc}}
td:last-child{{border-right:1px solid #ccc}}
tr:hover td{{background:#fffbe6}}
.total-row td{{font-size:10pt;font-weight:bold;border-top:1px solid #ccc;border-bottom:1px solid #ccc;padding:4px 2px;background:#fafafa}}
.total-row td:first-child{{border-left:1px solid #ccc}}
.total-row td:last-child{{border-right:1px solid #ccc}}
.total-amount{{font-size:10pt}}
.note-row td{{font-size:10pt;font-weight:normal;text-align:left;padding:3px 8px;border:1px solid #ccc}}
.btn-bar{{display:flex;gap:8px;margin-bottom:12px}}
.btn{{padding:6px 16px;border:1px solid #ccc;border-radius:4px;background:#fff;cursor:pointer;font-size:13px;text-decoration:none;color:#333}}
.btn-primary{{background:#4361ee;color:#fff;border-color:#4361ee}}
.btn:hover{{opacity:.85}}
@media print{{
  body{{background:#fff;padding:0}}
  .container{{box-shadow:none;padding:10px}}
  .btn-bar{{display:none}}
}}
</style>
</head>
<body>
<div class="container">
  <div class="btn-bar">
    <button class="btn btn-primary" onclick="window.print()">🖨 打印</button>
    <button class="btn" onclick="parent.document.querySelector('#formModal .btn-close')?.click()">关闭</button>
  </div>
  <div class="info">{'  |  '.join(info_parts) if info_parts else ''}</div>
  <div class="title">{quote.title or '报价单'}</div>
  <div style="overflow-x:auto">
  <table>
    <thead>
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
      </tr>
    </thead>
    <tbody>
      {items_html}
    </tbody>
    <tfoot>
      <tr class="total-row">
        <td colspan="9" style="text-align:right">合计（大写）：<strong>{number_to_cn(quote.total_amount or 0)}</strong></td>
        <td class="total-amount">¥{fmt(quote.total_amount or 0)}</td>
        <td></td>
      </tr>
    </tfoot>
  </table>
  </div>
  <div class="note-row" style="margin-top:0;font-size:10pt;padding:3px 8px;border:1px solid #ccc;border-top:none">注：硬件默认自验收日起维保1年，硬件1年内享受免费寄修服务。</div>
</div>
</body>
</html>'''
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


# ─── Frontend ────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


def bump_version():
    """Auto-increment patch version: 0.1.1 → 0.1.2 … 0.1.9 → 0.2.0, etc."""
    version_file = BASE_DIR / 'version.txt'
    try:
        ver = version_file.read_text().strip()
        parts = [int(x) for x in ver.split('.')]
        if len(parts) != 3:
            parts = [0, 1, 1]
    except:
        parts = [0, 1, 1]
    parts[2] += 1
    if parts[2] >= 10:
        parts[2] = 0
        parts[1] += 1
    if parts[1] >= 10:
        parts[1] = 0
        parts[0] += 1
    new_ver = f'{parts[0]}.{parts[1]}.{parts[2]}'
    version_file.write_text(new_ver)
    return new_ver


@app.route('/api/version', methods=['GET'])
def get_version():
    version_file = BASE_DIR / 'version.txt'
    try:
        ver = version_file.read_text().strip()
    except:
        ver = '0.1.1'
    return jsonify({'version': ver})

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """提供上传的图片等静态文件"""
    return send_from_directory(UPLOAD_DIR, filename)


# ─── Init DB ────────────────────────────────────────────────

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
