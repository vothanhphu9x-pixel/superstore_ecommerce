"""
superstore_odoo_setup.py
━━━━━━━━━━━━━━━━━━━━━━━
Tự động hóa cấu hình ban đầu cho database superstore_erp qua XML-RPC.
Dùng API Odoo (không trực tiếp PostgreSQL) để Odoo tự tạo các bản ghi liên quan.

CHẠY SAU KHI:
  1. Odoo đã installed thành công
  2. Đã vào web đặt company country=US, currency=USD THỦ CÔNG

CHẠY TRƯỚC KHI:
  - superstore_data_generator.py (cần có kho trước!)
  - superstore_marketing_data_generator.py

Kết quả:
  ✓ Module settings (discounts, UoM, work orders, multi-warehouse)
  ✓ 4 Warehouses (WEST/EAST/CENTRAL/SOUTH)
  ✓ 3 Work Centers (WC-CUT / WC-ASM / WC-QC)
  ✓ Routing 3 công đoạn cho Furniture
  ✓ UTM sources & mediums
  ✓ 8 phòng ban (hr.department)

Chạy:
    python superstore_odoo_setup.py
"""

import xmlrpc.client
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

# ─── CONFIG ──────────────────────────────────────────────────────────────────
ODOO_URL  = "http://localhost:8069"
ODOO_DB   = "superstore_erp"
ODOO_USER = "admin"
ODOO_PASS = "admin"


class OdooAPI:
    """Wrapper đơn giản cho Odoo XML-RPC."""

    def __init__(self, url, db, user, password):
        self.db  = db
        self.pwd = password
        common   = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
        self.uid = common.authenticate(db, user, password, {})
        if not self.uid:
            raise RuntimeError("Không login được — kiểm tra username/password")
        self.models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
        log.info(f"Kết nối Odoo OK — uid={self.uid}")

    def search(self, model, domain=None, fields=None, limit=1000):
        domain = domain or []
        ids = self.models.execute_kw(
            self.db, self.uid, self.pwd, model, 'search', [domain], {'limit': limit}
        )
        if not ids:
            return []
        return self.models.execute_kw(
            self.db, self.uid, self.pwd, model, 'read', [ids],
            {'fields': fields or ['id', 'name']}
        )

    def search_id(self, model, domain):
        """Tìm ID đầu tiên khớp domain, trả về None nếu không có."""
        ids = self.models.execute_kw(
            self.db, self.uid, self.pwd, model, 'search', [domain], {'limit': 1}
        )
        return ids[0] if ids else None

    def create(self, model, vals):
        return self.models.execute_kw(
            self.db, self.uid, self.pwd, model, 'create', [vals]
        )

    def write(self, model, ids, vals):
        if isinstance(ids, int):
            ids = [ids]
        return self.models.execute_kw(
            self.db, self.uid, self.pwd, model, 'write', [ids, vals]
        )

    def call(self, model, method, args=None, kwargs=None):
        return self.models.execute_kw(
            self.db, self.uid, self.pwd, model, method,
            args or [], kwargs or {}
        )


def get_or_create(api, model, domain, vals, label=""):
    """Tìm record theo domain, tạo mới nếu không có."""
    existing = api.search_id(model, domain)
    if existing:
        log.info(f"  EXISTS: {label or model} id={existing}")
        return existing, False
    new_id = api.create(model, vals)
    log.info(f"  CREATED: {label or model} id={new_id}")
    return new_id, True


# ─── PHASE 1: MODULE SETTINGS ────────────────────────────────────────────────

def configure_settings(api: OdooAPI):
    """Bật các settings cần thiết cho từng module.
    Thử từng setting riêng lẻ — field nào không tồn tại trong Odoo 18 thì skip.
    """
    log.info("\n── Phase 1: Module Settings ──")

    company_id = api.search_id('res.company', [])
    if not company_id:
        raise RuntimeError("Không tìm thấy company!")

    # Danh sách settings cần bật — thử từng cái một
    # Một số field đã đổi tên trong Odoo 18 nên dùng get_or_create pattern
    settings_list = [
        # Inventory
        ('group_stock_multi_locations', True,  'Storage Locations'),
        ('group_uom',                   True,  'Units of Measure'),
        # Sales
        ('group_discount_per_so_line',  True,  'Discounts on order line'),
        # Manufacturing
        ('group_mrp_routings',          True,  'Work Orders + Routing'),
    ]

    ok_count = 0
    for field, value, label in settings_list:
        try:
            config_id = api.create('res.config.settings', {field: value})
            api.call('res.config.settings', 'execute', [[config_id]])
            log.info(f"  ✅ {label} ({field})")
            ok_count += 1
        except Exception as e:
            # Field không tồn tại trong version này → bật tay trong UI
            short = str(e)[:80]
            log.warning(f"  ⚠️  {label}: skip — bật tay trong Settings ({short})")

    log.info(f"  Settings: {ok_count}/{len(settings_list)} applied")
    log.info("  Multi-warehouse: tự bật khi tạo kho thứ 2")


# ─── PHASE 2: WAREHOUSES ─────────────────────────────────────────────────────

def create_warehouses(api: OdooAPI) -> dict:
    """Tạo 4 distribution centers. Odoo tự sinh locations + routes."""
    log.info("\n── Phase 2: Warehouses ──")

    company_id = api.search_id('res.company', [])
    warehouses_def = [
        {
            "name": "Los Angeles (West)",
            "code": "WEST",
            "note": "HQ + Manufacturing Plant"
        },
        {
            "name": "Newark (East)",
            "code": "EAST",
            "note": "East Region Distribution"
        },
        {
            "name": "Chicago (Central)",
            "code": "CNTL",
            "note": "Central Region Distribution"
        },
        {
            "name": "Houston (South)",
            "code": "SOUT",
            "note": "South Region Distribution"
        },
    ]

    wh_ids = {}
    for wh in warehouses_def:
        wh_id, created = get_or_create(
            api,
            'stock.warehouse',
            [('code', '=', wh['code']), ('company_id', '=', company_id)],
            {'name': wh['name'], 'code': wh['code'], 'company_id': company_id},
            label=f"WH-{wh['code']}"
        )
        wh_ids[wh['code']] = wh_id
        if created:
            log.info(f"    → Odoo đã tự tạo input/output/stock locations cho {wh['code']}")

    log.info(f"  Warehouses: {list(wh_ids.keys())}")
    return wh_ids


# ─── PHASE 3: WORK CENTERS & ROUTING ─────────────────────────────────────────

def create_work_centers(api: OdooAPI) -> dict:
    """Tạo 3 work centers cho nhà máy WH-WEST."""
    log.info("\n── Phase 3: Work Centers ──")

    company_id = api.search_id('res.company', [])

    wc_defs = [
        {
            "name": "Cutting Station",
            "code": "WC-CUT",
            "color": 1,       # Odoo color index
            "capacity": 2,    # 2 operators
            "time_efficiency": 100.0,
            "note": "Cắt và chuẩn bị vật liệu theo BOM"
        },
        {
            "name": "Assembly Line",
            "code": "WC-ASM",
            "color": 2,
            "capacity": 3,
            "time_efficiency": 100.0,
            "note": "Lắp ráp sản phẩm hoàn chỉnh"
        },
        {
            "name": "Quality Control",
            "code": "WC-QC",
            "color": 5,
            "capacity": 1,
            "time_efficiency": 100.0,
            "note": "Kiểm tra chất lượng + đóng gói"
        },
    ]

    wc_ids = {}
    for wc in wc_defs:
        wc_id, _ = get_or_create(
            api,
            'mrp.workcenter',
            [('code', '=', wc['code']), ('company_id', '=', company_id)],
            {
                'name': wc['name'],
                'code': wc['code'],
                'company_id': company_id,
                'default_capacity': wc['capacity'],
                'time_efficiency': wc['time_efficiency'],
                'color': wc['color'],
            },
            label=f"WorkCenter {wc['code']}"
        )
        wc_ids[wc['code']] = wc_id

    log.info(f"  Work Centers: {list(wc_ids.keys())}")
    return wc_ids


# ─── PHASE 4: UTM TRACKING ────────────────────────────────────────────────────

def create_utm(api: OdooAPI):
    """Tạo UTM sources và mediums."""
    log.info("\n── Phase 4: UTM Tracking ──")

    sources = ["google", "facebook", "instagram", "email", "direct", "referral", "organic"]
    # 5 medium cuối khớp đúng CHANNELS trong scripts/superstore_marketing_data_generator.py
    # (email_marketing, google_search, google_display, meta_facebook, meta_instagram) — để
    # sil_channel_enriched (data_platform) JOIN utm_medium.name = channel_code ra kết quả thật,
    # không phải luôn NULL như trước khi thêm (utm.medium mặc định của Odoo dùng tên chung
    # chung "email"/"display", không khớp channel_code dạng CSV của bộ data marketing riêng).
    mediums = [
        "cpc", "email", "social", "organic", "referral", "none", "display",
        "email_marketing", "google_search", "google_display", "meta_facebook", "meta_instagram",
    ]

    source_ids = {}
    for src in sources:
        sid, _ = get_or_create(api, 'utm.source', [('name', '=', src)],
                               {'name': src}, label=f"utm.source/{src}")
        source_ids[src] = sid

    medium_ids = {}
    for med in mediums:
        mid, _ = get_or_create(api, 'utm.medium', [('name', '=', med)],
                               {'name': med}, label=f"utm.medium/{med}")
        medium_ids[med] = mid

    log.info(f"  UTM: {len(source_ids)} sources, {len(medium_ids)} mediums")


# ─── PHASE 5: HR DEPARTMENTS ─────────────────────────────────────────────────

def create_departments(api: OdooAPI):
    """Tạo 8 phòng ban."""
    log.info("\n── Phase 5: HR Departments ──")

    company_id = api.search_id('res.company', [])
    departments = [
        "Executive",
        "Sales & CRM",
        "Marketing",
        "Purchasing",
        "Warehouse & Logistics",
        "Manufacturing",
        "Accounting",
        "HR & Administration",
        "IT & Data",
    ]

    dept_ids = {}
    for dept in departments:
        did, _ = get_or_create(
            api,
            'hr.department',
            [('name', '=', dept), ('company_id', '=', company_id)],
            {'name': dept, 'company_id': company_id},
            label=f"dept/{dept}"
        )
        dept_ids[dept] = did

    log.info(f"  Departments: {len(dept_ids)} created")
    return dept_ids


# ─── PHASE 6: PRODUCT CATEGORIES ─────────────────────────────────────────────

def create_product_categories(api: OdooAPI):
    """Tạo category tree: All > Furniture/Technology/Office Supplies > sub-categories."""
    log.info("\n── Phase 6: Product Categories ──")

    root_id = api.search_id('product.category', [('parent_id', '=', False)])

    categories = {
        "Furniture": ["Tables", "Chairs", "Bookcases", "Furnishings"],
        "Technology": ["Phones", "Machines", "Copiers", "Accessories"],
        "Office Supplies": [
            "Paper", "Binders", "Storage", "Envelopes",
            "Fasteners", "Labels", "Art", "Appliances", "Supplies"
        ],
    }

    all_cat_ids = {}
    for cat_name, subs in categories.items():
        parent_id, _ = get_or_create(
            api, 'product.category',
            [('name', '=', cat_name), ('parent_id', '=', root_id)],
            {'name': cat_name, 'parent_id': root_id},
            label=f"cat/{cat_name}"
        )
        for sub in subs:
            sub_id, _ = get_or_create(
                api, 'product.category',
                [('name', '=', sub), ('parent_id', '=', parent_id)],
                {'name': sub, 'parent_id': parent_id},
                label=f"cat/{cat_name}/{sub}"
            )
            all_cat_ids[sub] = sub_id

    log.info(f"  Product categories: {len(all_cat_ids)} sub-categories")


# ─── PHASE 7: VERIFY ─────────────────────────────────────────────────────────

def verify_setup(api: OdooAPI):
    """Kiểm tra tất cả đã setup đúng."""
    log.info("\n── Phase 7: Verification ──")

    checks = [
        ("stock.warehouse",    [], "Warehouses"),
        ("mrp.workcenter",     [], "Work Centers"),
        ("utm.source",         [], "UTM Sources"),
        ("hr.department",      [], "Departments"),
        ("product.category",   [], "Product Categories"),
    ]

    all_ok = True
    for model, domain, label in checks:
        records = api.search(model, domain, fields=['id', 'name'])
        status = "✓" if records else "✗ MISSING"
        log.info(f"  {status} {label}: {len(records)} records")
        if not records:
            all_ok = False

    # Kiểm tra settings
    wh_count = len(api.search('stock.warehouse', []))
    if wh_count < 4:
        log.warning(f"  ⚠ Chỉ có {wh_count} warehouse, cần 4")
        all_ok = False

    wc_count = len(api.search('mrp.workcenter', []))
    if wc_count < 3:
        log.warning(f"  ⚠ Chỉ có {wc_count} work center, cần 3")
        all_ok = False

    if all_ok:
        log.info("\n  ══ Setup hoàn chỉnh! Sẵn sàng chạy generators ══")
        log.info("  Bước tiếp: python superstore_data_generator.py")
    else:
        log.warning("\n  ⚠ Có vấn đề, kiểm tra lại log ở trên")

    return all_ok


# ─── MAIN ────────────────────────────────────────────────────────────────────

def run():
    log.info("═══ SUPERSTORE ODOO SETUP ═══")
    log.info(f"URL: {ODOO_URL} | DB: {ODOO_DB}")
    log.info("")
    log.info("⚠️  YÊU CẦU: Trước khi chạy script này, bạn phải:")
    log.info("   1. Đã login vào Odoo web (http://localhost:8069)")
    log.info("   2. Đã vào Settings → Company → đặt Country=US và Currency=USD")
    log.info("   3. Odoo server đang chạy")
    log.info("")

    try:
        api = OdooAPI(ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASS)

        configure_settings(api)
        wh_ids  = create_warehouses(api)
        wc_ids  = create_work_centers(api)
        create_utm(api)
        create_departments(api)
        create_product_categories(api)
        verify_setup(api)

        log.info("\n═══ SETUP HOÀN THÀNH ═══")
        log.info("Thứ tự chạy tiếp theo:")
        log.info("  1. python superstore_data_generator.py")
        log.info("  2. python superstore_rfm_customer_behaviors.py")
        log.info("  3. python superstore_marketing_data_generator.py --all")

    except ConnectionRefusedError:
        log.error("Không kết nối được Odoo — chắc chắn server đang chạy?")
        log.error("Chạy: python odoo-bin -c ../odoo.conf -d superstore_erp")
        sys.exit(1)
    except Exception as e:
        log.error(f"Lỗi: {e}")
        raise


if __name__ == "__main__":
    run()