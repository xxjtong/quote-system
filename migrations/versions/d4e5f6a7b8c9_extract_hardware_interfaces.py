"""extract hardware interfaces and sensor capabilities from product descriptions

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-30 02:30:00.000000

"""
import re
from alembic import op
import sqlalchemy as sa


revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


# ─── Hardware Interfaces ───────────────────────────────────────

def _parse_interfaces(text):
    if not text:
        return []
    results = []
    seen_lower = set()

    # Pattern 1: "NAME*N" or "NAME ×N" or "NAMExN" (not dimension patterns like 261x167x29mm)
    for m in re.finditer(r'(?<!\d)([A-Za-z][\w.\-\s/]*?)\s*[*×]\s*(\d+)(?!\s*(?:mm|cm|kg|g|px))', text):
        name = m.group(1).strip()
        name = re.sub(r'\s+', ' ', name)
        qty = int(m.group(2))
        # Filter: skip dimensions, weight specs, and very generic names
        if name.lower() in ('mm', 'cm', 'kg', 'g', 'kg', 'x', 'px'):
            continue
        if re.match(r'^[\d.x]+$', name):  # pure numbers/dots
            continue
        if 2 <= len(name) <= 30 and qty <= 999 and name.lower() not in seen_lower:
            seen_lower.add(name.lower())
            ctx = text[max(0, m.start()-5):m.end()+30].strip()
            results.append((name, qty, ctx[:255]))

    # Pattern 2: "N路/个/组 NAME"
    for m in re.finditer(r'(\d+)\s*(?:路|个|组|通道)\s*([一-鿿A-Za-z][一-鿿\w.\-]{1,20})', text):
        qty = int(m.group(1))
        name = m.group(2).strip()
        if len(name) >= 1 and name.lower() not in seen_lower:
            seen_lower.add(name.lower())
            ctx = text[max(0, m.start()-3):m.end()+20].strip()
            results.append((name, qty, ctx[:255]))

    # Filter noise
    filtered = [(n, q, c) for n, q, c in results if len(n) >= 2 and not re.match(r'^\d+$', n)]

    priority = {'RJ-45':0,'RJ45':0,'USB':1,'USB2.0':2,'USB3.0':3,
                'RS-485':4,'RS485':4,'RS-232':5,'RS232':5,
                'WGD':6,'HDMI':7,'GPIO':8,'DI':9,'DO':10,'DI/DO':11}
    filtered.sort(key=lambda x: (priority.get(x[0], 99), x[0]))

    seen = set()
    return [(n, q, c) for n, q, c in filtered if not (n.lower() in seen or seen.add(n.lower()))]


# ─── Sensor Capabilities ───────────────────────────────────────

# keyword → (metric_id, metric_name_for_log)
SENSOR_KEYWORDS = [
    # Chinese name, English alias → metric_id
    (r'温度|temp(?:erature)?(?!\s*(?:范围|补偿))', 1),
    (r'湿度|humidity', 2),
    (r'CO2|二氧化碳(?!\s*(?:传感|监测|浓度))', 3),
    (r'TVOC|tvoc', 4),
    (r'PM2\.5|pm2\.5|PM2_5', 5),
    (r'PM10|pm10', 6),
    (r'(?:大气?)?气压|barometric|pressure(?!\s*(?:传感))', 7),  # avoid "pressure sensor" (压力传感器 could be generic)
    (r'光照|光感(?:应)?|亮度|illumin|lux(?!\w)', 8),
    (r'噪声|噪音|noise|分贝|sound\s*level', 9),
    (r'水浸|漏水|water\s*leak|flood', 10),
    (r'门磁|door\s*sensor|门开关', 11),
    (r'倾斜|tilt|倾角', 12),
    (r'液位|water\s*level|liquid\s*level', 13),
    (r'压力|pressure(?!\s*(?:传感))', 14),  # be careful: "压力" could mean "气压"
    (r'距离|测距|探测距离|distance|超声波|ultrasonic|TOF|ToF|雷达', 15),
    (r'人数|客流|people\s*count|occupancy', 16),
    (r'人体存在|存在感应|存在检测|PIR|人体感应|人体检测|occupancy|mmWave|毫米波', 17),
    (r'CO(?!2)|一氧化碳|carbon\s*monoxide', 18),
    (r'O3|臭氧|ozone', 19),
    (r'HCHO|甲醛|formaldehyde', 20),
    (r'电流|current(?!\s*(?:loop))', 21),
]

RANGE_PATTERNS = [
    # measurement range patterns: "0~100℃", "0-50°C", "0 to 100ppm", "±0.5℃"
    r'([-+]?\d+\.?\d*\s*[-~～to]+\s*[-+]?\d+\.?\d*\s*(?:℃|°C|%RH|ppm|ppb|lux|dB|hPa|μg/m³|m|A)?)',
    r'(?:精度|准确度|accuracy)[:：]?\s*([-+]?\d+\.?\d*\s*(?:℃|°C|%RH|ppm|ppb|lux|dB|hPa|μg/m³|m|A|%|级)?)',
    r'([-+]?\d+\.?\d*\s*(?:℃|°C|%RH|ppm|ppb|lux|dB|hPa|μg/m³|m|A))',
]

RESOLUTION_PATTERNS = [
    r'(?:分辨率|resolution)[:：]?\s*([-+]?\d+\.?\d*\s*(?:℃|°C|%RH|ppm|ppb|lux|dB|hPa|μg/m³|m|A|bit)?)',
]


def _extract_sensors(text):
    """Extract sensor capabilities from text. Returns list of (metric_id, range_str, accuracy_str, resolution_str)."""
    if not text:
        return []
    results = []
    seen_metrics = set()

    for pattern, metric_id in SENSOR_KEYWORDS:
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            continue
        if metric_id in seen_metrics:
            continue
        seen_metrics.add(metric_id)

        # Extract context window around the match
        ctx_start = max(0, m.start() - 40)
        ctx_end = min(len(text), m.end() + 80)
        ctx = text[ctx_start:ctx_end]

        measure_range = ''
        accuracy = ''
        resolution = ''

        for rp in RANGE_PATTERNS:
            rm = re.search(rp, ctx)
            if rm:
                val = rm.group(1).strip().rstrip(',.;，。；')
                if len(val) > 2 and len(val) < 30:
                    if '精度' in rp or '准确度' in rp or 'accuracy' in rp.lower():
                        if not accuracy:
                            accuracy = val
                    else:
                        if not measure_range:
                            measure_range = val

        for rp in RESOLUTION_PATTERNS:
            rm = re.search(rp, ctx)
            if rm:
                resolution = rm.group(1).strip()

        results.append((metric_id, measure_range, accuracy, resolution))

    return results


# ─── Upgrade / Downgrade ───────────────────────────────────────

def upgrade():
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT id, function_desc, spec, remark FROM products"
    )).fetchall()

    hw_data = []
    sensor_data = []
    hw_products = 0
    hw_rows = 0
    sn_products = 0
    sn_rows = 0

    for prod_id, func_desc, spec, remark in rows:
        text = ' '.join(filter(None, [func_desc or '', spec or '', remark or '']))
        if not text.strip():
            continue

        # Hardware interfaces
        interfaces = _parse_interfaces(text)
        if interfaces:
            hw_products += 1
            for sort_order, (name, qty, ctx) in enumerate(interfaces):
                hw_data.append({
                    'product_id': prod_id,
                    'interface_name': name[:50],
                    'quantity': qty,
                    'description': ctx[:255],
                })
                hw_rows += 1

        # Sensor capabilities
        sensors = _extract_sensors(text)
        if sensors:
            sn_products += 1
            for metric_id, measure_range, accuracy, resolution in sensors:
                sensor_data.append({
                    'product_id': prod_id,
                    'metric_id': metric_id,
                    'measure_range': measure_range or '',
                    'accuracy': accuracy or '',
                    'resolution': resolution or '',
                })
                sn_rows += 1

    if hw_data:
        conn.execute(sa.text("""INSERT INTO product_hardware_interfaces
            (product_id, interface_name, quantity, description)
            VALUES (:product_id, :interface_name, :quantity, :description)"""), hw_data)

    if sensor_data:
        conn.execute(sa.text("""INSERT INTO product_sensor_capabilities
            (product_id, metric_id, measure_range, accuracy, resolution)
            VALUES (:product_id, :metric_id, :measure_range, :accuracy, :resolution)"""), sensor_data)

    print(f"[migration] HW interfaces: {hw_rows} rows for {hw_products} products")
    print(f"[migration] Sensors: {sn_rows} rows for {sn_products} products")


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM product_hardware_interfaces"))
    conn.execute(sa.text("DELETE FROM product_sensor_capabilities"))
    print("[migration] Reverted: cleared HW interfaces and sensors")
