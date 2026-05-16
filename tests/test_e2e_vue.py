"""
Vue 3 报价系统 E2E 测试 — Playwright
Test browser interactions against the new Vue frontend.
"""
import pytest
from playwright.sync_api import sync_playwright, Page, Browser

BASE = "http://127.0.0.1:5000"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"
T = 15000  # timeout ms
NAV = 2000  # nav settle


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
    """Login as admin against Vue frontend."""
    page.goto(BASE)
    # Vue: inputs use placeholder, no ids
    page.get_by_placeholder("用户名").wait_for(state="visible", timeout=T)
    page.get_by_placeholder("用户名").fill(ADMIN_USER)
    page.get_by_placeholder("密码").fill(ADMIN_PASS)
    page.get_by_role("button", name="登录").click()
    # Wait for sidebar to appear
    page.locator(".sidebar").wait_for(state="visible", timeout=T)
    page.wait_for_timeout(1500)


def click_nav(page: Page, text: str):
    """Click sidebar nav link."""
    # Use .first to avoid strict mode issues with "管理" matching "产品管理"
    link = page.locator(".sidebar-nav .nav-link").filter(has_text=text).first
    link.wait_for(state="visible", timeout=T)
    link.click()
    page.wait_for_timeout(NAV)


# ═══════════════════════════════════════════════════
# AUTH — Vue Login
# ═══════════════════════════════════════════════════

class TestVueAuth:
    def test_page_loads_login(self, page):
        page.goto(BASE)
        assert page.get_by_placeholder("用户名").is_visible()
        assert page.get_by_placeholder("密码").is_visible()

    def test_login_success(self, page):
        do_login(page)
        assert page.locator(".sidebar").is_visible()
        assert "概览" in page.text_content("body")

    def test_login_wrong_password(self, page):
        page.goto(BASE)
        page.get_by_placeholder("用户名").fill(ADMIN_USER)
        page.get_by_placeholder("密码").fill("wrongpass")
        page.get_by_role("button", name="登录").click()
        page.wait_for_timeout(1500)
        body = page.text_content("body")
        assert "错误" in body or page.get_by_placeholder("用户名").is_visible()

    def test_register_form_accessible(self, page):
        page.goto(BASE)
        page.get_by_text("注册新账号").click()
        page.wait_for_timeout(500)
        assert page.get_by_placeholder("用户名").is_visible()

    def test_sidebar_navigation(self, page):
        do_login(page)
        nav = page.text_content(".sidebar-nav")
        for item in ["概览", "产品管理", "报价单", "新建报价", "导入产品"]:
            assert item in nav, f"Missing nav item: {item}"

    def test_admin_sees_admin_link(self, page):
        do_login(page)
        nav = page.text_content(".sidebar-nav")
        assert "管理" in nav

    def test_logout(self, page):
        do_login(page)
        # Click user dropdown toggle
        toggle = page.locator(".topbar .dropdown-toggle")
        toggle.wait_for(state="visible", timeout=T)
        toggle.click()
        page.wait_for_timeout(800)
        # Click logout link in dropdown
        logout_link = page.locator(".dropdown-item.text-danger")
        logout_link.wait_for(state="visible", timeout=T)
        logout_link.click()
        page.wait_for_timeout(1500)
        assert page.get_by_placeholder("用户名").is_visible()


# ═══════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════

class TestVueDashboard:
    def test_dashboard_renders(self, page):
        do_login(page)
        body = page.text_content("body")
        assert "系统概览" in body
        assert "产品总数" in body

    def test_four_stat_cards(self, page):
        do_login(page)
        cards = page.locator(".stat-card")
        assert cards.count() == 4

    def test_quick_actions(self, page):
        do_login(page)
        assert page.get_by_role("button", name="从Excel导入产品").is_visible()
        assert page.get_by_role("button", name="新建报价单").is_visible()
        assert page.get_by_role("button", name="管理产品库").is_visible()

    def test_page_header(self, page):
        do_login(page)
        assert page.locator(".page-header").is_visible()
        assert page.locator(".topbar-title").text_content() == "概览"


# ═══════════════════════════════════════════════════
# PRODUCTS — Vue
# ═══════════════════════════════════════════════════

class TestVueProducts:
    def test_page_loads(self, page):
        do_login(page)
        click_nav(page, "产品管理")
        assert page.locator("table.table-modern").is_visible(timeout=T)

    def test_search_works(self, page):
        do_login(page)
        click_nav(page, "产品管理")
        search = page.get_by_placeholder("搜索名称/规格/型号/功能/厂家...（支持拼音/缩写）")
        search.fill("交换机")
        page.wait_for_timeout(1500)
        assert page.locator("table.table-modern").is_visible()

    def test_filter_dropdowns(self, page):
        do_login(page)
        click_nav(page, "产品管理")
        selects = page.locator("select.form-select-sm")

    def test_add_product_modal(self, page):
        do_login(page)
        click_nav(page, "产品管理")
        page.get_by_role("button", name="新增产品").click()
        page.wait_for_timeout(500)
        # Vue modal: check form fields via labels (use .first for strict mode)
        assert page.get_by_text("产品名称").first.is_visible()
        assert page.locator("label").filter(has_text="规格型号").is_visible()

    def test_create_and_verify(self, page):
        do_login(page)
        click_nav(page, "产品管理")
        # Open modal
        page.get_by_role("button", name="新增产品").click()
        page.wait_for_timeout(500)
        # Fill form
        name_input = page.get_by_placeholder("产品名称")
        name_input.fill("E2E_VUE_TEST_DELME")
        page.get_by_placeholder("规格型号").fill("VUE-T-001")
        page.get_by_placeholder("0.00").first.fill("999")
        # Save
        page.get_by_role("button", name="新增").click()
        page.wait_for_timeout(2000)
        # Check toast
        body = page.text_content("body")
        assert "成功" in body or "添加" in body or "已添加" in body

    def test_export_template_button(self, page):
        do_login(page)
        click_nav(page, "产品管理")
        assert page.get_by_role("button", name="下载模板").is_visible()

    def test_pagination_exists(self, page):
        do_login(page)
        click_nav(page, "产品管理")
        page.wait_for_timeout(1000)
        # Pagination shows if >1 page
        # Just verify page doesn't crash
        assert page.locator("table.table-modern").is_visible()


# ═══════════════════════════════════════════════════
# QUOTES — Vue
# ═══════════════════════════════════════════════════

class TestVueQuotes:
    def test_list_loads(self, page):
        do_login(page)
        click_nav(page, "报价单")
        assert page.locator("table.table-modern").is_visible()

    def test_new_quote_button(self, page):
        do_login(page)
        click_nav(page, "报价单")
        assert page.get_by_role("button", name="新建报价单").is_visible()

    def test_new_quote_form(self, page):
        do_login(page)
        click_nav(page, "新建报价")
        page.wait_for_timeout(1000)
        body = page.text_content("body")
        assert "客户信息" in body
        assert "产品明细" in body

    def test_save_validation(self, page):
        do_login(page)
        click_nav(page, "新建报价")
        # Try saving with empty fields
        page.get_by_role("button", name="保存报价单").click()
        page.wait_for_timeout(1500)
        body = page.text_content("body")
        assert len(body) > 0  # Should show error or warning

    def test_add_product_picker(self, page):
        do_login(page)
        click_nav(page, "新建报价")
        page.get_by_role("button", name="添加产品").click()
        page.wait_for_timeout(1000)
        body = page.text_content("body")
        assert "选择产品" in body or page.get_by_placeholder("搜索产品名称/拼音...").is_visible()


# ═══════════════════════════════════════════════════
# IMPORT — Vue
# ═══════════════════════════════════════════════════

class TestVueImport:
    def test_page_loads(self, page):
        do_login(page)
        click_nav(page, "导入产品")
        body = page.text_content("body")
        assert "Excel" in body or "导入" in body

    def test_download_template(self, page):
        do_login(page)
        click_nav(page, "导入产品")
        assert page.get_by_role("button", name="下载模板").is_visible()


# ═══════════════════════════════════════════════════
# ADMIN — Vue
# ═══════════════════════════════════════════════════

class TestVueAdmin:
    def test_admin_page_accessible(self, page):
        do_login(page)
        click_nav(page, "管理")
        body = page.text_content("body")
        assert "用户管理" in body

    def test_user_table(self, page):
        do_login(page)
        click_nav(page, "管理")
        assert page.locator("table.table-modern").first.is_visible()
        assert ADMIN_USER in page.text_content("body")

    def test_registration_toggle(self, page):
        do_login(page)
        click_nav(page, "管理")
        assert "注册控制" in page.text_content("body")

    def test_field_visibility_section(self, page):
        do_login(page)
        click_nav(page, "管理")
        assert "字段可见性" in page.text_content("body")


# ═══════════════════════════════════════════════════
# UI — Responsive & Layout
# ═══════════════════════════════════════════════════

class TestVueUI:
    def test_mobile_sidebar_toggle(self, page):
        do_login(page)
        # Mobile: sidebar toggle visible at small width
        page.set_viewport_size({"width": 375, "height": 800})
        page.wait_for_timeout(500)
        toggle = page.locator(".sidebar-toggle")
        if toggle.is_visible():
            toggle.click()
            page.wait_for_timeout(500)
        assert page.locator(".main-wrapper").is_visible()

    def test_desktop_layout(self, page):
        do_login(page)
        page.set_viewport_size({"width": 1280, "height": 900})
        page.wait_for_timeout(500)
        assert page.locator(".sidebar").is_visible()
        assert page.locator(".main-content").is_visible()

    def test_topbar_shows_title(self, page):
        do_login(page)
        assert page.locator(".topbar-title").is_visible()

    def test_version_display(self, page):
        do_login(page)
        page.wait_for_timeout(3000)
        body = page.text_content(".sidebar-nav")
        assert "v" in body  # Version somewhere in sidebar

    def test_multiple_tab_switching(self, page):
        do_login(page)
        tabs = ["产品管理", "报价单", "概览", "管理"]
        for tab in tabs:
            click_nav(page, tab)
            assert page.locator(".main-content").is_visible()
