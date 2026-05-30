"""extract URLs from remark and function_desc into product_url

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-30 02:50:00.000000

"""
import re
from alembic import op
import sqlalchemy as sa


revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


URL_RE = re.compile(r'https?://[^\s,，。；;）\)】\]一-鿿]+', re.IGNORECASE)


def upgrade():
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT id, function_desc, remark, product_url FROM products"
    )).fetchall()

    updates = []
    for prod_id, func_desc, remark, product_url in rows:
        if product_url and product_url.strip():
            continue  # already has URL, don't overwrite
        text = ' '.join(filter(None, [remark or '', func_desc or '']))
        urls = URL_RE.findall(text)
        if urls:
            # Use the first URL found
            url = urls[0].rstrip('.')
            if len(url) > 500:
                url = url[:500]
            updates.append({'id': prod_id, 'url': url})

    if updates:
        conn.execute(
            sa.text("UPDATE products SET product_url = :url WHERE id = :id"),
            updates
        )

    print(f"[migration] Extracted product_url for {len(updates)} products")


def downgrade():
    pass  # no destructive action needed
