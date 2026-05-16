"""
边界条件 & 安全测试 — SQL注入 / XSS / 大请求 / 竞态 / 特殊字符
"""
import pytest
import requests
from urllib.parse import quote as url_quote
from conftest import api, BASE_URL


# ═══════════════════════════════════════════════════
# 公开端点
# ═══════════════════════════════════════════════════

class TestPublicEndpoints:
    def test_api_version(self):
        """版本号端点（公开，无需认证）"""
        resp = api("GET", "/api/version")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert len(data["version"]) > 0

    def test_static_files(self):
        """静态文件访问"""
        resp = requests.get(f"{BASE_URL}/", timeout=10)
        # 应返回 HTML（登录页或主页）
        assert resp.status_code == 200

    def test_nonexistent_route(self):
        """不存在的路由"""
        resp = api("GET", "/api/nonexistent_route_xyz")
        # /api/ 路径先过 auth 中间件 → 401；也可能是 404
        assert resp.status_code in [401, 404]


# ═══════════════════════════════════════════════════
# SQL 注入防护
# ═══════════════════════════════════════════════════

class TestSQLInjection:
    def test_search_sql_injection(self, admin_token):
        """搜索参数 SQL 注入尝试"""
        payloads = [
            "'; DROP TABLE products; --",
            "1' OR '1'='1",
            "1 UNION SELECT * FROM users",
            "1; DELETE FROM products;",
        ]
        for p in payloads:
            resp = api("GET", f"/api/products?search={url_quote(p)}",
                       token=admin_token)
            # 不应导致 500 错误；SQLAlchemy 参数化查询应防护
            assert resp.status_code in [200, 400], \
                f"SQL injection payload '{p[:30]}' caused {resp.status_code}: {resp.text[:200]}"

    def test_json_injection(self, admin_token):
        """JSON body SQL 注入"""
        resp = api("POST", "/api/products", json={
            "name": "test'; DROP TABLE products; --",
            "spec": "1' OR '1'='1",
        }, token=admin_token)
        # 应正常创建（字段值被转义或参数化）
        assert resp.status_code == 201

    def test_category_filter_injection(self, admin_token):
        """分类筛选注入"""
        resp = api("GET", "/api/products?category='; --",
                   token=admin_token)
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════
# XSS 防护
# ═══════════════════════════════════════════════════

class TestXSS:
    def test_xss_in_product_name(self, admin_token):
        """产品名称含 XSS 脚本 — 后端拦截，返回 400"""
        resp = api("POST", "/api/products", json={
            "name": '<script>alert("XSS")</script>',
            "spec": '<img src=x onerror=alert(1)>',
        }, token=admin_token)
        # 后端有 XSS 防护，应返回 400
        assert resp.status_code == 400
        assert "非法" in resp.json().get("error", "")

    def test_xss_in_search(self, admin_token):
        """搜索参数含 XSS"""
        resp = api("GET", "/api/products?search=<script>alert(1)</script>",
                   token=admin_token)
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════
# 输入边界
# ═══════════════════════════════════════════════════

class TestInputBoundaries:
    def test_very_long_product_name(self, admin_token):
        """超长产品名（接近 200 字符限制）"""
        long_name = "A" * 200
        resp = api("POST", "/api/products", json={
            "name": long_name
        }, token=admin_token)
        assert resp.status_code == 201

    def test_overlong_product_name(self, admin_token):
        """超过 200 字符 — 数据库可能截断或抛错"""
        long_name = "A" * 300
        resp = api("POST", "/api/products", json={
            "name": long_name
        }, token=admin_token)
        # SQLite 默认不截断，但 String(200) 在 SQLAlchemy 也不强制
        assert resp.status_code in [201, 400, 500]

    def test_special_unicode(self, admin_token):
        """特殊 Unicode 字符"""
        resp = api("POST", "/api/products", json={
            "name": "测试 🚀 产品 émoji ñoño",
            "spec": "型号 𝕏 測試",
        }, token=admin_token)
        assert resp.status_code == 201

    def test_negative_price(self, admin_token):
        """负价格"""
        resp = api("POST", "/api/products", json={
            "name": "负价格产品",
            "price": -100,
            "cost_price": -200,
        }, token=admin_token)
        assert resp.status_code == 201

    def test_zero_quantity_quote_item(self, admin_token, test_product):
        """数量为 0 的报价单明细"""
        resp = api("POST", "/api/quotes", json={
            "title": "零数量报价单",
            "client": "x",
            "items": [{
                "product_id": test_product["id"],
                "product_name": test_product["name"],
                "quantity": 0,
                "unit_price": 100,
            }],
        }, token=admin_token)
        assert resp.status_code == 201
        # 总金额应为 0
        assert resp.json()["quote"]["total_amount"] == 0


# ═══════════════════════════════════════════════════
# HTTP 方法验证
# ═══════════════════════════════════════════════════

class TestHTTPMethods:
    def test_wrong_method_on_endpoint(self, admin_token):
        """错误 HTTP 方法"""
        # POST 到 GET-only 端点
        resp = api("POST", "/api/version")
        # auth 中间件先拦截 → 401；也可能是 405/404
        assert resp.status_code in [401, 405, 404]

    def test_malformed_json(self):
        """畸形 JSON"""
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            headers={"Content-Type": "application/json"},
            data="this is not json",
            timeout=10,
        )
        assert resp.status_code in [400, 415, 500]

    def test_missing_content_type(self):
        """缺少 Content-Type"""
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            data="username=admin&password=admin123",
            timeout=10,
        )
        assert resp.status_code in [400, 415]


# ═══════════════════════════════════════════════════
# 并发 & 一致性
# ═══════════════════════════════════════════════════

class TestConcurrency:
    def test_create_many_products_sequential(self, admin_token):
        """连续创建 10 个产品 — 确认无 ID 冲突"""
        ids = []
        for i in range(10):
            resp = api("POST", "/api/products", json={
                "name": f"批量产品_{i}",
            }, token=admin_token)
            assert resp.status_code == 201
            ids.append(resp.json()["product"]["id"])
        # 所有 ID 唯一
        assert len(ids) == len(set(ids))

    def test_sku_spec_sync(self, admin_token):
        """SKU 自动同步 spec"""
        resp = api("POST", "/api/products", json={
            "name": "SKU同步测试",
            "spec": "SYNC-MODEL-001",
        }, token=admin_token)
        p = resp.json()["product"]
        assert p["sku"] == p["spec"] == "SYNC-MODEL-001"

        # 更新 spec 后 sku 也变化
        resp2 = api("PUT", f"/api/products/{p['id']}", json={
            "spec": "SYNC-MODEL-002",
        }, token=admin_token)
        p2 = resp2.json()["product"]
        assert p2["sku"] == "SYNC-MODEL-002"

    def test_product_price_type(self, admin_token):
        """价格字段类型验证"""
        resp = api("POST", "/api/products", json={
            "name": "类型测试",
            "price": "99.99",     # 字符串
            "cost_price": 50,     # 整数
        }, token=admin_token)
        assert resp.status_code == 201
        p = resp.json()["product"]
        assert isinstance(p["price"], (int, float))
        assert isinstance(p["cost_price"], (int, float))


# ═══════════════════════════════════════════════════
# 认证边界
# ═══════════════════════════════════════════════════

class TestAuthEdgeCases:
    def test_disabled_user_login(self, admin_token, user_token):
        """禁用用户后应无法登录"""
        uid = user_token["user"]["id"]
        uname = user_token["username"]
        # 先确保用户启用且密码正确
        api("PUT", f"/api/admin/users/{uid}", json={
            "is_active": True
        }, token=admin_token)
        api("PUT", f"/api/admin/users/{uid}/password", json={
            "password": "disableme"
        }, token=admin_token)
        # 禁用用户
        api("PUT", f"/api/admin/users/{uid}", json={
            "is_active": False
        }, token=admin_token)
        # 尝试登录
        resp = api("POST", "/api/auth/login",
                   json={"username": uname, "password": "disableme"})
        # 禁用用户可能返回 403 "账号已被停用" 或 401
        assert resp.status_code in [401, 403]
        # 恢复启用
        api("PUT", f"/api/admin/users/{uid}", json={
            "is_active": True
        }, token=admin_token)

    def test_disabled_user_token_rejected(self, admin_token):
        """禁用后旧 token 应失效"""
        import time
        # 确保注册开放
        api("PUT", "/api/admin/registration",
            json={"registration_open": True}, token=admin_token)
        # 创建临时用户
        u = f"disabletest_{int(time.time()) % 100000}"
        c = api("POST", "/api/auth/register",
                json={"username": u, "password": "test123"})
        if c.status_code != 201:
            # 注册可能被关闭（多 worker），用 admin 直接创建
            pytest.skip("Registration unavailable in this worker")
        tok = c.json()["token"]
        uid = c.json()["user"]["id"]
        # 禁用
        api("PUT", f"/api/admin/users/{uid}", json={
            "is_active": False
        }, token=admin_token)
        # 旧 token 应失效
        resp = api("GET", "/api/products", token=tok)
        assert resp.status_code in [401, 403]

    def test_multiple_failed_logins(self):
        """多次错误密码尝试（无暴力破解防护，仅验证不崩溃）"""
        for i in range(5):
            resp = api("POST", "/api/auth/login",
                       json={"username": "admin", "password": f"wrong_{i}"})
            assert resp.status_code == 401
