"""add missing indexes

Revision ID: 9d16b898cc1c
Revises: e0d0ca6f2b58
Create Date: 2026-05-30 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '9d16b898cc1c'
down_revision = 'e0d0ca6f2b58'
branch_labels = None
depends_on = None


def upgrade():
    # === 产品表缺失的 FK 索引 (models.py 已声明但 DB 未建) ===
    op.create_index('ix_products_sku', 'products', ['sku'])
    op.create_index('ix_products_model', 'products', ['model'])
    op.create_index('ix_products_category_id', 'products', ['category_id'])
    op.create_index('ix_products_manufacturer_id', 'products', ['manufacturer_id'])
    op.create_index('ix_products_supplier_id', 'products', ['supplier_id'])
    op.create_index('ix_products_parent_id', 'products', ['parent_id'])
    op.create_index('ix_products_status', 'products', ['status'])

    # === FK 关联表缺失索引 (高频 per-product 查询) ===
    op.create_index('ix_download_logs_quote_id', 'download_logs', ['quote_id'])
    op.create_index('ix_product_images_product_id', 'product_images', ['product_id'])
    op.create_index('ix_product_hardware_interfaces_product_id', 'product_hardware_interfaces', ['product_id'])
    op.create_index('ix_category_spec_definitions_category_id', 'category_spec_definitions', ['category_id'])
    op.create_index('ix_product_dependencies_product_id', 'product_dependencies', ['product_id'])
    op.create_index('ix_product_dependencies_depends_on_product_id', 'product_dependencies', ['depends_on_product_id'])

    # === suppliers 名称查找 ===
    op.create_index('ix_suppliers_name', 'suppliers', ['name'])

    # === 复合索引 (常用组合查询) ===
    op.create_index('ix_ai_usage_user_created', 'ai_usage_logs', ['user_id', 'created_at'])
    op.create_index('ix_quotes_created_by_status', 'quotes', ['created_by', 'status'])
    op.create_index('ix_quotes_created_at', 'quotes', ['created_at'])
    op.create_index('ix_login_logs_user_created', 'login_logs', ['user_id', 'created_at'])

    # === 清理冗余索引: conversation_id 单列被复合索引覆盖 ===
    op.drop_index('ix_ai_messages_conversation_id', table_name='ai_messages')


def downgrade():
    op.create_index('ix_ai_messages_conversation_id', 'ai_messages', ['conversation_id'])

    op.drop_index('ix_login_logs_user_created', table_name='login_logs')
    op.drop_index('ix_quotes_created_at', table_name='quotes')
    op.drop_index('ix_quotes_created_by_status', table_name='quotes')
    op.drop_index('ix_ai_usage_user_created', table_name='ai_usage_logs')

    op.drop_index('ix_suppliers_name', table_name='suppliers')

    op.drop_index('ix_product_dependencies_depends_on_product_id', table_name='product_dependencies')
    op.drop_index('ix_product_dependencies_product_id', table_name='product_dependencies')
    op.drop_index('ix_category_spec_definitions_category_id', table_name='category_spec_definitions')
    op.drop_index('ix_product_hardware_interfaces_product_id', table_name='product_hardware_interfaces')
    op.drop_index('ix_product_images_product_id', table_name='product_images')
    op.drop_index('ix_download_logs_quote_id', table_name='download_logs')

    op.drop_index('ix_products_status', table_name='products')
    op.drop_index('ix_products_parent_id', table_name='products')
    op.drop_index('ix_products_supplier_id', table_name='products')
    op.drop_index('ix_products_manufacturer_id', table_name='products')
    op.drop_index('ix_products_category_id', table_name='products')
    op.drop_index('ix_products_model', table_name='products')
    op.drop_index('ix_products_sku', table_name='products')
