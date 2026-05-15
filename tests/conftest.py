"""
pytest 配置 & fixtures — 报价系统自动化测试
"""

import pytest
import requests
import os
import time
from pathlib import Path

# ─── 配置 ─────────────────────────────────────────────
BASE_URL = os.environ.get("QUOTE_TEST_URL", "http://127.0.0.1:5000")
ADMIN_USER = os.environ.get("QUOTE_TEST_ADMIN", "admin")
ADMIN_PASS = os.environ.get("QUOTE_TEST_PASS", "admin123")
TEST_DIR = Path(__file__).parent


def api(method, path, token=None, json=None, files=None, params=None):
    """通用 API 请求封装"""
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if not files:
        headers["Content-Type"] = "application/json"

    url = f"{BASE_URL}{path}"
    if method == "GET":
        resp = requests.get(url, headers=headers, params=params, timeout=30)
    elif method == "POST":
        resp = requests.post(url, headers=headers, json=json, files=files, timeout=30)
    elif method == "PUT":
        resp = requests.put(url, headers=headers, json=json, timeout=30)
    elif method == "PATCH":
        resp = requests.patch(url, headers=headers, json=json, timeout=30)
    elif method == "DELETE":
        resp = requests.delete(url, headers=headers, timeout=30)
    else:
        raise ValueError(f"Unsupported method: {method}")
    return resp


@pytest.fixture(scope="session")
def admin_token():
    """管理员登录获取 token"""
    resp = api("POST", "/api/auth/login",
               json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="session")
def user_token(admin_token):
    """创建测试用户并获取 token"""
    # 先注册一个测试用户
    test_user = f"test_{int(time.time()) % 100000}"
    resp = api("POST", "/api/auth/register",
               json={"username": test_user, "password": "test123"})
    if resp.status_code == 403:
        # 注册关闭，用管理员开启
        api("PUT", "/api/admin/registration",
            json={"registration_open": True}, token=admin_token)
        resp = api("POST", "/api/auth/register",
                   json={"username": test_user, "password": "test123"})
    if resp.status_code == 409:
        # 用户已存在，直接用 testuser
        resp = api("POST", "/api/auth/login",
                   json={"username": test_user, "password": "test123"})
    assert resp.status_code in [200, 201], f"User setup failed: {resp.text}"
    data = resp.json()
    return {"token": data.get("token"), "username": test_user,
            "user": data.get("user", {})}


@pytest.fixture(scope="session")
def test_product(admin_token):
    """创建测试产品并返回"""
    resp = api("POST", "/api/products", json={
        "name": "测试产品_自动化",
        "spec": "TEST-MODEL-001",
        "category": "测试分类",
        "supplier": "测试厂商",
        "unit": "台",
        "price": 100.00,
        "cost_price": 80.00,
        "function_desc": "这是一个测试产品的功能描述",
        "remark": "内部备注信息",
    }, token=admin_token)
    assert resp.status_code == 201, f"Create test product failed: {resp.text}"
    return resp.json()["product"]


@pytest.fixture(scope="session")
def test_quote(admin_token, test_product):
    """创建测试报价单并返回"""
    resp = api("POST", "/api/quotes", json={
        "title": "测试报价单_自动化",
        "client": "测试客户",
        "contact": "张三",
        "phone": "13800138000",
        "quote_date": "2026-05-15",
        "valid_days": 30,
        "remark": "测试备注",
        "items": [{
            "product_id": test_product["id"],
            "product_name": test_product["name"],
            "product_spec": test_product["spec"],
            "product_sku": test_product["sku"],
            "product_unit": test_product["unit"],
            "quantity": 5,
            "unit_price": test_product["price"],
            "remark": "行备注测试",
        }],
    }, token=admin_token)
    assert resp.status_code == 201, f"Create test quote failed: {resp.text}"
    return resp.json()["quote"]


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL
