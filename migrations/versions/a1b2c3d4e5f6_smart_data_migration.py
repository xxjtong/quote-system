"""smart data migration: populate manufacturers and product manufacturer_id

Revision ID: a1b2c3d4e5f6
Revises: 9d16b898cc1c
Create Date: 2026-05-30 01:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


revision = 'a1b2c3d4e5f6'
down_revision = '9d16b898cc1c'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # 1. 将供应商中有产品的同步为制造商（supplier = manufacturer 是 IoT 行业常见模式）
    conn.execute(sa.text("""
        INSERT OR IGNORE INTO manufacturers (name, created_at, updated_at)
        SELECT DISTINCT s.name, datetime('now'), datetime('now')
        FROM suppliers s
        INNER JOIN products p ON p.supplier_id = s.id
        WHERE s.name NOT IN (SELECT name FROM manufacturers)
    """))
    result = conn.execute(sa.text("SELECT COUNT(*) FROM manufacturers"))
    mfr_count = result.scalar()
    print(f"[migration] Created {mfr_count} manufacturer entries from suppliers")

    # 2. 同步 product.manufacturer_id = product.supplier_id
    #    （产品从供应商采购，供应商即制造商）
    conn.execute(sa.text("""
        UPDATE products
        SET manufacturer_id = supplier_id
        WHERE supplier_id IS NOT NULL
          AND manufacturer_id IS NULL
    """))
    result = conn.execute(sa.text(
        "SELECT COUNT(*) FROM products WHERE manufacturer_id IS NOT NULL"
    ))
    product_count = result.scalar()
    print(f"[migration] Set manufacturer_id on {product_count} products")

    # 3. 处理遗留 category 逗号分隔 → 确保 category_id 填充（兜底逻辑）
    #    注意：主迁移已完成，此步骤仅处理边缘情况
    result = conn.execute(sa.text("""
        SELECT id, category FROM products
        WHERE category_id IS NULL AND category IS NOT NULL AND category != ''
    """))
    remaining = result.fetchall()
    if remaining:
        # 获取 category 名称 → id 映射
        cats = {
            row[1]: row[0]
            for row in conn.execute(sa.text("SELECT id, name FROM device_categories")).fetchall()
        }
        for prod_id, category_str in remaining:
            primary = category_str.split(',')[0].strip()
            cat_id = cats.get(primary)
            if cat_id:
                conn.execute(
                    sa.text("UPDATE products SET category_id = :cid WHERE id = :pid"),
                    {"cid": cat_id, "pid": prod_id}
                )
        print(f"[migration] Filled category_id for {len(remaining)} edge-case products")

    # 4. 清理无意义的 model 值
    conn.execute(sa.text("UPDATE products SET model = NULL WHERE model = '/' OR model = ''"))
    result = conn.execute(sa.text(
        "SELECT COUNT(*) FROM products WHERE model IS NOT NULL AND model != ''"
    ))
    print(f"[migration] Cleaned model field, now {result.scalar()} products have valid model")


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE products SET manufacturer_id = NULL"))
    conn.execute(sa.text("DELETE FROM manufacturers"))
    print("[migration] Reverted: cleared manufacturers and product manufacturer_id")
