"""报价系统数据模型 — Product / Quote / QuoteItem / User / 辅助表"""
from datetime import datetime
from extensions import db


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
    image_data = db.Column(db.LargeBinary, nullable=True)
    image_mime = db.Column(db.String(30), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
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
            'has_image': bool(self.image_data),
            'is_active': self.is_active if self.is_active is not None else True,
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
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    remark = db.Column(db.Text, nullable=True)
    tax_rate = db.Column(db.Float, default=0)
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
    quote_id = db.Column(db.Integer, db.ForeignKey('quotes.id', ondelete='CASCADE'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    product_name = db.Column(db.String(200), nullable=False)
    product_sku = db.Column(db.String(100), nullable=True)
    product_spec = db.Column(db.String(500), nullable=True)
    product_unit = db.Column(db.String(20), nullable=True)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, default=0)
    amount = db.Column(db.Float, default=0)
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
            'remark': self.remark or '',
            'sort_order': self.sort_order,
            'profit': profit,
            'profit_rate': profit_rate,
        }


class DownloadLog(db.Model):
    __tablename__ = 'download_logs'
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey('quotes.id', ondelete='CASCADE'), nullable=False)
    user_name = db.Column(db.String(100), nullable=False)
    downloaded_at = db.Column(db.DateTime, default=datetime.now)
    quote = db.relationship('Quote', backref=db.backref('download_logs', cascade='all, delete-orphan'))

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

    def to_dict(self):
        return {
            'id': self.id, 'username': self.username,
            'role': self.role, 'is_active': self.is_active,
            'email': self.email or '',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
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


class AIChatSession(db.Model):
    """AI 对话初始化标记 — 替代内存 set，多 worker 安全"""
    __tablename__ = 'ai_chat_sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    initialized_at = db.Column(db.DateTime, default=datetime.now)
