"""add product type dict and FK

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-30 08:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


PRODUCT_TYPES = ['传感器', '控制器', '网关', '路由器', '配件', '终端设备', '执行器', '电源']


def upgrade():
    # Create dict_product_types table
    op.create_table('dict_product_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('sort_order', sa.Integer(), default=0),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    # Seed product types
    conn = op.get_bind()
    for i, name in enumerate(PRODUCT_TYPES):
        conn.execute(
            sa.text("INSERT INTO dict_product_types (id, name, sort_order) VALUES (:id, :name, :sort)"),
            {'id': i + 1, 'name': name, 'sort': i}
        )

    # Add product_type_id FK to products
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.add_column(sa.Column('product_type_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_products_product_type_id', ['product_type_id'])
        batch_op.create_foreign_key('fk_product_type', 'dict_product_types', ['product_type_id'], ['id'])


def downgrade():
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_constraint('fk_product_type', type_='foreignkey')
        batch_op.drop_index('ix_products_product_type_id')
        batch_op.drop_column('product_type_id')
    op.drop_table('dict_product_types')
