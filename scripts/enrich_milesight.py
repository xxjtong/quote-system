"""
Milesight 产品规格爬取 v2 — 解析多行嵌套规格表，提取传感器精度/量程/分辨率
"""
import re, sqlite3, time, urllib.request
from html import unescape

DB = 'quote.db'

SENSOR_MAP = {
    '温度':1,'temp':1,'湿度':2,'humidity':2,'二氧化碳':3,'CO2':3,'co2':3,
    'TVOC':4,'tvoc':4,'PM2.5':5,'pm2.5':5,'PM10':6,'pm10':6,
    '气压':7,'大气压':7,'barometric':7,'光照':8,'light':8,'lux':8,
    '噪声':9,'noise':9,'水浸':10,'leak':10,'门磁':11,'door':11,
    '倾斜':12,'tilt':12,'液位':13,'level':13,'压力':14,'pressure':14,
    '距离':15,'distance':15,'人数':16,'people':16,'客流':16,
    '人体':17,'PIR':17,'存在':17,'pir':17,'一氧化碳':18,'CO':18,
    '臭氧':19,'O3':19,'o3':19,'ozone':19,'甲醛':20,'HCHO':20,'hcho':20,'formaldehyde':20,
    '电流':21,'current':21,'IAQ':4,  # IAQ → TVOC
}

RANGE_KEYS = ['采集范围','测量范围','检测范围','量程','范围','range','Range']
ACCURACY_KEYS = ['采集精度','精度','准确度','accuracy','Accuracy','±']
RESOLUTION_KEYS = ['分辨率','resolution','Resolution']


def fetch(url):
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode('utf-8', errors='replace')
    except Exception as e:
        return None


def parse_specs(html):
    """Parse spec table, return list of (param_category, param_name, variant_values)."""
    tables = re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL)
    if not tables:
        return [], []

    # Find and merge ALL tables
    all_rows = []
    for t in tables:
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', t, re.DOTALL)
        parsed = []
        for r in rows:
            cells = re.findall(r'<(?:td|th)[^>]*>(.*?)</(?:td|th)>', r, re.DOTALL)
            clean = []
            for c in cells:
                text = re.sub(r'<[^>]+>', '', c)
                text = unescape(text).strip()
                text = re.sub(r'\s+', ' ', text)
                clean.append(text)
            if clean:
                parsed.append(clean)
        if parsed:
            all_rows.extend(parsed)

    return all_rows


def match_sensor(text):
    """Return (metric_id, sensor_name) if text matches a sensor, else None."""
    for kw, mid in sorted(SENSOR_MAP.items(), key=lambda x: -len(x[0])):
        if re.search(kw, text, re.IGNORECASE):
            return (mid, kw)
    return None


def extract_metric_value(text):
    """Extract range, accuracy, resolution from a value cell."""
    result = {'measure_range': '', 'accuracy': '', 'resolution': ''}
    text = text.strip()
    if not text or text.strip() in ('—', '-', '/', '\\', '–', ''):
        return result

    # Try to find range pattern: N~M unit or N-M unit
    m = re.search(r'([-+]?\d+\.?\d*\s*[-~～]+\s*[-+]?\d+\.?\d*\s*(?:℃|°C|%RH|%|ppm|ppb|lux|dB|hPa|μg|mg|m|A)?)', text)
    if m:
        result['measure_range'] = m.group(1).strip()

    # Accuracy (±X or ±X% or ±X unit)
    m = re.search(r'([±+-]\s*\d+\.?\d*\s*(?:%|℃|°C|ppm|ppb|lux|dB|hPa|μg|mg|m|A)?)', text)
    if m:
        result['accuracy'] = m.group(1).strip()

    # Resolution
    m = re.search(r'(\d+\.?\d*\s*(?:μg|mg|ppm|ppb|lux|℃|°C|dB|hPa|m|A|bit))', text)
    if m and 'resolution' not in result:
        result['resolution'] = m.group(1).strip()

    return result


def extract_main_image(html, base_url):
    """Extract product image URL from meta tags or first large image."""
    # Try og:image first
    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html)
    if m:
        img = m.group(1)
        if img.startswith('/'):
            from urllib.parse import urlparse
            parts = urlparse(base_url)
            img = f'{parts.scheme}://{parts.netloc}{img}'
        return img
    # Try first product image with dimensions
    m = re.search(r'<img[^>]+src=["\']([^"\']+\.(?:jpg|png|webp))["\'][^>]*width=["\']([5-9]\d{2}|\d{4,})', html)
    if m:
        img = m.group(1)
        if img.startswith('/'):
            from urllib.parse import urlparse
            parts = urlparse(base_url)
            img = f'{parts.scheme}://{parts.netloc}{img}'
        return img
    return None


def save_image(pid, image_url):
    """Save image URL to product_images table. Replace if existing image is broken (local path)."""
    # Skip placeholder images
    if 'help-ursalink' in image_url or 'placeholder' in image_url.lower():
        return
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # Check if existing image is a broken local file
    c.execute("SELECT url FROM product_images WHERE product_id=? AND is_primary=1", (pid,))
    existing = c.fetchone()
    needs_replace = False
    if existing:
        existing_url = existing[0]
        if existing_url.startswith('/uploads/'):
            import os
            fpath = os.path.join(os.path.dirname(os.path.abspath(DB)), existing_url.lstrip('/'))
            if not os.path.exists(fpath):
                needs_replace = True

    if needs_replace:
        c.execute("UPDATE product_images SET url=? WHERE product_id=?", (image_url, pid))
        c.execute("UPDATE products SET image_url=? WHERE id=?", (image_url, pid))
    elif not existing:
        c.execute("INSERT INTO product_images (product_id, url, is_primary, sort_order) VALUES (?, ?, 1, 0)",
                  (pid, image_url))
        c.execute("UPDATE products SET image_url=? WHERE id=? AND (image_url IS NULL OR image_url='')",
                  (image_url, pid))

    conn.commit()
    conn.close()


def process_product(pid, name, model, url):
    """Fetch and update one product."""
    print(f'[{pid}] {name}')
    html = fetch(url)
    if not html:
        print(f'  ✗ fetch failed')
        return False

    # Extract and save product image
    img_url = extract_main_image(html, url)
    if img_url:
        save_image(pid, img_url)
        print(f'  image: {img_url[:80]}')

    rows = parse_specs(html)
    if not rows:
        print(f'  ✗ no tables')
        return False

    # Group rows: if col0 is non-empty, it's a category header
    # Build: {sensor_metric_id: {range, accuracy, resolution}}
    sensor_data = {}
    current_category = ''
    current_sensor = None  # Track last matched sensor for sub-rows

    for cells in rows:
        if len(cells) < 2:
            continue

        col0 = cells[0]
        col1 = cells[1] if len(cells) > 1 else ''
        values = cells[2:] if len(cells) > 2 else [col1]

        # If col0 is a category header (bold, short, not a value)
        if col0 and not re.match(r'^[-–—±+\d]', col0) and len(col0) <= 30:
            current_category = col0

        # Try to match sensor from col1 (sub-parameter) or col0 or inherit
        param_text = f'{current_category} {col1}'
        match = match_sensor(param_text)
        if not match:
            match = match_sensor(col0)

        # If no new match but col0 is empty, inherit last sensor
        if not match and not col0:
            metric_id = current_sensor
        elif match:
            metric_id, _ = match
            current_sensor = metric_id
        else:
            current_sensor = None
            continue
        val = values[0] if values else ''

        # Determine if this row specifies range, accuracy, or resolution
        is_range = any(k in param_text for k in RANGE_KEYS)
        is_accuracy = any(k in param_text for k in ACCURACY_KEYS)
        is_resolution = any(k in param_text for k in RESOLUTION_KEYS)

        if not is_range and not is_accuracy and not is_resolution:
            # Generic row — treat the value as a combined spec
            is_range = True

        if metric_id not in sensor_data:
            sensor_data[metric_id] = {'measure_range': '', 'accuracy': '', 'resolution': ''}

        extracted = extract_metric_value(val)

        if is_range and extracted['measure_range']:
            sensor_data[metric_id]['measure_range'] = extracted['measure_range']
        elif is_range and val:
            sensor_data[metric_id]['measure_range'] = val[:80]

        if is_accuracy and extracted['accuracy']:
            if extracted['accuracy'] not in ('—', '-', '/'):
                sensor_data[metric_id]['accuracy'] = extracted['accuracy']
        elif is_accuracy and val and val not in ('—', '-', '/'):
            sensor_data[metric_id]['accuracy'] = val[:80]

        if is_resolution and extracted['resolution']:
            if extracted['resolution'] not in ('—', '-', '/'):
                sensor_data[metric_id]['resolution'] = extracted['resolution']
        elif is_resolution and val and val not in ('—', '-', '/'):
            sensor_data[metric_id]['resolution'] = val[:80]

    # Filter out invalid metric_ids
    sensor_data = {k: v for k, v in sensor_data.items() if k is not None and k > 0}

    if not sensor_data:
        print(f'  - no sensor data found')
        return False

    # Update DB
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("DELETE FROM product_sensor_capabilities WHERE product_id=?", (pid,))
        for mid, detail in sensor_data.items():
            c.execute("""INSERT INTO product_sensor_capabilities
                (product_id, metric_id, measure_range, accuracy, resolution)
                VALUES (?, ?, ?, ?, ?)""",
                (pid, mid, detail['measure_range'] or '',
                 detail['accuracy'] or '', detail['resolution'] or ''))
        conn.commit()
    except Exception as e:
        print(f'  DB error: {e}')
    finally:
        conn.close()

    for mid, d in sorted(sensor_data.items()):
        parts = []
        if d['measure_range']: parts.append(f"range={d['measure_range']}")
        if d['accuracy']: parts.append(f"acc={d['accuracy']}")
        if d['resolution']: parts.append(f"res={d['resolution']}")
        print(f'  metric_id={mid}: {", ".join(parts)}')
    return True


def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""SELECT id, name, model, product_url FROM products
        WHERE product_url LIKE '%milesight%' AND product_url != '' ORDER BY id""")
    products = c.fetchall()
    conn.close()

    print(f'Processing {len(products)} products...\n')
    ok = fail = 0

    for pid, name, model, url in products:
        if process_product(pid, name, model, url):
            ok += 1
        else:
            fail += 1
        time.sleep(0.3)

    print(f'\nDone: {ok} updated, {fail} failed')


if __name__ == '__main__':
    main()
