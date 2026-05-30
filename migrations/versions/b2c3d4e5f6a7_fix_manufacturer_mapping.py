"""fix manufacturer_id to use name-based matching instead of ID-based

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-30 01:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # 按名称匹配修正 manufacturer_id（不能用 supplier_id 直接赋值，ID 序列不同）
    conn.execute(sa.text("""
        UPDATE products SET manufacturer_id = (
            SELECT m.id FROM manufacturers m
            JOIN suppliers s ON m.name = s.name
            WHERE s.id = products.supplier_id
        )
        WHERE supplier_id IS NOT NULL
    """))

    # 验证
    result = conn.execute(sa.text("""
        SELECT COUNT(*) FROM products p
        JOIN suppliers s ON p.supplier_id = s.id
        JOIN manufacturers m ON p.manufacturer_id = m.id
        WHERE s.name != m.name
    """))
    mismatches = result.scalar()
    if mismatches > 0:
        raise Exception(f"Still have {mismatches} mismatches after fix!")
    print(f"[migration] Fixed manufacturer_id mapping, {mismatches} mismatches remain")


def downgrade():
    pass  # 无需回退，只是修正数据
