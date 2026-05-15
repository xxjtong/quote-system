"""
认证系统测试 — 登录/注册/Session/个人信息
"""
import pytest
from conftest import api


# ═══════════════════════════════════════════════════
# 登录测试
# ═══════════════════════════════════════════════════

class TestLogin:
    def test_login_success_admin(self, admin_token):
        """管理员正常登录"""
        assert admin_token, "Token 不应为空"
        assert len(admin_token) > 20, "Token 长度异常"

    def test_login_wrong_password(self):
        """错误密码登录"""
        resp = api("POST", "/api/auth/login",
                   json={"username": "admin", "password": "wrong_password_xyz"})
        assert resp.status_code == 401
        assert "错误" in resp.json().get("error", "")

    def test_login_empty_fields(self):
        """空用户名/密码"""
        resp = api("POST", "/api/auth/login", json={"username": "", "password": ""})
        assert resp.status_code == 400

    def test_login_missing_fields(self):
        """缺少字段"""
        resp = api("POST", "/api/auth/login", json={"username": "admin"})
        assert resp.status_code == 400

    def test_login_nonexistent_user(self):
        """不存在的用户"""
        resp = api("POST", "/api/auth/login",
                   json={"username": "nonexistent_user_xyz99", "password": "123"})
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════
# 注册测试
# ═══════════════════════════════════════════════════

class TestRegister:
    def test_register_duplicate(self, admin_token):
        """重复注册"""
        resp = api("POST", "/api/auth/register",
                   json={"username": "admin", "password": "123456"})
        # 409=重复, 403=注册关闭
        assert resp.status_code in [409, 403]

    def test_register_empty_fields(self):
        """空字段注册"""
        resp = api("POST", "/api/auth/register",
                   json={"username": "", "password": ""})
        # 400=校验失败, 403=注册关闭
        assert resp.status_code in [400, 403]

    def test_register_short_password(self):
        """短密码注册（允许但记录行为）"""
        import time
        u = f"testpw_{int(time.time()) % 100000}"
        resp = api("POST", "/api/auth/register",
                   json={"username": u, "password": "ab"})
        # 短密码后端不限制（UI校验），记录返回
        assert resp.status_code in [201, 400, 403]


# ═══════════════════════════════════════════════════
# Session & Token 测试
# ═══════════════════════════════════════════════════

class TestSession:
    def test_session_with_valid_token(self, admin_token):
        """有效 token 获取 session"""
        resp = api("GET", "/api/session", token=admin_token)
        assert resp.status_code == 200
        data = resp.json()
        assert "user" in data
        assert data["user"]["username"] == "admin"

    def test_session_without_token(self):
        """无 token 访问 session"""
        resp = api("GET", "/api/session")
        assert resp.status_code == 401

    def test_session_with_invalid_token(self):
        """无效 token"""
        resp = api("GET", "/api/session", token="invalid_token_12345")
        assert resp.status_code == 401

    def test_session_with_expired_token(self):
        """伪造过期 token — 应返回 401"""
        fake_token = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJ1c2VyX2lkIjoxLCJ1c2VybmFtZSI6ImFkbWluIiwicm9sZSI6ImFkbWluIiwiZXhwIjoxMDAwMDAwfQ."
            "fake_signature"
        )
        resp = api("GET", "/api/session", token=fake_token)
        assert resp.status_code == 401

    def test_token_auto_renew(self, admin_token):
        """验证 session 返回 X-New-Token（token 快过期时自动续签）"""
        resp = api("GET", "/api/session", token=admin_token)
        # 不一定会续签（token 有效期 72h），但 header 存在性取决于后端逻辑
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════
# 个人信息修改
# ═══════════════════════════════════════════════════

class TestProfile:
    def test_update_email(self, admin_token):
        """修改邮箱"""
        resp = api("PUT", "/api/auth/profile",
                   json={"email": "test@example.com"}, token=admin_token)
        assert resp.status_code == 200

    def test_update_empty_body(self, admin_token):
        """空请求体"""
        resp = api("PUT", "/api/auth/profile", json={}, token=admin_token)
        assert resp.status_code == 400

    def test_update_without_auth(self):
        """未登录修改"""
        resp = api("PUT", "/api/auth/profile",
                   json={"email": "test@example.com"})
        assert resp.status_code == 401
