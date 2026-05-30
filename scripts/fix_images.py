"""Fix broken product images by scraping from product_url"""
import re, sqlite3, os, time, urllib.request
from urllib.parse import urlparse

DB = 'quote.db'
BASE = os.path.dirname(os.path.abspath(DB))

def fetch(url):
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode('utf-8', errors='replace')
    except:
        return None

def extract_image(html, base_url):
    # og:image
    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html)
    if m:
        img = m.group(1)
        if img.startswith('/'):
            parts = urlparse(base_url)
            img = f'{parts.scheme}://{parts.netloc}{img}'
        if 'help-ursalink' not in img:
            return img
    return None

conn = sqlite3.connect(DB)
c = conn.cursor()

# Find products with broken local images that have product_url
c.execute("""SELECT p.id, p.name, p.product_url, pi.url as img_url
    FROM products p
    JOIN product_images pi ON p.id = pi.product_id
    WHERE pi.url LIKE '/uploads/%'
    AND p.product_url IS NOT NULL AND p.product_url != ''
    AND p.product_url LIKE '%milesight%'""")
products = c.fetchall()
print(f"Found {len(products)} products with broken local images + product_url")

fixed = 0
for pid, name, prod_url, old_img in products:
    fpath = os.path.join(BASE, old_img.lstrip('/'))
    if os.path.exists(fpath):
        continue  # File exists, skip

    html = fetch(prod_url)
    if not html:
        continue
    new_img = extract_image(html, prod_url)
    if not new_img:
        continue

    c.execute("UPDATE product_images SET url=? WHERE product_id=?", (new_img, pid))
    c.execute("UPDATE products SET image_url=? WHERE id=?", (new_img, pid))
    fixed += 1
    print(f"  [{pid}] {name[:30]} -> {new_img[:80]}")
    time.sleep(0.3)

conn.commit()
conn.close()
print(f"\nFixed {fixed} images")
