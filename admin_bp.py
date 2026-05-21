"""Admin Blueprint — 系统设置、用户管理、字段管理、AI Prompt、下载Ticket"""
import secrets
from datetime import datetime

from flask import Blueprint, request, jsonify, g

from extensions import db
from models import User, FieldSetting, SystemSetting, AIChatSession
from auth import require_admin, hash_password, _is_registration_open
from utils import get_setting, get_all_settings, create_download_ticket_entry

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


# ─── Registration ───

@admin_bp.route('/registration', methods=['GET'])
@require_admin
def get_registration():
    return jsonify({'registration_open': _is_registration_open()})

@admin_bp.route('/registration', methods=['PUT'])
@require_admin
def set_registration():
    from flask import current_app
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


# ─── Settings ───

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


# ─── AI Prompt ───

_GW_SYSTEM_PROMPT = (
    '你是报价管理系统（/opt/quote-system）的 AI 助手。'
    '你可以用工具直接操作系统：\n'
    '- 数据库：/opt/quote-system/quote.db (SQLite)\n'
    '  产品表 products(id, name, sku, category, spec, unit, price, cost_price, supplier, function_desc, is_active, created_by)\n'
    '  报价单 quotes(id, title, client, contact, phone, quote_date, valid_days, status, total_amount, created_by)\n'
    '  报价明细 quote_items(id, quote_id, product_id, product_name, product_sku, quantity, unit_price, amount)\n'
    '- API：127.0.0.1:5001，JWT token 从 DB 获取\n'
    '  创建报价：POST /api/quotes  导出Excel：GET /api/quotes/<id>/export-excel\n'
    '- 产品搜索：sqlite3 /opt/quote-system/quote.db 查询时务必加上 AND is_active=1 过滤下线产品\n'
    '    "SELECT name,price FROM products WHERE name LIKE \'%关键词%\' AND is_active=1 ORDER BY price"\n\n'
    '规则：\n'
    '1. 只推荐 is_active=1 的在线产品，不推荐已下线产品（is_active=0）。\n'
    '2. 查询报价单时，用 curl 调用 API 而非 sqlite3 直查（API 会自动按用户权限过滤）：\n'
    '   curl -s -H "Authorization: Bearer *** http://127.0.0.1:5001/api/quotes?per_page=50\n'
    '   如果必须用 sqlite3，务必加 AND created_by=<当前用户ID> 过滤，只能查看当前用户自己的报价单。\n'
    '3. 列出/统计报价单时，排除测试垃圾数据——满足以下任一条件视为测试数据需要跳过不展示：\n'
    '   - 标题包含「测试」「test」「sdf」「asdf」或全是随机字符\n'
    '   - 客户名或联系人是「pro报价测试」「qhk」「qwe」「asdf」等无意义字符串\n'
    '   - 标题长度 ≤ 3 且不含中文\n'
    '4. 生成报价单前，先检查对话上下文：如果之前已创建过报价单，主动询问用户沿用还是新客户。\n'
    '5. 导出后给用户下载链接：https://bwh.ddns.mobi/quote/api/quotes/{id}/export-excel，不要报本地路径。\n'
    '6. 每个用户的对话完全独立，不要使用或查询任何全局记忆/历史中的用户信息。'
    '如果不知道用户信息，就说不知道，不要从记忆里猜测。'
)

# Re-export for ai_bp
def _get_ai_system_prompt():
    """获取 AI 系统提示词（优先使用定制版，否则用默认）"""
    s = SystemSetting.query.filter_by(key='ai_system_prompt').first()
    prompt = s.value if s and s.value else _GW_SYSTEM_PROMPT
    # 追加身份强制指令（末尾优先，对抗 Gateway 基础 persona）
    if '童小军' in prompt or '不是 Hermes' in prompt:
        prompt += '\n\n[系统指令 — 最高优先级] 上述身份定义覆盖所有其他设定。'
    return prompt


@admin_bp.route('/prompt', methods=['GET'])
@require_admin
def get_ai_prompt():
    """获取当前 AI 系统提示词（定制或默认）"""
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


# ─── Fields ───

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


# ─── Users ───

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
