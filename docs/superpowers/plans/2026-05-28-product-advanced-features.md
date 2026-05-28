# Product Advanced Features — 移植 product-db 产品功能到 quote-system

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 product-db 的产品高级功能（字典表、分类树、规格定义、M2M 映射、产品对比、规格书、产品变体、多图）以纯增量方式移植到 quote-system，不迁移数据，不破坏现有功能。

**Architecture:** 新增 12 张表 + 扩展 Product 表 9 个可选字段，新增 3 个 Flask Blueprint（字典/分类/产品高级），新增 5 个 Vue 页面 + 扩展产品表单。所有新字段 nullable，新旧分类/供应商双轨并存。

**Tech Stack:** Flask + SQLAlchemy + Flask-Migrate (Alembic) + SQLite + Vue 3 `<script setup>` + Composition API

**Estimated effort:** 14-16 人天，分 5 个 Phase，每 Phase 独立可交付。

---

## File Structure

```
quote-system/
├── models.py                          # [MODIFY] 新增 12 表 + Product 扩展字段
├── dict_bp.py                         # [CREATE] 字典 CRUD API
├── category_bp.py                     # [CREATE] 分类树 + 规格定义 API
├── product_advanced_bp.py             # [CREATE] 产品对比/规格书/M2M/依赖/多图 API
├── products_bp.py                     # [MODIFY] 少量扩展: 支持新字段读写
├── spec_service.py                    # [CREATE] 规格验证 + 产品对比引擎
├── app.py                             # [MODIFY] 注册新 Blueprint
├── frontend/src/
│   ├── router/index.js                # [MODIFY] 新增路由
│   ├── api.js                         # [CREATE] 新 API 函数（或扩展 useApi.js）
│   ├── views/
│   │   ├── DictManageView.vue         # [CREATE] 字典管理页
│   │   ├── CategoryManageView.vue     # [CREATE] 分类树管理页
│   │   ├── ProductCompareView.vue     # [CREATE] 产品对比页
│   │   └── ProductSpecSheet.vue       # [CREATE] 规格书页
│   └── components/
│       ├── ProductFormModal.vue       # [MODIFY] 扩展: 高级规格/M2M/多图 Tab
│       ├── ProductDetailModal.vue     # [MODIFY] 扩展: 显示 M2M/规格/变体
│       ├── SpecFieldGroup.vue         # [CREATE] 动态规格字段组
│       ├── M2MSelector.vue            # [CREATE] 多对多映射选择器
│       ├── MultiImageUpload.vue       # [CREATE] 多图上传组件
│       └── CategoryTree.vue           # [CREATE] 分类树组件
└── tests/
    ├── test_dicts.py                  # [CREATE]
    ├── test_categories.py             # [CREATE]
    └── test_product_advanced.py       # [CREATE]
```

---

## Phase 1: Database Foundation (模型 + 迁移)

### Task 1.1: 新增字典表、分类表、供应商表模型

**Files:**
- Modify: `models.py` (append after existing models)

**在新表之后追加以下模型（在 `class LoginLog` 之后）：**

```python
# ═══════════════════════════════════════════════════════════════
# v2.6.0 新增: 产品高级功能 — 字典表 / 分类树 / M2M 映射 / 规格定义
# ═══════════════════════════════════════════════════════════════

class Manufacturer(db.Model):
    """制造商/品牌"""
    __tablename__ = 'manufacturers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    website = db.Column(db.String(500), nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name,
            'website': self.website or '', 'description': self.description or '',
        }


class DictCommMethod(db.Model):
    """通讯方式字典 (有线/无线)"""
    __tablename__ = 'dict_comm_methods'
    id = db.Column(db.Integer, primary_key=True)
    method_type = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(50), nullable=False, unique=True)

    def to_dict(self):
        return {'id': self.id, 'method_type': self.method_type, 'name': self.name}


class DictCommProtocol(db.Model):
    """通讯协议字典"""
    __tablename__ = 'dict_comm_protocols'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)

    def to_dict(self):
        return {'id': self.id, 'name': self.name}


class DictPowerSupply(db.Model):
    """供电方式字典"""
    __tablename__ = 'dict_power_supplies'
    id = db.Column(db.Integer, primary_key=True)
    supply_category = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(50), nullable=False, unique=True)

    def to_dict(self):
        return {'id': self.id, 'supply_category': self.supply_category, 'name': self.name}


class DictSensorMetric(db.Model):
    """传感指标字典"""
    __tablename__ = 'dict_sensor_metrics'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    unit = db.Column(db.String(20), nullable=True)

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'unit': self.unit or ''}


class Supplier(db.Model):
    """供应商（规范化表，与 Product.supplier 字符串并存）"""
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    contact_person = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(200), nullable=True)
    website = db.Column(db.String(500), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name,
            'contact_person': self.contact_person or '',
            'phone': self.phone or '', 'email': self.email or '',
            'website': self.website or '', 'notes': self.notes or '',
        }


class DeviceCategory(db.Model):
    """设备分类树 (2级+)"""
    __tablename__ = 'device_categories'
    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('device_categories.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=True, index=True)
    level = db.Column(db.Integer, default=1)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    parent = db.relationship('DeviceCategory', remote_side=[id], backref='children')
    spec_definitions = db.relationship(
        'CategorySpecDefinition', backref='category',
        cascade='all, delete-orphan', order_by='CategorySpecDefinition.sort_order'
    )

    def to_dict(self):
        return {
            'id': self.id, 'parent_id': self.parent_id, 'name': self.name,
            'slug': self.slug or '', 'level': self.level or 1,
            'sort_order': self.sort_order, 'is_active': self.is_active,
        }


class CategorySpecDefinition(db.Model):
    """分类动态规格定义"""
    __tablename__ = 'category_spec_definitions'
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('device_categories.id', ondelete='CASCADE'), nullable=False)
    spec_key = db.Column(db.String(100), nullable=False)
    display_name = db.Column(db.String(200), nullable=False)
    spec_type = db.Column(db.String(50), nullable=False)  # string/number/enum/boolean/range
    unit = db.Column(db.String(50), nullable=True)
    sort_order = db.Column(db.Integer, default=0)
    is_filterable = db.Column(db.Boolean, default=True)
    is_comparable = db.Column(db.Boolean, default=True)
    display_group = db.Column(db.String(100), nullable=True)
    options = db.Column(db.Text, nullable=True)   # JSON: enum 选项列表
    validation = db.Column(db.Text, nullable=True) # JSON: {min, max} for number

    def to_dict(self):
        return {
            'id': self.id, 'category_id': self.category_id,
            'spec_key': self.spec_key, 'display_name': self.display_name,
            'spec_type': self.spec_type, 'unit': self.unit or '',
            'sort_order': self.sort_order, 'is_filterable': self.is_filterable,
            'is_comparable': self.is_comparable, 'display_group': self.display_group or '',
            'options': json.loads(self.options) if self.options else None,
            'validation': json.loads(self.validation) if self.validation else None,
        }
```

- [ ] 在 `models.py` 末尾追加上述 8 个模型类
- [ ] 在文件顶部确认 `import json` 存在（用于 `CategorySpecDefinition.to_dict`）

### Task 1.2: Product 表扩展 + M2M 映射表 + ProductImage + ProductDependency

**Files:**
- Modify: `models.py` (在 Product 类中添加字段，在文件末尾追加映射表)

**在 Product 类中添加以下字段（插入到 `is_active` 之后，所有字段 nullable）：**

```python
    # v2.6.0 新增: 产品高级功能字段 (全部 nullable, 向后兼容)
    model = db.Column(db.String(100), nullable=True, index=True)        # 产品型号 (独立于 spec)
    category_id = db.Column(db.Integer, db.ForeignKey('device_categories.id'), nullable=True, index=True)
    manufacturer_id = db.Column(db.Integer, db.ForeignKey('manufacturers.id'), nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    product_url = db.Column(db.String(500), nullable=True)              # 官方产品页链接
    status = db.Column(db.String(20), default='active', index=True)     # active/archived/discontinued
    parent_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True, index=True)  # 变体父产品
    specs = db.Column(db.Text, nullable=True)                           # JSON: 结构化规格 {key: value}
    urls = db.Column(db.Text, nullable=True)                            # JSON: 多链接
    custom_fields = db.Column(db.Text, nullable=True)                   # JSON: 自定义字段
```

**更新 `Product.to_dict()` — 在现有返回字典中添加以下键：**

```python
    'model': self.model or '',
    'category_id': self.category_id,
    'category_name': '',  # 由 API 层填充
    'manufacturer_id': self.manufacturer_id,
    'manufacturer_name': '',  # 由 API 层填充
    'supplier_id': self.supplier_id,
    'supplier_name': '',  # 由 API 层填充
    'product_url': self.product_url or '',
    'status': self.status or 'active',
    'parent_id': self.parent_id,
    'specs': json.loads(self.specs) if self.specs else {},
    'urls': json.loads(self.urls) if self.urls else {},
    'custom_fields': json.loads(self.custom_fields) if self.custom_fields else {},
    'spec_definitions': [],       # 由 API 层填充 (分类的规格定义)
    'comm_methods': [],           # 由 API 层填充
    'comm_protocols': [],         # 由 API 层填充
    'power_supplies': [],         # 由 API 层填充
    'hardware_interfaces': [],    # 由 API 层填充
    'sensor_capabilities': [],    # 由 API 层填充
    'images': [],                 # 由 API 层填充
    'dependencies': [],           # 由 API 层填充
    'variants': [],               # 由 API 层填充
```

**在 `Product` 类中添加 relationship（在 `to_dict` 方法之前）：**

```python
    # v2.6.0 relationships
    category_rel = db.relationship('DeviceCategory', foreign_keys=[category_id], backref='products')
    manufacturer_rel = db.relationship('Manufacturer', foreign_keys=[manufacturer_id], backref='products')
    supplier_rel = db.relationship('Supplier', foreign_keys=[supplier_id], backref='products')
    parent_rel = db.relationship('Product', remote_side=[id], backref='variants')
```

**在 models.py 末尾追加 M2M 映射表 + ProductImage + ProductDependency：**

```python
class ProductCommMethod(db.Model):
    __tablename__ = 'product_comm_methods'
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), primary_key=True)
    method_id = db.Column(db.Integer, db.ForeignKey('dict_comm_methods.id', ondelete='CASCADE'), primary_key=True)
    details = db.Column(db.String(255), nullable=True)

    method = db.relationship('DictCommMethod')

    def to_dict(self):
        return {
            'method_id': self.method_id,
            'method_name': self.method.name if self.method else '',
            'method_type': self.method.method_type if self.method else '',
            'details': self.details or '',
        }


class ProductCommProtocol(db.Model):
    __tablename__ = 'product_comm_protocols'
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), primary_key=True)
    protocol_id = db.Column(db.Integer, db.ForeignKey('dict_comm_protocols.id', ondelete='CASCADE'), primary_key=True)
    direction = db.Column(db.String(20), default='both')

    protocol = db.relationship('DictCommProtocol')

    def to_dict(self):
        return {
            'protocol_id': self.protocol_id,
            'protocol_name': self.protocol.name if self.protocol else '',
            'direction': self.direction,
        }


class ProductPowerSupply(db.Model):
    __tablename__ = 'product_power_supplies'
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), primary_key=True)
    power_id = db.Column(db.Integer, db.ForeignKey('dict_power_supplies.id', ondelete='CASCADE'), primary_key=True)
    voltage_range = db.Column(db.String(100), nullable=True)
    battery_life = db.Column(db.String(100), nullable=True)

    power = db.relationship('DictPowerSupply')

    def to_dict(self):
        return {
            'power_id': self.power_id,
            'power_name': self.power.name if self.power else '',
            'power_category': self.power.supply_category if self.power else '',
            'voltage_range': self.voltage_range or '',
            'battery_life': self.battery_life or '',
        }


class ProductHardwareInterface(db.Model):
    __tablename__ = 'product_hardware_interfaces'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True)
    interface_name = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    description = db.Column(db.String(255), nullable=True)

    def to_dict(self):
        return {
            'id': self.id, 'product_id': self.product_id,
            'interface_name': self.interface_name,
            'quantity': self.quantity, 'description': self.description or '',
        }


class ProductSensorCapability(db.Model):
    __tablename__ = 'product_sensor_capabilities'
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), primary_key=True)
    metric_id = db.Column(db.Integer, db.ForeignKey('dict_sensor_metrics.id', ondelete='CASCADE'), primary_key=True)
    measure_range = db.Column(db.String(100), nullable=True)
    accuracy = db.Column(db.String(100), nullable=True)
    resolution = db.Column(db.String(50), nullable=True)

    metric = db.relationship('DictSensorMetric')

    def to_dict(self):
        return {
            'metric_id': self.metric_id,
            'metric_name': self.metric.name if self.metric else '',
            'unit': self.metric.unit if self.metric else '',
            'measure_range': self.measure_range or '',
            'accuracy': self.accuracy or '',
            'resolution': self.resolution or '',
        }


class ProductImage(db.Model):
    __tablename__ = 'product_images'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True)
    url = db.Column(db.String(500), nullable=False)
    is_primary = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)
    alt_text = db.Column(db.String(200), nullable=True)

    def to_dict(self):
        return {
            'id': self.id, 'product_id': self.product_id,
            'url': self.url, 'is_primary': self.is_primary,
            'sort_order': self.sort_order, 'alt_text': self.alt_text or '',
        }


class ProductDependency(db.Model):
    __tablename__ = 'product_dependencies'
    __table_args__ = (
        db.CheckConstraint(
            'depends_on_product_id IS NOT NULL OR depends_on_category_id IS NOT NULL',
            name='ck_dependency_target'
        ),
    )
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True)
    depends_on_product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    depends_on_category_id = db.Column(db.Integer, db.ForeignKey('device_categories.id'), nullable=True)
    dependency_type = db.Column(db.String(20), default='required')
    description = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, default=0)

    product = db.relationship('Product', foreign_keys=[product_id], backref='dependencies_as_source')
    target_product = db.relationship('Product', foreign_keys=[depends_on_product_id])
    target_category = db.relationship('DeviceCategory')

    def to_dict(self):
        return {
            'id': self.id, 'product_id': self.product_id,
            'depends_on_product_id': self.depends_on_product_id,
            'depends_on_category_id': self.depends_on_category_id,
            'dependency_type': self.dependency_type,
            'description': self.description or '',
            'sort_order': self.sort_order,
        }
```

- [ ] 在 Product 类中添加 9 个新字段（全部 nullable）
- [ ] 更新 `Product.to_dict()` 添加新键
- [ ] 添加 Product relationships
- [ ] 追加 9 个新模型类
- [ ] 确认 `import json` 在文件顶部

### Task 1.3: 数据库迁移 + 种子数据

```bash
cd /Users/tong/quote-system
source venv/bin/activate
export FLASK_APP=app.py

# 生成迁移脚本
flask db migrate -m "v2.6.0: product advanced features - dicts, categories, M2M mappings, product extensions"

# 检查生成的迁移文件
cat migrations/versions/*v2.6.0*.py

# 执行迁移
flask db upgrade
```

**在 `app.py` 的 `with app.app_context():` 块中添加种子数据（在 `db.create_all()` 之后）：**

```python
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
```

- [ ] 运行 `flask db migrate` 生成迁移
- [ ] 运行 `flask db upgrade` 执行迁移
- [ ] 在 `app.py` 中添加种子数据初始化逻辑
- [ ] 重启 Flask 确认无报错
- [ ] 验证 `quote.db` 中新表已创建

**验证命令：**
```bash
cd /Users/tong/quote-system && source venv/bin/activate
python -c "
from app import app
with app.app_context():
    from models import *
    print('Tables:', [t for t in db.engine.table_names() if not t.startswith('sqlite')])
"
```

---

## Phase 2: Backend APIs

### Task 2.1: 字典管理 API (`dict_bp.py`)

**Create:** `dict_bp.py`

```python
"""字典管理 Blueprint — 通讯方式/协议/供电/传感指标/制造商/供应商 CRUD"""
from flask import Blueprint, request, jsonify, g
from extensions import db
from models import (
    DictCommMethod, DictCommProtocol, DictPowerSupply, DictSensorMetric,
    Manufacturer, Supplier
)
from auth import require_auth, require_admin

dict_bp = Blueprint('dicts', __name__)


# ─── Helper ───

def _paginate(query):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        'items': [item.to_dict() for item in pagination.items],
        'total': pagination.total, 'page': page, 'per_page': per_page,
    }


# ─── 通讯方式 ───

@dict_bp.route('/api/dicts/comm-methods', methods=['GET'])
@require_auth
def list_comm_methods():
    items = DictCommMethod.query.order_by(DictCommMethod.method_type, DictCommMethod.name).all()
    return jsonify({'items': [i.to_dict() for i in items]})

@dict_bp.route('/api/dicts/comm-methods', methods=['POST'])
@require_admin
def create_comm_method():
    data = request.get_json()
    if not data.get('name'):
        return jsonify({'error': '名称不能为空'}), 400
    item = DictCommMethod(method_type=data.get('method_type', 'wired'), name=data['name'])
    db.session.add(item); db.session.commit()
    return jsonify(item.to_dict()), 201

@dict_bp.route('/api/dicts/comm-methods/<int:id>', methods=['PUT'])
@require_admin
def update_comm_method(id):
    item = DictCommMethod.query.get_or_404(id)
    data = request.get_json()
    if 'name' in data: item.name = data['name']
    if 'method_type' in data: item.method_type = data['method_type']
    db.session.commit()
    return jsonify(item.to_dict())

@dict_bp.route('/api/dicts/comm-methods/<int:id>', methods=['DELETE'])
@require_admin
def delete_comm_method(id):
    item = DictCommMethod.query.get_or_404(id)
    db.session.delete(item); db.session.commit()
    return jsonify({'ok': True})


# ─── 通讯协议 (pattern identical to comm-methods) ───

@dict_bp.route('/api/dicts/comm-protocols', methods=['GET'])
@require_auth
def list_comm_protocols():
    items = DictCommProtocol.query.order_by(DictCommProtocol.name).all()
    return jsonify({'items': [i.to_dict() for i in items]})

@dict_bp.route('/api/dicts/comm-protocols', methods=['POST'])
@require_admin
def create_comm_protocol():
    data = request.get_json()
    if not data.get('name'): return jsonify({'error': '名称不能为空'}), 400
    item = DictCommProtocol(name=data['name'])
    db.session.add(item); db.session.commit()
    return jsonify(item.to_dict()), 201

@dict_bp.route('/api/dicts/comm-protocols/<int:id>', methods=['PUT'])
@require_admin
def update_comm_protocol(id):
    item = DictCommProtocol.query.get_or_404(id)
    data = request.get_json()
    if 'name' in data: item.name = data['name']
    db.session.commit()
    return jsonify(item.to_dict())

@dict_bp.route('/api/dicts/comm-protocols/<int:id>', methods=['DELETE'])
@require_admin
def delete_comm_protocol(id):
    item = DictCommProtocol.query.get_or_404(id)
    db.session.delete(item); db.session.commit()
    return jsonify({'ok': True})


# ─── 供电方式 ───

@dict_bp.route('/api/dicts/power-supplies', methods=['GET'])
@require_auth
def list_power_supplies():
    items = DictPowerSupply.query.order_by(DictPowerSupply.supply_category, DictPowerSupply.name).all()
    return jsonify({'items': [i.to_dict() for i in items]})

@dict_bp.route('/api/dicts/power-supplies', methods=['POST'])
@require_admin
def create_power_supply():
    data = request.get_json()
    if not data.get('name'): return jsonify({'error': '名称不能为空'}), 400
    item = DictPowerSupply(supply_category=data.get('supply_category', ''), name=data['name'])
    db.session.add(item); db.session.commit()
    return jsonify(item.to_dict()), 201

@dict_bp.route('/api/dicts/power-supplies/<int:id>', methods=['PUT'])
@require_admin
def update_power_supply(id):
    item = DictPowerSupply.query.get_or_404(id)
    data = request.get_json()
    if 'name' in data: item.name = data['name']
    if 'supply_category' in data: item.supply_category = data['supply_category']
    db.session.commit()
    return jsonify(item.to_dict())

@dict_bp.route('/api/dicts/power-supplies/<int:id>', methods=['DELETE'])
@require_admin
def delete_power_supply(id):
    item = DictPowerSupply.query.get_or_404(id)
    db.session.delete(item); db.session.commit()
    return jsonify({'ok': True})


# ─── 传感指标 ───

@dict_bp.route('/api/dicts/sensor-metrics', methods=['GET'])
@require_auth
def list_sensor_metrics():
    items = DictSensorMetric.query.order_by(DictSensorMetric.name).all()
    return jsonify({'items': [i.to_dict() for i in items]})

@dict_bp.route('/api/dicts/sensor-metrics', methods=['POST'])
@require_admin
def create_sensor_metric():
    data = request.get_json()
    if not data.get('name'): return jsonify({'error': '名称不能为空'}), 400
    item = DictSensorMetric(name=data['name'], unit=data.get('unit', ''))
    db.session.add(item); db.session.commit()
    return jsonify(item.to_dict()), 201

@dict_bp.route('/api/dicts/sensor-metrics/<int:id>', methods=['PUT'])
@require_admin
def update_sensor_metric(id):
    item = DictSensorMetric.query.get_or_404(id)
    data = request.get_json()
    if 'name' in data: item.name = data['name']
    if 'unit' in data: item.unit = data['unit']
    db.session.commit()
    return jsonify(item.to_dict())

@dict_bp.route('/api/dicts/sensor-metrics/<int:id>', methods=['DELETE'])
@require_admin
def delete_sensor_metric(id):
    item = DictSensorMetric.query.get_or_404(id)
    db.session.delete(item); db.session.commit()
    return jsonify({'ok': True})


# ─── 制造商 ───

@dict_bp.route('/api/dicts/manufacturers', methods=['GET'])
@require_auth
def list_manufacturers():
    items = Manufacturer.query.order_by(Manufacturer.name).all()
    return jsonify({'items': [i.to_dict() for i in items]})

@dict_bp.route('/api/dicts/manufacturers', methods=['POST'])
@require_admin
def create_manufacturer():
    data = request.get_json()
    if not data.get('name'): return jsonify({'error': '名称不能为空'}), 400
    item = Manufacturer(name=data['name'], website=data.get('website', ''), description=data.get('description', ''))
    db.session.add(item); db.session.commit()
    return jsonify(item.to_dict()), 201

@dict_bp.route('/api/dicts/manufacturers/<int:id>', methods=['PUT'])
@require_admin
def update_manufacturer(id):
    item = Manufacturer.query.get_or_404(id)
    data = request.get_json()
    if 'name' in data: item.name = data['name']
    if 'website' in data: item.website = data['website']
    if 'description' in data: item.description = data['description']
    db.session.commit()
    return jsonify(item.to_dict())

@dict_bp.route('/api/dicts/manufacturers/<int:id>', methods=['DELETE'])
@require_admin
def delete_manufacturer(id):
    item = Manufacturer.query.get_or_404(id)
    db.session.delete(item); db.session.commit()
    return jsonify({'ok': True})


# ─── 供应商 ───

@dict_bp.route('/api/dicts/suppliers', methods=['GET'])
@require_auth
def list_suppliers():
    search = request.args.get('search', '')
    q = Supplier.query
    if search:
        q = q.filter(Supplier.name.ilike(f'%{search}%'))
    items = q.order_by(Supplier.name).all()
    return jsonify({'items': [i.to_dict() for i in items]})

@dict_bp.route('/api/dicts/suppliers', methods=['POST'])
@require_admin
def create_supplier():
    data = request.get_json()
    if not data.get('name'): return jsonify({'error': '名称不能为空'}), 400
    item = Supplier(
        name=data['name'], contact_person=data.get('contact_person', ''),
        phone=data.get('phone', ''), email=data.get('email', ''),
        website=data.get('website', ''), notes=data.get('notes', ''),
    )
    db.session.add(item); db.session.commit()
    return jsonify(item.to_dict()), 201

@dict_bp.route('/api/dicts/suppliers/<int:id>', methods=['PUT'])
@require_admin
def update_supplier(id):
    item = Supplier.query.get_or_404(id)
    data = request.get_json()
    for f in ['name', 'contact_person', 'phone', 'email', 'website', 'notes']:
        if f in data: setattr(item, f, data[f])
    db.session.commit()
    return jsonify(item.to_dict())

@dict_bp.route('/api/dicts/suppliers/<int:id>', methods=['DELETE'])
@require_admin
def delete_supplier(id):
    item = Supplier.query.get_or_404(id)
    db.session.delete(item); db.session.commit()
    return jsonify({'ok': True})
```

- [ ] 创建 `dict_bp.py`，包含 5 组字典 + 制造商 + 供应商的完整 CRUD (22 个端点)
- [ ] 在 `app.py` 中注册 Blueprint: `from dict_bp import dict_bp; app.register_blueprint(dict_bp)`

### Task 2.2: 分类管理 API (`category_bp.py`)

**Create:** `category_bp.py`

关键端点:
- `GET /api/categories` — 列表（含扁平结构）
- `GET /api/categories/tree` — 嵌套树结构（递归组装）
- `POST /api/categories` — 创建 (admin only)
- `PUT /api/categories/<id>` — 更新 (admin only)
- `DELETE /api/categories/<id>` — 删除 (admin only，检查无子节点)
- `GET /api/categories/<id>/spec-definitions` — 获取某分类的规格定义
- `POST /api/categories/<id>/spec-definitions` — 创建规格定义 (admin only)
- `PUT /api/dicts/spec-definitions/<id>` — 更新规格定义 (admin only)
- `DELETE /api/dicts/spec-definitions/<id>` — 删除规格定义 (admin only)

**Tree 端点实现要点：**
```python
@category_bp.route('/api/categories/tree', methods=['GET'])
@require_auth
def get_category_tree():
    """返回嵌套分类树"""
    all_cats = DeviceCategory.query.order_by(DeviceCategory.sort_order).all()
    cat_map = {c.id: {**c.to_dict(), 'children': []} for c in all_cats}
    roots = []
    for c in all_cats:
        node = cat_map[c.id]
        node['spec_definitions'] = [sd.to_dict() for sd in c.spec_definitions] if c.spec_definitions else []
        if c.parent_id and c.parent_id in cat_map:
            cat_map[c.parent_id]['children'].append(node)
        else:
            roots.append(node)
    return jsonify({'tree': roots})
```

- [ ] 创建 `category_bp.py`，包含 9 个端点
- [ ] 在 `app.py` 中注册: `from category_bp import category_bp; app.register_blueprint(category_bp)`

### Task 2.3: 规格服务 (`spec_service.py`)

**Create:** `spec_service.py`

移植 product-db 的 `spec_service.py`，适配 Flask/SQLAlchemy 模式：

```python
"""规格验证 + 产品对比引擎"""
import json
from models import CategorySpecDefinition


def validate_specs(specs: dict, category_id: int) -> list:
    """根据分类的规格定义验证提交的规格值。
    Args: specs = {spec_key: value}  (来自前端)
    Returns: 错误信息列表，空列表表示通过
    """
    spec_defs = CategorySpecDefinition.query.filter_by(category_id=category_id).all()
    spec_def_map = {sd.spec_key: sd for sd in spec_defs}
    errors = []

    for key, value in specs.items():
        if key not in spec_def_map:
            continue  # 未知 key 允许通过 (custom_fields 兜底)

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
    """
    if len(products) < 2:
        return _extract_all_specs(products)

    all_keys = set()
    product_specs = {}
    for p in products:
        specs = json.loads(p.specs) if p.specs else {}
        # 注入派生字段
        specs.update({
            '_model': p.model or '',
            '_category': p.category_rel.name if p.category_rel else (p.category or ''),
            '_manufacturer': p.manufacturer_rel.name if p.manufacturer_rel else '',
            '_supplier': p.supplier_rel.name if p.supplier_rel else (p.supplier or ''),
            '_unit': p.unit or '',
            '_price': str(p.price or 0),
            '_cost_price': str(p.cost_price or 0),
            '_status': p.status or 'active',
        })
        # 注入 M2M 派生字段
        sensors = []
        if hasattr(p, '_sensor_caps'):
            sensors = [f"{s.metric.name if s.metric else ''}({s.measure_range or ''})" for s in p._sensor_caps]
        specs['_sensors'] = ', '.join(sensors)
        
        comms = []
        if hasattr(p, '_comm_methods'):
            comms = [cm.method.name if cm.method else '' for cm in p._comm_methods]
        specs['_comm_methods'] = ', '.join(comms)

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
    """单产品时显示所有规格（含相同值）"""
    result = {}
    for p in products:
        specs = json.loads(p.specs) if p.specs else {}
        for k, v in specs.items():
            if k not in result:
                result[k] = {}
            result[k][p.id] = v
    return result
```

- [ ] 创建 `spec_service.py`
- [ ] 用 pytest 验证: `validate_specs({'voltage': 5}, category_id)` 对 number 类型 + min/max validation 正确报错

### Task 2.4: 产品高级 API (`product_advanced_bp.py`)

**Create:** `product_advanced_bp.py`

包含以下端点组：

**M2M 映射管理（每种映射 3 个端点: GET/POST 批量替换/DELETE 单项）：**
```
POST   /api/products/<id>/comm-methods       — 批量替换: {methods: [{method_id, details}, ...]}
POST   /api/products/<id>/comm-protocols     — 批量替换: {protocols: [{protocol_id, direction}, ...]}
POST   /api/products/<id>/power-supplies     — 批量替换: {supplies: [{power_id, voltage_range, battery_life}, ...]}
POST   /api/products/<id>/hardware-interfaces — 批量替换: {interfaces: [{interface_name, quantity, description}, ...]}
POST   /api/products/<id>/sensor-capabilities — 批量替换: {capabilities: [{metric_id, measure_range, accuracy, resolution}, ...]}
GET    /api/products/<id>/hardware-interfaces — 列表
DELETE /api/products/<id>/hardware-interfaces/<iface_id> — 删除单项
```

**多图管理：**
```
GET    /api/products/<id>/images             — 列表
POST   /api/products/<id>/images             — 批量替换: {images: [{url, is_primary, sort_order, alt_text}, ...]}
```

**产品依赖：**
```
GET    /api/products/<id>/dependencies       — 列表
POST   /api/products/<id>/dependencies       — 创建
PUT    /api/products/<id>/dependencies/<dep_id> — 更新
DELETE /api/products/<id>/dependencies/<dep_id> — 删除
```

**产品对比：**
```
GET    /api/products/compare?ids=1,2,3       — 返回对比矩阵 + 产品基本信息
```

**规格书：**
```
GET    /api/products/<id>/spec-sheet         — 返回 HTML 规格书页面
```

**按分类筛选（多维度交叉筛选）：**
```
GET    /api/products/advanced-search         — 支持 category_id, manufacturer_id, comm_method_ids, protocol_ids, power_ids, metric_ids, status 等参数
```

- [ ] 创建 `product_advanced_bp.py`，包含上述所有端点（约 25 个端点）
- [ ] 在 `app.py` 中注册: `from product_advanced_bp import product_advanced_bp; app.register_blueprint(product_advanced_bp)`

### Task 2.5: 扩展现有 `products_bp.py` 支持新字段

**Modify:** `products_bp.py` 的 create/update 端点

在 `POST /api/products` 和 `PUT /api/products/<id>` 中新增对新字段的支持：

```python
# 在 create_product() 和 update_product() 中添加以下可选字段处理
optional_new_fields = [
    'model', 'category_id', 'manufacturer_id', 'supplier_id',
    'product_url', 'status', 'parent_id',
]
for f in optional_new_fields:
    if f in data:
        setattr(product, f, data[f] or None)

# JSON 字段处理
if 'specs' in data:
    product.specs = json.dumps(data['specs'], ensure_ascii=False) if data['specs'] else None
if 'urls' in data:
    product.urls = json.dumps(data['urls'], ensure_ascii=False) if data['urls'] else None
if 'custom_fields' in data:
    product.custom_fields = json.dumps(data['custom_fields'], ensure_ascii=False) if data['custom_fields'] else None
```

**扩展 `GET /api/products` 列表端点：** 添加新筛选参数支持:
```python
category_id = request.args.get('category_id', type=int)
manufacturer_id = request.args.get('manufacturer_id', type=int)
status_filter = request.args.get('status', '')
```

- [ ] 扩展 create/update 端点支持新字段
- [ ] 扩展 list 端点支持新筛选参数
- [ ] 扩展 `Product.to_dict()` 调用处，填充 category_name/manufacturer_name/supplier_name

### Task 2.6: 注册所有新 Blueprint

**Modify:** `app.py`

```python
# 在现有 Blueprint 注册之后添加:
from dict_bp import dict_bp
app.register_blueprint(dict_bp)
from category_bp import category_bp
app.register_blueprint(category_bp)
from product_advanced_bp import product_advanced_bp
app.register_blueprint(product_advanced_bp)
```

- [ ] 注册 3 个新 Blueprint
- [ ] 启动 Flask 确认无报错: `python app.py`
- [ ] 用 curl 测试基础端点: `curl -H "Authorization: Bearer <token>" http://localhost:5001/api/dicts/comm-methods`

---

## Phase 3: Frontend — 字典 + 分类管理

### Task 3.1: 前端 API 函数

**Create:** `frontend/src/composables/useAdvancedApi.js`

```javascript
import { useApi } from './useApi.js'

export function useAdvancedApi() {
  const { api } = useApi()

  // ─── 字典 ───
  const dicts = {
    commMethods: () => api('/api/dicts/comm-methods'),
    commProtocols: () => api('/api/dicts/comm-protocols'),
    powerSupplies: () => api('/api/dicts/power-supplies'),
    sensorMetrics: () => api('/api/dicts/sensor-metrics'),
    manufacturers: () => api('/api/dicts/manufacturers'),
    suppliers: (search = '') => api(`/api/dicts/suppliers?search=${encodeURIComponent(search)}`),
  }

  // ─── 分类 ───
  const categories = {
    tree: () => api('/api/categories/tree'),
    list: () => api('/api/categories'),
    create: (data) => api('/api/categories', 'POST', data),
    update: (id, data) => api(`/api/categories/${id}`, 'PUT', data),
    delete: (id) => api(`/api/categories/${id}`, 'DELETE'),
    specDefs: (catId) => api(`/api/categories/${catId}/spec-definitions`),
    createSpecDef: (catId, data) => api(`/api/categories/${catId}/spec-definitions`, 'POST', data),
    updateSpecDef: (id, data) => api(`/api/dicts/spec-definitions/${id}`, 'PUT', data),
    deleteSpecDef: (id) => api(`/api/dicts/spec-definitions/${id}`, 'DELETE'),
  }

  // ─── 产品高级 ───
  const productAdvanced = {
    compare: (ids) => api(`/api/products/compare?ids=${ids.join(',')}`),
    specSheet: (id) => api(`/api/products/${id}/spec-sheet`),
    // M2M
    commMethods: (id) => api(`/api/products/${id}/comm-methods`),
    updateCommMethods: (id, data) => api(`/api/products/${id}/comm-methods`, 'POST', data),
    commProtocols: (id) => api(`/api/products/${id}/comm-protocols`),
    updateCommProtocols: (id, data) => api(`/api/products/${id}/comm-protocols`, 'POST', data),
    powerSupplies: (id) => api(`/api/products/${id}/power-supplies`),
    updatePowerSupplies: (id, data) => api(`/api/products/${id}/power-supplies`, 'POST', data),
    hardwareInterfaces: (id) => api(`/api/products/${id}/hardware-interfaces`),
    updateHardwareInterfaces: (id, data) => api(`/api/products/${id}/hardware-interfaces`, 'POST', data),
    sensorCapabilities: (id) => api(`/api/products/${id}/sensor-capabilities`),
    updateSensorCapabilities: (id, data) => api(`/api/products/${id}/sensor-capabilities`, 'POST', data),
    // 图片
    images: (id) => api(`/api/products/${id}/images`),
    updateImages: (id, data) => api(`/api/products/${id}/images`, 'POST', data),
    // 依赖
    dependencies: (id) => api(`/api/products/${id}/dependencies`),
    createDependency: (id, data) => api(`/api/products/${id}/dependencies`, 'POST', data),
    updateDependency: (pid, did, data) => api(`/api/products/${pid}/dependencies/${did}`, 'PUT', data),
    deleteDependency: (pid, did) => api(`/api/products/${pid}/dependencies/${did}`, 'DELETE'),
  }

  return { dicts, categories, productAdvanced }
}
```

- [ ] 创建 `useAdvancedApi.js` composable

### Task 3.2: 字典管理页面 (`DictManageView.vue`)

**Create:** `frontend/src/views/DictManageView.vue`

- Tab 切换: 通讯方式 | 通讯协议 | 供电方式 | 传感指标 | 制造商 | 供应商
- 每个 Tab: 简单表格 + 新增/编辑/删除按钮
- 使用 `useAdvancedApi` composable
- 参考现有 `AdminView.vue` 的 UI 风格

- [ ] 创建 `DictManageView.vue`
- [ ] 在 `router/index.js` 中添加路由: `/dicts` → `DictManageView`

### Task 3.3: 分类树管理页面 (`CategoryManageView.vue`)

**Create:** `frontend/src/views/CategoryManageView.vue`

- 左侧: 分类树（递归组件，支持展开/折叠）
- 右侧: 选中分类的详情 + 规格定义表格
- 新增/编辑分类: 模态框（名称、slug、父级选择、排序）
- 规格定义编辑器: spec_key、display_name、spec_type、unit、options、validation、display_group、筛选/对比开关

**Create:** `frontend/src/components/CategoryTree.vue`

- 递归树组件，支持选中、展开/折叠
- 使用 `<script setup>` + `defineProps(['nodes'])`

- [ ] 创建 `CategoryTree.vue` 递归树组件
- [ ] 创建 `CategoryManageView.vue` 分类管理页
- [ ] 在 router 中添加路由: `/categories` → `CategoryManageView`

---

## Phase 4: Frontend — 产品增强

### Task 4.1: 扩展产品表单 (`ProductFormModal.vue`)

**Modify:** `frontend/src/components/ProductFormModal.vue`

在现有表单中添加 Tab 页签结构:
- **Tab 1: 基本信息** — 现有字段（名称/规格/分类/供应商/价格等）
  - 新增: 型号(`model`)、产品URL、制造商(下拉选择)、分类(树选择器)、供应商(下拉+搜索)
- **Tab 2: 高级规格** — 动态规格字段（根据分类加载 spec_definitions）
  - 创建 `SpecFieldGroup.vue` 组件
- **Tab 3: 技术参数** — M2M 映射选择器
  - 创建 `M2MSelector.vue` 组件
  - 通讯方式（多选 + details 补充输入）
  - 通讯协议（多选 + direction 选择）
  - 供电方式（多选 + 电压范围/电池寿命）
  - 硬件接口（动态行列表）
  - 传感能力（多选 + 量程/精度/分辨率）
- **Tab 4: 图片** — 多图上传
  - 创建 `MultiImageUpload.vue` 组件
- **Tab 5: 依赖 & 变体** — 产品依赖 + 变体管理

**Create:** `frontend/src/components/SpecFieldGroup.vue`

```vue
<script setup>
import { computed } from 'vue'
const props = defineProps({ specDefs: Array, modelValue: Object })
const emit = defineEmits(['update:modelValue'])
// 根据 spec_type 渲染不同控件: text input / number input / select / checkbox / range
</script>
<template>
  <div v-for="sd in specDefs" :key="sd.spec_key" class="mb-2">
    <label>{{ sd.display_name }} <small class="text-muted">{{ sd.unit }}</small></label>
    <input v-if="sd.spec_type === 'string'" class="form-control" v-model="localSpecs[sd.spec_key]" />
    <input v-else-if="sd.spec_type === 'number'" type="number" class="form-control" v-model.number="localSpecs[sd.spec_key]" />
    <select v-else-if="sd.spec_type === 'enum'" class="form-select" v-model="localSpecs[sd.spec_key]">
      <option value="">--</option>
      <option v-for="opt in sd.options" :key="opt" :value="opt">{{ opt }}</option>
    </select>
    <!-- boolean → checkbox -->
  </div>
</template>
```

**Create:** `frontend/src/components/M2MSelector.vue`

- 通用多对多选择器组件
- Props: `dictItems` (字典列表), `selectedItems` (已选), `extraFields` (额外字段定义)
- 多选下拉 + 已选列表（带额外字段输入）

**Create:** `frontend/src/components/MultiImageUpload.vue`

- 图片列表（拖拽排序）
- 上传按钮（使用现有图片上传 API）
- 主图标记、alt_text 输入、删除按钮

- [ ] 创建 `SpecFieldGroup.vue`
- [ ] 创建 `M2MSelector.vue`
- [ ] 创建 `MultiImageUpload.vue`
- [ ] 扩展 `ProductFormModal.vue` 添加 Tab 结构和新字段
- [ ] 确保原有表单功能不受影响

### Task 4.2: 扩展产品详情 (`ProductDetailModal.vue`)

**Modify:** `frontend/src/components/ProductDetailModal.vue`

在现有详情展示中添加:
- M2M 映射信息展示（通讯/协议/供电/接口/传感）
- 多图轮播
- 产品变体列表
- 产品依赖列表
- "查看规格书" 链接 → 新窗口打开规格书页面
- "加入对比" 复选框

- [ ] 扩展 `ProductDetailModal.vue` 展示新字段

### Task 4.3: 产品对比页面 (`ProductCompareView.vue`)

**Create:** `frontend/src/views/ProductCompareView.vue`

- 顶部: 产品搜索 + 添加对比项（最多 5 个）
- 主体: 差异矩阵表格
  - 行 = 规格字段，列 = 产品
  - 仅显示有差异的行
  - 相同值的行可折叠（"显示全部" 开关）
- URL 参数支持: `/compare?ids=1,2,3`

- [ ] 创建 `ProductCompareView.vue`
- [ ] 在 router 中添加路由: `/products/compare` → `ProductCompareView`

### Task 4.4: 规格书页面 (`ProductSpecSheet.vue`)

**Create:** `frontend/src/views/ProductSpecSheet.vue`

- 纯展示页面，类似产品详情但更结构化
- 基本信息卡片
- 分组规格表（按 `display_group` 分组）
- 通讯信息卡片
- 传感能力表
- 硬件接口表
- 打印友好样式

- [ ] 创建 `ProductSpecSheet.vue`
- [ ] 在 router 中添加路由: `/products/:id/spec-sheet` → `ProductSpecSheet`

### Task 4.5: 路由更新

**Modify:** `frontend/src/router/index.js`

```javascript
// 新增路由:
{ path: '/dicts', name: 'DictManage', component: () => import('../views/DictManageView.vue') },
{ path: '/categories', name: 'CategoryManage', component: () => import('../views/CategoryManageView.vue') },
{ path: '/products/compare', name: 'ProductCompare', component: () => import('../views/ProductCompareView.vue') },
{ path: '/products/:id/spec-sheet', name: 'ProductSpecSheet', component: () => import('../views/ProductSpecSheet.vue') },
```

- [ ] 添加 4 条新路由

### Task 4.6: 导航栏更新

**Modify:** 导航栏组件（`App.vue` 或独立 Nav 组件）

在导航栏添加新菜单项:
- "字典管理" (`/dicts`) — admin only
- "分类管理" (`/categories`) — admin only
- 产品列表页添加 "对比" 按钮（选中产品后可用）

- [ ] 添加导航菜单项

---

## Phase 5: Testing & Polish

### Task 5.1: 字典 API 测试

**Create:** `tests/test_dicts.py`

覆盖:
- 所有字典 GET 端点返回 200 + items 数组
- 管理员 POST/PUT/DELETE 正常
- 普通用户 POST/PUT/DELETE 返回 403
- 供应商搜索功能

### Task 5.2: 分类 API 测试

**Create:** `tests/test_categories.py`

覆盖:
- 分类树返回嵌套结构
- 分类 CRUD
- 规格定义 CRUD
- 删除有子节点的分类应报错

### Task 5.3: 产品高级 API 测试

**Create:** `tests/test_product_advanced.py`

覆盖:
- M2M 映射批量替换 + 读取
- 产品对比: 2 产品返回差异矩阵，单产品返回全部
- 规格书端点返回 HTML
- 产品依赖 CRUD
- 多图管理
- 新字段在产品 create/update/get 中正确返回

### Task 5.4: 回归测试

```bash
cd /Users/tong/quote-system && source venv/bin/activate
python -m pytest tests/ -v
```

- [ ] 确保现有 138 个测试全部通过
- [ ] 确保新测试全部通过

---

## Phase 依赖关系

```
Phase 1 (DB) ──> Phase 2 (API) ──> Phase 4 (Frontend 产品)
                              └──> Phase 3 (Frontend 字典/分类)
                                                └──> Phase 5 (Test)
```

Phase 3 和 Phase 4 可并行开发。

## Rollback Plan

如果出问题，三步回退：
```bash
flask db downgrade    # 撤销迁移
git checkout models.py products_bp.py app.py  # 恢复被修改文件
rm dict_bp.py category_bp.py product_advanced_bp.py spec_service.py  # 删除新文件
```
