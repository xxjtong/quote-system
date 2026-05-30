"""字典管理 Blueprint — 通讯方式/协议/供电/传感指标/制造商/供应商 CRUD"""
from flask import Blueprint, request, jsonify, g
from sqlalchemy import func

from extensions import db
from models import (
    DictCommMethod, DictCommProtocol, DictPowerSupply, DictSensorMetric,
    Manufacturer, Supplier,
)
from auth import require_auth, require_admin

dict_bp = Blueprint('dicts', __name__)


def _list_all(model, order_by):
    items = model.query.order_by(order_by).all()
    return jsonify({'items': [d.to_dict() for d in items]})


# ─── DictCommMethod ────────────────────────────────────────────

@dict_bp.route('/api/dicts/comm-methods', methods=['GET'])
@require_auth
def list_comm_methods():
    return _list_all(DictCommMethod, DictCommMethod.method_type.asc())


@dict_bp.route('/api/dicts/comm-methods', methods=['POST'])
@require_admin
def create_comm_method():
    data = request.get_json()
    if not data or not data.get('name', '').strip():
        return jsonify({'error': '名称不能为空'}), 400
    item = DictCommMethod(method_type=data['method_type'], name=data['name'].strip())
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@dict_bp.route('/api/dicts/comm-methods/<int:id>', methods=['PUT'])
@require_admin
def update_comm_method(id):
    item = DictCommMethod.query.get_or_404(id)
    data = request.get_json()
    if 'name' in data and data['name'] is not None:
        item.name = data['name'].strip()
    if 'method_type' in data and data['method_type'] is not None:
        item.method_type = data['method_type']
    db.session.commit()
    return jsonify(item.to_dict())


@dict_bp.route('/api/dicts/comm-methods/<int:id>', methods=['DELETE'])
@require_admin
def delete_comm_method(id):
    item = DictCommMethod.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({'ok': True})


# ─── DictCommProtocol ─────────────────────────────────────────

@dict_bp.route('/api/dicts/comm-protocols', methods=['GET'])
@require_auth
def list_comm_protocols():
    return _list_all(DictCommProtocol, DictCommProtocol.name.asc())


@dict_bp.route('/api/dicts/comm-protocols', methods=['POST'])
@require_admin
def create_comm_protocol():
    data = request.get_json()
    if not data or not data.get('name', '').strip():
        return jsonify({'error': '名称不能为空'}), 400
    item = DictCommProtocol(name=data['name'].strip())
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@dict_bp.route('/api/dicts/comm-protocols/<int:id>', methods=['PUT'])
@require_admin
def update_comm_protocol(id):
    item = DictCommProtocol.query.get_or_404(id)
    data = request.get_json()
    if 'name' in data and data['name'] is not None:
        item.name = data['name'].strip()
    db.session.commit()
    return jsonify(item.to_dict())


@dict_bp.route('/api/dicts/comm-protocols/<int:id>', methods=['DELETE'])
@require_admin
def delete_comm_protocol(id):
    item = DictCommProtocol.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({'ok': True})


# ─── DictPowerSupply ──────────────────────────────────────────

@dict_bp.route('/api/dicts/power-supplies', methods=['GET'])
@require_auth
def list_power_supplies():
    return _list_all(DictPowerSupply, DictPowerSupply.supply_category.asc())


@dict_bp.route('/api/dicts/power-supplies', methods=['POST'])
@require_admin
def create_power_supply():
    data = request.get_json()
    if not data or not data.get('name', '').strip():
        return jsonify({'error': '名称不能为空'}), 400
    item = DictPowerSupply(supply_category=data['supply_category'], name=data['name'].strip())
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@dict_bp.route('/api/dicts/power-supplies/<int:id>', methods=['PUT'])
@require_admin
def update_power_supply(id):
    item = DictPowerSupply.query.get_or_404(id)
    data = request.get_json()
    if 'name' in data and data['name'] is not None:
        item.name = data['name'].strip()
    if 'supply_category' in data and data['supply_category'] is not None:
        item.supply_category = data['supply_category']
    db.session.commit()
    return jsonify(item.to_dict())


@dict_bp.route('/api/dicts/power-supplies/<int:id>', methods=['DELETE'])
@require_admin
def delete_power_supply(id):
    item = DictPowerSupply.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({'ok': True})


# ─── DictSensorMetric ─────────────────────────────────────────

@dict_bp.route('/api/dicts/sensor-metrics', methods=['GET'])
@require_auth
def list_sensor_metrics():
    return _list_all(DictSensorMetric, DictSensorMetric.name.asc())


@dict_bp.route('/api/dicts/sensor-metrics', methods=['POST'])
@require_admin
def create_sensor_metric():
    data = request.get_json()
    if not data or not data.get('name', '').strip():
        return jsonify({'error': '名称不能为空'}), 400
    item = DictSensorMetric(name=data['name'].strip(), unit=data.get('unit', ''))
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@dict_bp.route('/api/dicts/sensor-metrics/<int:id>', methods=['PUT'])
@require_admin
def update_sensor_metric(id):
    item = DictSensorMetric.query.get_or_404(id)
    data = request.get_json()
    if 'name' in data and data['name'] is not None:
        item.name = data['name'].strip()
    if 'unit' in data:
        item.unit = data['unit']
    db.session.commit()
    return jsonify(item.to_dict())


@dict_bp.route('/api/dicts/sensor-metrics/<int:id>', methods=['DELETE'])
@require_admin
def delete_sensor_metric(id):
    item = DictSensorMetric.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({'ok': True})


# ─── Manufacturer ─────────────────────────────────────────────

@dict_bp.route('/api/dicts/manufacturers', methods=['GET'])
@require_auth
def list_manufacturers():
    query = Manufacturer.query.order_by(Manufacturer.name.asc())
    search = request.args.get('search', '').strip()
    if search:
        like = f'%{search}%'
        query = query.filter(Manufacturer.name.ilike(like))
    items = query.all()
    return jsonify({'items': [m.to_dict() for m in items]})


@dict_bp.route('/api/dicts/manufacturers', methods=['POST'])
@require_admin
def create_manufacturer():
    data = request.get_json()
    if not data or not data.get('name', '').strip():
        return jsonify({'error': '名称不能为空'}), 400
    item = Manufacturer(
        name=data['name'].strip(),
        website=data.get('website', ''),
        description=data.get('description', ''),
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@dict_bp.route('/api/dicts/manufacturers/<int:id>', methods=['PUT'])
@require_admin
def update_manufacturer(id):
    item = Manufacturer.query.get_or_404(id)
    data = request.get_json()
    if 'name' in data and data['name'] is not None:
        item.name = data['name'].strip()
    if 'website' in data:
        item.website = data['website']
    if 'description' in data:
        item.description = data['description']
    db.session.commit()
    return jsonify(item.to_dict())


@dict_bp.route('/api/dicts/manufacturers/<int:id>', methods=['DELETE'])
@require_admin
def delete_manufacturer(id):
    item = Manufacturer.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({'ok': True})


# ─── Supplier ─────────────────────────────────────────────────

@dict_bp.route('/api/dicts/suppliers', methods=['GET'])
@require_auth
def list_suppliers():
    query = Supplier.query.order_by(Supplier.name.asc())
    search = request.args.get('search', '').strip()
    if search:
        like = f'%{search}%'
        query = query.filter(Supplier.name.ilike(like))
    items = query.all()
    return jsonify({'items': [s.to_dict() for s in items]})


@dict_bp.route('/api/dicts/suppliers', methods=['POST'])
@require_admin
def create_supplier():
    data = request.get_json()
    if not data or not data.get('name', '').strip():
        return jsonify({'error': '名称不能为空'}), 400
    item = Supplier(
        name=data['name'].strip(),
        contact_person=data.get('contact_person', ''),
        phone=data.get('phone', ''),
        email=data.get('email', ''),
        website=data.get('website', ''),
        notes=data.get('notes', ''),
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@dict_bp.route('/api/dicts/suppliers/<int:id>', methods=['PUT'])
@require_admin
def update_supplier(id):
    item = Supplier.query.get_or_404(id)
    data = request.get_json()
    for f in ['name', 'contact_person', 'phone', 'email', 'website', 'notes']:
        if f in data:
            setattr(item, f, data[f])
    db.session.commit()
    return jsonify(item.to_dict())


@dict_bp.route('/api/dicts/suppliers/<int:id>', methods=['DELETE'])
@require_admin
def delete_supplier(id):
    item = Supplier.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({'ok': True})


# ─── DictProductType ──────────────────────────────────────────

@dict_bp.route('/api/dicts/product-types', methods=['GET'])
@require_auth
def list_product_types():
    from models import DictProductType
    items = DictProductType.query.order_by(DictProductType.sort_order).all()
    return jsonify({'items': [t.to_dict() for t in items]})
