"""smart M2M data extraction: parse comm methods, protocols, power supplies from product descriptions

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-30 02:10:00.000000

"""
import re
from alembic import op
import sqlalchemy as sa


revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


# Keyword → (model_class, dict_id) mapping
# Order matters: longer/more specific patterns first to avoid partial matches
COMM_METHOD_PATTERNS = [
    # (regex pattern, dict_comm_methods.id)
    (r'(?:^|[^\w])LoRaWAN(?:$|[^\w])', 8),      # LoRaWAN before LoRa
    (r'(?:^|[^\w])LoRa(?:$|[^\w])', 8),
    (r'Sub-G|SubG', 8),                            # Sub-G → LoRaWAN (closest match)
    (r'(?:^|[^\w])Wi-?Fi(?:$|[^\w])', 9),
    (r'(?:^|[^\w])4G(?:$|[^\w])', 10),
    (r'(?:^|[^\w])LTE(?:$|[^\w])', 10),
    (r'(?:^|[^\w])5G(?:$|[^\w])', 11),
    (r'NB-?IoT', 12),
    (r'(?:^|[^\w])Zig[bB]ee(?:$|[^\w])', 13),
    (r'(?:^|[^\w])BLE(?:$|[^\w])', 14),
    (r'蓝牙|Bluetooth', 14),
    (r'(?:^|[^\w])NFC(?:$|[^\w])', 15),
    (r'GPS|GNSS', 16),
    (r'RJ-?45|以太网|Ethernet|千兆网口|百兆网口', 1),
    (r'RS-?485', 2),
    (r'RS-?232', 3),
    (r'KNX', 5),
    (r'M-BUS|M-Bus', 6),
    (r'(?:^|[^\w])USB(?:$|[^\w])', 7),
]

COMM_PROTOCOL_PATTERNS = [
    # (regex pattern, dict_comm_protocols.id)
    (r'MQTTS', 4),                                 # MQTTS before MQTT
    (r'(?:^|[^\w])MQTT(?:$|[^\w])', 3),
    (r'ModBus-?RTU|Modbus\s*RTU', 5),
    (r'ModBus-?TCP|Modbus\s*TCP', 6),
    (r'ModBus|Modbus', 5),                         # Generic Modbus → RTU default
    (r'HTTPS(?!://)', 2),                           # HTTPS not part of URL
    (r'(?:^|[^\w])HTTP(?!S|s)(?:$|[^\w/])', 1),    # HTTP standalone, not HTTPS
    (r'BACnet/?IP', 7),
    (r'BACnet/?MS-?TP', 8),
    (r'BACnet', 7),                                # Generic BACnet → IP default
    (r'(?:^|[^\w])SNMP(?:$|[^\w])', 11),
    (r'(?:^|[^\w])SSH(?:$|[^\w])', 12),
    (r'(?:^|[^\w])VPN(?:$|[^\w])', 13),
    (r'(?:^|[^\w])RTSP(?:$|[^\w])', 14),
    (r'(?:^|[^\w])NTP(?:$|[^\w])', 15),
    (r'(?:^|[^\w])TCP(?:$|[^\w/])', 9),
    (r'(?:^|[^\w])UDP(?:$|[^\w/])', 10),
]

POWER_SUPPLY_PATTERNS = [
    # (regex pattern, dict_power_supplies.id)
    (r'POE|PoE(?:\s*供?电|[\s(]|$|,)', 2),        # PoE with context
    (r'USB-?C|Type-?C(?:\s*供?电)?', 4),
    (r'太阳能|Solar', 6),
    (r'电池(?:供?电)?|Battery|锂电|蓄电池', 3),
    (r'DC\s*(?:供?电|电源|输入)?(?:\s*\d{1,2}\s*V)?', 1),   # DC with voltage context
    (r'(?:^|[^\w])DC(?:\s|$|,|\)|\d)', 1),         # DC at word boundary
    (r'AC\s*(?:供?电|电源|输入)?(?:\s*\d{2,3}\s*V)?', 5),
    (r'220\s*V|110\s*V', 5),                       # Mains voltage → AC
]


def _extract(text, patterns):
    """Extract matched dict_ids from text using patterns. Returns set of dict_ids."""
    if not text:
        return set()
    result = set()
    for pattern, dict_id in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            result.add(dict_id)
    return result


def upgrade():
    conn = op.get_bind()

    # Fetch all products with their descriptions
    rows = conn.execute(sa.text(
        "SELECT id, function_desc, spec, remark FROM products"
    )).fetchall()

    comm_methods_data = []
    comm_protocols_data = []
    power_supplies_data = []
    stats = {'comm': 0, 'proto': 0, 'power': 0, 'products': 0}

    for prod_id, func_desc, spec, remark in rows:
        text = ' '.join(filter(None, [func_desc or '', spec or '', remark or '']))
        if not text.strip():
            continue

        cm_ids = _extract(text, COMM_METHOD_PATTERNS)
        cp_ids = _extract(text, COMM_PROTOCOL_PATTERNS)
        ps_ids = _extract(text, POWER_SUPPLY_PATTERNS)

        has_data = False
        for cm_id in cm_ids:
            comm_methods_data.append({'product_id': prod_id, 'method_id': cm_id})
            has_data = True
        for cp_id in cp_ids:
            comm_protocols_data.append({'product_id': prod_id, 'protocol_id': cp_id})
            has_data = True
        for ps_id in ps_ids:
            power_supplies_data.append({'product_id': prod_id, 'power_id': ps_id})
            has_data = True

        if has_data:
            stats['products'] += 1
            stats['comm'] += len(cm_ids)
            stats['proto'] += len(cp_ids)
            stats['power'] += len(ps_ids)

    # Batch insert
    if comm_methods_data:
        conn.execute(
            sa.text("INSERT INTO product_comm_methods (product_id, method_id) VALUES (:product_id, :method_id)"),
            comm_methods_data
        )
    if comm_protocols_data:
        conn.execute(
            sa.text("INSERT INTO product_comm_protocols (product_id, protocol_id) VALUES (:product_id, :protocol_id)"),
            comm_protocols_data
        )
    if power_supplies_data:
        conn.execute(
            sa.text("INSERT INTO product_power_supplies (product_id, power_id) VALUES (:product_id, :power_id)"),
            power_supplies_data
        )

    print(f"[migration] Extracted M2M data for {stats['products']} products:")
    print(f"  Comm methods: {len(comm_methods_data)} rows")
    print(f"  Comm protocols: {len(comm_protocols_data)} rows")
    print(f"  Power supplies: {len(power_supplies_data)} rows")


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM product_comm_methods"))
    conn.execute(sa.text("DELETE FROM product_comm_protocols"))
    conn.execute(sa.text("DELETE FROM product_power_supplies"))
    print("[migration] Reverted: cleared all M2M data")
