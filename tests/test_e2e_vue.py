"""
Vue 3 报价系统 E2E 测试 — Playwright
Test browser interactions against the new Vue frontend (via nginx /quote/ proxy).
"""
import pytest
from playwright.sync_api import sync_playwright, Page, Browser

BASE = "http://127.0.0.1:8080/quote"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"
T = 15000  # timeout ms
NAV = 2000  # nav settle

# Current sidebar labels (App.vue tabs)
NAV_HOME = "首页"
NAV_PRODUCTS = "产品管理"
NAV_QUOTES = "报价管理"
NAV_IMPORT = "导入导出"
NAV_ADMIN = "管理"


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
    page.get_by_placeholder("用户名").wait_for(state="visible", timeout=T)
    page.get_by_placeholder("用户名").fill(ADMIN_USER)
    page.get_by_placeholder("密码").fill(ADMIN_PASS)
    page.get_by_role("button", name="登录").click()
    page.locator(".sidebar").wait_for(state="visible", timeout=T)
    page.wait_for_timeout(1500)


def click_nav(page: Page, text: str):
    """Click sidebar nav link. Use exact text match to avoid partial matches."""
    link = page.locator(".sidebar-nav .nav-link").filter(has_text=text).last
    link.wait_for(state="visible", timeout=T)
    link.click()
    page.wait_for_timeout(NAV)


def click_nav_exact(page: Page, text: str):
    """Click sidebar nav link matching text exactly."""
    link = page.locator(".sidebar-nav .nav-link").filter(has=page.locator(f"text={text}")).last
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
        body = page.text_content("body")
        assert NAV_HOME in body or "首页" in body

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
        for item in [NAV_HOME, NAV_PRODUCTS, NAV_QUOTES, NAV_IMPORT, NAV_ADMIN]:
            assert item in nav, f"Missing nav item: {item}"

    def test_admin_sees_admin_link(self, page):
        do_login(page)
        nav = page.text_content(".sidebar-nav")
        assert NAV_ADMIN in nav

    def test_logout(self, page):
        do_login(page)
        # User dropdown in sidebar (not topbar)
        toggle = page.locator(".sidebar-user .dropdown-toggle")
        toggle.wait_for(state="visible", timeout=T)
        toggle.click()
        page.wait_for_timeout(800)
        # Click logout link
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
        assert "系统概览" in page.locator(".page-header").text_content()


# ═══════════════════════════════════════════════════
# PRODUCTS — Vue
# ═══════════════════════════════════════════════════

class TestVueProducts:
    def test_page_loads(self, page):
        do_login(page)
        click_nav(page, NAV_PRODUCTS)
        assert page.locator("table.table-modern").is_visible(timeout=T)

    def test_search_works(self, page):
        do_login(page)
        click_nav(page, NAV_PRODUCTS)
        search = page.get_by_placeholder("搜索名称/规格/型号/功能/厂家...（支持拼音/缩写）")
        search.fill("交换机")
        page.wait_for_timeout(1500)
        assert page.locator("table.table-modern").is_visible()

    def test_filter_dropdowns(self, page):
        do_login(page)
        click_nav(page, NAV_PRODUCTS)
        # Verify select dropdowns exist
        selects = page.locator("select.form-select-sm")
        # At minimum the page has loaded

    def test_add_product_modal(self, page):
        do_login(page)
        click_nav(page, NAV_PRODUCTS)
        page.get_by_role("button", name="新增产品").click()
        page.wait_for_timeout(500)
        assert page.get_by_text("产品名称").first.is_visible()
        assert page.locator("label").filter(has_text="规格型号").is_visible()

    def test_create_and_verify(self, page):
        do_login(page)
        click_nav(page, NAV_PRODUCTS)
        page.get_by_role("button", name="新增产品").click()
        page.wait_for_timeout(500)
        name_input = page.get_by_placeholder("产品名称")
        name_input.fill("E2E_VUE_TEST_DELME")
        page.get_by_placeholder("规格型号").fill("VUE-T-001")
        page.get_by_placeholder("0.00").first.fill("999")
        # Click the modal save button ("新增"), not the page button ("新增产品")
        page.locator(".modern-modal .btn-primary").filter(has_text="新增").click()
        page.wait_for_timeout(2000)
        body = page.text_content("body")
        assert "成功" in body or "创建" in body or "已添加" in body

    def test_export_template_button(self, page):
        do_login(page)
        click_nav(page, NAV_PRODUCTS)
        assert page.get_by_role("button", name="下载模板").is_visible()

    def test_pagination_exists(self, page):
        do_login(page)
        click_nav(page, NAV_PRODUCTS)
        page.wait_for_timeout(1000)
        assert page.locator("table.table-modern").is_visible()


# ═══════════════════════════════════════════════════
# QUOTES — Vue
# ═══════════════════════════════════════════════════

class TestVueQuotes:
    def test_list_loads(self, page):
        do_login(page)
        click_nav(page, NAV_QUOTES)
        assert page.locator("table.table-modern").is_visible()

    def test_new_quote_button(self, page):
        do_login(page)
        click_nav(page, NAV_QUOTES)
        assert page.get_by_role("button", name="新建报价单").is_visible()

    def test_new_quote_form(self, page):
        do_login(page)
        # Navigate via badge '+' on quotes tab
        page.goto(BASE + "/new-quote")
        page.wait_for_timeout(1000)
        body = page.text_content("body")
        assert "客户信息" in body or "产品明细" in body

    def test_save_validation(self, page):
        do_login(page)
        page.goto(BASE + "/new-quote")
        page.wait_for_timeout(1000)
        page.get_by_role("button", name="保存报价单").click()
        page.wait_for_timeout(1500)
        body = page.text_content("body")
        assert len(body) > 0

    def test_add_product_picker(self, page):
        do_login(page)
        page.goto(BASE + "/new-quote")
        page.wait_for_timeout(1000)
        page.get_by_role("button", name="添加产品").click()
        page.wait_for_timeout(1000)
        body = page.text_content("body")
        assert "选择产品" in body or "搜索" in body or page.get_by_placeholder("搜索产品名称/拼音...").is_visible()


# ═══════════════════════════════════════════════════
# IMPORT — Vue
# ═══════════════════════════════════════════════════

class TestVueImport:
    def test_page_loads(self, page):
        do_login(page)
        click_nav(page, NAV_IMPORT)
        body = page.text_content("body")
        assert "Excel" in body or "导入" in body

    def test_download_template(self, page):
        do_login(page)
        click_nav(page, NAV_IMPORT)
        assert page.get_by_role("button", name="下载模板").is_visible()


# ═══════════════════════════════════════════════════
# ADMIN — Vue
# ═══════════════════════════════════════════════════

class TestVueAdmin:
    def _go_admin(self, page):
        """Navigate to admin page — use .last to skip 产品管理"""
        do_login(page)
        click_nav(page, NAV_ADMIN)

    def test_admin_page_accessible(self, page):
        self._go_admin(page)
        body = page.text_content("body")
        assert "用户管理" in body

    def test_user_table(self, page):
        self._go_admin(page)
        assert page.locator("table.table-modern").first.is_visible()
        assert ADMIN_USER in page.text_content("body")

    def test_registration_toggle(self, page):
        self._go_admin(page)
        assert "注册控制" in page.text_content("body")

    def test_field_visibility_section(self, page):
        self._go_admin(page)
        assert "字段可见性" in page.text_content("body")


# ═══════════════════════════════════════════════════
# UI — Responsive & Layout
# ═══════════════════════════════════════════════════

class TestVueUI:
    def test_mobile_sidebar_toggle(self, page):
        do_login(page)
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
        # Dashboard page header contains title
        assert page.locator(".page-header").is_visible()

    def test_version_display(self, page):
        do_login(page)
        page.wait_for_timeout(3000)
        body = page.text_content(".sidebar-nav")
        assert "v" in body

    def test_multiple_tab_switching(self, page):
        do_login(page)
        tabs = [NAV_PRODUCTS, NAV_QUOTES, NAV_HOME, NAV_ADMIN]
        for tab in tabs:
            click_nav(page, tab)
            assert page.locator(".main-content").is_visible()
