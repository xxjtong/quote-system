"""更新所有星纵产品详细规格 — 从产品URL页面抓取"""
import re, sqlite3, time, urllib.request
from html import unescape

DB = 'quote.db'

def fetch(url):
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=12) as r:
            return r.read().decode('utf-8', errors='replace')
    except:
        return None

def extract_text(html):
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text)
    return text

def scrape_comm_details(text, method_name):
    """Extract details for a specific communication method."""
    patterns = {
        'LoRaWAN': [
            (r'(?:工作频段|频段|Frequency)[:\s]*([\d~、\-A-Za-z/()]+)', '频段'),
            (r'(?:发射功率|Tx\s*Power)[:\s]*([\d~、\-A-Za-z()dBm/]+)', '发射功率'),
            (r'(?:接收灵敏度|Sensitivity)[:\s]*([\d~、\-A-Za-z()dBm/]+)', '灵敏度'),
            (r'(?:Class|工作模式)[:\s]*([\d~、\-A-Za-z/()]+)', '模式'),
            (r'(?:协议|Protocol)[:\s]*([^。，,\n]{5,40})', '协议'),
            (r'(\d+)\s*(?:通道|Channel)', '通道'),
        ],
        'BLE': [
            (r'(?:蓝牙|BLE|Bluetooth)[^。]{0,60}(?:(\d+\.?\d*)\s*BLE)', '版本'),
            (r'蓝牙\s*(\d+\.?\d*)', '版本'),
            (r'BLE\s*(\d+\.?\d*)', '版本'),
        ],
        'NFC': [
            (r'NFC[^。]{0,40}', 'NFC'),
            (r'(\d+\.?\d*)\s*MHz.*?NFC', '频率'),
        ],
        'WiFi': [
            (r'Wi-?Fi[^。]{0,60}(?:(\d+\.?\d*)\s*GHz)', '频段'),
            (r'(?:802\.11\s*[a-z/]+)', '标准'),
        ],
        '4G': [
            (r'(?:4G|LTE|CAT\s*\d)[^。]{0,80}', '4G'),
        ],
        'Ethernet': [
            (r'(?:以太网|Ethernet|RJ-?45)[^。]{0,60}(?:(\d+/\d+\s*Mbps))', '速率'),
        ],
    }

    pats = patterns.get(method_name, [])
    details = []
    for pattern, label in pats:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip() if m.lastindex else m.group(0).strip()
            if len(val) > 3 and len(val) < 60:
                details.append(val)
    return '; '.join(details[:3]) if details else ''

def scrape_power_details(text, power_name):
    """Extract details for power supply."""
    if power_name == 'Battery':
        patterns = [
            r'(\d+\s*[节×]\s*\d+\s*(?:mAh|毫安时)\s*(?:ER\d+|锂\w*\s*电池|Li[-\s]\w+))',
            r'(?:电池|Battery)[^。]{0,60}(\d+\s*(?:年|year|Y))',
        ]
    elif power_name == 'DC':
        patterns = [
            r'DC\s*(\d+\s*[-~]\s*\d+\s*V)',
            r'(\d+\s*VDC)',
        ]
    elif power_name == 'PoE':
        patterns = [
            r'(802\.3\s*[a-z]+\s*PoE[^,，。]*)',
        ]
    else:
        return ''

    details = []
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip() if m.lastindex else m.group(0).strip()
            if len(val) > 2:
                details.append(val)
    return details[0] if details else ''

def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT id FROM manufacturers WHERE name='星纵'")
    xz_id = c.fetchone()[0]

    c.execute("""SELECT DISTINCT p.id, p.name, p.product_url FROM products p
        WHERE p.manufacturer_id = ? AND p.product_url IS NOT NULL AND p.product_url != ''
        AND p.product_url LIKE '%milesight%'
        ORDER BY p.id""", (xz_id,))
    products = c.fetchall()
    print(f"处理 {len(products)} 个星纵产品\n")

    updated_comm = 0
    updated_power = 0

    for pid, name, url in products:
        html = fetch(url)
        if not html:
            continue
        text = extract_text(html)

        # Update comm method details
        c.execute("""SELECT pcm.method_id, dm.name FROM product_comm_methods pcm
            JOIN dict_comm_methods dm ON pcm.method_id = dm.id
            WHERE pcm.product_id = ? AND (pcm.details IS NULL OR pcm.details = '')""", (pid,))
        for mid, mname in c.fetchall():
            detail = scrape_comm_details(text, mname)
            if detail:
                c.execute("UPDATE product_comm_methods SET details=? WHERE product_id=? AND method_id=?",
                          (detail, pid, mid))
                updated_comm += 1

        # Update power supply details
        c.execute("""SELECT pps.power_id, dps.name FROM product_power_supplies pps
            JOIN dict_power_supplies dps ON pps.power_id = dps.id
            WHERE pps.product_id = ? AND (pps.voltage_range IS NULL OR pps.voltage_range = '')""", (pid,))
        for pw_id, pw_name in c.fetchall():
            detail = scrape_power_details(text, pw_name)
            if detail:
                c.execute("UPDATE product_power_supplies SET voltage_range=? WHERE product_id=? AND power_id=?",
                          (detail, pid, pw_id))
                updated_power += 1

        print(f"  [{pid}] {name[:35]}")
        time.sleep(0.2)

    conn.commit()
    print(f"\n更新通讯详情: {updated_comm} 条")
    print(f"更新供电规格: {updated_power} 条")
    conn.close()

if __name__ == '__main__':
    main()
