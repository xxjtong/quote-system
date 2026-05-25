"""
Admin Blueprint — 管理后台 API 路由
从 app.py 拆分出的所有 /api/admin/* 路由及 /api/download-ticket
"""

import secrets
from datetime import datetime

from flask import Blueprint, request, jsonify, g, current_app

from extensions import db
from models import User, FieldSetting, SystemSetting, AIChatSession, AIUsageLog, LoginLog
from auth import require_admin, hash_password, _is_registration_open
from helpers import get_setting, get_all_settings

# ─── Blueprint 定义 ──────────────────────────────────────────
admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# ─── 下载 Ticket 机制（数据库存储，多 worker 安全） ───────
_TICKET_TTL = 120  # 秒


def _validate_download_ticket(ticket_str):
    """验证下载ticket，返回 user_id 或 None"""
    from models import DownloadTicket
    row = DownloadTicket.query.filter_by(ticket=ticket_str).first()
    if not row:
        return None
    if datetime.now().timestamp() > row.expires_at:
        db.session.delete(row)
        db.session.commit()
        return None
    # 一次性使用后删除
    db.session.delete(row)
    db.session.commit()
    return row.user_id


# ─── Registration ────────────────────────────────────────────

@admin_bp.route('/registration', methods=['GET'])
@require_admin
def get_registration():
    return jsonify({'registration_open': _is_registration_open()})


@admin_bp.route('/registration', methods=['PUT'])
@require_admin
def set_registration():
    data = request.get_json()
    if 'registration_open' in data:
        open_val = bool(data['registration_open'])
        s = SystemSetting.query.filter_by(key='registration_open').first()
        if s:
            s.value = str(open_val).lower()
        else:
            db.session.add(SystemSetting(key='registration_open', value=str(open_val).lower()))
        db.session.commit()
        current_app.config['REGISTRATION_OPEN'] = open_val
    return jsonify({'registration_open': _is_registration_open()})


# get_setting / get_all_settings 从 helpers.py 直接导入（见文件顶部）


@admin_bp.route('/settings', methods=['GET'])
@require_admin
def get_settings():
    return jsonify({'settings': get_all_settings()})


@admin_bp.route('/settings', methods=['PUT'])
@require_admin
def update_settings():
    data = request.get_json()
    if not data:
        return jsonify({'error': '数据为空'}), 400
    for key, value in data.items():
        s = SystemSetting.query.filter_by(key=key).first()
        if s:
            s.value = str(value) if value else ''
        else:
            db.session.add(SystemSetting(key=key, value=str(value) if value else ''))
    db.session.commit()
    return jsonify({'settings': get_all_settings()})


# ─── AI Prompt 管理 ──────────────────────────────────────────

@admin_bp.route('/prompt', methods=['GET'])
@require_admin
def get_ai_prompt():
    """获取当前 AI 系统提示词（定制或默认）"""
    from ai_bp import _GW_SYSTEM_PROMPT
    s = SystemSetting.query.filter_by(key='ai_system_prompt').first()
    current = s.value if s and s.value else _GW_SYSTEM_PROMPT
    return jsonify({
        'prompt': current,
        'is_custom': bool(s and s.value),
        'default': _GW_SYSTEM_PROMPT,
    })


@admin_bp.route('/prompt', methods=['PUT'])
@require_admin
def update_ai_prompt():
    """更新 AI 系统提示词 — 同时清除所有会话缓存，下次对话立即生效"""
    from ai_bp import _GW_SYSTEM_PROMPT
    data = request.get_json()
    if not data:
        return jsonify({'error': '数据为空'}), 400
    prompt = data.get('prompt', '')
    s = SystemSetting.query.filter_by(key='ai_system_prompt').first()
    if s:
        s.value = prompt
    else:
        db.session.add(SystemSetting(key='ai_system_prompt', value=prompt))
    # 清除所有用户的 AIChatSession，强制下次对话注入新 prompt
    AIChatSession.query.delete()
    db.session.commit()
    return jsonify({'prompt': prompt, 'message': 'Prompt 已保存，下次对话生效', 'sessions_cleared': True})


# ─── 字段设置 ────────────────────────────────────────────────

@admin_bp.route('/fields', methods=['GET'])
@require_admin
def get_field_settings():
    fields = FieldSetting.query.all()
    if not fields:
        # 初始化默认字段
        defaults = [
            ('cost_price', '成本价', True),
            ('remark', '内部备注', True),
            ('supplier', '供应商', True),
            ('function_desc', '功能描述', True),
        ]
        for fname, label, visible in defaults:
            if not FieldSetting.query.filter_by(field_name=fname).first():
                db.session.add(FieldSetting(field_name=fname, label=label, user_visible=visible))
        db.session.commit()
        fields = FieldSetting.query.all()
    return jsonify({'fields': [{'field_name': f.field_name, 'label': f.label, 'user_visible': f.user_visible} for f in fields]})


@admin_bp.route('/fields', methods=['PUT'])
@require_admin
def set_field_settings():
    data = request.get_json()
    if 'fields' in data:
        fields_data = data['fields']
        # 兼容两种格式：对象 {key: bool} 或数组 [{field_name, user_visible}]
        if isinstance(fields_data, dict):
            for field_name, user_visible in fields_data.items():
                f = FieldSetting.query.filter_by(field_name=field_name).first()
                if f:
                    f.user_visible = bool(user_visible)
        else:
            for item in fields_data:
                f = FieldSetting.query.filter_by(field_name=item['field_name']).first()
                if f:
                    f.user_visible = bool(item.get('user_visible', True))
        db.session.commit()
    return get_field_settings()


# ─── 用户管理 ────────────────────────────────────────────────

@admin_bp.route('/users', methods=['GET'])
@require_admin
def list_users():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 200)
    search = request.args.get('search', '').strip()
    query = User.query
    if search:
        query = query.filter(
            db.or_(User.username.contains(search), User.email.contains(search))
        )
    query = query.order_by(User.created_at.desc())
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'users': [u.to_dict() for u in paginated.items],
        'total': paginated.total,
        'page': page,
        'pages': paginated.pages
    })


@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@require_admin
def update_user(user_id):
    if user_id == g.current_user.id:
        return jsonify({'error': '不能修改自己的状态'}), 400
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    data = request.get_json()
    if user_id == 1 and 'role' in data and data['role'] != 'admin':
        return jsonify({'error': '主管理员不能被降级'}), 403
    if 'is_active' in data:
        user.is_active = bool(data['is_active'])
    if 'role' in data and data['role'] in ('admin', 'user'):
        user.role = data['role']
    db.session.commit()
    return jsonify({'user': user.to_dict()})


@admin_bp.route('/users/<int:user_id>/password', methods=['PUT'])
@require_admin
def reset_user_password(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    data = request.get_json()
    new_pw = (data.get('password') or '').strip()
    if len(new_pw) < 8:
        return jsonify({'error': '密码至少8位'}), 400
    user.password_hash = hash_password(new_pw)
    db.session.commit()
    return jsonify({'success': True, 'username': user.username})


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@require_admin
def delete_user(user_id):
    if user_id == g.current_user.id:
        return jsonify({'error': '不能删除自己'}), 400
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    if user.role == 'admin':
        return jsonify({'error': '不能删除管理员'}), 403
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': f'用户 {user.username} 已删除'})


# ─── 登录记录 ───────────────────────────────────────────────
@admin_bp.route('/login-logs', methods=['GET'])
@require_admin
def login_logs():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 200)
    user_id = request.args.get('user_id', type=int)
    query = LoginLog.query.order_by(LoginLog.created_at.desc())
    if user_id:
        query = query.filter(LoginLog.user_id == user_id)
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'logs': [log.to_dict() for log in paginated.items],
        'total': paginated.total,
        'page': page,
        'pages': paginated.pages,
    })


# ─── 下载 Ticket ───────────────────────────────────────────
# create_download_ticket 路由已移至 quotes_bp.py
# _validate_download_ticket 保留在此供 app.py check_auth() 使用


# ─── AI 使用统计 ─────────────────────────────────────────────
@admin_bp.route('/ai-usage', methods=['GET'])
@require_admin
def ai_usage_stats():
    """AI 使用统计 — 管理员查看（从 ai_bp.py 迁入）"""
    from sqlalchemy import func
    days = min(int(request.args.get('days', 7)), 90)
    since = datetime.now() - __import__('datetime').timedelta(days=days)

    total = AIUsageLog.query.filter(AIUsageLog.created_at >= since).count()
    success = AIUsageLog.query.filter(AIUsageLog.created_at >= since, AIUsageLog.success == True).count()
    avg_elapsed = db.session.query(func.avg(AIUsageLog.elapsed)).filter(
        AIUsageLog.created_at >= since, AIUsageLog.success == True
    ).scalar() or 0

    by_action = db.session.query(
        AIUsageLog.action, func.count(), func.avg(AIUsageLog.elapsed)
    ).filter(AIUsageLog.created_at >= since).group_by(AIUsageLog.action).all()

    by_user = db.session.query(
        AIUsageLog.user_id, User.username, func.count()
    ).join(User, AIUsageLog.user_id == User.id).filter(
        AIUsageLog.created_at >= since
    ).group_by(AIUsageLog.user_id, User.username).order_by(func.count().desc()).limit(10).all()

    by_date = db.session.query(
        func.date(AIUsageLog.created_at), func.count(),
        func.avg(AIUsageLog.elapsed)
    ).filter(AIUsageLog.created_at >= since).group_by(
        func.date(AIUsageLog.created_at)
    ).order_by(func.date(AIUsageLog.created_at).desc()).limit(days).all()

    recent = AIUsageLog.query.filter(AIUsageLog.created_at >= since).order_by(
        AIUsageLog.created_at.desc()
    ).limit(50).all()

    return jsonify({
        'summary': {'total': total, 'success': success, 'fail': total - success, 'avg_elapsed': round(avg_elapsed, 2), 'days': days},
        'by_action': [{'action': a, 'count': c, 'avg_elapsed': round(e, 2)} for a, c, e in by_action],
        'by_user': [{'user_id': uid, 'username': u, 'count': c} for uid, u, c in by_user],
        'by_date': [{'date': str(d), 'count': c, 'avg_elapsed': round(e, 2)} for d, c, e in by_date],
        'recent': [r.to_dict() for r in recent],
    })
