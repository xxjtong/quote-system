"""规格验证 + 产品对比引擎"""
import json

from extensions import db
from models import (
    CategorySpecDefinition, DeviceCategory, Manufacturer, Supplier
)


def validate_specs(specs: dict, category_id: int) -> list:
    """根据分类的规格定义验证提交的规格值。返回错误信息列表。"""
    spec_defs = CategorySpecDefinition.query.filter_by(category_id=category_id).all()
    spec_def_map = {sd.spec_key: sd for sd in spec_defs}
    errors = []

    for key, value in specs.items():
        if key not in spec_def_map:
            continue

        sd = spec_def_map[key]

        if sd.spec_type == 'enum' and sd.options:
            options = json.loads(sd.options) if sd.options else []
            if isinstance(value, list):
                for v in value:
                    if v not in options:
                        errors.append(f"{sd.display_name}: '{v}' 不在有效选项中")
            elif value is not None and value not in options:
                errors.append(f"{sd.display_name}: '{value}' 不在有效选项中")

        elif sd.spec_type == 'number' and sd.validation:
            validation = json.loads(sd.validation) if sd.validation else {}
            try:
                num_val = float(value) if value not in (None, '') else None
                if num_val is not None:
                    if 'min' in validation and num_val < validation['min']:
                        errors.append(f"{sd.display_name}: 最小值为 {validation['min']}")
                    if 'max' in validation and num_val > validation['max']:
                        errors.append(f"{sd.display_name}: 最大值为 {validation['max']}")
            except (ValueError, TypeError):
                errors.append(f"{sd.display_name}: 必须为数字")

        elif sd.spec_type == 'boolean':
            if value is not None and not isinstance(value, bool):
                errors.append(f"{sd.display_name}: 必须为 true 或 false")

    return errors


def compare_products(products: list) -> dict:
    """生成产品对比矩阵: {spec_key: {product_id: value, ...}, ...}
    仅包含各产品间存在差异的字段。
    products 是 Product ORM 对象列表，需要预加载 M2M 关联数据。
    """
    if len(products) < 2:
        return _extract_all_specs(products)

    all_keys = set()
    product_specs = {}

    for p in products:
        specs = json.loads(p.specs) if p.specs else {}
        # Load related objects explicitly (legacy columns shadow relationships)
        _cat = db.session.get(DeviceCategory, p.category_id) if p.category_id else None
        _mfr = db.session.get(Manufacturer, p.manufacturer_id) if p.manufacturer_id else None
        _sup = db.session.get(Supplier, p.supplier_id) if p.supplier_id else None
        specs.update({
            '_model': p.model or '',
            '_category': _cat.name if _cat else '',
            '_manufacturer': _mfr.name if _mfr else '',
            '_supplier': _sup.name if _sup else '',
            '_unit': p.unit or '',
            '_price': str(p.price or 0),
            '_status': p.status or 'active',
            '_function_desc': p.function_desc or '',
        })
        product_specs[p.id] = specs
        all_keys.update(specs.keys())

    result = {}
    for key in sorted(all_keys):
        values = {p.id: product_specs[p.id].get(key) for p in products}
        unique_vals = set(str(v) for v in values.values())
        if len(unique_vals) > 1:
            result[key] = values

    return result


def _extract_all_specs(products: list) -> dict:
    result = {}
    for p in products:
        specs = json.loads(p.specs) if p.specs else {}
        for k, v in specs.items():
            if k not in result:
                result[k] = {}
            result[k][p.id] = v
    return result
