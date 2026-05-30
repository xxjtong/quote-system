"""分类管理 Blueprint — 分类树 + 规格定义 CRUD"""
import json as json_lib

from flask import Blueprint, request, jsonify, g

from extensions import db
from models import DeviceCategory, CategorySpecDefinition
from auth import require_auth, require_admin

category_bp = Blueprint('categories', __name__)


# ─── Category CRUD ────────────────────────────────────────────

@category_bp.route('/api/categories', methods=['GET'])
@require_auth
def list_categories():
    cats = DeviceCategory.query.order_by(DeviceCategory.level, DeviceCategory.sort_order).all()
    return jsonify({
        'items': [{
            **c.to_dict(),
            'spec_definitions': [sd.to_dict() for sd in c.spec_definitions] if c.spec_definitions else [],
        } for c in cats]
    })


@category_bp.route('/api/categories/tree', methods=['GET'])
@require_auth
def get_category_tree():
    all_cats = DeviceCategory.query.filter_by(is_active=True).order_by(DeviceCategory.level, DeviceCategory.sort_order).all()
    cat_map = {}
    for c in all_cats:
        d = c.to_dict()
        d['children'] = []
        d['spec_definitions'] = [sd.to_dict() for sd in c.spec_definitions] if c.spec_definitions else []
        cat_map[c.id] = d
    roots = []
    for c in all_cats:
        node = cat_map[c.id]
        if c.parent_id and c.parent_id in cat_map:
            cat_map[c.parent_id]['children'].append(node)
        else:
            roots.append(node)
    return jsonify({'tree': roots})


@category_bp.route('/api/categories', methods=['POST'])
@require_admin
def create_category():
    data = request.get_json()
    if not data or not data.get('name', '').strip():
        return jsonify({'error': '分类名称不能为空'}), 400

    name = data['name'].strip()
    parent_id = data.get('parent_id')

    level = data.get('level')
    if level is None and parent_id:
        parent = db.session.get(DeviceCategory, parent_id)
        if parent:
            level = parent.level + 1
    if level is None:
        level = 1

    cat = DeviceCategory(
        name=name,
        slug=data.get('slug', ''),
        parent_id=parent_id,
        level=level,
        sort_order=data.get('sort_order', 0),
    )
    db.session.add(cat)
    db.session.commit()
    return jsonify(cat.to_dict()), 201


@category_bp.route('/api/categories/<int:id>', methods=['PUT'])
@require_admin
def update_category(id):
    cat = DeviceCategory.query.get_or_404(id)
    data = request.get_json()
    for f in ['name', 'slug', 'parent_id', 'level', 'sort_order', 'is_active']:
        if f in data:
            setattr(cat, f, data[f])
    db.session.commit()
    return jsonify(cat.to_dict())


@category_bp.route('/api/categories/<int:id>', methods=['DELETE'])
@require_admin
def delete_category(id):
    cat = DeviceCategory.query.get_or_404(id)
    # 检查是否有子分类
    if DeviceCategory.query.filter_by(parent_id=id).first():
        return jsonify({'error': '请先删除子分类'}), 400
    db.session.delete(cat)
    db.session.commit()
    return jsonify({'ok': True})


# ─── Spec Definition CRUD ─────────────────────────────────────

_VALID_SPEC_TYPES = {'string', 'number', 'enum', 'boolean', 'range'}


@category_bp.route('/api/categories/<int:cat_id>/spec-definitions', methods=['GET'])
@require_auth
def list_spec_definitions(cat_id):
    cat = DeviceCategory.query.get_or_404(cat_id)
    defs = CategorySpecDefinition.query.filter_by(category_id=cat_id).order_by(
        CategorySpecDefinition.sort_order
    ).all()
    return jsonify({'items': [sd.to_dict() for sd in defs]})


@category_bp.route('/api/categories/<int:cat_id>/spec-definitions', methods=['POST'])
@require_admin
def create_spec_definition(cat_id):
    cat = DeviceCategory.query.get_or_404(cat_id)
    data = request.get_json()
    if not data or not data.get('spec_key', '').strip():
        return jsonify({'error': '规格键名不能为空'}), 400

    spec_type = data.get('spec_type', 'string')
    if spec_type not in _VALID_SPEC_TYPES:
        return jsonify({'error': f'规格类型必须为 {", ".join(sorted(_VALID_SPEC_TYPES))}'}), 400

    options = data.get('options')
    validation = data.get('validation')

    sd = CategorySpecDefinition(
        category_id=cat_id,
        spec_key=data['spec_key'].strip(),
        display_name=data.get('display_name', data['spec_key'].strip()),
        spec_type=spec_type,
        unit=data.get('unit', ''),
        sort_order=data.get('sort_order', 0),
        is_filterable=data.get('is_filterable', True),
        is_comparable=data.get('is_comparable', True),
        display_group=data.get('display_group', ''),
        options=json_lib.dumps(options, ensure_ascii=False) if options else None,
        validation=json_lib.dumps(validation, ensure_ascii=False) if validation else None,
    )
    db.session.add(sd)
    db.session.commit()
    return jsonify(sd.to_dict()), 201


@category_bp.route('/api/dicts/spec-definitions/<int:id>', methods=['PUT'])
@require_admin
def update_spec_definition(id):
    sd = CategorySpecDefinition.query.get_or_404(id)
    data = request.get_json()
    for f in ['spec_key', 'display_name', 'spec_type', 'unit', 'sort_order',
              'is_filterable', 'is_comparable', 'display_group']:
        if f in data:
            setattr(sd, f, data[f])
    if 'spec_type' in data and data['spec_type'] not in _VALID_SPEC_TYPES:
        return jsonify({'error': f'规格类型必须为 {", ".join(sorted(_VALID_SPEC_TYPES))}'}), 400
    # JSON fields
    for json_f in ['options', 'validation']:
        if json_f in data:
            val = data[json_f]
            setattr(sd, json_f, json_lib.dumps(val, ensure_ascii=False) if val else None)
    db.session.commit()
    return jsonify(sd.to_dict())


@category_bp.route('/api/dicts/spec-definitions/<int:id>', methods=['DELETE'])
@require_admin
def delete_spec_definition(id):
    sd = CategorySpecDefinition.query.get_or_404(id)
    db.session.delete(sd)
    db.session.commit()
    return jsonify({'ok': True})
