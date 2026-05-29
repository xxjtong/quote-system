"""AI 回复解析 — 价格提取 + Quick Reply 生成"""
import json
import re


def parse_reply_actions(reply_text):
    """从 AI 回复中提取产品名/价格/报价单引用/快捷回复等结构化数据。
    迁移自 ai_bp.py 的 _parse_reply_actions()，逻辑不变。
    """
    if not reply_text:
        return {'products': [], 'quote_refs': [], 'quick_replies': []}

    products = []
    quote_refs = []
    quick_replies = []

    text = reply_text.strip()

    # Pattern 1: "产品名 — ¥价格"
    pat1 = re.findall(r'([一-龥A-Za-z0-9\s\-]+?)\s*[—\-]\s*[¥￥]\s*([\d,]+\.?\d*)', text)
    for name, price in pat1:
        name = name.strip()
        if len(name) >= 2 and not _is_blacklisted(name):
            try:
                products.append({'name': name, 'price': float(price.replace(',', ''))})
            except ValueError:
                pass

    # Pattern 2: "产品名 ¥价格"
    pat2 = re.findall(r'([一-龥A-Za-z0-9\s\-]+?)\s+[¥￥]\s*([\d,]+\.?\d*)', text)
    for name, price in pat2:
        name = name.strip()
        if len(name) >= 2 and not _is_blacklisted(name):
            try:
                products.append({'name': name, 'price': float(price.replace(',', ''))})
            except ValueError:
                pass

    # Pattern 3: markdown table 行提取产品名和价格
    table_rows = re.findall(r'\|\s*([一-龥A-Za-z0-9\s\-]+?)\s*\|\s*[^|]*\|\s*[¥￥]?\s*([\d,]+\.?\d*)\s*\|', text)
    for name, price in table_rows:
        name = name.strip()
        if len(name) >= 2 and not _is_blacklisted(name):
            try:
                products.append({'name': name, 'price': float(price.replace(',', ''))})
            except ValueError:
                pass

    # Pattern 4: 价格在前，回溯找产品名
    price_lines = re.findall(r'[¥￥]\s*([\d,]+\.?\d*)', text)
    for p in price_lines[:5]:
        if not any(prod.get('price') == float(p.replace(',', '')) for prod in products):
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if p in line:
                    if i > 0:
                        prev = lines[i-1].strip()
                        if len(prev) >= 2 and len(prev) < 60 and not _is_blacklisted(prev):
                            try:
                                products.append({'name': prev, 'price': float(p.replace(',', ''))})
                            except ValueError:
                                pass

    # Pattern 5: 报价单引用 #数字
    refs = re.findall(r'#(\d+)', text)
    for r in refs:
        try:
            quote_refs.append(int(r))
        except ValueError:
            pass

    # Pattern 6: 快捷回复提取
    qr_patterns = [
        r'["""]([^"""]+)["”]',
        r'[“]([^”]+)[”]',
        r'\*\*([^*]+)\*\*',
    ]
    for pat in qr_patterns:
        matches = re.findall(pat, text)
        for m in matches:
            m = m.strip()
            if 2 <= len(m) <= 30 and m not in quick_replies:
                quick_replies.append(m)

    # 去重
    seen = set()
    unique_products = []
    for p in products:
        key = (p['name'], p.get('price'))
        if key not in seen:
            seen.add(key)
            unique_products.append(p)

    return {
        'products': unique_products[:12],
        'quote_refs': list(set(quote_refs))[:10],
        'quick_replies': quick_replies[:6],
    }


_BLACKLIST = {'成本价', '销售价', '单价', '合计', '总计', '方案一', '方案二', '方案三',
              '成本', '售价', '总价', '小计', '折扣', '指导价', '最低零售价', '成交价',
              '供应商', '备注', '数量', '型号', '规格', '单位', '序号', '编号'}


def _is_blacklisted(name):
    name_clean = name.strip().rstrip('：:')
    return name_clean in _BLACKLIST or len(name_clean) < 2


def generate_quick_replies(reply_text, quick_reply_fn=None):
    """用 LLM 生成快捷回复按钮。
    quick_reply_fn(model_id, system_msg, user_msg, max_tokens) → 文本或 None
    """
    if not quick_reply_fn:
        return []
    snippet = reply_text.strip()[-800:]
    user_msg = (
        '根据AI助手回复，推测用户最可能想说的2-4个简短回复。\n'
        '规则：\n'
        '- 每个回复5-15字，简洁自然\n'
        '- 如果AI问了"还是"选择题，提取两个选项\n'
        '- 如果AI推荐了产品，生成"详细对比这两款""查看更多同类产品"\n'
        '- 如果AI问了是否创建报价单，生成"创建报价单""先不用"\n'
        '- 如果AI给了价格，生成"有更便宜的替代吗""查看参数对比"\n'
        '- 返回纯JSON数组如["创建报价单","先看看参数"]，不要markdown\n'
        f'AI回复摘要："""{snippet}"""'
    )
    result = quick_reply_fn(
        system_msg='你是快捷回复生成器，只返回JSON数组，不要任何解释。',
        user_msg=user_msg,
        max_tokens=100,
    )
    if not result:
        return []
    try:
        if result.startswith('['):
            arr = json.loads(result)
            if isinstance(arr, list) and 1 <= len(arr) <= 6:
                return [str(x).strip() for x in arr if 2 <= len(str(x).strip()) <= 30][:4]
    except Exception:
        pass
    return []
