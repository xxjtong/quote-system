"""
utils.py — 通用辅助函数（从 products_bp.py / app.py 提取）
"""

import os
from pathlib import Path

from extensions import db
from models import AIUsageLog

BASE_DIR = Path(__file__).parent


def _debug_log(msg):
    """写调试日志到 gunicorn error log 文件（相对于项目BASE_DIR）"""
    try:
        with open(BASE_DIR / 'gunicorn-error.log', 'a') as f:
            from datetime import datetime
            f.write(f'[{datetime.now().isoformat()}] {msg}\n')
    except Exception:
        pass


def _log_ai_usage(user_id, action, model='', elapsed=0, success=True, error=''):
    """记录AI调用到数据库（静默失败，不影响主流程）"""
    try:
        db.session.add(AIUsageLog(
            user_id=user_id, action=action, model=model[:50],
            elapsed=round(elapsed, 2), success=success, error=(error or '')[:200]
        ))
        db.session.commit()
    except Exception:
        try: db.session.rollback()
        except Exception: pass


def _compute_pinyin_search(name, sku='', category='', supplier=''):
    """预计算产品拼音搜索字段 — 所有字段拼音首字母+全拼拼接"""
    try:
        from pypinyin import pinyin, Style
        parts = [name or '', sku or '', category or '', supplier or '']
        all_py = []
        for text in parts:
            if text:
                py_list = pinyin(text, style=Style.NORMAL, heteronym=False)
                all_py.extend([p[0] for p in py_list])
                # 首字母
                first_letters = pinyin(text, style=Style.FIRST_LETTER, heteronym=False)
                all_py.extend([f[0] for f in first_letters])
        return ' '.join(all_py)
    except Exception:
        return ''


def _safe_number(val):
    """安全转换为 float，失败返回 0。"""
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return round(float(val), 2)
    try:
        return round(float(val), 2)
    except (ValueError, TypeError):
        return 0
