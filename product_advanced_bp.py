"""产品高级功能 Blueprint — M2M映射 / 多图 / 依赖 / 对比 / 规格书"""
import json

from flask import Blueprint, request, jsonify, g, render_template_string

from extensions import db
from models import (
    Product, ProductCommMethod, ProductCommProtocol, ProductPowerSupply,
    ProductHardwareInterface, ProductSensorCapability, ProductImage,
    ProductDependency, User,
)
from auth import require_auth, require_admin
from spec_service import compare_products

product_advanced_bp = Blueprint('product_advanced', __name__)


def _get_product_or_404(id):
    product = db.session.get(Product, id)
    if not product:
        return None
    return product


def _check_product_permission(product):
    """检查当前用户是否有权限编辑该产品（管理员或创建者）"""
    is_admin = hasattr(g, 'current_user') and g.current_user and g.current_user.role == 'admin'
    if not is_admin and product.created_by != g.current_user.id:
        return False
    return True


# ─── M2M: Communication Methods ───────────────────────────────

@product_advanced_bp.route('/api/products/<int:id>/comm-methods', methods=['POST'])
@require_auth
def replace_comm_methods(id):
    product = _get_product_or_404(id)
    if product is None:
        return jsonify({'error': '产品不存在'}), 404
    if not _check_product_permission(product):
        return jsonify({'error': '只能编辑自己创建的产品'}), 403
    data = request.get_json()
    methods = data.get('methods', [])
    ProductCommMethod.query.filter_by(product_id=id).delete()
    from models import DictCommMethod as DCM
    for m in methods:
        mid = m.get('method_id')
        if not mid and m.get('_custom_name'):
            existing = DCM.query.filter_by(name=m['_custom_name']).first()
            if not existing:
                existing = DCM(name=m['_custom_name'], method_type='other')
                db.session.add(existing)
                db.session.flush()
            mid = existing.id
        if mid:
            db.session.add(ProductCommMethod(
                product_id=id, method_id=mid,
                details=m.get('details', ''),
            ))
    db.session.commit()
    return jsonify({'ok': True})


# ─── M2M: Communication Protocols ─────────────────────────────

@product_advanced_bp.route('/api/products/<int:id>/comm-protocols', methods=['POST'])
@require_auth
def replace_comm_protocols(id):
    product = _get_product_or_404(id)
    if product is None:
        return jsonify({'error': '产品不存在'}), 404
    if not _check_product_permission(product):
        return jsonify({'error': '只能编辑自己创建的产品'}), 403
    data = request.get_json()
    protocols = data.get('methods', data.get('protocols', []))
    ProductCommProtocol.query.filter_by(product_id=id).delete()
    from models import DictCommProtocol as DCP
    for p in protocols:
        pid = p.get('protocol_id')
        if not pid and p.get('_custom_name'):
            existing = DCP.query.filter_by(name=p['_custom_name']).first()
            if not existing:
                existing = DCP(name=p['_custom_name'])
                db.session.add(existing)
                db.session.flush()
            pid = existing.id
        if pid:
            db.session.add(ProductCommProtocol(
                product_id=id, protocol_id=pid,
                direction=p.get('direction', 'both'),
            ))
    db.session.commit()
    return jsonify({'ok': True})


# ─── M2M: Power Supplies ─────────────────────────────────────

@product_advanced_bp.route('/api/products/<int:id>/power-supplies', methods=['POST'])
@require_auth
def replace_power_supplies(id):
    product = _get_product_or_404(id)
    if product is None:
        return jsonify({'error': '产品不存在'}), 404
    if not _check_product_permission(product):
        return jsonify({'error': '只能编辑自己创建的产品'}), 403
    data = request.get_json()
    supplies = data.get('methods', data.get('supplies', []))
    ProductPowerSupply.query.filter_by(product_id=id).delete()
    from models import DictPowerSupply as DPS
    for s in supplies:
        pid = s.get('power_id')
        if not pid and s.get('_custom_name'):
            existing = DPS.query.filter_by(name=s['_custom_name']).first()
            if not existing:
                existing = DPS(name=s['_custom_name'], supply_category='other')
                db.session.add(existing)
                db.session.flush()
            pid = existing.id
        if pid:
            db.session.add(ProductPowerSupply(
                product_id=id, power_id=pid,
                voltage_range=s.get('voltage_range', ''),
                battery_life=s.get('battery_life', ''),
            ))
    db.session.commit()
    return jsonify({'ok': True})


# ─── Hardware Interfaces ──────────────────────────────────────

@product_advanced_bp.route('/api/products/<int:id>/hardware-interfaces', methods=['GET'])
@require_auth
def list_hardware_interfaces(id):
    product = _get_product_or_404(id)
    if product is None:
        return jsonify({'error': '产品不存在'}), 404
    items = ProductHardwareInterface.query.filter_by(product_id=id).order_by(
        ProductHardwareInterface.id
    ).all()
    return jsonify({'items': [i.to_dict() for i in items]})


@product_advanced_bp.route('/api/products/<int:id>/hardware-interfaces', methods=['POST'])
@require_auth
def replace_hardware_interfaces(id):
    product = _get_product_or_404(id)
    if product is None:
        return jsonify({'error': '产品不存在'}), 404
    if not _check_product_permission(product):
        return jsonify({'error': '只能编辑自己创建的产品'}), 403
    data = request.get_json()
    interfaces = data.get('methods', data.get('interfaces', []))
    ProductHardwareInterface.query.filter_by(product_id=id).delete()
    for iface in interfaces:
        db.session.add(ProductHardwareInterface(
            product_id=id,
            interface_name=iface['interface_name'],
            quantity=iface.get('quantity', 1),
            description=iface.get('description', ''),
        ))
    db.session.commit()
    return jsonify({'ok': True})


@product_advanced_bp.route('/api/products/<int:id>/hardware-interfaces/<int:iface_id>', methods=['DELETE'])
@require_auth
def delete_hardware_interface(id, iface_id):
    product = _get_product_or_404(id)
    if product is None:
        return jsonify({'error': '产品不存在'}), 404
    if not _check_product_permission(product):
        return jsonify({'error': '只能编辑自己创建的产品'}), 403
    iface = ProductHardwareInterface.query.get_or_404(iface_id)
    db.session.delete(iface)
    db.session.commit()
    return jsonify({'ok': True})


# ─── Sensor Capabilities ─────────────────────────────────────

@product_advanced_bp.route('/api/products/<int:id>/sensor-capabilities', methods=['POST'])
@require_auth
def replace_sensor_capabilities(id):
    product = _get_product_or_404(id)
    if product is None:
        return jsonify({'error': '产品不存在'}), 404
    if not _check_product_permission(product):
        return jsonify({'error': '只能编辑自己创建的产品'}), 403
    data = request.get_json()
    capabilities = data.get('methods', data.get('capabilities', []))
    ProductSensorCapability.query.filter_by(product_id=id).delete()
    from models import DictSensorMetric as DSM
    for c in capabilities:
        mid = c.get('metric_id')
        if not mid and c.get('_custom_name'):
            existing = DSM.query.filter_by(name=c['_custom_name']).first()
            if not existing:
                existing = DSM(name=c['_custom_name'])
                db.session.add(existing)
                db.session.flush()
            mid = existing.id
        if mid:
            db.session.add(ProductSensorCapability(
                product_id=id, metric_id=mid,
                measure_range=c.get('measure_range', ''),
                accuracy=c.get('accuracy', ''),
                resolution=c.get('resolution', ''),
            ))
    db.session.commit()
    return jsonify({'ok': True})


# ─── Images ──────────────────────────────────────────────────

@product_advanced_bp.route('/api/products/<int:id>/images', methods=['GET'])
@require_auth
def list_product_images(id):
    product = _get_product_or_404(id)
    if product is None:
        return jsonify({'error': '产品不存在'}), 404
    items = ProductImage.query.filter_by(product_id=id).order_by(ProductImage.sort_order).all()
    return jsonify({'items': [img.to_dict() for img in items]})


@product_advanced_bp.route('/api/products/<int:id>/images', methods=['POST'])
@require_auth
def replace_product_images(id):
    product = _get_product_or_404(id)
    if product is None:
        return jsonify({'error': '产品不存在'}), 404
    if not _check_product_permission(product):
        return jsonify({'error': '只能编辑自己创建的产品'}), 403
    data = request.get_json()
    images = data.get('images', [])
    # 清理被移除的旧图片文件
    from pathlib import Path
    new_urls = {img.get('url', '') for img in images}
    old_imgs = ProductImage.query.filter_by(product_id=id).all()
    for oi in old_imgs:
        if oi.url and oi.url.startswith('/uploads/') and oi.url not in new_urls:
            fpath = Path(__file__).parent / oi.url.lstrip('/')
            try:
                fpath.unlink(missing_ok=True)
                thumb = fpath.parent / (fpath.stem + '_thumb.jpg')
                thumb.unlink(missing_ok=True)
            except Exception:
                pass
    ProductImage.query.filter_by(product_id=id).delete()
    # Ensure at least one primary image
    has_primary = any(img.get('is_primary') for img in images)
    for i, img in enumerate(images):
        is_primary = img.get('is_primary', False) or (not has_primary and i == 0)
        db.session.add(ProductImage(
            product_id=id,
            url=img['url'],
            is_primary=is_primary,
            sort_order=img.get('sort_order', i),
            alt_text=img.get('alt_text', ''),
        ))
    db.session.commit()
    return jsonify({'ok': True})


# ─── Dependencies ─────────────────────────────────────────────

@product_advanced_bp.route('/api/products/<int:id>/dependencies', methods=['GET'])
@require_auth
def list_dependencies(id):
    product = _get_product_or_404(id)
    if product is None:
        return jsonify({'error': '产品不存在'}), 404
    items = ProductDependency.query.filter_by(product_id=id).order_by(
        ProductDependency.sort_order
    ).all()
    return jsonify({'items': [d.to_dict() for d in items]})


@product_advanced_bp.route('/api/products/<int:id>/dependencies', methods=['POST'])
@require_auth
def create_dependency(id):
    product = _get_product_or_404(id)
    if product is None:
        return jsonify({'error': '产品不存在'}), 404
    if not _check_product_permission(product):
        return jsonify({'error': '只能编辑自己创建的产品'}), 403
    data = request.get_json()
    dep_product_id = data.get('depends_on_product_id')
    dep_category_id = data.get('depends_on_category_id')
    if not dep_product_id and not dep_category_id:
        return jsonify({'error': '必须指定依赖的产品或分类'}), 400
    dep = ProductDependency(
        product_id=id,
        depends_on_product_id=dep_product_id,
        depends_on_category_id=dep_category_id,
        dependency_type=data.get('dependency_type', 'required'),
        description=data.get('description', ''),
        sort_order=data.get('sort_order', 0),
    )
    db.session.add(dep)
    db.session.commit()
    return jsonify(dep.to_dict()), 201


@product_advanced_bp.route('/api/products/<int:id>/dependencies/<int:dep_id>', methods=['PUT'])
@require_auth
def update_dependency(id, dep_id):
    product = _get_product_or_404(id)
    if product is None:
        return jsonify({'error': '产品不存在'}), 404
    if not _check_product_permission(product):
        return jsonify({'error': '只能编辑自己创建的产品'}), 403
    dep = ProductDependency.query.get_or_404(dep_id)
    data = request.get_json()
    for f in ['depends_on_product_id', 'depends_on_category_id', 'dependency_type',
              'description', 'sort_order']:
        if f in data:
            setattr(dep, f, data[f])
    db.session.commit()
    return jsonify(dep.to_dict())


@product_advanced_bp.route('/api/products/<int:id>/dependencies/<int:dep_id>', methods=['DELETE'])
@require_auth
def delete_dependency(id, dep_id):
    product = _get_product_or_404(id)
    if product is None:
        return jsonify({'error': '产品不存在'}), 404
    if not _check_product_permission(product):
        return jsonify({'error': '只能编辑自己创建的产品'}), 403
    dep = ProductDependency.query.get_or_404(dep_id)
    db.session.delete(dep)
    db.session.commit()
    return jsonify({'ok': True})


# ─── Product Comparison ──────────────────────────────────────

@product_advanced_bp.route('/api/products/compare', methods=['GET'])
@require_auth
def compare_products_endpoint():
    ids_str = request.args.get('ids', '')
    if not ids_str:
        return jsonify({'error': '请提供产品ID'}), 400
    try:
        ids = [int(x.strip()) for x in ids_str.split(',') if x.strip()]
    except ValueError:
        return jsonify({'error': 'ID格式错误'}), 400
    if len(ids) < 2:
        return jsonify({'error': '至少选择2个产品进行对比'}), 400
    if len(ids) > 5:
        return jsonify({'error': '最多对比5个产品'}), 400

    products = Product.query.filter(Product.id.in_(ids)).all()
    if len(products) < 2:
        return jsonify({'error': '未找到足够的产品'}), 404

    matrix = compare_products(products)
    return jsonify({
        'products': [p.to_dict() for p in products],
        'comparison': matrix,
    })


# ─── Spec Sheet ──────────────────────────────────────────────

@product_advanced_bp.route('/api/products/<int:id>/spec-sheet', methods=['GET'])
def spec_sheet(id):
    # 支持 query param token 认证（浏览器直接访问时无法设置 Authorization header）
    from flask import request as _req
    from flask import current_app
    token = (_req.headers.get('Authorization', '').replace('Bearer ', '')
             or _req.args.get('token', ''))
    if not token:
        return jsonify({'error': '请先登录'}), 401
    try:
        import jwt as _jwt
        data = _jwt.decode(token, current_app.config['JWT_SECRET'], algorithms=['HS256'])
        user = db.session.get(User, data['user_id'])
        if not user or not user.is_active:
            return jsonify({'error': '请先登录'}), 401
    except Exception:
        return jsonify({'error': '请先登录'}), 401

    product = db.session.get(Product, id)
    if not product:
        return jsonify({'error': '产品不存在'}), 404

    # Gather related data (load explicitly due to legacy column name conflicts)
    from models import DeviceCategory, Manufacturer, Supplier
    _cat = db.session.get(DeviceCategory, product.category_id) if product.category_id else None
    _mfr = db.session.get(Manufacturer, product.manufacturer_id) if product.manufacturer_id else None
    _sup = db.session.get(Supplier, product.supplier_id) if product.supplier_id else None
    specs = json.loads(product.specs) if product.specs else {}
    comm_methods = ProductCommMethod.query.filter_by(product_id=id).all()
    comm_protocols = ProductCommProtocol.query.filter_by(product_id=id).all()
    power_supplies = ProductPowerSupply.query.filter_by(product_id=id).all()
    hw_interfaces = ProductHardwareInterface.query.filter_by(product_id=id).all()
    sensor_caps = ProductSensorCapability.query.filter_by(product_id=id).all()
    images = ProductImage.query.filter_by(product_id=id).order_by(ProductImage.sort_order).all()
    dependencies = ProductDependency.query.filter_by(product_id=id).order_by(
        ProductDependency.sort_order
    ).all()

    html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ product.name }} - 规格书</title>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;max-width:960px;margin:0 auto;padding:20px;color:#333}
h1{font-size:24px;border-bottom:2px solid #1a73e8;padding-bottom:8px}
h2{font-size:18px;margin:24px 0 12px;color:#1a73e8}
table{width:100%;border-collapse:collapse;margin:8px 0 16px}
th,td{border:1px solid #ddd;padding:8px 12px;text-align:left;font-size:14px}
th{background:#f5f5f5;font-weight:600;width:180px}
.spec-label{font-weight:600;color:#555}
.info-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:12px 0}
.info-item{padding:8px 12px;background:#f9f9f9;border-radius:4px}
.info-label{font-size:12px;color:#888}
.info-value{font-size:14px;font-weight:500}
</style>
</head>
<body>
<h1>{{ product.name }}</h1>
<div class="info-grid">
<div class="info-item"><div class="info-label">型号</div><div class="info-value">{{ product.model or '-' }}</div></div>
<div class="info-item"><div class="info-label">品牌/制造商</div><div class="info-value">{{ manufacturer_name or '-' }}</div></div>
<div class="info-item"><div class="info-label">产品分类</div><div class="info-value">{{ category_name or '-' }}</div></div>
<div class="info-item"><div class="info-label">供应商</div><div class="info-value">{{ supplier_name or '-' }}</div></div>
<div class="info-item"><div class="info-label">单价</div><div class="info-value">{{ product.price or 0 }}</div></div>
<div class="info-item"><div class="info-label">状态</div><div class="info-value">{{ product.status or 'active' }}</div></div>
</div>

{% if product.function_desc %}
<h2>功能描述</h2>
<p>{{ product.function_desc }}</p>
{% endif %}

{% if specs %}
<h2>规格参数</h2>
<table>
<tbody>
{% for key, value in specs.items() %}
<tr><td class="spec-label">{{ key }}</td><td>{{ value }}</td></tr>
{% endfor %}
</tbody>
</table>
{% endif %}

{% if comm_methods %}
<h2>通讯方式</h2>
<table>
<thead><tr><th>方法</th><th>类型</th><th>详情</th></tr></thead>
<tbody>
{% for m in comm_methods %}
<tr><td>{{ m.method.name if m.method else '' }}</td><td>{{ m.method.method_type if m.method else '' }}</td><td>{{ m.details or '' }}</td></tr>
{% endfor %}
</tbody>
</table>
{% endif %}

{% if comm_protocols %}
<h2>通讯协议</h2>
<table>
<thead><tr><th>协议</th><th>方向</th></tr></thead>
<tbody>
{% for p in comm_protocols %}
<tr><td>{{ p.protocol.name if p.protocol else '' }}</td><td>{{ p.direction }}</td></tr>
{% endfor %}
</tbody>
</table>
{% endif %}

{% if power_supplies %}
<h2>供电方式</h2>
<table>
<thead><tr><th>供电</th><th>类别</th><th>电压范围</th><th>续航</th></tr></thead>
<tbody>
{% for s in power_supplies %}
<tr><td>{{ s.power.name if s.power else '' }}</td><td>{{ s.power.supply_category if s.power else '' }}</td><td>{{ s.voltage_range or '' }}</td><td>{{ s.battery_life or '' }}</td></tr>
{% endfor %}
</tbody>
</table>
{% endif %}

{% if hw_interfaces %}
<h2>硬件接口</h2>
<table>
<thead><tr><th>接口</th><th>数量</th><th>描述</th></tr></thead>
<tbody>
{% for iface in hw_interfaces %}
<tr><td>{{ iface.interface_name }}</td><td>{{ iface.quantity }}</td><td>{{ iface.description or '' }}</td></tr>
{% endfor %}
</tbody>
</table>
{% endif %}

{% if sensor_caps %}
<h2>传感能力</h2>
<table>
<thead><tr><th>指标</th><th>量程</th><th>精度</th><th>分辨率</th></tr></thead>
<tbody>
{% for sc in sensor_caps %}
<tr><td>{{ sc.metric.name if sc.metric else '' }} ({{ sc.metric.unit if sc.metric else '' }})</td><td>{{ sc.measure_range or '' }}</td><td>{{ sc.accuracy or '' }}</td><td>{{ sc.resolution or '' }}</td></tr>
{% endfor %}
</tbody>
</table>
{% endif %}

{% if images %}
<h2>产品图片</h2>
<div style="display:flex;flex-wrap:wrap;gap:12px">
{% for img in images %}
<div><img src="{{ img.url }}" alt="{{ img.alt_text or '' }}" style="max-width:200px;max-height:200px;border:1px solid #ddd;border-radius:4px"></div>
{% endfor %}
</div>
{% endif %}

{% if dependencies %}
<h2>依赖关系</h2>
<table>
<thead><tr><th>类型</th><th>目标</th><th>描述</th></tr></thead>
<tbody>
{% for d in dependencies %}
<tr><td>{{ d.dependency_type }}</td><td>{{ d.target_product.name if d.target_product else (d.target_category.name if d.target_category else '-') }}</td><td>{{ d.description or '' }}</td></tr>
{% endfor %}
</tbody>
</table>
{% endif %}
</body>
</html>'''

    return render_template_string(html,
        product=product,
        manufacturer_name=_mfr.name if _mfr else '',
        category_name=_cat.name if _cat else '',
        supplier_name=_sup.name if _sup else '',
        specs=specs,
        comm_methods=comm_methods,
        comm_protocols=comm_protocols,
        power_supplies=power_supplies,
        hw_interfaces=hw_interfaces,
        sensor_caps=sensor_caps,
        images=images,
        dependencies=dependencies,
    )


# ─── Advanced Search ──────────────────────────────────────────

@product_advanced_bp.route('/api/products/advanced-search', methods=['GET'])
@require_auth
def advanced_search():
    category_id = request.args.get('category_id', type=int)
    manufacturer_id = request.args.get('manufacturer_id', type=int)
    comm_method_ids_str = request.args.get('comm_method_ids', '')
    protocol_ids_str = request.args.get('protocol_ids', '')
    power_ids_str = request.args.get('power_ids', '')
    metric_ids_str = request.args.get('metric_ids', '')
    status = request.args.get('status', '').strip()
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    query = Product.query

    if category_id:
        query = query.filter(Product.category_id == category_id)
    if manufacturer_id:
        query = query.filter(Product.manufacturer_id == manufacturer_id)
    if status:
        query = query.filter(Product.status == status)
    if search:
        like = f'%{search}%'
        query = query.filter(
            db.or_(Product.name.ilike(like), Product.model.ilike(like),
                   Product.function_desc.ilike(like))
        )

    # M2M filters via subqueries (avoids cross-join duplication)
    if comm_method_ids_str:
        ids = [int(x) for x in comm_method_ids_str.split(',') if x.strip()]
        if ids:
            query = query.filter(Product.id.in_(
                db.session.query(ProductCommMethod.product_id).filter(
                    ProductCommMethod.method_id.in_(ids)
                )
            ))

    if protocol_ids_str:
        ids = [int(x) for x in protocol_ids_str.split(',') if x.strip()]
        if ids:
            query = query.filter(Product.id.in_(
                db.session.query(ProductCommProtocol.product_id).filter(
                    ProductCommProtocol.protocol_id.in_(ids)
                )
            ))

    if power_ids_str:
        ids = [int(x) for x in power_ids_str.split(',') if x.strip()]
        if ids:
            query = query.filter(Product.id.in_(
                db.session.query(ProductPowerSupply.product_id).filter(
                    ProductPowerSupply.power_id.in_(ids)
                )
            ))

    if metric_ids_str:
        ids = [int(x) for x in metric_ids_str.split(',') if x.strip()]
        if ids:
            query = query.filter(Product.id.in_(
                db.session.query(ProductSensorCapability.product_id).filter(
                    ProductSensorCapability.metric_id.in_(ids)
                )
            ))

    total = query.count()
    products = query.order_by(Product.id.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    return jsonify({
        'items': [p.to_dict() for p in products],
        'total': total,
        'page': page,
        'per_page': per_page,
    })
