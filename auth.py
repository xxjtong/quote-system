"""认证模块 — JWT + 登录/注册/会话（Flask Blueprint）"""
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import Blueprint, request, jsonify, g

from extensions import db
from models import User, SystemSetting

auth_bp = Blueprint('auth', __name__)


# ─── Helpers ─────────────────────────────────

def hash_password(password):
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f'{salt}${h}'


def verify_password(password, password_hash):
    try:
        salt, h = password_hash.split('$', 1)
        return hashlib.sha256((salt + password).encode()).hexdigest() == h
    except Exception:
        return False


def create_token(user, app):
    payload = {
        'user_id': user.id, 'username': user.username, 'role': user.role,
        'exp': datetime.utcnow() + timedelta(hours=app.config['JWT_EXPIRY_HOURS']),
    }
    return jwt.encode(payload, app.config['JWT_SECRET'], algorithm='HS256')


def get_current_user(app):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return None
    try:
        data = jwt.decode(token, app.config['JWT_SECRET'], algorithms=['HS256'])
        user = db.session.get(User, data['user_id'])
        if user and user.is_active:
            return user
    except Exception:
        pass
    return None


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        from flask import current_app
        user = get_current_user(current_app)
        if not user:
            return jsonify({'error': '请先登录'}), 401
        g.current_user = user
        return fn(*args, **kwargs)
    return wrapper


def require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        from flask import current_app
        user = get_current_user(current_app)
        if not user:
            return jsonify({'error': '请先登录'}), 401
        if user.role != 'admin':
            return jsonify({'error': '需要管理员权限'}), 403
        g.current_user = user
        return fn(*args, **kwargs)
    return wrapper


def _is_registration_open():
    """检查注册是否开放（DB 优先，解决多 worker 不一致问题）"""
    s = SystemSetting.query.filter_by(key='registration_open').first()
    db_val = (s.value if s else '').strip().lower()
    if db_val in ('true', 'false'):
        return db_val == 'true'
    from flask import current_app
    return current_app.config.get('REGISTRATION_OPEN', True)


# ─── Routes ─────────────────────────────────

@auth_bp.route('/api/auth/registration-status', methods=['GET'])
def auth_registration_status():
    return jsonify({'registration_open': _is_registration_open()})


@auth_bp.route('/api/auth/register', methods=['POST'])
def auth_register():
    from flask import current_app
    if not _is_registration_open():
        return jsonify({'error': '暂不开放自主注册'}), 403
    data = request.get_json()
    if not data or not data.get('username', '').strip() or not data.get('password', '').strip():
        return jsonify({'error': '用户名和密码不能为空'}), 400
    username = data['username'].strip()
    if User.query.filter_by(username=username).first():
        return jsonify({'error': '用户名已存在'}), 409
    user = User(
        username=username,
        password_hash=hash_password(data['password'].strip()),
        role='user', is_active=True,
        email=data.get('email', '').strip(),
    )
    db.session.add(user)
    db.session.commit()
    token = create_token(user, current_app)
    return jsonify({'token': token, 'user': user.to_dict()}), 201


@auth_bp.route('/api/auth/login', methods=['POST'])
def auth_login():
    from flask import current_app
    data = request.get_json()
    if not data or not data.get('username', '').strip() or not data.get('password', '').strip():
        return jsonify({'error': '用户名和密码不能为空'}), 400
    user = User.query.filter_by(username=data['username'].strip()).first()
    if not user or not verify_password(data['password'].strip(), user.password_hash):
        return jsonify({'error': '用户名或密码错误'}), 401
    if not user.is_active:
        return jsonify({'error': '账号已被停用'}), 403
    token = create_token(user, current_app)
    return jsonify({'token': token, 'user': user.to_dict()})


@auth_bp.route('/api/auth/me', methods=['GET'])
@require_auth
def auth_me():
    return jsonify({'user': g.current_user.to_dict()})


@auth_bp.route('/api/auth/profile', methods=['PUT'])
@require_auth
def update_profile():
    data = request.get_json()
    user = g.current_user
    changed = False

    if 'email' in data:
        user.email = (data['email'] or '').strip()
        changed = True

    new_pw = (data.get('new_password') or '').strip()
    if new_pw:
        current_pw = (data.get('current_password') or '').strip()
        if not verify_password(current_pw, user.password_hash):
            return jsonify({'error': '当前密码错误'}), 400
        if len(new_pw) < 3:
            return jsonify({'error': '新密码至少3位'}), 400
        user.password_hash = hash_password(new_pw)
        changed = True

    if changed:
        db.session.commit()
        return jsonify({'user': user.to_dict(), 'message': '个人信息已更新'})
    return jsonify({'error': '没有需要修改的内容'}), 400


@auth_bp.route('/api/session', methods=['GET'])
@require_auth
def session_info():
    from flask import current_app
    is_admin = g.current_user.role == 'admin'
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    new_token = None
    try:
        data = jwt.decode(token, current_app.config['JWT_SECRET'], algorithms=['HS256'])
        remaining = data['exp'] - int(datetime.utcnow().timestamp())
        if remaining < 86400:
            new_token = create_token(g.current_user, current_app)
    except Exception:
        pass
    # Lazy import to avoid circular dependency
    from app import get_field_visibility
    resp = jsonify({
        'user': g.current_user.to_dict(),
        'field_visibility': get_field_visibility() if not is_admin else {},
        'registration_open': _is_registration_open(),
    })
    if new_token:
        resp.headers['X-New-Token'] = new_token
    return resp
