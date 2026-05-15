"""
产品管理测试 — CRUD / 搜索 / 拼音 / 版本 / 批量操作
"""
import pytest
from conftest import api


# ═══════════════════════════════════════════════════
# 产品 CRUD
# ═══════════════════════════════════════════════════

class TestProductCRUD:
    def test_list_products(self, admin_token):
        """获取产品列表"""
        resp = api("GET", "/api/products", token=admin_token)
        assert resp.status_code == 200
        data = resp.json()
        assert "products" in data
        assert "total" in data
        assert "categories" in data
        assert "suppliers" in data
        assert "version" in data

    def test_list_products_paginated(self, admin_token):
        """分页测试"""
        resp = api("GET", "/api/products?page=1&per_page=5", token=admin_token)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["products"]) <= 5
        assert data["page"] == 1
        assert data["per_page"] == 5

    def test_get_product_detail(self, admin_token, test_product):
        """获取单个产品"""
        resp = api("GET", f"/api/products/{test_product['id']}", token=admin_token)
        assert resp.status_code == 200
        data = resp.json()
        assert data["product"]["name"] == test_product["name"]

    def test_create_product(self, admin_token):
        """创建产品"""
        resp = api("POST", "/api/products", json={
            "name": "新建产品_测试",
            "spec": "NEW-SPEC-001",
            "category": "测试分类",
            "supplier": "测试厂商",
            "unit": "个",
            "price": 99.99,
            "cost_price": 50.00,
        }, token=admin_token)
        assert resp.status_code == 201
        p = resp.json()["product"]
        assert p["name"] == "新建产品_测试"
        assert p["sku"] == "NEW-SPEC-001"  # sku 自动同步 spec
        assert p["price"] == 99.99

    def test_create_product_minimal(self, admin_token):
        """最小字段创建产品（仅名称）"""
        resp = api("POST", "/api/products", json={
            "name": "最小产品_测试",
        }, token=admin_token)
        assert resp.status_code == 201
        assert resp.json()["product"]["name"] == "最小产品_测试"

    def test_create_product_empty_name(self, admin_token):
        """空名称创建 — 应失败"""
        resp = api("POST", "/api/products", json={"name": ""}, token=admin_token)
        assert resp.status_code == 400

    def test_update_product(self, admin_token, test_product):
        """更新产品"""
        resp = api("PUT", f"/api/products/{test_product['id']}", json={
            "name": "测试产品_已更新",
            "price": 150.00,
        }, token=admin_token)
        assert resp.status_code == 200
        p = resp.json()["product"]
        assert p["name"] == "测试产品_已更新"
        assert p["price"] == 150.00

    def test_update_nonexistent_product(self, admin_token):
        """更新不存在的产品"""
        resp = api("PUT", "/api/products/99999", json={"name": "x"}, token=admin_token)
        assert resp.status_code == 404

    def test_delete_product(self, admin_token):
        """删除产品"""
        # 先创建
        c = api("POST", "/api/products",
                json={"name": "待删除产品"}, token=admin_token)
        pid = c.json()["product"]["id"]
        # 再删除
        resp = api("DELETE", f"/api/products/{pid}", token=admin_token)
        assert resp.status_code == 200
        # 确认已删除
        resp2 = api("GET", f"/api/products/{pid}", token=admin_token)
        assert resp2.status_code == 404

    def test_delete_nonexistent_product(self, admin_token):
        """删除不存在的产品"""
        resp = api("DELETE", "/api/products/99999", token=admin_token)
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════
# 搜索测试
# ═══════════════════════════════════════════════════

class TestProductSearch:
    def test_search_by_name(self, admin_token):
        """按名称搜索"""
        resp = api("GET", "/api/products?search=测试", token=admin_token)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_search_by_spec(self, admin_token):
        """按规格搜索"""
        resp = api("GET", "/api/products?search=TEST-MODEL", token=admin_token)
        assert resp.status_code == 200

    def test_search_no_results(self, admin_token):
        """无结果搜索"""
        resp = api("GET", "/api/products?search=xyz_nonexistent_abc123", token=admin_token)
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_pinyin_search_full(self, admin_token):
        """拼音全拼搜索 — ce shi"""
        resp = api("GET", "/api/products?search=ceshi", token=admin_token)
        assert resp.status_code == 200
        data = resp.json()
        # 应该有 _py 字段
        if data["products"]:
            assert "_py" in data["products"][0]
            assert "_py_initials" in data["products"][0]

    def test_pinyin_search_initials(self, admin_token):
        """拼音首字母搜索 — cs"""
        resp = api("GET", "/api/products?search=cs", token=admin_token)
        assert resp.status_code == 200

    def test_category_filter(self, admin_token):
        """分类筛选"""
        resp = api("GET", "/api/products?category=测试分类", token=admin_token)
        assert resp.status_code == 200

    def test_supplier_filter(self, admin_token):
        """厂商筛选"""
        resp = api("GET", "/api/products?supplier=测试厂商", token=admin_token)
        assert resp.status_code == 200

    def test_sorting(self, admin_token):
        """排序 — 按价格降序"""
        resp = api("GET", "/api/products?sort_by=price&sort_order=desc", token=admin_token)
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════
# 版本检查 & 批量操作
# ═══════════════════════════════════════════════════

class TestProductVersion:
    def test_version_endpoint(self, admin_token):
        """产品版本检查端点"""
        resp = api("GET", "/api/products/version", token=admin_token)
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "max_updated_at" in data

    def test_version_changes_on_update(self, admin_token):
        """修改产品后版本号变化"""
        v1 = api("GET", "/api/products/version", token=admin_token).json()
        # 创建新产品
        api("POST", "/api/products",
            json={"name": "版本测试产品", "price": 1}, token=admin_token)
        v2 = api("GET", "/api/products/version", token=admin_token).json()
        assert v2["count"] > v1["count"] or v2["max_updated_at"] != v1["max_updated_at"]


class TestBatchOperations:
    def test_batch_delete(self, admin_token):
        """批量删除"""
        # 创建 3 个产品
        ids = []
        for i in range(3):
            c = api("POST", "/api/products",
                    json={"name": f"批量删除_{i}"}, token=admin_token)
            ids.append(c.json()["product"]["id"])

        resp = api("POST", "/api/products/batch-delete",
                   json={"ids": ids}, token=admin_token)
        assert resp.status_code == 200

        # 确认已删除
        for pid in ids:
            r = api("GET", f"/api/products/{pid}", token=admin_token)
            assert r.status_code == 404

    def test_batch_delete_empty(self, admin_token):
        """空列表批量删除"""
        resp = api("POST", "/api/products/batch-delete",
                   json={"ids": []}, token=admin_token)
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════
# 认证拦截
# ═══════════════════════════════════════════════════

class TestProductAuth:
    def test_list_without_auth(self):
        """未登录获取产品列表"""
        resp = api("GET", "/api/products")
        assert resp.status_code == 401

    def test_create_without_auth(self):
        """未登录创建产品"""
        resp = api("POST", "/api/products", json={"name": "test"})
        assert resp.status_code == 401

    def test_delete_without_auth(self):
        """未登录删除产品"""
        resp = api("DELETE", "/api/products/1")
        assert resp.status_code == 401
