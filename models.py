"""报价系统数据模型 — Product / Quote / QuoteItem / User / 辅助表"""
import json
from datetime import datetime
from extensions import db


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    sku = db.Column(db.String(100), nullable=True, index=True)
    category = db.Column(db.String(100), nullable=True, index=True)
    spec = db.Column(db.String(500), nullable=True)
    unit = db.Column(db.String(20), nullable=True)
    price = db.Column(db.Numeric(10, 2, asdecimal=False), nullable=True)
    cost_price = db.Column(db.Numeric(10, 2, asdecimal=False), nullable=True)
    supplier = db.Column(db.String(200), nullable=True, index=True)
    function_desc = db.Column(db.Text, nullable=True)
    remark = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    image_data = db.Column(db.LargeBinary, nullable=True)
    image_mime = db.Column(db.String(30), nullable=True)
    is_active = db.Column(db.Boolean, default=True, index=True)
    # v2.6.0 新增: 产品高级功能字段 (全部 nullable, 向后兼容)
    model = db.Column(db.String(100), nullable=True, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('device_categories.id'), nullable=True, index=True)
    manufacturer_id = db.Column(db.Integer, db.ForeignKey('manufacturers.id'), nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    product_url = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), default='active', index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True, index=True)
    specs = db.Column(db.Text, nullable=True)        # JSON string
    urls = db.Column(db.Text, nullable=True)         # JSON string
    custom_fields = db.Column(db.Text, nullable=True) # JSON string
    pinyin_search = db.Column(db.Text, nullable=True, index=True)  # 预计算拼音，搜索用
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # v2.6.0 relationships (prefixed to avoid collision with legacy columns 'category'/'supplier')
    device_category = db.relationship('DeviceCategory', foreign_keys=[category_id], backref='products')
    product_manufacturer = db.relationship('Manufacturer', foreign_keys=[manufacturer_id], backref='products')
    product_supplier = db.relationship('Supplier', foreign_keys=[supplier_id], backref='products')
    parent_product = db.relationship('Product', remote_side=[id], backref='variants')

    def to_dict(self, users_map=None):
        creator_name = None
        if self.created_by:
            if users_map is not None:
                creator_name = users_map.get(self.created_by)
            else:
                creator = db.session.get(User, self.created_by)
                creator_name = creator.username if creator else None
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
            'has_image': bool(self.image_data),
            'is_active': self.is_active if self.is_active is not None else True,
            'created_by': self.created_by,
            'created_by_name': creator_name,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else '',
            'model': self.model or '',
            'category_id': self.category_id,
            'category_name': '',
            'manufacturer_id': self.manufacturer_id,
            'manufacturer_name': '',
            'supplier_id': self.supplier_id,
            'supplier_name': '',
            'product_url': self.product_url or '',
            'status': self.status or 'active',
            'parent_id': self.parent_id,
            'specs': (json.loads(self.specs) if self.specs else {}),
            'urls': (json.loads(self.urls) if self.urls else {}),
            'custom_fields': (json.loads(self.custom_fields) if self.custom_fields else {}),
            'spec_definitions': [],
            'comm_methods': [],
            'comm_protocols': [],
            'power_supplies': [],
            'hardware_interfaces': [],
            'sensor_capabilities': [],
            'images': [],
            'dependencies': [],
            'variants': [],
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
    status = db.Column(db.String(20), default='draft', index=True)
    total_amount = db.Column(db.Numeric(12, 2, asdecimal=False), default=0)
    download_count = db.Column(db.Integer, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    remark = db.Column(db.Text, nullable=True)
    tax_rate = db.Column(db.Numeric(5, 2, asdecimal=False), default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    items = db.relationship('QuoteItem', backref='quote', lazy='dynamic',
                            cascade='all, delete-orphan', order_by='QuoteItem.sort_order')

    def to_dict(self, products_map=None, users_map=None):
        creator_name = None
        if self.created_by:
            if users_map is not None:
                creator_name = users_map.get(self.created_by)
            else:
                creator = db.session.get(User, self.created_by)
                creator_name = creator.username if creator else None
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
            'created_by': self.created_by,
            'created_by_name': creator_name,
            'remark': self.remark or '',
            'tax_rate': self.tax_rate or 0,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else '',
            'items': [item.to_dict(products_map) for item in self.items],
        }


class QuoteItem(db.Model):
    __tablename__ = 'quote_items'
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey('quotes.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True, index=True)
    product_name = db.Column(db.String(200), nullable=False)
    product_sku = db.Column(db.String(100), nullable=True)
    product_spec = db.Column(db.String(500), nullable=True)
    product_unit = db.Column(db.String(20), nullable=True)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Numeric(10, 2, asdecimal=False), default=0)
    amount = db.Column(db.Numeric(12, 2, asdecimal=False), default=0)
    discount_rate = db.Column(db.Numeric(5, 2, asdecimal=False), default=100)  # 折扣率(%), 100=原价
    remark = db.Column(db.String(500), nullable=True)
    sort_order = db.Column(db.Integer, default=0)

    def to_dict(self, products_map=None):
        profit = 0
        profit_rate = 0
        if self.product_id:
            product = products_map.get(self.product_id) if products_map else db.session.get(Product, self.product_id)
            if product and product.cost_price:
                profit = round((self.unit_price or 0) - (product.cost_price or 0), 2)
                profit_rate = round(profit / (self.unit_price or 1) * 100, 1) if self.unit_price else 0
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
            'discount_rate': self.discount_rate if self.discount_rate else 100,
            'remark': self.remark or '',
            'sort_order': self.sort_order,
            'profit': profit,
            'profit_rate': profit_rate,
            'function_desc': product.function_desc or '' if self.product_id and product else '',
        }


class DownloadLog(db.Model):
    __tablename__ = 'download_logs'
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey('quotes.id', ondelete='CASCADE'), nullable=False)
    user_name = db.Column(db.String(100), nullable=False)
    downloaded_at = db.Column(db.DateTime, default=datetime.now)
    quote = db.relationship('Quote', backref=db.backref('download_logs'))  # 审计日志不随报价单删除

    def to_dict(self):
        return {
            'id': self.id,
            'quote_id': self.quote_id,
            'user_name': self.user_name,
            'downloaded_at': self.downloaded_at.strftime('%Y-%m-%d %H:%M') if self.downloaded_at else '',
            'quote_title': self.quote.title if self.quote else '',
            'quote_client': self.quote.client if self.quote else '',
        }


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(10), default='user')
    is_active = db.Column(db.Boolean, default=True)
    email = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    last_login = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id, 'username': self.username,
            'role': self.role, 'is_active': self.is_active,
            'email': self.email or '',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
            'last_login': self.last_login.strftime('%Y-%m-%d %H:%M') if self.last_login else '',
        }


class FieldSetting(db.Model):
    __tablename__ = 'field_settings'
    id = db.Column(db.Integer, primary_key=True)
    field_name = db.Column(db.String(50), unique=True, nullable=False)
    label = db.Column(db.String(100), nullable=False)
    user_visible = db.Column(db.Boolean, default=True)


class SystemSetting(db.Model):
    """系统设置 key-value 存储 (v1.3.8)"""
    __tablename__ = 'system_settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=True, default='')


class DownloadTicket(db.Model):
    """下载凭证 — 替代内存字典，多 worker 安全"""
    __tablename__ = 'download_tickets'
    id = db.Column(db.Integer, primary_key=True)
    ticket = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    expires_at = db.Column(db.Float, nullable=False)


class AIChatSession(db.Model):
    """AI 对话初始化标记 — 替代内存 set，多 worker 安全"""
    __tablename__ = 'ai_chat_sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    initialized_at = db.Column(db.DateTime, default=datetime.now)
    prompt_hash = db.Column(db.String(64), nullable=True)


class AIUsageLog(db.Model):
    """AI 调用统计 — 记录每次chat/recognize调用"""
    __tablename__ = 'ai_usage_logs'
    __table_args__ = (
        db.Index('ix_ai_usage_user_created', 'user_id', 'created_at'),
    )
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    action = db.Column(db.String(30), nullable=False, index=True)  # 'chat' / 'recognize'
    model = db.Column(db.String(50), nullable=True)
    elapsed = db.Column(db.Float, default=0)  # 秒
    success = db.Column(db.Boolean, default=True)
    error = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'model': self.model or '',
            'elapsed': self.elapsed,
            'success': self.success,
            'error': self.error or '',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
        }


class AIConversation(db.Model):
    """AI 对话会话 — 替代 Hermes Gateway 的 conversation 状态"""
    __tablename__ = 'ai_conversations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    session_id = db.Column(db.String(64), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=True)
    message_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


class AIMessage(db.Model):
    """AI 对话消息 — 完整服务端持久化"""
    __tablename__ = 'ai_messages'
    __table_args__ = (
        db.Index('ix_ai_msg_conv_created', 'conversation_id', 'created_at'),
    )
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('ai_conversations.id', ondelete='CASCADE'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=True)
    tool_calls = db.Column(db.Text, nullable=True)
    tool_call_id = db.Column(db.String(64), nullable=True)
    name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)


class LoginLog(db.Model):
    """用户登录记录 — 记录登录时间、IP、区域"""
    __tablename__ = 'login_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    username = db.Column(db.String(50), nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    region = db.Column(db.String(100), nullable=True)
    user_agent = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)
    user = db.relationship('User', backref=db.backref('login_logs', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'ip_address': self.ip_address or '',
            'region': self.region or '',
            'user_agent': self.user_agent or '',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else '',
        }


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
