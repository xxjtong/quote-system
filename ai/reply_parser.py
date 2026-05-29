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
        name = re.sub(r'\*{1,3}\s*', '', name.strip())   # strip markdown bold (both sides)
        name = re.sub(r'^\d+\.\s*', '', name).strip()     # strip leading number
        if _is_valid_product_name(name):
            try:
                products.append({'name': name[:60], 'price': float(price.replace(',', ''))})
            except ValueError:
                pass

    # Pattern 2: "产品名 ¥价格"
    pat2 = re.findall(r'([一-龥A-Za-z0-9\s\-]+?)\s+[¥￥]\s*([\d,]+\.?\d*)', text)
    for name, price in pat2:
        name = re.sub(r'\*{1,3}\s*', '', name.strip())
        name = re.sub(r'^\d+\.\s*', '', name).strip()
        if _is_valid_product_name(name):
            try:
                products.append({'name': name[:60], 'price': float(price.replace(',', ''))})
            except ValueError:
                pass

    # Pattern 3: markdown table 行提取产品名和价格
    table_rows = re.findall(r'\|\s*([一-龥A-Za-z0-9\s\-]+?)\s*\|\s*[^|]*\|\s*[¥￥]?\s*([\d,]+\.?\d*)\s*\|', text)
    for name, price in table_rows:
        name = name.strip()
        if _is_valid_product_name(name):
            try:
                products.append({'name': name[:60], 'price': float(price.replace(',', ''))})
            except ValueError:
                pass

    # Pattern 4: 价格在前，回溯找产品名（只取第一条）
    seen_prices = {prod.get('price') for prod in products}
    price_lines = re.findall(r'[¥￥]\s*([\d,]+\.?\d*)', text)
    for p in price_lines:
        price_val = float(p.replace(',', ''))
        if price_val in seen_prices:
            continue
        seen_prices.add(price_val)
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if p in line and i > 0:
                prev = lines[i-1].strip()
                # Clean markdown prefixes
                prev = re.sub(r'^\*{1,3}\s*', '', prev)
                prev = re.sub(r'^\d+\.\s*', '', prev)
                prev = prev.strip()
                if _is_valid_product_name(prev):
                    products.append({'name': prev[:60], 'price': price_val})
                    break

    # Pattern 5: 报价单引用 #数字
    refs = re.findall(r'#(\d+)', text)
    for r in refs:
        try:
            quote_refs.append(int(r))
        except ValueError:
            pass

    # Pattern 6: 快捷回复提取 — 只提取产品型号 + 操作建议
    # 产品型号模式: 大写字母+数字+连字符 (如 AM319-470M-HCHO-IR, NANO, LD-AQS)
    model_matches = re.findall(r'\b([A-Z][A-Z0-9]{1,3}(?:-[A-Z0-9]+){1,5})\b', text)
    for m in model_matches:
        m = m.strip()
        if 3 <= len(m) <= 30 and m not in quick_replies:
            quick_replies.append(m)

    # 操作建议关键词
    action_keywords = [
        '创建报价单', '一键创建报价', '加入报价单',
        '对比产品', '对比这几款', '详细对比',
        '查看详情', '查看参数', '查看更多', '看看其他',
        '再推荐几款', '换个方向', '有便宜的吗',
    ]
    for kw in action_keywords:
        if kw in text and kw not in quick_replies:
            quick_replies.append(kw)

    # 过滤：去掉含管道符/表格标记的产品名，以及黑名单词
    def _valid_name(name):
        name = name.strip()
        if len(name) < 2 or len(name) > 60:
            return False
        if '|' in name or name.startswith('-') or name.startswith(':'):
            return False
        if _is_blacklisted(name):
            return False
        return True

    # 去重 + 过滤
    seen = set()
    unique_products = []
    for p in products:
        name = (p.get('name') or '').strip()
        if not _valid_name(name):
            continue
        # Dedup by first 8 normalized chars (brand+prefix, ignores model suffix)
        import re as _re
        short = _re.sub(r'\s+', '', name)[:8]
        if short not in seen:
            seen.add(short)
            unique_products.append(p)

    return {
        'products': unique_products[:12],
        'quote_refs': list(set(quote_refs))[:10],
        'quick_replies': quick_replies[:6],
    }


_BLACKLIST = {'成本价', '销售价', '单价', '合计', '总计', '方案一', '方案二', '方案三',
              '成本', '售价', '总价', '小计', '折扣', '指导价', '最低零售价', '成交价',
              '供应商', '备注', '数量', '型号', '规格', '单位', '序号', '编号'}

_HEADER_PATTERNS = [
    r'推荐建议', r'若\s*需要', r'如果', r'请问', r'总结', r'综上', r'注意',
    r'提示', r'建议', r'可选', r'另外', r'此外', r'或者', r'还可',
    r'^\d+\.\s*$',  # just a number like "1."
]


def _is_blacklisted(name):
    name_clean = name.strip().rstrip('：:')
    if name_clean in _BLACKLIST or len(name_clean) < 2:
        return True
    import re as _re
    for pat in _HEADER_PATTERNS:
        if _re.match(pat, name_clean):
            return True
    return False


def _is_valid_product_name(name):
    """Check if a string looks like a real product name (not a header/sentence)."""
    if not name or len(name) < 3 or len(name) > 60:
        return False
    if _is_blacklisted(name):
        return False
    # Must contain Chinese or alphanumeric product-like content
    if '|' in name or name.startswith('>') or name.startswith('-'):
        return False
    # Sentences with 建议/需要/感兴趣 are headers, not products
    if any(kw in name for kw in ['建议', '推荐', '需要', '感兴趣', '请问', '如果']):
        return False
    return True


def generate_quick_replies(reply_text, quick_reply_fn=None):
    """用 LLM 生成快捷回复按钮。
    quick_reply_fn(model_id, system_msg, user_msg, max_tokens) → 文本或 None
    """
    if not quick_reply_fn:
        return []
    snippet = reply_text.strip()[-800:]
    user_msg = (
        '根据AI助手回复，生成2-3个用户最可能点击的快捷按钮。\n'
        '规则：\n'
        '- 每个按钮5-15字，是用户下一步会说的话\n'
        '- 只生成产品型号/名称 或 操作建议，不要生成价格数字、单位、无关词汇\n'
        '- 如果AI推荐了产品，提取产品型号作为按钮（如"AM319-HCHO-IR"）\n'
        '- 如果有报价相关，生成"创建报价单"\n'
        '- 如果有多款产品，生成"对比这几款"\n'
        '- 如果AI问了场景，生成选项之一（如"LoRa无线方案"）\n'
        '- 最多3个按钮，不够就少生成\n'
        '- 返回纯JSON数组如["创建报价单","AM319-HCHO-IR"]，不要markdown\n'
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
