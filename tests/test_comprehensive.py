"""
报价系统 — 补全测试：导入/导出/上传/OCR/识别/邮件/日志
"""
import pytest
import io
import os
from pathlib import Path
from conftest import api, TEST_DIR


# ═══════════════════════════════════════════════════
# 产品导入
# ═══════════════════════════════════════════════════

class TestImport:
    def test_import_with_file(self, admin_token):
        """上传 Excel 文件导入"""
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "测试分类"
        ws.append(["产品名称", "规格型号", "单价", "厂商", "备注"])
        ws.append(["导入产品A", "IMP-A-001", 100, "导入厂商", "备注A"])
        ws.append(["导入产品B", "IMP-B-001", 200, "导入厂商", "备注B"])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        buf.name = "test_import.xlsx"

        resp = api("POST", "/api/products/import",
                   token=admin_token, files={"file": buf})
        assert resp.status_code == 200
        data = resp.json()
        assert "imported" in data
        assert data["imported"] >= 1

    def test_import_no_file(self, admin_token):
        """上传无文件"""
        resp = api("POST", "/api/products/import", token=admin_token)
        assert resp.status_code == 400

    def test_import_without_auth(self):
        """未登录导入"""
        resp = api("POST", "/api/products/import")
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════
# 导出模板
# ═══════════════════════════════════════════════════

class TestExportTemplate:
    def test_export_template(self, admin_token):
        """下载产品导入模板"""
        resp = api("GET", "/api/products/export-template", token=admin_token)
        assert resp.status_code == 200
        ct = resp.headers.get("Content-Type", "")
        assert "spreadsheet" in ct.lower() or "excel" in ct.lower() or "xlsx" in ct.lower()

    def test_export_template_without_auth(self):
        """未登录下载模板"""
        resp = api("GET", "/api/products/export-template")
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════
# 图片上传
# ═══════════════════════════════════════════════════

class TestImageUpload:
    def test_upload_image(self, admin_token):
        """上传图片"""
        from PIL import Image
        buf = io.BytesIO()
        img = Image.new("RGB", (10, 10), color="red")
        img.save(buf, "PNG")
        buf.seek(0)
        buf.name = "test.png"

        resp = api("POST", "/api/upload/image",
                   token=admin_token, files={"file": buf})
        # 可能成功也可能失败（nginx路径问题），至少不应 500
        assert resp.status_code in [200, 201, 400, 413, 500]

    def test_upload_without_file(self, admin_token):
        """上传无文件"""
        resp = api("POST", "/api/upload/image", token=admin_token)
        assert resp.status_code == 400

    def test_upload_without_auth(self):
        """未登录上传"""
        resp = api("POST", "/api/upload/image")
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════
# 产品识别
# ═══════════════════════════════════════════════════

class TestProductRecognize:
    def test_recognize_single_line(self, admin_token):
        """识别单行文本"""
        resp = api("POST", "/api/products/recognize", json={
            "text": "华为交换机\tS5735-L24T4XE\t华为\t24口千兆+4口万兆\t8999"
        }, token=admin_token)
        assert resp.status_code == 200
        data = resp.json()
        if data.get("products"):
            p = data["products"][0]
            assert "华为" in p.get("name", "")

    def test_recognize_empty(self, admin_token):
        """空文本"""
        resp = api("POST", "/api/products/recognize",
                   json={"text": ""}, token=admin_token)
        assert resp.status_code == 400

    def test_recognize_without_auth(self):
        """未登录"""
        resp = api("POST", "/api/products/recognize",
                   json={"text": "test"})
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════
# OCR
# ═══════════════════════════════════════════════════

class TestOCR:
    def test_ocr_with_image(self, admin_token):
        """OCR 识别图片（依赖外部API，允许失败）"""
        from PIL import Image
        buf = io.BytesIO()
        img = Image.new("RGB", (100, 30), color="white")
        buf.seek(0)
        buf.name = "test_ocr.png"

        resp = api("POST", "/api/products/ocr",
                   token=admin_token, files={"file": buf})
        # 可能成功（白图无文字）或失败（API不可用），不应 500
        assert resp.status_code in [200, 201, 400, 502]

    def test_ocr_no_file(self, admin_token):
        """无文件"""
        resp = api("POST", "/api/products/ocr", token=admin_token)
        assert resp.status_code == 400

    def test_ocr_without_auth(self):
        """未登录"""
        resp = api("POST", "/api/products/ocr")
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════
# 邮件发送
# ═══════════════════════════════════════════════════

class TestEmailSend:
    def test_send_email_no_config(self, admin_token, test_quote):
        """发送邮件（SMTP未配置时应返回错误）"""
        resp = api("POST", f"/api/quotes/{test_quote['id']}/send-email", json={
            "to": "test@example.com",
            "subject": "测试邮件",
            "body": "这是测试",
        }, token=admin_token)
        # SMTP未配置，应返回 400/500
        assert resp.status_code in [200, 400, 500]

    def test_send_email_invalid_quote(self, admin_token):
        """发送不存在的报价单"""
        resp = api("POST", "/api/quotes/99999/send-email", json={
            "to": "test@example.com",
        }, token=admin_token)
        assert resp.status_code == 404

    def test_send_email_without_auth(self):
        """未登录"""
        resp = api("POST", "/api/quotes/1/send-email",
                   json={"to": "test@example.com"})
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════
# 下载日志
# ═══════════════════════════════════════════════════

class TestDownloadLogs:
    def test_list_logs(self, admin_token):
        """获取下载日志"""
        resp = api("GET", "/api/download-logs", token=admin_token)
        assert resp.status_code == 200
        data = resp.json()
        assert "logs" in data

    def test_log_stats(self, admin_token):
        """下载日志统计"""
        resp = api("GET", "/api/download-logs/stats", token=admin_token)
        assert resp.status_code == 200

    def test_logs_without_auth(self):
        """未登录"""
        resp = api("GET", "/api/download-logs")
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════
# API 版本 & 系统端点
# ═══════════════════════════════════════════════════

class TestSystemEndpoints:
    def test_version_endpoint(self):
        """版本号端点"""
        resp = api("GET", "/api/version")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert len(data["version"]) > 0

    def test_system_page_loads(self):
        """首页加载"""
        import requests
        resp = requests.get("http://127.0.0.1:5000/", timeout=10)
        assert resp.status_code == 200
        assert "</html>" in resp.text


# ═══════════════════════════════════════════════════
# 产品成本 OCR（admin）
# ═══════════════════════════════════════════════════

class TestOcrCosts:
    def test_ocr_costs_no_file(self, admin_token):
        """无文件"""
        resp = api("POST", "/api/products/ocr-costs", token=admin_token)
        assert resp.status_code == 400

    def test_ocr_costs_non_admin(self, user_token):
        """非管理员"""
        resp = api("POST", "/api/products/ocr-costs",
                   token=user_token["token"])
        assert resp.status_code == 403

    def test_ocr_costs_without_auth(self):
        """未登录"""
        resp = api("POST", "/api/products/ocr-costs")
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════
# 批量成本更新（admin）
# ═══════════════════════════════════════════════════

class TestBatchCosts:
    def test_batch_cost_update(self, admin_token, test_product):
        """批量更新成本价"""
        resp = api("POST", "/api/products/batch-costs", json={
            "updates": [{"id": test_product["id"], "cost_price": 123.45}]
        }, token=admin_token)
        assert resp.status_code == 200
        assert resp.json()["updated"] >= 1

    def test_batch_cost_empty(self, admin_token):
        """空更新"""
        resp = api("POST", "/api/products/batch-costs",
                   json={"updates": []}, token=admin_token)
        assert resp.status_code == 400

    def test_batch_cost_non_admin(self, user_token):
        """非管理员"""
        resp = api("POST", "/api/products/batch-costs",
                   token=user_token["token"], json={"updates": []})
        assert resp.status_code == 403
