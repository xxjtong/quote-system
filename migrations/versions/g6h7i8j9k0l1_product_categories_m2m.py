"""product categories M2M table

Revision ID: g6h7i8j9k0l1
Revises: f6a7b8c9d0e1
Create Date: 2026-05-30 13:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'g6h7i8j9k0l1'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('product_categories',
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('device_categories.id', ondelete='CASCADE'), primary_key=True),
    )
    op.create_index('ix_product_categories_category_id', 'product_categories', ['category_id'])

    # Migrate existing data: parse comma-separated category strings
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, category FROM products WHERE category IS NOT NULL AND category != ''")).fetchall()
    seen = set()
    count = 0
    for pid, cat_str in rows:
        cat_ids = set()
        from models import DeviceCategory
        cats = DeviceCategory.query.filter_by(is_active=True).all()
        cat_map = {c.name: c.id for c in cats}
        for tag in cat_str.split(','):
            tag = tag.strip()
            if tag and tag in cat_map:
                cat_ids.add(cat_map[tag])
        for cid in cat_ids:
            key = (pid, cid)
            if key not in seen:
                seen.add(key)
                conn.execute(sa.text("INSERT INTO product_categories (product_id, category_id) VALUES (:pid, :cid)"), {'pid': pid, 'cid': cid})
                count += 1
    print(f"[migration] Created {count} product-category M2M rows")


def downgrade():
    op.drop_index('ix_product_categories_category_id', table_name='product_categories')
    op.drop_table('product_categories')
