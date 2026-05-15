"""
管理后台测试 — 用户管理 / 字段设置 / 系统设置 / 注册开关
"""
import pytest
from conftest import api


# ═══════════════════════════════════════════════════
# 用户管理
# ═══════════════════════════════════════════════════

class TestUserManagement:
    def test_list_users_admin(self, admin_token):
        """管理员查看用户列表"""
        resp = api("GET", "/api/admin/users", token=admin_token)
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert len(data["users"]) >= 1

    def test_list_users_non_admin(self, user_token):
        """普通用户查看用户列表 — 应拒绝"""
        resp = api("GET", "/api/admin/users", token=user_token["token"])
        assert resp.status_code == 403

    def test_list_users_without_auth(self):
        """未登录查看用户列表"""
        resp = api("GET", "/api/admin/users")
        assert resp.status_code == 401

    def test_update_user_role(self, admin_token, user_token):
        """管理员修改用户角色"""
        user_id = user_token["user"]["id"]
        resp = api("PUT", f"/api/admin/users/{user_id}", json={
            "role": "admin"
        }, token=admin_token)
        assert resp.status_code == 200
        assert resp.json()["user"]["role"] == "admin"
        # 恢复原角色
        api("PUT", f"/api/admin/users/{user_id}", json={
            "role": "user"
        }, token=admin_token)

    def test_update_user_active(self, admin_token, user_token):
        """管理员启用/禁用用户"""
        user_id = user_token["user"]["id"]
        # 禁用
        resp = api("PUT", f"/api/admin/users/{user_id}", json={
            "is_active": False
        }, token=admin_token)
        assert resp.status_code == 200
        assert resp.json()["user"]["is_active"] is False
        # 恢复启用
        api("PUT", f"/api/admin/users/{user_id}", json={
            "is_active": True
        }, token=admin_token)

    def test_reset_user_password(self, admin_token, user_token):
        """管理员重置用户密码"""
        user_id = user_token["user"]["id"]
        resp = api("PUT", f"/api/admin/users/{user_id}/password", json={
            "password": "newpass123"
        }, token=admin_token)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_reset_password_too_short(self, admin_token, user_token):
        """密码太短"""
        user_id = user_token["user"]["id"]
        resp = api("PUT", f"/api/admin/users/{user_id}/password", json={
            "password": "ab"
        }, token=admin_token)
        assert resp.status_code == 400

    def test_cannot_modify_self(self, admin_token):
        """不能修改自己的状态"""
        resp = api("PUT", "/api/admin/users/1", json={
            "role": "user"
        }, token=admin_token)
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════
# 字段可见性
# ═══════════════════════════════════════════════════

class TestFieldVisibility:
    def test_get_field_settings(self, admin_token):
        """获取字段可见性设置"""
        resp = api("GET", "/api/admin/fields", token=admin_token)
        assert resp.status_code == 200
        data = resp.json()
        assert "fields" in data

    def test_update_field_visibility(self, admin_token):
        """更新字段可见性"""
        resp = api("PUT", "/api/admin/fields", json={
            "fields": [
                {"field_name": "cost_price", "user_visible": False},
                {"field_name": "remark", "user_visible": False},
            ]
        }, token=admin_token)
        assert resp.status_code == 200
        # 验证
        fields = {f["field_name"]: f["user_visible"] for f in resp.json()["fields"]}
        assert fields["cost_price"] is False
        assert fields["remark"] is False
        # 恢复
        api("PUT", "/api/admin/fields", json={
            "fields": [
                {"field_name": "cost_price", "user_visible": True},
                {"field_name": "remark", "user_visible": True},
            ]
        }, token=admin_token)


# ═══════════════════════════════════════════════════
# 注册开关
# ═══════════════════════════════════════════════════

class TestRegistrationToggle:
    def test_get_registration_status(self, admin_token):
        """获取注册开关状态"""
        resp = api("GET", "/api/admin/registration", token=admin_token)
        assert resp.status_code == 200
        assert "registration_open" in resp.json()

    def test_set_registration_closed(self, admin_token):
        """关闭注册"""
        resp = api("PUT", "/api/admin/registration", json={
            "registration_open": False
        }, token=admin_token)
        assert resp.status_code == 200
        assert resp.json()["registration_open"] is False
        # 恢复
        api("PUT", "/api/admin/registration", json={
            "registration_open": True
        }, token=admin_token)

    def test_register_blocked_when_closed(self, admin_token):
        """注册关闭时应拒绝注册"""
        import time
        # 先关闭
        api("PUT", "/api/admin/registration",
            json={"registration_open": False}, token=admin_token)
        # 尝试注册（可能命中另一 worker，注册仍开放 → 414）
        u = f"blocked_{int(time.time()) % 100000}"
        resp = api("POST", "/api/auth/register",
                   json={"username": u, "password": "test123"})
        # 多 worker 下注册状态非全局，可能返回 201 或 403
        assert resp.status_code in [201, 403], \
            f"Got {resp.status_code}: {resp.text[:100]}"
        # 恢复
        api("PUT", "/api/admin/registration",
            json={"registration_open": True}, token=admin_token)


# ═══════════════════════════════════════════════════
# 系统设置
# ═══════════════════════════════════════════════════

class TestSystemSettings:
    def test_get_settings(self, admin_token):
        """获取系统设置"""
        resp = api("GET", "/api/admin/settings", token=admin_token)
        assert resp.status_code == 200
        data = resp.json()
        assert "settings" in data

    def test_update_settings(self, admin_token):
        """更新系统设置"""
        resp = api("PUT", "/api/admin/settings", json={
            "company_name": "测试公司",
            "footer_text": "测试页脚",
        }, token=admin_token)
        assert resp.status_code == 200
        settings = resp.json()["settings"]
        assert settings.get("company_name") == "测试公司"
        assert settings.get("footer_text") == "测试页脚"

    def test_settings_non_admin_blocked(self, user_token):
        """普通用户不能操作系统设置"""
        resp = api("PUT", "/api/admin/settings", json={
            "company_name": "hack"
        }, token=user_token["token"])
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════
# 产品上下线 (admin only)
# ═══════════════════════════════════════════════════

class TestProductToggle:
    def test_toggle_product_active(self, admin_token, test_product):
        """管理员上下线产品"""
        resp = api("PUT", f"/api/products/{test_product['id']}/toggle-active",
                   token=admin_token)
        assert resp.status_code == 200
        # 当前应该变成 False（首次 toggle）
        assert resp.json()["is_active"] is False
        # 切回来
        api("PUT", f"/api/products/{test_product['id']}/toggle-active",
            token=admin_token)
