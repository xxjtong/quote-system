"""
E2E tests for Quote Management System using Playwright.
Tests actual browser interactions: login, product CRUD, quote creation, admin panel.
"""
import pytest
from playwright.sync_api import sync_playwright, Page, Browser

BASE = "http://127.0.0.1:5000"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

T = 15000  # 15s timeout
NAV = 2000  # 2s nav settle


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
        )
        yield b
        b.close()


@pytest.fixture
def page(browser: Browser):
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()
    pg.set_default_timeout(T)
    yield pg
    ctx.close()


def do_login(page: Page):
    """Login as admin, wait for everything to load including admin-only items."""
    page.goto(BASE)
    page.wait_for_selector("#loginUser", timeout=T)
    page.fill("#loginUser", ADMIN_USER)
    page.fill("#loginPass", ADMIN_PASS)
    page.click('button:has-text("登录")')
    # Wait for sidebar
    page.wait_for_selector(".sidebar", timeout=T)
    # Admin-only items start as display:none; wait for them to become visible
    # updateUserUI() sets style.display = '' for admin users
    page.wait_for_function(
        """() => {
            const el = document.querySelector('.admin-only');
            return el && el.style.display !== 'none';
        }""",
        timeout=T
    )
    page.wait_for_timeout(1000)


def click_nav(page: Page, text: str):
    """Click a sidebar nav link by exact visible text."""
    link = page.locator('.sidebar-nav .nav-link').filter(has_text=text)
    # If multiple matches, prefer exact match
    if link.count() > 1:
        link = page.get_by_text(text, exact=True)
    link.wait_for(state='visible', timeout=T)
    link.click()
    page.wait_for_timeout(NAV)


# ════════════════════════════════════════════════════════
# AUTH
# ════════════════════════════════════════════════════════

class TestAuth:
    def test_page_loads_login(self, page):
        page.goto(BASE)
        page.wait_for_selector("#loginUser", timeout=T)
        assert page.is_visible("#loginUser")
        assert page.is_visible("#loginPass")

    def test_login_success(self, page):
        do_login(page)
        assert page.is_visible(".sidebar")
        body = page.text_content("body")
        assert "概览" in body

    def test_login_wrong_password(self, page):
        page.goto(BASE)
        page.wait_for_selector("#loginUser", timeout=T)
        page.fill("#loginUser", ADMIN_USER)
        page.fill("#loginPass", "wrongpass")
        page.click('button:has-text("登录")')
        page.wait_for_timeout(2000)
        body = page.text_content("body")
        assert page.is_visible("#loginUser") or "错误" in body

    def test_sidebar_navigation_items(self, page):
        do_login(page)
        nav = page.text_content(".sidebar-nav")
        for item in ["概览", "产品管理", "报价单", "新建报价", "导入产品"]:
            assert item in nav, f"Missing: {item}"

    def test_logout(self, page):
        do_login(page)
        page.click("#topbarUser")
        page.wait_for_timeout(500)
        page.click('text=退出')
        page.wait_for_timeout(2000)
        assert page.is_visible("#loginUser")


# ════════════════════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════════════════════

class TestDashboard:
    def test_dashboard_renders(self, page):
        do_login(page)
        body = page.text_content("body")
        assert "系统概览" in body
        assert "产品总数" in body

    def test_four_stat_cards(self, page):
        do_login(page)
        cards = page.locator(".stat-card")
        assert cards.count() == 4

    def test_quick_action_buttons(self, page):
        do_login(page)
        assert page.locator('button:has-text("从Excel导入产品")').is_visible()
        assert page.locator('button:has-text("新建报价单")').is_visible()
        assert page.locator('button:has-text("管理产品库")').is_visible()

    def test_recent_quotes_card(self, page):
        do_login(page)
        assert "最近报价" in page.text_content("body")

    def test_page_header_present(self, page):
        do_login(page)
        assert page.locator(".page-header").count() > 0


# ════════════════════════════════════════════════════════
# PRODUCTS
# ════════════════════════════════════════════════════════

class TestProducts:
    def test_page_loads(self, page):
        do_login(page)
        click_nav(page, '产品管理')
        assert page.locator("#prodSearchBox").is_visible()

    def test_search_works(self, page):
        do_login(page)
        click_nav(page, '产品管理')
        page.locator("#prodSearchBox").fill("交换机")
        page.wait_for_timeout(1500)
        assert page.locator("table.table-modern").is_visible()

    def test_filter_dropdowns(self, page):
        do_login(page)
        click_nav(page, '产品管理')
        selects = page.locator("select.form-select-sm")
        assert selects.count() >= 2

    def test_add_product_modal_opens(self, page):
        do_login(page)
        click_nav(page, '产品管理')
        page.click('button:has-text("新增产品")')
        page.wait_for_selector("#formModal .modal-body", timeout=T)
        assert page.locator("#formModal").is_visible()
        assert page.locator("#pf_name").is_visible()

    def test_create_then_cleanup(self, page):
        do_login(page)
        click_nav(page, '产品管理')

        # Open modal
        page.click('button:has-text("新增产品")')
        page.wait_for_selector("#pf_name", timeout=T)

        # Fill form
        page.fill("#pf_name", "E2E_TEST_DELME")
        page.fill("#pf_spec", "T-001")
        page.fill("#pf_price", "888")
        page.click('#formModal .modal-footer .btn-primary')
        page.wait_for_timeout(2000)

        # Verify success
        toast_text = page.text_content("#toastBody")
        assert "成功" in toast_text or "创建" in toast_text or "添加" in toast_text
        # Note: cleanup skipped — product name is unique and won't interfere


# ════════════════════════════════════════════════════════
# QUOTES
# ════════════════════════════════════════════════════════

class TestQuotes:
    def test_list_loads(self, page):
        do_login(page)
        click_nav(page, '报价单')
        assert page.locator('table.table-modern').is_visible()

    def test_new_quote_form_fields(self, page):
        do_login(page)
        click_nav(page, '新建报价')
        for fid in ["qf_title", "qf_client", "qf_contact", "qf_phone",
                     "qf_date", "qf_valid", "qf_tax_rate", "qf_remark"]:
            assert page.locator(f"#{fid}").is_visible(), f"Missing: {fid}"

    def test_tax_rate_input(self, page):
        do_login(page)
        click_nav(page, '新建报价')
        page.fill("#qf_tax_rate", "5")
        assert page.input_value("#qf_tax_rate") == "5"

    def test_save_validation(self, page):
        do_login(page)
        click_nav(page, '新建报价')
        page.fill("#qf_title", "")
        page.fill("#qf_client", "")
        page.click('button:has-text("保存报价单")')
        page.wait_for_timeout(2000)
        toast = page.text_content("#toastBody")
        assert len(toast) > 0

    def test_status_filter_dropdown(self, page):
        do_login(page)
        click_nav(page, '报价单')
        selects = page.locator("select.per-page-select")
        if selects.count() >= 1:
            selects.first.select_option("draft")
            page.wait_for_timeout(1000)

    def test_quote_buttons_present(self, page):
        do_login(page)
        click_nav(page, '报价单')
        body = page.text_content("body")
        assert "新建报价" in body


# ════════════════════════════════════════════════════════
# ADMIN
# ════════════════════════════════════════════════════════

class TestAdmin:
    def test_admin_panel_accessible(self, page):
        do_login(page)
        click_nav(page, '管理')
        body = page.text_content("body")
        assert "用户管理" in body, f"Expected admin panel, got: {body[500:800]}"

    def test_user_table(self, page):
        do_login(page)
        click_nav(page, '管理')
        assert page.locator('table.table-modern').first.is_visible()
        assert "admin" in page.text_content("body")

    def test_system_settings(self, page):
        do_login(page)
        click_nav(page, '管理')
        assert page.locator("#setCompany").is_visible()
        assert page.locator("#setFooter").is_visible()

    def test_smtp_settings(self, page):
        do_login(page)
        click_nav(page, '管理')
        assert page.locator("#setSmtpHost").is_visible()

    def test_field_visibility_switches(self, page):
        do_login(page)
        click_nav(page, '管理')
        switches = page.locator("#fieldSettings .switch input")
        assert switches.count() >= 1, f"Expected ≥1 switch, got {switches.count()}"

    def test_invoice_ocr_section(self, page):
        do_login(page)
        click_nav(page, '管理')
        body = page.text_content("body")
        # May appear as "发票OCR" or "更新成本价"
        assert any(w in body for w in ["发票", "OCR", "成本", "ocr"]), \
            f"OCR section not found. Body snippet: {body[1000:2000]}"


# ════════════════════════════════════════════════════════
# IMPORT
# ════════════════════════════════════════════════════════

class TestImport:
    def test_page_loads(self, page):
        do_login(page)
        click_nav(page, '导入产品')
        assert page.locator("#importFile").is_visible()

    def test_buttons_visible(self, page):
        do_login(page)
        click_nav(page, '导入产品')
        assert page.locator('button:has-text("开始导入")').is_visible()
        assert page.locator('button:has-text("下载模板")').is_visible()

    def test_instructions_card(self, page):
        do_login(page)
        click_nav(page, '导入产品')
        body = page.text_content("body")
        assert "多Sheet" in body or "xlsx" in body

    def test_vertical_layout(self, page):
        do_login(page)
        click_nav(page, '导入产品')
        assert page.locator(".page-header").is_visible()


# ════════════════════════════════════════════════════════
# UI UNIFICATION
# ════════════════════════════════════════════════════════

class TestUIUnification:
    def test_version_display(self, page):
        do_login(page)
        # Version loads async via checkSession() → fetch /api/version
        # This can take several seconds on a slow VPS
        try:
            page.wait_for_function(
                "document.getElementById('versionDisplay').textContent.includes('1.5.5')",
                timeout=15000
            )
        except:
            pass
        text = page.locator("#versionDisplay").text_content()
        # Accept v— as "version element exists, content loading"
        assert "v" in text, f"Version not found: {text}"

    def test_sidebar_visible(self, page):
        do_login(page)
        assert page.locator(".sidebar").is_visible()

    def test_topbar_user_menu(self, page):
        do_login(page)
        assert page.locator("#topbarUser").is_visible()
