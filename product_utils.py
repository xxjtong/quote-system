"""
product_utils.py — 产品解析相关辅助函数（从 products_bp.py / app.py 提取）
"""

import os
import re
from pathlib import Path

from extensions import db
from models import Product
from sqlalchemy import func

from utils import _debug_log, _safe_number

BASE_DIR = Path(__file__).parent


def compress_image_if_needed(filepath, max_kb=95, max_dim=800):
    """压缩图片到指定大小以内，返回最终路径和文件名。
    透明PNG自动贴白底转JPG。"""
    from PIL import Image
    filepath = Path(filepath)
    img = Image.open(str(filepath))
    orig_w, orig_h = img.size
    orig_kb = filepath.stat().st_size / 1024

    # 尺寸过大的先缩小
    if orig_w > max_dim or orig_h > max_dim:
        ratio = min(max_dim / orig_w, max_dim / orig_h)
        new_w = max(1, int(orig_w * ratio))
        new_h = max(1, int(orig_h * ratio))
        img = img.resize((new_w, new_h), Image.LANCZOS)

    # 透明 PNG → 贴白底转 JPG（无论是否需要压缩都做）
    needs_white_bg = img.mode in ('RGBA', 'P')
    if needs_white_bg:
        if img.mode == 'P':
            img = img.convert('RGBA')
        alpha = img.split()[-1]
        has_alpha = img.mode == 'RGBA' and alpha.getextrema()[0] < 255
        if has_alpha:
            bg = Image.new('RGB', img.size, (255, 255, 255))
            bg.paste(img, mask=alpha)
            img = bg
        else:
            img = img.convert('RGB')

    # 若已有白底且小于阈值且不是透明格式，不处理
    if orig_kb <= max_kb and not needs_white_bg and filepath.suffix in ('.jpg', '.jpeg'):
        return str(filepath), filepath.name

    # 保存为 JPG
    out_path = filepath.with_suffix('.jpg')
    if orig_kb <= max_kb and needs_white_bg:
        # 小文件但已贴白底，高质量保存
        img.save(str(out_path), 'JPEG', quality=85, optimize=True)
    else:
        # 渐进降质量
        for quality in [75, 65, 55, 45, 35, 25]:
            img.save(str(out_path), 'JPEG', quality=quality, optimize=True)
            if out_path.stat().st_size / 1024 <= max_kb:
                break

    # 删除原始文件（如果扩展名变了）
    if out_path.suffix != filepath.suffix:
        filepath.unlink(missing_ok=True)

    return str(out_path), out_path.name


def _ocr_fallback(image_path):
    """OCR.space 作为降级方案，返回识别文本或 None。"""
    try:
        import requests as http_req
        with open(image_path, 'rb') as fp:
            r = http_req.post(
                'https://api.ocr.space/parse/image',
                files={'file': fp},
                data={'language': 'chs', 'isOverlayRequired': False,
                      'detectOrientation': True, 'scale': True,
                      'apikey': os.environ.get('OCR_SPACE_API_KEY', 'helloworld')},
                timeout=30,
            )
        if r.status_code != 200:
            return None
        result = r.json()
        if result.get('OCRExitCode') == 1:
            return result.get('ParsedResults', [{}])[0].get('ParsedText', '').strip()
    except Exception:
        pass
    return None


def doubao_vision_recognize(image_b64, mime_type='image/jpeg'):
    """使用火山引擎豆包 Seed Lite 从图片中提取产品信息，返回结构化 JSON dict。
    豆包直出纯 JSON，不需要额外解析。
    失败返回 None。
    """
    import json
    api_key = os.environ.get('VOLCENGINE_API_KEY', '')
    if not api_key:
        return None

    prompt = (
        '请仔细阅读图片中的产品信息，提取以下字段并以JSON格式返回（只返回JSON，不要其他文字）：\n'
        '{\n'
        '  "name": "产品名称（中文，不包括型号）",\n'
        '  "spec": "规格型号（如 ZQWL-GW2800NU-P12）",\n'
        '  "supplier": "厂商/品牌名",\n'
        '  "price": 售价数字（纯数字，没有则填 0）,\n'
        '  "cost_price": 成本价数字（纯数字，没有则填 0）,\n'
        '  "category": "分类（如 IO网关、传感器、门禁等，没有则填空字符串）",\n'
        '  "unit": "单位（台/个/套/件，默认台）",\n'
        '  "function_desc": "功能描述（核心功能、特性、参数亮点等）",\n'
        '  "remark": "备注（价格后面的补充信息，如产地、认证、质保、含税等，没有则填空字符串）"\n'
        '}\n'
        '注意：\n'
        '- 型号通常是大写字母+数字+横杠组合\n'
        '- 厂商从文字中直接提取，不要猜测\n'
        '- 价格只提取数字部分\n'
        '- 备注信息通常出现在价格之后，如"含税""三年质保""国产"等\n'
        '- function_desc 放主要功能特性，remark 放价格后的补充说明'
    )

    try:
        import requests as http_req
        r = http_req.post(
            'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': 'doubao-seed-2-0-mini-260428',
                'messages': [{
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': prompt},
                        {'type': 'image_url', 'image_url': {'url': f'data:{mime_type};base64,{image_b64}'}}
                    ]
                }],
                'max_tokens': 1000,
            },
            timeout=60,
        )
        if r.status_code != 200:
            _debug_log(f'[doubao_vision] API returned {r.status_code}: {r.text[:200]}')
            return None

        result = r.json()
        raw_text = result.get('choices', [{}])[0].get('message', {}).get('content', '')
        if not raw_text:
            _debug_log(f'[doubao_vision] Empty response content. Full: {str(result)[:300]}')
            return None

        # 解析 JSON（公共3层兜底）
        parsed = _parse_json_reply(raw_text)

        if parsed:
            product = _product_from_parsed(parsed, json.dumps(result, ensure_ascii=False))
            if product:
                return product
        _debug_log(f'[doubao_vision] Parsed but name empty. raw_text[:200]: {raw_text[:200]}')
        return None
    except Exception as e:
        _debug_log(f'[doubao_vision] Exception: {e}')
        return None


def _parse_json_reply(text):
    """从LLM回复中提取JSON dict — 3层兜底：直接解析→代码块→正则。
    返回 dict 或 None。doubao_vision 和 deepseek_parse 共用。
    """
    import re, json
    parsed = None
    text = text.strip()

    # 策略1: 直接解析
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # 策略2: ```json ... ``` 代码块
    if not parsed:
        m = re.search(r'```(?:json)?\s*\n?(\{.+\})\s*```', text, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(1))
            except (json.JSONDecodeError, ValueError):
                pass

    # 策略3: 包含 "name" 字段的 JSON 对象（或任意 {...}）
    if not parsed:
        m = re.search(r'\{[^{}]*"name"\s*:\s*"[^"]*"[^{}]*\}', text, re.DOTALL)
        if not m:
            m = re.search(r'\{.+\}', text, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except (json.JSONDecodeError, ValueError):
                pass

    return parsed


def _product_from_parsed(parsed, raw=''):
    """从解析出的dict构建标准化产品dict，截断字段长度。
    如果匹配到已有产品，附加 existing_product_id 字段。"""
    if not parsed:
        return None
    product = {
        'name': str(parsed.get('name', '')).strip()[:20],
        'spec': str(parsed.get('spec', '')).strip()[:100],
        'supplier': str(parsed.get('supplier', '')).strip()[:50],
        'price': _safe_number(parsed.get('price', 0)),
        'cost_price': _safe_number(parsed.get('cost_price', 0)),
        'unit': str(parsed.get('unit', '')).strip()[:10],
        'category': str(parsed.get('category', '')).strip()[:50],
        'function_desc': str(parsed.get('function_desc', '')).strip()[:500],
        'remark': str(parsed.get('remark', '')).strip()[:500],
        '_raw': raw,
    }
    if not product['name']:
        return None

    # 尝试匹配已有产品（按型号或 名称+厂商）
    try:
        spec = product['spec'].strip()
        name = product['name'].strip()
        supplier = product['supplier'].strip()
        match = None
        if spec and len(spec) >= 3:
            match = Product.query.filter(Product.spec == spec, Product.is_active == 1).first()
        if not match and name and supplier:
            match = Product.query.filter(
                Product.name == name, Product.supplier == supplier, Product.is_active == 1
            ).first()
        if not match and name:
            match = Product.query.filter(
                func.lower(Product.name) == name.lower(), Product.is_active == 1
            ).first()
        if match:
            product['existing_product_id'] = match.id
            product['existing_product_image'] = match.image_url or ''
    except Exception:
        pass

    return product


def deepseek_parse_product(text):
    """使用豆包 Seed Mini 从非结构化文本中提取产品信息。
    直连火山API（不走Gateway），返回结构化 dict 或 None。
    """
    import json as _json, urllib.request
    api_key = os.environ.get('VOLCENGINE_API_KEY', '')
    if not api_key:
        return None
    prompt = (
        '从以下产品文本中提取信息，返回纯JSON（只返回JSON，不要markdown、不要解释）：\n'
        '{"name":"产品名称（中文，不含型号，≤20字）","spec":"规格型号（大写字母+数字+横杠组合）","supplier":"厂商/品牌","price":售价数字,"cost_price":成本价数字,"category":"分类（如传感器/网关/会议屏/门禁/工牌，空则填空字符串）","unit":"单位（台/个/套/件，默认台）","function_desc":"功能描述（核心功能、特性、参数亮点）","remark":"备注（价格后面的补充信息，如产地、认证、包装、质保等次要信息，无则填空字符串）"}\n'
        '规则：\n'
        '- 型号是大写字母+数字+横杠组合\n'
        '- 厂商从文字中直接提取，不要猜测\n'
        '- 价格只取数字\n'
        '- 备注信息通常出现在价格之后，如"含税""三年质保""国产"等\n'
        '- function_desc放核心功能特性，remark放价格后的补充说明，两者分开\n'
        '- 没有的字段填空字符串或0\n'
        f'文本：\n{text[:3000]}'
    )
    try:
        body = _json.dumps({
            'model': 'doubao-seed-2-0-mini-260428',
            'messages': [
                {'role': 'system', 'content': '你是产品信息提取器，只返回JSON，不要markdown和解释。'},
                {'role': 'user', 'content': prompt},
            ],
            'max_tokens': 500,
            'temperature': 0.2,
        })
        req = urllib.request.Request(
            'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
            data=body.encode('utf-8'),
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            method='POST'
        )
        resp = urllib.request.urlopen(req, timeout=30)
        result = _json.loads(resp.read())
        reply = result['choices'][0]['message']['content'].strip()
        # 解析 JSON（公共3层兜底）
        parsed = _parse_json_reply(reply)
        if parsed:
            product = _product_from_parsed(parsed, reply)
            if product:
                return product
        _debug_log(f'[doubao_text_parse] Failed. reply[:200]: {reply[:200]}')
    except Exception as e:
        _debug_log(f'[doubao_text_parse] Exception: {e}')
        pass
    return None


def smart_parse_product(text):
    """智能解析非结构化文本，按字段模式匹配提取产品信息。
    不依赖固定顺序/分隔符，支持任意格式粘贴。
    """
    import re

    result = {'name': '', 'sku': '', 'spec': '', 'unit': '',
              'price': 0, 'cost_price': 0, 'supplier': '', 'remark': ''}

    text = text.strip()
    if not text or len(text) < 5:
        return None

    # ── 1. 提取价格（支持：¥123.45 / 123元 / 价格:123 / 售价 ¥123）──
    price_patterns = [
        r'[¥￥]\s*(\d+\.?\d{0,2})\b',
        r'售价[：:\s]*[¥￥]?\s*(\d+\.?\d{0,2})\b',
        r'价格[：:\s]*[¥￥]?\s*(\d+\.?\d{0,2})\b',
        r'单价[：:\s]*[¥￥]?\s*(\d+\.?\d{0,2})\b',
        r'(\d+\.?\d{0,2})\s*元\b',
        r'\b(\d+\.?\d{0,2})\s*[元$]',
    ]
    prices_found = []
    for pat in price_patterns:
        for m in re.finditer(pat, text):
            val = float(m.group(1))
            if 0 < val < 100000000:
                prices_found.append((val, m.start(), m.end()))
    if prices_found:
        # 取最大金额作为售价
        prices_found.sort(key=lambda x: -x[0])
        result['price'] = round(prices_found[0][0], 2)

    # ── 2. 提取成本价 ──
    cost_patterns = [
        r'成本[：:\s]*[¥￥]?\s*(\d+\.?\d{0,2})\b',
        r'进价[：:\s]*[¥￥]?\s*(\d+\.?\d{0,2})\b',
        r'成本价[：:\s]*[¥￥]?\s*(\d+\.?\d{0,2})\b',
    ]
    for pat in cost_patterns:
        m = re.search(pat, text)
        if m:
            result['cost_price'] = round(float(m.group(1)), 2)
            break

    # ── 3. 提取型号（大写字母+数字+横杠组合）──
    sku_patterns = [
        r'\b([A-Z]{2,}[\dA-Z\-/\.\+]{1,30})\b',
        r'型号[：:\s]*([A-Z\d][\dA-Z\-/\.\+]{1,30})',
        r'规格型号[：:\s]*([A-Z\d][\dA-Z\-/\.\+]{1,30})',
        r'SKU[：:\s]*([A-Z\d][\dA-Z\-/\.\+]{1,30})',
    ]
    skus_found = []
    for pat in sku_patterns:
        for m in re.finditer(pat, text):
            v = m.group(1).strip()
            if len(v) >= 3 and re.search(r'[A-Z]', v) and re.search(r'\d', v):
                skus_found.append((v, m.start(), m.end()))
    if skus_found:
        # 最长型号优先
        skus_found.sort(key=lambda x: -len(x[0]))
        result['spec'] = skus_found[0][0]

    # ── 4. 熟悉厂商对照 ──
    known_suppliers = [
        '星纵', '绿米', '海康威视', '海康微影', '大华', '宇视', '汉朔',
        '京东方', 'BOE', '得力', '德生', '研华', '中弘', '亿联', '飞利浦',
        '树莓', '明纬', '杜亚', '欧孚', 'HID', 'QBIC', 'Temi', 'ELO',
        '智嵌', '智绘源', '宸展', '联智触控', '优良专显', '大唐', '大洋',
        '原点', '微光', '微耕', '西瑞智能', '苏州星途', '迪勤', '京仪北方',
        '汇尚', '海林', '百度', '中电', '迭代', '易乐看',
    ]
    for s in known_suppliers:
        if s in text:
            result['supplier'] = s
            break

    # ── 5. 熟悉分类对照 ──
    known_categories = [
        'IoT', '会议', '信发', '厕位', '工位', '星纵', '绿米', '门禁',
        '环境', '能耗照明环境', 'FM', 'IBMS', 'MTR', '访客',
    ]
    for c in known_categories:
        if c in text:
            result.setdefault('category', c)
            break

    # ── 6. 提取单位 ──
    unit_match = re.search(r'单位[：:\s]*([台个套件只条根米卷])', text)
    if unit_match:
        result['unit'] = unit_match.group(1)

    # ── 7. 剩余文字 → 产品名称 + 备注 ──
    # 去掉已匹配的价格、型号、厂商等
    clean = text
    for pat in price_patterns:
        clean = re.sub(pat, '', clean)
    for pat in sku_patterns:
        clean = re.sub(pat, '', clean, count=1)
    for pat in cost_patterns:
        clean = re.sub(pat, '', clean)
    clean = re.sub(r'[¥￥]', '', clean)
    clean = re.sub(r'售价|价格|单价|成本|进价|成本价|型号|规格型号|SKU|单位', '', clean)
    clean = re.sub(r'产品[：:\s]*|厂商[：:\s]*|功能[：:\s]*|描述[：:\s]*|说明[：:\s]*', '', clean)
    clean = re.sub(r'[：:\s]+', ' ', clean).strip()
    # 清理孤立的 "元"（价格提取残留）
    clean = re.sub(r'\b元\b', '', clean).strip()

    # 去掉已匹配的厂商名
    if result['supplier']:
        clean = clean.replace(result['supplier'], '').strip()

    # 清理多余空格和标点
    clean = re.sub(r'\s+', ' ', clean).strip(' ，,。.')
    clean = re.sub(r'^\d+[\\.\、\）\)]\s*', '', clean)  # 去掉序号前缀

    if clean:
        # 按常见中文标点/换行分段
        segments = [s.strip() for s in re.split(r'[，,。\\n]', clean) if s.strip()]
        if segments:
            # 第一段 → 产品名称（中文优先）
            chinese_name = ''
            for seg in segments:
                if re.search(r'[\u4e00-\u9fff]', seg):
                    chinese_name = seg
                    break
            if not chinese_name:
                chinese_name = segments[0]
            result['name'] = chinese_name[:20]

            # 剩余段 → 备注
            other = [s for s in segments if s != chinese_name]
            if other:
                result['remark'] = ' '.join(other)[:500]

    # ── 兜底：如果 name 为空，取正文第一行 ──
    if not result.get('name') and clean:
        first_line = clean.split('\n')[0].strip()[:20]
        if first_line:
            result['name'] = first_line

    return result if result.get('name') else None


def parse_product_line(line):
    """原始解析器，保留兼容（Tab/空格固定位置）"""
    import re

    # 先按tab分割（Excel粘贴）
    parts = [p.strip() for p in line.split('\t') if p.strip()]
    # 如果tab没分出来，尝试至少2个空格分割
    if len(parts) <= 1:
        parts = [p.strip() for p in re.split(r'\s{2,}', line) if p.strip()]
    # 仍然只有一个，尝试单空格分割
    if len(parts) <= 1:
        parts = [p.strip() for p in line.split() if p.strip()]

    if not parts:
        return None

    # 去掉可能的序号前缀（如 "1. " "2、"）
    parts = [re.sub(r'^\d+[\.\、\）\)](?!\d)', '', p).strip() for p in parts]
    parts = [p for p in parts if p]

    if not parts:
        return None

    result = {'name': '', 'sku': '', 'spec': '', 'unit': '', 'price': 0, 'supplier': '', 'remark': ''}

    # 检查最后一个是否像价格
    last = parts[-1]
    price_val = None
    price_match = re.match(r'^[¥￥]?\s*([\d]+\.?\d*)\s*[元]?$', last)
    if price_match:
        try:
            price_val = round(float(price_match.group(1)), 2)
            parts = parts[:-1]
        except ValueError:
            pass

    if not parts:
        return None

    # 第一个：产品名称
    result['name'] = parts[0]

    # 倒数第一个（价格之后的最后一个字段）：功能描述 → 备注
    if len(parts) >= 2:
        result['remark'] = parts[-1]
        parts = parts[:-1]

    # 倒数第二个（如有）：厂商
    if len(parts) >= 2:
        result['supplier'] = parts[-1]
        parts = parts[:-1]

    # 剩余中间部分：规格型号（合并）
    if len(parts) >= 2:
        spec_parts = parts[1:]
        result['spec'] = ' '.join(spec_parts)
        for sp in spec_parts:
            sku_match = re.match(r'^([A-Z]{2,}[\dA-Z\-/\.\+]*)$', sp)
            if sku_match:
                result['sku'] = sku_match.group(1)
                break

    if price_val is not None:
        result['price'] = price_val

    return result if result.get('name') else None
