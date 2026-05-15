"""
报价单管理测试 — CRUD / 状态流转 / 导出 / 权限
"""
import pytest
from conftest import api


# ═══════════════════════════════════════════════════
# 报价单 CRUD
# ═══════════════════════════════════════════════════

class TestQuoteCRUD:
    def test_list_quotes(self, admin_token):
        """获取报价单列表"""
        resp = api("GET", "/api/quotes", token=admin_token)
        assert resp.status_code == 200
        data = resp.json()
        assert "quotes" in data

    def test_get_quote_detail(self, admin_token, test_quote):
        """获取报价单详情"""
        resp = api("GET", f"/api/quotes/{test_quote['id']}", token=admin_token)
        assert resp.status_code == 200
        data = resp.json()
        quote = data["quote"]
        assert quote["title"] == test_quote["title"]
        assert "items" in quote
        assert len(quote["items"]) >= 1
        # 验证 items 含利润字段
        item = quote["items"][0]
        assert "profit" in item
        assert "profit_rate" in item
        assert "product_name" in item

    def test_create_quote_minimal(self, admin_token):
        """最小字段创建报价单"""
        resp = api("POST", "/api/quotes", json={
            "title": "最简报价单",
            "client": "最简客户",
        }, token=admin_token)
        assert resp.status_code == 201
        q = resp.json()["quote"]
        assert q["title"] == "最简报价单"
        assert q["status"] == "draft"
        assert q["total_amount"] == 0

    def test_create_quote_full(self, admin_token, test_product):
        """完整字段创建报价单"""
        resp = api("POST", "/api/quotes", json={
            "title": "完整报价单_测试",
            "client": "完整客户",
            "contact": "李四",
            "phone": "13900139000",
            "quote_date": "2026-05-15",
            "valid_days": 60,
            "tax_rate": 5,
            "remark": "完整备注",
            "items": [
                {
                    "product_id": test_product["id"],
                    "product_name": test_product["name"],
                    "product_spec": test_product["spec"],
                    "product_sku": test_product["sku"],
                    "product_unit": test_product["unit"],
                    "quantity": 3,
                    "unit_price": 200.00,
                    "remark": "明细备注",
                },
                {
                    "product_id": None,
                    "product_name": "手工添加产品",
                    "product_spec": "HAND-001",
                    "product_sku": "",
                    "product_unit": "套",
                    "quantity": 1,
                    "unit_price": 500.00,
                    "remark": "",
                },
            ],
        }, token=admin_token)
        assert resp.status_code == 201
        q = resp.json()["quote"]
        assert q["total_amount"] == 1100.00  # 3*200 + 1*500
        assert len(q["items"]) == 2
        assert q["tax_rate"] == 5

    def test_update_quote(self, admin_token, test_quote):
        """更新报价单"""
        resp = api("PUT", f"/api/quotes/{test_quote['id']}", json={
            "title": "已更新报价单",
            "client": "新客户",
            "contact": "王五",
        }, token=admin_token)
        assert resp.status_code == 200
        q = resp.json()["quote"]
        assert q["title"] == "已更新报价单"
        assert q["client"] == "新客户"

    def test_update_nonexistent_quote(self, admin_token):
        """更新不存在的报价单"""
        resp = api("PUT", "/api/quotes/99999",
                   json={"title": "x"}, token=admin_token)
        assert resp.status_code == 404

    def test_delete_quote(self, admin_token):
        """删除报价单"""
        c = api("POST", "/api/quotes",
                json={"title": "待删除报价单", "client": "x"}, token=admin_token)
        qid = c.json()["quote"]["id"]
        resp = api("DELETE", f"/api/quotes/{qid}", token=admin_token)
        assert resp.status_code == 200
        resp2 = api("GET", f"/api/quotes/{qid}", token=admin_token)
        assert resp2.status_code == 404


# ═══════════════════════════════════════════════════
# 报价单状态流转
# ═══════════════════════════════════════════════════

class TestQuoteStatus:
    VALID_STATUSES = ["draft", "sent", "confirmed", "rejected", "expired"]

    def test_default_status_is_draft(self, admin_token):
        """新报价单默认状态应为 draft"""
        c = api("POST", "/api/quotes",
                json={"title": "状态测试", "client": "x"}, token=admin_token)
        assert c.json()["quote"]["status"] == "draft"

    def test_status_transition_to_sent(self, admin_token, test_quote):
        """draft → sent"""
        resp = api("PATCH", f"/api/quotes/{test_quote['id']}/status",
                   json={"status": "sent"}, token=admin_token)
        assert resp.status_code == 200
        assert resp.json()["quote"]["status"] == "sent"

    def test_status_transition_to_confirmed(self, admin_token, test_quote):
        """→ confirmed"""
        resp = api("PATCH", f"/api/quotes/{test_quote['id']}/status",
                   json={"status": "confirmed"}, token=admin_token)
        assert resp.status_code == 200

    def test_status_transition_to_completed(self, admin_token, test_quote):
        """→ rejected / expired"""
        for s in ["rejected", "expired"]:
            resp = api("PATCH", f"/api/quotes/{test_quote['id']}/status",
                       json={"status": s}, token=admin_token)
            assert resp.status_code == 200

    def test_invalid_status_rejected(self, admin_token, test_quote):
        """无效状态"""
        resp = api("PATCH", f"/api/quotes/{test_quote['id']}/status",
                   json={"status": "invalid_status"}, token=admin_token)
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════
# 报价单导出 & 预览
# ═══════════════════════════════════════════════════

class TestQuoteExport:
    def test_preview_html(self, admin_token, test_quote):
        """HTML 预览"""
        resp = api("GET", f"/api/quotes/{test_quote['id']}/preview",
                   token=admin_token)
        assert resp.status_code == 200
        # 预览返回 HTML
        assert "<html" in resp.text.lower() or "<table" in resp.text.lower()

    def test_export_excel(self, admin_token, test_quote):
        """导出 Excel"""
        resp = api("GET", f"/api/quotes/{test_quote['id']}/export-excel",
                   token=admin_token)
        assert resp.status_code == 200
        # 确认是 Excel 文件
        ct = resp.headers.get("Content-Type", "")
        assert "spreadsheet" in ct.lower() or "excel" in ct.lower() or \
               resp.headers.get("Content-Disposition", "").endswith(".xlsx")

    def test_export_increments_download_count(self, admin_token, test_quote):
        """导出后 download_count 应递增"""
        # 获取当前计数
        before = api("GET", f"/api/quotes/{test_quote['id']}", token=admin_token)
        count_before = before.json()["quote"]["download_count"]
        # 执行导出
        api("GET", f"/api/quotes/{test_quote['id']}/export-excel",
            token=admin_token)
        after = api("GET", f"/api/quotes/{test_quote['id']}", token=admin_token)
        count_after = after.json()["quote"]["download_count"]
        assert count_after >= count_before + 1


# ═══════════════════════════════════════════════════
# 统计 & 客户聚合
# ═══════════════════════════════════════════════════

class TestQuoteStats:
    def test_quote_stats(self, admin_token):
        """客户维度聚合统计"""
        resp = api("GET", "/api/quotes/stats", token=admin_token)
        assert resp.status_code == 200
        data = resp.json()
        assert "customers" in data


# ═══════════════════════════════════════════════════
# 权限测试
# ═══════════════════════════════════════════════════

class TestQuoteAuth:
    def test_list_without_auth(self):
        """未登录获取报价单"""
        resp = api("GET", "/api/quotes")
        assert resp.status_code == 401

    def test_detail_without_auth(self):
        """未登录获取报价单详情"""
        resp = api("GET", "/api/quotes/1")
        assert resp.status_code == 401

    def test_non_owner_access(self, admin_token, user_token):
        """非管理员用户访问他人报价单"""
        # admin 创建一个报价单
        c = api("POST", "/api/quotes",
                json={"title": "admin专属", "client": "x"}, token=admin_token)
        qid = c.json()["quote"]["id"]
        # 普通用户尝试访问
        resp = api("GET", f"/api/quotes/{qid}", token=user_token["token"])
        # 普通用户只能看到自己的报价单，别人的应 404 或 403
        assert resp.status_code in [403, 404]
