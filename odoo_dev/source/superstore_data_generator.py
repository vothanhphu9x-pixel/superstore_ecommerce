"""
superstore_data_generator
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Generator hoàn chỉnh theo đúng quy trình nghiệp vụ Odoo:

  Phase 0 — Prerequisites  : Raw materials + BOMs tự động
  Phase 1 — SQL Master     : UTM, Products, Partners, Employees
  Phase 2 — O2C (XML-RPC)  : SO → confirm → deliver → invoice → pay
  Phase 3 — P2P (XML-RPC)  : PO → confirm → receipt → bill → pay
  Phase 4 — MFG (XML-RPC)  : BOM → MO → Work Orders → validate
  Phase 5 — Verify         : Kiểm chứng toàn bộ data

Yêu cầu:
  - Odoo server ĐANG CHẠY
  - superstore_odoo_setup.py đã chạy (có warehouses + work centers)
  - pip install psycopg2-binary faker numpy

Chạy:
  python superstore_data_generator.py
  python superstore_data_generator.py --repair-crm  # chỉ repair CRM/SO cũ, không sinh thêm data
  cd odoo_dev && make -f makefile repair-mart-data  # bổ sung UTM/carrier qua local ORM
"""

import csv
from pathlib import Path

import psycopg2, psycopg2.extras, xmlrpc.client
try:
    from faker import Faker
except ModuleNotFoundError:  # Odoo runtime tối giản vẫn chạy được repair-only.
    Faker = None
try:
    import numpy as np
except ModuleNotFoundError:  # Full generator sẽ báo lỗi rõ ở run().
    np = None
import os
import random, logging, time, sys
from datetime import datetime, timedelta, date

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler(),
              logging.FileHandler('generator.log', encoding='utf-8')]
)
log = logging.getLogger(__name__)

# ─── CONFIG ──────────────────────────────────────────────────────────────────
ODOO_URL  = os.getenv("ODOO_URL", "http://localhost:8069")
ODOO_DB   = os.getenv("ODOO_DB", "superstore_erp")
ODOO_USER = os.getenv("ODOO_USER", "admin")
ODOO_PASS = os.getenv("ODOO_PASSWORD", "admin")
DB_CFG    = dict(
    dbname=os.getenv("PGDATABASE", "superstore_erp"),
    user=os.getenv("PGUSER", "odoo"),
    password=os.getenv("PGPASSWORD") or None,
    host=os.getenv("PGHOST", "localhost"),
    port=int(os.getenv("PGPORT", "5432")),
)

CFG = {
    "n_customers"   : 2000,
    "n_suppliers"   : 20,
    "n_products"    : 450,
    "n_employees"   : 45,
    "n_orders"      : 10000,
    "start"         : date(2023, 1, 1),
    "end"           : date(2026, 12, 31),
    # Imperfections
    "cancel_rate"   : 0.03,
    "overdue_b2b"   : 0.10,
    "missing_zip"   : 0.02,
    "missing_phone" : 0.03,   # % khách hàng thiếu SĐT
    "dup_customer"  : 0.01,
    "late_delivery" : 0.08,   # % pickings/receipts trễ hẹn (scheduled_date vs date_done)
    # P2P/MFG demand-driven replenishment (Phase 3/4 chạy SAU Phase 2, bù đắp đúng lượng đã bán)
    "opening_stock_min": 15,  # tồn kho đầu kỳ/SKU/kho khu vực (~4 tuần tiêu thụ ước tính)
    "opening_stock_max": 40,
    "replenish_cover_ratio": 1.05,  # nhập bù = 105% lượng đã bán tháng đó (buffer 5%)
    # Batch sizes
    "b_so"          : 30,
    "b_confirm"     : 100,
    "b_validate"    : 50,
    "b_invoice"     : 50,
    "b_post"        : 100,
}

fake = Faker("en_US") if Faker else None
random.seed(2024)
if np is not None:
    np.random.seed(2024)

# ─── SEED DATA ────────────────────────────────────────────────────────────────
REGIONS = {
    "West"   : ["CA","OR","WA","NV","AZ","CO","NM","UT"],
    "East"   : ["NY","NJ","PA","MA","CT","MD","DE","VA"],
    "Central": ["IL","OH","MI","IN","WI","MN","MO","KS"],
    "South"  : ["TX","FL","GA","NC","SC","TN","AL","MS"],
}
REGION_WH   = {"West":"WEST","East":"EAST","Central":"CNTL","South":"SOUT"}
REG_W       = [0.30, 0.25, 0.25, 0.20]
# Late-delivery lệch hẳn về kho Central (đội vận chuyển/nhân lực kém hơn 3 kho còn lại) —
# thay vì tỉ lệ đều CFG["late_delivery"] cho mọi kho như trước.
LATE_DELIVERY_WH_MULT = {"CNTL": 2.5}
def late_delivery_rate(wh_code):
    return CFG["late_delivery"] * LATE_DELIVERY_WH_MULT.get(wh_code, 0.7)
SEGMENTS    = ["Consumer","Corporate","Home Office"]
SEG_W       = [0.50, 0.33, 0.17]
CATEGORIES  = {
    "Furniture"      : {"sub":["Tables","Chairs","Bookcases","Furnishings"],"margin":0.30,"mfg":True},
    "Technology"     : {"sub":["Phones","Machines","Copiers","Accessories"],"margin":0.25,"mfg":False},
    "Office Supplies": {"sub":["Paper","Binders","Storage","Envelopes","Fasteners",
                               "Labels","Art","Appliances","Supplies"],"margin":0.35,"mfg":False},
}
SHIP_W      = [0.04, 0.16, 0.20, 0.60]
UTM_SRC     = ["google","facebook","instagram","email","direct","referral","organic"]
UTM_MED     = ["cpc","email","social","organic","referral","none"]
CAMP_TYPES  = ["back-to-school","year-end-promo","new-year-sale","spring-office-refresh",
               "summer-deals","black-friday","corporate-outreach","email-newsletter"]
SUPP_NAMES  = [
    "Office Pro Supply Co","TechWorld Distributors","Premier Furniture Materials LLC",
    "Pacific Paper & Print","AllTech Electronics Inc","National Binder Group",
    "Western Wood Supply","Steel Frame Solutions","EastCoast Office Systems",
    "QuickShip Supplies","ProTech Components","Cardinal Business Products",
    "Atlas Storage Systems","Precision Metal Works","Continental Label Co",
    "Digital Accessories Direct","Midwest Foam & Fabric","Copier Source America",
    "Speedy Print Solutions","United Hardware Supply",
]
# Chức danh theo phòng ban: 1 "lead" (trưởng/quản lý) + phần còn lại random từ "staff"
JOB_TITLES = {
    "Sales & CRM"          : {"lead":"Sales Manager","staff":["Sales Representative","Account Executive","Inside Sales Rep"]},
    "Marketing"            : {"lead":"Marketing Manager","staff":["Marketing Specialist","Content Marketing Associate"]},
    "Purchasing"           : {"lead":"Purchasing Manager","staff":["Buyer","Procurement Analyst"]},
    "Warehouse & Logistics": {"lead":"Warehouse Supervisor","staff":["Warehouse Associate","Logistics Coordinator","Forklift Operator"]},
    "Manufacturing"        : {"lead":"Production Supervisor","staff":["Production Worker","Machine Operator","Quality Inspector"]},
    "Accounting"           : {"lead":"Accounting Manager","staff":["Staff Accountant","Accounts Payable Clerk"]},
    "HR & Administration"  : {"lead":"HR Manager","staff":["HR Generalist","Office Administrator"]},
    "IT & Data"            : {"lead":"IT Manager","staff":["Data Analyst","IT Support Specialist"]},
    "Executive"            : {"lead":"Chief Executive Officer","staff":["Chief Operating Officer","Chief Financial Officer"]},
}
# Raw materials cho Furniture manufacturing
RAW_MATERIALS = [
    ("Tabletop Panel",    "RM-WOOD-001", 45.0),
    ("Steel Frame Set",   "RM-STEEL-001", 38.0),
    ("Hardware Kit",      "RM-HW-001",   12.0),
    ("Edge Banding Strip","RM-EDGE-001",  5.0),
    ("Packaging Box",     "RM-PKG-001",   3.5),
    ("Seat Cushion",      "RM-FOAM-001", 28.0),
    ("Backrest Frame",    "RM-BF-001",   22.0),
    ("Pneumatic Cylinder","RM-CYL-001",  18.0),
    ("Upholstery Fabric", "RM-FABR-001",  9.0),
    ("Shelf Board",       "RM-SHF-001",  15.0),
    ("Side Panel",        "RM-SIDE-001", 20.0),
]

# Các channel dưới đây là business code dùng xuyên suốt CSV marketing -> Odoo UTM
# -> dim_channel. Không dùng medium mặc định kiểu "Email"/"Social" vì chúng không
# khớp key snake_case của dữ liệu marketing ngoài Odoo.
PAID_CHANNEL_SOURCE = {
    "email_marketing": "email",
    "google_search": "google",
    "google_display": "google",
    "meta_facebook": "facebook",
    "meta_instagram": "instagram",
}
NON_CAMPAIGN_CHANNEL_SOURCE = {
    "direct": "direct",
    "organic": "organic",
    "referral": "referral",
}
DELIVERY_MODES = (
    ("Same Day", 4, 35.0),
    ("First Class", 16, 20.0),
    ("Second Class", 20, 10.0),
    ("Standard Class", 60, 5.0),
)
MARKETING_CAMPAIGN_MASTER = (
    Path(__file__).resolve().parents[1]
    / "CRM_Marketing_source"
    / "marketing_campaigns_master.csv"
)
MARKETING_AD_DAILY = (
    Path(__file__).resolve().parents[1]
    / "CRM_Marketing_source"
    / "ad_performance_daily.csv"
)

# ─── CONNECTIONS ─────────────────────────────────────────────────────────────
class OdooAPI:
    def __init__(self):
        c = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
        self.uid = c.authenticate(ODOO_DB, ODOO_USER, ODOO_PASS, {})
        if not self.uid: raise RuntimeError("Odoo login thất bại")
        self.m = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
        log.info(f"Odoo XML-RPC OK uid={self.uid}")

    def _x(self, model, method, args=None, kw=None):
        return self.m.execute_kw(ODOO_DB, self.uid, ODOO_PASS,
                                 model, method, args or [], kw or {})
    def create(self, m, v):      return self._x(m, 'create', [v])
    def write(self, m, ids, v):  return self._x(m, 'write', [ids, v])
    def call(self, m, mth, ids, kw=None): return self._x(m, mth, [ids], kw or {})
    def search(self, m, d, limit=5000):   return self._x(m,'search',[d],{'limit':limit})
    def read(self, m, ids, f):   return self._x(m, 'read', [ids], {'fields': f})
    def sid(self, m, d):
        r = self._x(m, 'search', [d], {'limit': 1})
        return r[0] if r else None

class PG:
    def __init__(self):
        self.conn = psycopg2.connect(**DB_CFG)
        self.conn.autocommit = False
        self.cur  = self.conn.cursor()
    def q(self,s,p=None):    self.cur.execute(s,p); return self.cur
    def one(self,s,p=None):  self.cur.execute(s,p); return self.cur.fetchone()
    def all(self,s,p=None):  self.cur.execute(s,p); return self.cur.fetchall()
    def many(self,s,d):      psycopg2.extras.execute_values(self.cur,s,d,page_size=500)
    def commit(self):        self.conn.commit()
    def rollback(self):      self.conn.rollback()
    def close(self):         self.cur.close(); self.conn.close()

def batches(lst, n):
    for i in range(0, len(lst), n): yield lst[i:i+n]

def jitter(v, p=0.10): return v*(1+random.uniform(-p,p))

def seasonal_w(d):
    return {1:.55,2:.60,3:.80,4:.85,5:.90,6:.88,
            7:.92,8:1.35,9:1.40,10:1.10,11:1.50,12:1.45}.get(d.month,1.0)

def gen_dates(n, s, e):
    days = [s+timedelta(d) for d in range((e-s).days+1)]
    wts  = [seasonal_w(d)*(0 if d.weekday()>=5 else 1) for d in days]
    tot  = sum(wts); wts = [w/tot for w in wts]
    return [days[i] for i in np.random.choice(len(days),size=n,replace=True,p=wts)]

# ─── CONTEXT ─────────────────────────────────────────────────────────────────
def load_context(pg, api) -> dict:
    ctx = {}
    ctx["cid"] = pg.one("SELECT id FROM res_company LIMIT 1")[0]
    r = pg.one("SELECT id FROM res_currency WHERE name='USD'")
    ctx["cur"] = r[0] if r else 1
    r = pg.one("SELECT id FROM res_users WHERE login='admin'")
    ctx["uid"] = r[0] if r else 2
    r = pg.one("SELECT id FROM res_country WHERE code='US'")
    ctx["us"]  = r[0] if r else 233
    whs = pg.all("SELECT code,id FROM stock_warehouse WHERE active=true")
    ctx["wh"]  = {r[0]:r[1] for r in whs}
    jnls = pg.all("SELECT type,id FROM account_journal WHERE company_id=%s",[ctx["cid"]])
    ctx["jnl"] = {r[0]:r[1] for r in jnls}
    # Work centers
    wcs = pg.all("SELECT code,id FROM mrp_workcenter WHERE active=true AND company_id=%s",[ctx["cid"]])
    ctx["wc"]  = {r[0]:r[1] for r in wcs}
    # Locations
    locs = pg.all("""SELECT usage,id FROM stock_location
                     WHERE active=true AND usage IN ('internal','customer','supplier','production')
                     AND (company_id=%s OR company_id IS NULL) LIMIT 30""",[ctx["cid"]])
    ctx["loc"] = {}
    for u,i in locs:
        if u not in ctx["loc"]: ctx["loc"][u] = i
    log.info(f"Context: cid={ctx['cid']} wh={list(ctx['wh'].keys())} wc={list(ctx['wc'].keys())}")
    return ctx

# ─── PHASE 0: PREREQUISITES ──────────────────────────────────────────────────
def p0_raw_materials(pg, api, ctx) -> dict:
    """Tạo raw material products cho manufacturing."""
    log.info("Phase 0.1 — Raw Materials")
    now = datetime.now()
    cid,uid = ctx["cid"],ctx["uid"]
    # Category cho raw materials
    root = pg.one("SELECT id FROM product_category WHERE parent_id IS NULL LIMIT 1")
    r = pg.one("SELECT id FROM product_category WHERE name=%s AND parent_id=%s",['Raw Materials',root[0]])
    if r: rm_cat = r[0]
    else:
        pg.q("INSERT INTO product_category(name,parent_id,create_uid,write_uid,create_date,write_date)"
             " VALUES('Raw Materials',%s,%s,%s,%s,%s) RETURNING id",[root[0],uid,uid,now,now])
        rm_cat = pg.cur.fetchone()[0]
    pg.commit()

    rm_ids = {}
    cost_map = {}   # tmpl_id → cost (set qua XML-RPC sau)

    for name, sku, cost in RAW_MATERIALS:
        r = pg.one("SELECT pp.id, pp.product_tmpl_id FROM product_product pp"
                   " WHERE pp.default_code=%s LIMIT 1",[sku])
        if r:
            rm_ids[sku] = r[0]
            cost_map[r[1]] = cost
            continue
        # Odoo 18: standard_price là company_dependent field → KHÔNG có cột trong product_template
        # Phải set qua XML-RPC sau khi INSERT
        pg.q("""INSERT INTO product_template
                (name,type,is_storable,service_tracking,tracking,purchase_line_warn,sale_line_warn,
                 categ_id,list_price,company_id,uom_id,uom_po_id,
                 invoice_policy,purchase_ok,sale_ok,active,
                 create_uid,write_uid,create_date,write_date)
                VALUES(%s,'consu',true,'no','none','no-message','no-message',
                       %s,%s,%s,1,1,'order',true,false,true,%s,%s,%s,%s)
                RETURNING id""",
             [psycopg2.extras.Json({'en_US': name}),rm_cat,round(cost*1.2,2),cid,uid,uid,now,now])
        tid = pg.cur.fetchone()[0]
        cost_map[tid] = cost
        pg.q("INSERT INTO product_product(product_tmpl_id,default_code,active,create_uid,write_uid,create_date,write_date)"
             " VALUES(%s,%s,true,%s,%s,%s,%s) RETURNING id",[tid,sku,uid,uid,now,now])
        rm_ids[sku] = pg.cur.fetchone()[0]

    pg.commit()

    # Set standard_price qua XML-RPC (xử lý company_dependent đúng cách)
    log.info(f"  Setting cost prices via XML-RPC ({len(cost_map)} products)...")
    for tid, cost in cost_map.items():
        try:
            api.write('product.template', [tid], {'standard_price': cost})
        except Exception as e:
            log.warning(f"  standard_price set failed tmpl {tid}: {e}")

    log.info(f"  {len(rm_ids)} raw materials ready")
    return rm_ids


def p0_create_boms(pg, api, ctx, rm_ids) -> list:
    """Tạo BOMs cho Furniture products với routing operations."""
    log.info("Phase 0.2 — Bills of Materials + Routing")

    wc = ctx.get("wc", {})
    wc_cut = wc.get("WC-CUT")
    wc_asm = wc.get("WC-ASM")
    wc_qc  = wc.get("WC-QC")

    if not wc_cut or not wc_asm or not wc_qc:
        log.warning("  Work Centers chưa có — bỏ qua BOM creation. Chạy superstore_odoo_setup.py trước!")
        return []

    # Furniture products (Tables, Chairs, Bookcases, Furnishings)
    furniture_prods = pg.all("""
        SELECT DISTINCT pt.id AS tmpl_id, pt.name->>'en_US' AS name
        FROM product_template pt
        JOIN product_category pc ON pc.id = pt.categ_id
        JOIN product_category pcp ON pcp.id = pc.parent_id
        WHERE pcp.name = 'Furniture' AND pt.active = true
        LIMIT 20
    """)

    if not furniture_prods:
        log.warning("  Không tìm thấy Furniture products — chạy Phase 1 trước")
        return []

    # BOM templates per product type
    BOM_TEMPLATES = {
        "Table" : [("RM-WOOD-001",1),("RM-STEEL-001",1),("RM-HW-001",1),("RM-EDGE-001",3.5),("RM-PKG-001",1)],
        "Chair" : [("RM-FOAM-001",1),("RM-BF-001",1),("RM-CYL-001",1),("RM-FABR-001",0.8),("RM-HW-001",1)],
        "Bookcase":[("RM-SHF-001",4),("RM-SIDE-001",2),("RM-HW-001",1),("RM-PKG-001",1)],
        "Furnishing":[("RM-STEEL-001",1),("RM-HW-001",1),("RM-PKG-001",1)],
    }

    bom_ids = []
    for tmpl_id, prod_name in furniture_prods:
        # Kiểm tra BOM đã tồn tại chưa
        existing = api.search('mrp.bom', [('product_tmpl_id','=',tmpl_id)])
        if existing: bom_ids.extend(existing); continue

        # Xác định BOM template theo tên
        bom_template = BOM_TEMPLATES["Furnishing"]  # default
        for key in BOM_TEMPLATES:
            if key.lower() in prod_name.lower():
                bom_template = BOM_TEMPLATES[key]; break

        # Build components
        components = []
        for sku, qty in bom_template:
            pid = rm_ids.get(sku)
            if pid:
                components.append((0, 0, {"product_id": pid, "product_qty": qty}))

        # Build operations (routing)
        ops_time = {"Table":120,"Chair":90,"Bookcase":100,"Furnishing":60}
        asm_time  = next((t for k,t in ops_time.items() if k.lower() in prod_name.lower()), 90)

        # mrp.routing.workcenter uses time_cycle_manual (minutes), not duration_expected
        operations = [
            (0,0,{"name":"OP-01: Material Preparation","workcenter_id":wc_cut,
                  "time_mode":"manual","time_cycle_manual":45.0,"sequence":1}),
            (0,0,{"name":"OP-02: Assembly","workcenter_id":wc_asm,
                  "time_mode":"manual","time_cycle_manual":float(asm_time),"sequence":2}),
            (0,0,{"name":"OP-03: QC & Packaging","workcenter_id":wc_qc,
                  "time_mode":"manual","time_cycle_manual":30.0,"sequence":3}),
        ]

        try:
            bom_id = api.create('mrp.bom', {
                "product_tmpl_id": tmpl_id,
                "product_qty": 1.0,
                "type": "normal",
                "bom_line_ids": components,
                "operation_ids": operations,
            })
            bom_ids.append(bom_id)
        except Exception as e:
            log.warning(f"  BOM failed for {prod_name}: {e}")

    log.info(f"  {len(bom_ids)} BOMs ready (with routing operations)")
    return bom_ids

# ─── PHASE 1: SQL MASTER DATA ─────────────────────────────────────────────────
def p1_utm(pg, ctx) -> dict:
    log.info("Phase 1.1 — UTM")
    now = datetime.now(); cid,uid = ctx["cid"],ctx["uid"]
    stage = pg.one("SELECT id FROM utm_stage LIMIT 1")
    stage_id = stage[0] if stage else None
    src,med,camps = {},{},[]
    for s in UTM_SRC:
        r = pg.one("SELECT id FROM utm_source WHERE name::text LIKE %s",[f'%{s}%'])
        if r: src[s]=r[0]
        else:
            pg.q("INSERT INTO utm_source(name) VALUES(%s) RETURNING id",[s])
            src[s]=pg.cur.fetchone()[0]
    for m in UTM_MED:
        r = pg.one("SELECT id FROM utm_medium WHERE name::text LIKE %s",[f'%{m}%'])
        if r: med[m]=r[0]
        else:
            pg.q("INSERT INTO utm_medium(name) VALUES(%s) RETURNING id",[m])
            med[m]=pg.cur.fetchone()[0]
    for yr in range(2023,2027):
        for ct in random.sample(CAMP_TYPES,4):
            nm = f"{ct}-{yr}"
            r = pg.one("SELECT id FROM utm_campaign WHERE name::text LIKE %s",[f'%{nm}%'])
            if r: camps.append(r[0])
            else:
                pg.q("INSERT INTO utm_campaign(name,title,user_id,stage_id,company_id,create_uid,write_uid,create_date,write_date)"
                     " VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                     [nm,psycopg2.extras.Json({'en_US': nm}),uid,stage_id,cid,uid,uid,now,now])
                camps.append(pg.cur.fetchone()[0])
    pg.commit()
    log.info(f"  UTM: {len(src)} src | {len(med)} med | {len(camps)} campaigns")
    return {"sources":src,"mediums":med,"campaigns":camps}


def p1_categories(pg, ctx) -> dict:
    log.info("Phase 1.2 — Product categories")
    now = datetime.now(); cid,uid = ctx["cid"],ctx["uid"]
    root = pg.one("SELECT id FROM product_category WHERE parent_id IS NULL LIMIT 1")
    rid  = root[0] if root else None
    cats = {}
    for cn, info in CATEGORIES.items():
        r = pg.one("SELECT id FROM product_category WHERE name=%s AND parent_id=%s",[cn,rid])
        if r: pid=r[0]
        else:
            pg.q("INSERT INTO product_category(name,parent_id,create_uid,write_uid,create_date,write_date)"
                 " VALUES(%s,%s,%s,%s,%s,%s) RETURNING id",[cn,rid,uid,uid,now,now])
            pid=pg.cur.fetchone()[0]
        for sub in info["sub"]:
            r = pg.one("SELECT id FROM product_category WHERE name=%s AND parent_id=%s",[sub,pid])
            if r: cats[sub]=r[0]
            else:
                pg.q("INSERT INTO product_category(name,parent_id,create_uid,write_uid,create_date,write_date)"
                     " VALUES(%s,%s,%s,%s,%s,%s) RETURNING id",[sub,pid,uid,uid,now,now])
                cats[sub]=pg.cur.fetchone()[0]
    pg.commit()
    log.info(f"  {len(cats)} sub-categories")
    return cats


def p1_products(pg, api, ctx, cats) -> list:
    log.info(f"Phase 1.3 — {CFG['n_products']} Products")
    now=datetime.now(); cid,uid=ctx["cid"],ctx["uid"]
    sub_margin={sub:info["margin"] for cn,info in CATEGORIES.items() for sub in info["sub"]}
    per_sub=max(2,CFG["n_products"]//len(cats))
    adjs=["Standard","Professional","Premium","Basic","Compact","Executive"]
    pids=[]; cost_map={}

    for sub,cid2 in cats.items():
        mg=sub_margin.get(sub,0.30)
        for i in range(per_sub):
            nm=f"{random.choice(adjs)} {sub.rstrip('s')} {i+1}"
            sku=f"SS-{sub[:3].upper()}-{str(i+1).zfill(4)}"
            pr=round(max(9.99,min(jitter(np.random.lognormal(5.5,0.8)),2999.99)),2)
            co=round(pr*(1-mg)*jitter(1.0,0.05),2)
            r=pg.one("SELECT pp.id, pp.product_tmpl_id FROM product_product pp"
                     " WHERE pp.default_code=%s LIMIT 1",[sku])
            if r:
                pids.append(r[0]); cost_map[r[1]]=co; continue
            # Odoo 18: bỏ standard_price khỏi SQL INSERT
            pg.q("""INSERT INTO product_template
                    (name,type,is_storable,service_tracking,tracking,purchase_line_warn,sale_line_warn,
                     categ_id,list_price,company_id,uom_id,uom_po_id,
                     invoice_policy,active,sale_ok,purchase_ok,
                     create_uid,write_uid,create_date,write_date)
                    VALUES(%s,'consu',true,'no','none','no-message','no-message',
                           %s,%s,%s,1,1,'order',true,true,true,%s,%s,%s,%s)
                    RETURNING id""",
                 [psycopg2.extras.Json({'en_US': nm}),cid2,pr,ctx["cid"],uid,uid,now,now])
            tid=pg.cur.fetchone()[0]; cost_map[tid]=co
            pg.q("INSERT INTO product_product(product_tmpl_id,default_code,active,"
                 "create_uid,write_uid,create_date,write_date)"
                 " VALUES(%s,%s,true,%s,%s,%s,%s) RETURNING id",[tid,sku,uid,uid,now,now])
            pids.append(pg.cur.fetchone()[0])
        if len(pids)>=CFG["n_products"]: break

    pg.commit()

    # Set standard_price (cost) qua XML-RPC — Odoo 18 company_dependent
    log.info(f"  Setting cost prices via XML-RPC ({len(cost_map)} products)...")
    done_cost=0
    for tid, co in cost_map.items():
        try:
            api.write('product.template',[tid],{'standard_price': co})
            done_cost+=1
        except Exception as e:
            log.warning(f"  cost set failed tmpl {tid}: {e}")
        if done_cost % 100 == 0:
            log.info(f"  Cost set: {done_cost}/{len(cost_map)}")

    log.info(f"  {len(pids)} products created | costs set via XML-RPC ✅")
    return pids


def p1_partners(pg, ctx) -> dict:
    log.info(f"Phase 1.4 — Partners")
    now=datetime.now(); cid,uid,us=ctx["cid"],ctx["uid"],ctx["us"]
    states=pg.all("SELECT id,code FROM res_country_state WHERE country_id=%s",[us])
    sm={r[1]:r[0] for r in states}
    regs=list(REGIONS.keys()); custs=[]
    for i in range(CFG["n_customers"]):
        reg=random.choices(regs,weights=REG_W)[0]
        sc=random.choice(REGIONS[reg]); sid2=sm.get(sc)
        seg=random.choices(SEGMENTS,weights=SEG_W)[0]
        is_co=seg in ["Corporate","Home Office"]
        zp=fake.zipcode() if random.random()>CFG["missing_zip"] else None
        ph=fake.phone_number()[:20] if random.random()>CFG["missing_phone"] else None
        nm=fake.company() if is_co else fake.name()
        if random.random()<CFG["dup_customer"] and i>0:
            nm=nm.split()[0]+" "+nm.split()[-1]+random.choice([" Inc"," LLC",""])
        pg.q("""INSERT INTO res_partner
                (company_id,name,is_company,customer_rank,supplier_rank,
                 email,phone,street,city,state_id,zip,country_id,
                 active,comment,autopost_bills,create_uid,write_uid,create_date,write_date)
                VALUES(%s,%s,%s,1,0,%s,%s,%s,%s,%s,%s,%s,true,%s,'ask',%s,%s,%s,%s) RETURNING id""",
             [cid,nm,is_co,
              fake.company_email() if is_co else fake.email(),
              ph,fake.street_address(),fake.city(),
              sid2,zp,us,seg,uid,uid,now,now])
        custs.append(pg.cur.fetchone()[0])
    supps=[]
    for nm in SUPP_NAMES[:CFG["n_suppliers"]]:
        r=pg.one("SELECT id FROM res_partner WHERE name::text LIKE %s",[f'%{nm}%'])
        if r: supps.append(r[0]); continue
        pg.q("""INSERT INTO res_partner(company_id,name,is_company,customer_rank,supplier_rank,
                 email,phone,active,autopost_bills,create_uid,write_uid,create_date,write_date)
                VALUES(%s,%s,true,0,1,%s,%s,true,'ask',%s,%s,%s,%s) RETURNING id""",
             [cid,nm,f"orders@{nm[:15].lower().replace(' ','-')}.com",
              fake.phone_number()[:20],uid,uid,now,now])
        supps.append(pg.cur.fetchone()[0])
    pg.commit()
    log.info(f"  {len(custs)} customers | {len(supps)} suppliers")
    return {"customers":custs,"suppliers":supps}


def p1_employees(pg, ctx) -> list:
    log.info("Phase 1.5 — Employees + Contracts (SCD2)")
    now=datetime.now(); cid,uid=ctx["cid"],ctx["uid"]
    dept_hc={"Sales & CRM":12,"Warehouse & Logistics":12,"Manufacturing":9,
              "Purchasing":3,"Accounting":3,"Marketing":2,"HR & Administration":1,
              "IT & Data":1,"Executive":2}
    dept_ids={}
    for d in dept_hc:
        r=pg.one("SELECT id FROM hr_department WHERE name::text LIKE %s AND company_id=%s",[f'%{d}%',cid])
        if r: dept_ids[d]=r[0]
        else:
            pg.q("INSERT INTO hr_department(name,company_id,active,create_uid,write_uid,create_date,write_date)"
                 " VALUES(%s,%s,true,%s,%s,%s,%s) RETURNING id",[psycopg2.extras.Json({'en_US': d}),cid,uid,uid,now,now])
            dept_ids[d]=pg.cur.fetchone()[0]
    # hr_job: 1 record/chức danh/phòng ban (get-or-create, tránh trùng khi rerun)
    job_ids={}
    for dept in dept_hc:
        did=dept_ids[dept]
        titles=[JOB_TITLES[dept]["lead"]] + JOB_TITLES[dept]["staff"]
        for title in titles:
            r=pg.one("SELECT id FROM hr_job WHERE name::text LIKE %s AND department_id=%s",[f'%{title}%',did])
            if r: job_ids[(dept,title)]=r[0]
            else:
                pg.q("INSERT INTO hr_job(name,department_id,company_id,create_uid,write_uid,create_date,write_date)"
                     " VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                     [psycopg2.extras.Json({'en_US': title}),did,cid,uid,uid,now,now])
                job_ids[(dept,title)]=pg.cur.fetchone()[0]

    emps=[]
    for dept,cnt in dept_hc.items():
        did=dept_ids[dept]
        for i in range(cnt):
            nm=fake.name(); hd=date(random.randint(2020,2022),random.randint(1,12),random.randint(1,28))
            title = JOB_TITLES[dept]["lead"] if i==0 else random.choice(JOB_TITLES[dept]["staff"])
            jid = job_ids[(dept,title)]
            r=pg.one("SELECT id FROM hr_employee WHERE name::text LIKE %s AND company_id=%s",[f'%{nm}%',cid])
            if r: eid=r[0]
            else:
                pg.q("INSERT INTO resource_resource(name,resource_type,time_efficiency,tz,company_id,create_uid,write_uid,create_date,write_date)"
                     " VALUES(%s,'user',100,'UTC',%s,%s,%s,%s,%s) RETURNING id",
                     [nm,cid,uid,uid,now,now])
                res_id=pg.cur.fetchone()[0]
                pg.q("INSERT INTO hr_employee(name,department_id,job_id,job_title,company_id,resource_id,active,work_email,"
                     "distance_home_work_unit,employee_type,marital,create_uid,write_uid,create_date,write_date)"
                     " VALUES(%s,%s,%s,%s,%s,%s,true,%s,'kilometers','employee','single',%s,%s,%s,%s) RETURNING id",
                     [nm,did,jid,title,cid,res_id,fake.company_email(),uid,uid,now,now])
                eid=pg.cur.fetchone()[0]
            wage=random.uniform(40000,120000)
            pg.q("INSERT INTO hr_contract(name,employee_id,wage,date_start,state,company_id,create_uid,write_uid,create_date,write_date)"
                 " VALUES(%s,%s,%s,%s,'open',%s,%s,%s,%s,%s)",
                 [f"CTR-{eid}-1",eid,round(wage,2),hd,cid,uid,uid,now,now])
            cs,cw=hd,wage
            for rn in range(random.choices([0,1,2],weights=[0.3,0.5,0.2])[0]):
                rd=cs+timedelta(days=random.randint(365,700))
                if rd>=date.today(): break
                pg.q("UPDATE hr_contract SET state='close',date_end=%s WHERE employee_id=%s AND date_end IS NULL",
                     [rd-timedelta(days=1),eid])
                cw=round(cw*(1+random.uniform(0.05,0.15)),2)
                pg.q("INSERT INTO hr_contract(name,employee_id,wage,date_start,state,company_id,create_uid,write_uid,create_date,write_date)"
                     " VALUES(%s,%s,%s,%s,'open',%s,%s,%s,%s,%s)",
                     [f"CTR-{eid}-{rn+2}",eid,cw,rd,cid,uid,uid,now,now])
                cs=rd
            emps.append(eid)
    pg.commit()
    log.info(f"  {len(emps)} employees")
    return emps

# ─── PHASE 2: O2C WORKFLOW ────────────────────────────────────────────────────
def p2_create_sos(api, pg, ctx, partners, prod_ids, utm) -> list:
    """Tạo SOs với order_lines qua XML-RPC."""
    log.info(f"Phase 2.1 — Create {CFG['n_orders']} SOs (XML-RPC)")
    rows=pg.all("SELECT pp.id,pt.list_price FROM product_product pp JOIN product_template pt ON pt.id=pp.product_tmpl_id WHERE pp.id=ANY(%s)",[prod_ids])
    prices={r[0]:float(r[1]) for r in rows}
    custs=partners["customers"]; camps=utm["campaigns"]
    nc,np_=len(custs),len(prod_ids)
    nt_c=max(1,int(nc*0.20)); cw=np.array([4.0/nt_c]*nt_c+[1.0/(nc-nt_c)]*(nc-nt_c)); cw/=cw.sum()
    nt_p=max(1,int(np_*0.20)); pw=np.array([4.0/nt_p]*nt_p+[1.0/(np_-nt_p)]*(np_-nt_p)); pw/=pw.sum()
    dates=gen_dates(CFG["n_orders"],CFG["start"],CFG["end"])
    so_list=[]; buf=[]; done=0
    for i,d in enumerate(dates):
        cid_=int(np.random.choice(custs,p=cw))
        r=pg.one("SELECT comment FROM res_partner WHERE id=%s",[cid_])
        seg=(r[0] if r else None) or "Consumer"
        r2=pg.one("SELECT state_id FROM res_partner WHERE id=%s",[cid_])
        wh_id=list(ctx["wh"].values())[0]
        if r2 and r2[0]:
            r3=pg.one("SELECT code FROM res_country_state WHERE id=%s",[r2[0]])
            if r3:
                for reg,states in REGIONS.items():
                    if r3[0] in states:
                        wh_id=ctx["wh"].get(REGION_WH.get(reg,"WEST"),wh_id); break
        nl=random.choices([1,2,3,4,5],weights=[0.30,0.28,0.22,0.12,0.08])[0]
        ch=list(np.random.choice(prod_ids,size=nl,replace=False,p=pw))
        lines=[]; amt=0
        for pid in ch:
            qty=random.randint(1,10); pr=round(jitter(prices.get(pid,150.0),0.05),2)
            sub=qty*pr; disc=0.0
            if seg=="Corporate":
                if sub>25000: disc=20.0
                elif sub>10000: disc=15.0
                elif sub>5000: disc=10.0
                elif sub>2000: disc=5.0
            amt+=sub*(1-disc/100)
            lines.append((0,0,{"product_id":int(pid),"product_uom_qty":qty,
                                "price_unit":pr,"discount":disc,"tax_id":[(5,)]}))
        camp=random.choice(camps) if camps and random.random()<0.50 else False
        state="cancel" if random.random()<CFG["cancel_rate"] else "confirm"
        buf.append({"_s":state,"_d":d,
                    "partner_id":cid_,
                    "date_order":datetime.combine(d,datetime.min.time().replace(
                        hour=random.randint(7,18),minute=random.randint(0,59)
                    )).strftime("%Y-%m-%d %H:%M:%S"),
                    "warehouse_id":int(wh_id),
                    "campaign_id":int(camp) if camp else False,
                    "order_line":lines})
        if len(buf)>=CFG["b_so"] or i==CFG["n_orders"]-1:
            for v in buf:
                s=v.pop("_s"); dd=v.pop("_d")
                try:
                    sid=api.create("sale.order",v)
                    so_list.append((sid,s,dd))
                except Exception as e:
                    log.warning(f"  SO create err: {e}")
            buf.clear(); done+=CFG["b_so"]
            if done%500==0: log.info(f"  {min(done,CFG['n_orders'])}/{CFG['n_orders']} SOs")
    log.info(f"  {len(so_list)} SOs created")
    return so_list


def p2_confirm_orders(api, pg, so_list) -> tuple:
    log.info("Phase 2.2 — Confirm SOs → stock_picking + stock_move")
    all_ids  = [s for s,_,_ in so_list]
    canc_ids = {s for s,st,_ in so_list if st=="cancel"}
    date_by_id={s:d for s,st,d in so_list}
    conf=[]; fail=[]
    for b in batches(all_ids,CFG["b_confirm"]):
        try: api.call("sale.order","action_confirm",b); conf.extend(b)
        except:
            for s in b:
                try: api.call("sale.order","action_confirm",[s]); conf.append(s)
                except: fail.append(s)

    # action_confirm() resets date_order to now() (Odoo's own _prepare_confirmation_values) —
    # restore the backfilled historical date so downstream pickings/invoices inherit it too.
    log.info("  Restoring historical date_order (Odoo resets it on confirm)...")
    rows = [(sid, datetime.combine(date_by_id[sid], datetime.min.time().replace(
                hour=random.randint(7,18), minute=random.randint(0,59))))
            for sid in conf]
    for b in batches(rows, 1000):
        pg.many("""
            UPDATE sale_order AS so SET date_order = v.d
            FROM (VALUES %s) AS v(id, d)
            WHERE so.id = v.id
        """, b)
        pg.commit()

    # NOTE: pickings/moves created during confirm inherit the (then-corrupted) date_order.
    # Don't bother cascading it here — button_validate() in p2_validate_deliveries stamps
    # date/date_done to now() again when it actually completes the transfer, so any fix
    # applied at this point gets overwritten anyway. The real fix runs post-validation.

    # Imperfection: cancel_rate % of orders are cancelled AFTER confirm, not before —
    # leaves behind a real (now-cancelled) picking/move trail from a broken sales cycle,
    # rather than a draft that never had one. Confirm first, then cancel the flagged subset.
    # action_cancel() on a non-draft order returns a sale.order.cancel WIZARD action dict
    # instead of cancelling (Odoo's _show_cancel_wizard() — any state != 'draft' triggers it)
    # — no exception is raised, so a bare try/except silently no-ops and the order stays
    # 'sale'. disable_cancel_warning=True skips the wizard and cancels directly.
    canc = [s for s in conf if s in canc_ids]
    n_cancelled = 0
    for b in batches(canc,100):
        try:
            api._x("sale.order","action_cancel",[b],{"context":{"disable_cancel_warning":True}})
            n_cancelled += len(b)
        except Exception as e:
            for s in b:
                try:
                    api._x("sale.order","action_cancel",[[s]],{"context":{"disable_cancel_warning":True}})
                    n_cancelled += 1
                except Exception as e2:
                    log.warning(f"  SO {s} cancel failed: {e2}")
    conf = [s for s in conf if s not in canc_ids]

    log.info(f"  Confirmed:{len(conf)} | Cancelled (post-confirm):{n_cancelled}/{len(canc)} | Failed:{len(fail)}")
    return conf, canc


def p2_validate_deliveries(api, pg, ctx, confirmed_so_ids) -> int:
    """
    Validate deliveries đúng quy trình:
    1. Lấy tất cả pickings từ confirmed SOs
    2. SQL: set quantity_done = product_uom_qty trên stock_move
    3. SQL: tạo stock_move_line
    4. XML-RPC: button_validate() batch → ORM update stock_quant
    """
    log.info("Phase 2.3 — Validate Deliveries (full ORM workflow)")
    cid = ctx["cid"]

    # Lấy tất cả OUT pickings từ confirmed SOs
    pickings = pg.all("""
        SELECT sp.id FROM stock_picking sp
        WHERE sp.state IN ('confirmed','assigned','waiting','ready')
        AND sp.company_id=%s
        AND sp.sale_id = ANY(%s)
    """, [cid, confirmed_so_ids])
    pick_ids = [r[0] for r in pickings]

    if not pick_ids:
        log.warning("  Không tìm thấy pickings — kiểm tra SO confirm đã chạy chưa")
        return 0

    log.info(f"  Found {len(pick_ids)} pickings to validate")

    # Step 1: action_assign (reserve stock)
    log.info("  Step 1: action_assign to reserve...")
    for b in batches(pick_ids, 100):
        try: api.call('stock.picking', 'action_assign', b)
        except: pass

    # Step 2: set quantity=product_uom_qty via ORM write (NOT raw SQL). quantity is a
    # compute+store+readonly=False field whose inverse propagates into move_line_ids and
    # is required for stock.quant to update on _action_done() — a raw SQL UPDATE bypasses
    # that inverse, silently leaving stock.quant empty even though the move still reaches
    # state='done'. Batch by distinct quantity value (qty is a small int 1-10) to keep this
    # to a handful of XML-RPC calls instead of one per move. Do NOT manually create
    # stock_move_line rows — button_validate() auto-generates them from quantity/picked.
    log.info("  Step 2: set quantity via ORM writes...")
    move_rows = pg.all("""
        SELECT id, product_uom_qty FROM stock_move
        WHERE picking_id = ANY(%s) AND state NOT IN ('done','cancel')
    """, [pick_ids])
    by_qty = {}
    for mid, qty in move_rows:
        by_qty.setdefault(float(qty), []).append(mid)
    for qty, ids in by_qty.items():
        for b in batches(ids, 500):
            try:
                api.write('stock.move', b, {'quantity': qty, 'picked': True})
            except Exception as e:
                log.warning(f"  set quantity batch failed (qty={qty}): {e}")

    # Step 4: XML-RPC button_validate in batches
    log.info("  Step 4: button_validate (XML-RPC)...")
    validated = 0
    for b in batches(pick_ids, CFG["b_validate"]):
        try:
            res = api._x('stock.picking', 'button_validate', [b],
                   {"context": {"skip_backorder": True, "skip_sms": True,
                                "picking_ids_not_to_backorder": b}})
            if res is not True:
                # button_validate() returns a wizard action (e.g. SMS confirm, backorder)
                # instead of completing the transfer when a pre-validation hook intervenes.
                raise RuntimeError(f"button_validate returned a wizard instead of completing: {res}")
            validated += len(b)
        except Exception as e:
            # Validate one by one as fallback
            for pid in b:
                try:
                    res = api._x('stock.picking', 'button_validate', [[pid]],
                           {"context": {"skip_backorder": True, "skip_sms": True,
                                        "picking_ids_not_to_backorder": [pid]}})
                    if res is not True:
                        raise RuntimeError(f"button_validate returned a wizard instead of completing: {res}")
                    validated += 1
                except Exception as e2:
                    log.warning(f"  Picking {pid} validate failed: {e2}")
        if validated % 500 == 0:
            log.info(f"  Validated {validated}/{len(pick_ids)} pickings")

    log.info(f"  ✅ {validated}/{len(pick_ids)} pickings validated → stock_quant updated by ORM")

    # button_validate()/_action_done() stamps date, date_done, scheduled_date and
    # date_deadline to now() when it completes the transfer — restore all four (+ the
    # underlying stock_move.date/date_deadline) to a historical date derived from
    # date_order. scheduled_date/date_deadline = the PLANNED date; date/date_done = the
    # ACTUAL completion date, which is later for the late_delivery % of pickings (the
    # imperfection documented in data_dictionary.md as "scheduled_date vs date_done").
    #
    # Công thức chuẩn Odoo (sale_stock + stock.rule):
    #   commitment_date = date_order + sale_delay + stock_rule.delay
    #                     (sale_delay: customer_lead trên sale_order_line, copy từ
    #                      product.sale_delay lúc tạo dòng; stock_rule.delay: "Lead Time"
    #                      của rule "<WH>: Stock → Customers" — thời gian vận chuyển kho→khách)
    #   scheduled_date  = commitment_date - security_lead
    #                   = date_order + sale_delay + stock_rule.delay - security_lead
    #                     (security_lead kéo ngày kho SẴN SÀNG sớm hơn ngày hứa khách, để có buffer)
    # Nếu sale_delay=0 và security_lead=0 (chưa cấu hình) → fallback 1 ngày, giữ hành vi cũ.
    log.info("  Restoring historical dates on completed pickings/moves (+ lead time + stock_rule.delay + late-delivery imperfection)...")
    sec_lead_row = pg.all("SELECT security_lead FROM res_company WHERE id=%s", [cid])
    sec_lead = float(sec_lead_row[0][0]) if sec_lead_row else 0.0
    rule_delay_rows = pg.all("""
        SELECT sw.code, sr.delay FROM stock_rule sr
        JOIN stock_warehouse sw ON sw.id = sr.warehouse_id
        WHERE sw.code IN ('WEST','EAST','CNTL','SOUT')
          AND sr.name->>'en_US' LIKE '%%Stock → Customers%%'
          AND sr.name->>'en_US' NOT LIKE '%%MTO%%'
    """)
    rule_delay = {code: float(delay) for code, delay in rule_delay_rows}
    rows = pg.all("""
        SELECT sp.id, so.id, so.date_order, sw.code,
               COALESCE((SELECT MAX(sol.customer_lead) FROM sale_order_line sol
                         WHERE sol.order_id = so.id), 0) AS sale_delay
        FROM stock_picking sp
        JOIN sale_order so ON so.id = sp.sale_id
        LEFT JOIN stock_location sl ON sl.id = sp.location_id
        LEFT JOIN stock_warehouse sw ON sw.id = sl.warehouse_id
        WHERE sp.id = ANY(%s)
    """, [pick_ids])
    pick_dates = []
    so_commitments = {}
    n_late = 0
    for pid, so_id, order_dt, wh_code, sale_delay in rows:
        commitment_days = float(sale_delay) + rule_delay.get(wh_code, 0.0)
        sched_days = commitment_days - sec_lead
        if sched_days <= 0:
            sched_days = 1  # chưa cấu hình lead time thật — giữ hành vi cũ
            commitment_days = max(commitment_days, sched_days)  # commitment >= scheduled
        scheduled = order_dt + timedelta(days=sched_days)
        commitment = order_dt + timedelta(days=commitment_days)
        so_commitments[so_id] = commitment  # 1 SO có thể có nhiều picking — giữ giá trị sau cùng
        if random.random() < late_delivery_rate(wh_code):
            actual = scheduled + timedelta(days=random.randint(1, 5))
            n_late += 1
        else:
            actual = scheduled
        pick_dates.append((pid, scheduled, actual))
    for b in batches(pick_dates, 1000):
        pg.many("""
            UPDATE stock_picking AS sp SET
                date = v.actual, date_done = v.actual,
                scheduled_date = v.scheduled, date_deadline = v.scheduled
            FROM (VALUES %s) AS v(id, scheduled, actual)
            WHERE sp.id = v.id
        """, b)
        pg.many("""
            UPDATE stock_move AS sm SET date = v.actual, date_deadline = v.scheduled
            FROM (VALUES %s) AS v(id, scheduled, actual)
            WHERE sm.picking_id = v.id
        """, b)
    for b in batches(list(so_commitments.items()), 1000):
        pg.many("""
            UPDATE sale_order AS so SET commitment_date = v.commitment
            FROM (VALUES %s) AS v(id, commitment)
            WHERE so.id = v.id
        """, b)
    pg.commit()
    log.info(f"    {n_late}/{len(pick_dates)} pickings marked late ({n_late/len(pick_dates)*100:.1f}%)")
    log.info(f"    {len(so_commitments)} sale_order.commitment_date ghi theo công thức date_order+sale_delay+stock_rule.delay")

    return validated


def p2_create_and_post_invoices(api, pg, ctx, confirmed_so_ids) -> list:
    """Tạo và post invoices từ confirmed SOs."""
    log.info("Phase 2.4 — Create + Post Invoices")
    cid = ctx["cid"]
    inv_ids = []

    # Tạo invoices qua wizard
    for b in batches(confirmed_so_ids, CFG["b_invoice"]):
        try:
            wiz_id = api.create('sale.advance.payment.inv', {
                'advance_payment_method': 'delivered',
                'sale_order_ids': [(6, 0, b)],
            })
            api.call('sale.advance.payment.inv', 'create_invoices', [wiz_id])
        except Exception as e:
            log.warning(f"  Invoice wizard failed: {e} — trying _create_invoices")
            try:
                api.call('sale.order', '_create_invoices', b)
            except Exception as e2:
                log.warning(f"  _create_invoices also failed: {e2}")

    # Đọc draft invoices
    draft_invs = pg.all("""
        SELECT id FROM account_move
        WHERE move_type='out_invoice' AND state='draft' AND company_id=%s
        ORDER BY id
    """, [cid])
    draft_ids = [r[0] for r in draft_invs]

    if not draft_ids:
        log.warning("  Không có draft invoices — fallback SQL invoice creation")
        draft_ids = _fallback_sql_invoices(pg, ctx, confirmed_so_ids)
    else:
        # Wizard defaults invoice_date to today — restore it from the SO's (already-restored)
        # historical date_order, joined via invoice_origin = sale_order.name.
        pg.q("""
            UPDATE account_move am
            SET invoice_date = (so.date_order::date + (random()*5)::int),
                date          = (so.date_order::date + (random()*5)::int)
            FROM sale_order so
            WHERE am.invoice_origin = so.name AND am.id = ANY(%s)
        """, [draft_ids])
        pg.commit()

        # Post invoices
        log.info(f"  Posting {len(draft_ids)} invoices...")
        for b in batches(draft_ids, CFG["b_post"]):
            try: api.call('account.move', 'action_post', b); inv_ids.extend(b)
            except:
                for inv in b:
                    try: api.call('account.move', 'action_post', [inv]); inv_ids.append(inv)
                    except: pass

    log.info(f"  ✅ {len(inv_ids)} invoices posted")
    return inv_ids


def _fallback_sql_invoices(pg, ctx, so_ids) -> list:
    """SQL fallback invoice creation với đầy đủ journal entries."""
    log.info("  (SQL fallback) Creating invoices + journal entries")
    now=datetime.now(); cid,uid=ctx["cid"],ctx["uid"]
    jnl=ctx["jnl"].get("sale")
    ar=pg.one("SELECT id FROM account_account WHERE account_type='asset_receivable' AND company_id=%s LIMIT 1",[cid])
    rev=pg.one("SELECT id FROM account_account WHERE account_type='income' AND company_id=%s LIMIT 1",[cid])
    if not jnl or not ar or not rev: return []
    ar_id,rev_id=ar[0],rev[0]
    so_data=pg.all("SELECT id,partner_id,amount_total,date_order::date,campaign_id FROM sale_order WHERE id=ANY(%s) AND state='sale'",[so_ids])
    inv_ids=[]
    for so_id,pid,amt,idate,camp in so_data:
        amt=round(amt or 0,2)
        if amt<=0: continue
        idate2=idate+timedelta(days=random.randint(1,5))
        pg.q("""INSERT INTO account_move(company_id,move_type,partner_id,invoice_date,state,
                journal_id,currency_id,amount_untaxed,amount_total,amount_residual,
                payment_state,campaign_id,create_uid,write_uid,create_date,write_date)
               VALUES(%s,'out_invoice',%s,%s,'posted',%s,%s,%s,%s,%s,'not_paid',%s,%s,%s,%s,%s)
               RETURNING id""",
             [cid,pid,idate2,jnl,ctx["cur"],amt,amt,amt,camp,uid,uid,now,now])
        iid=pg.cur.fetchone()[0]; inv_ids.append(iid)
        for acct,dr,cr in [(ar_id,amt,0),(rev_id,0,amt)]:
            pg.q("""INSERT INTO account_move_line(move_id,account_id,partner_id,name,
                    debit,credit,date,company_id,currency_id,create_uid,write_uid,create_date,write_date)
                   VALUES(%s,%s,%s,'Invoice line',%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                 [iid,acct,pid,dr,cr,idate2,cid,ctx["cur"],uid,uid,now,now])
    pg.commit()
    return inv_ids


def p2_register_payments(api, pg, ctx, inv_ids) -> int:
    """Tạo payments + reconcile với invoices qua XML-RPC."""
    log.info(f"Phase 2.5 — Register Payments ({len(inv_ids)} invoices)")
    cid = ctx["cid"]
    jnl_bank = ctx["jnl"].get("bank") or ctx["jnl"].get("cash")
    if not jnl_bank:
        log.warning("  Không tìm thấy Bank journal"); return 0

    paid = 0
    inv_data = pg.all("""
        SELECT id, partner_id, amount_total, invoice_date, payment_state
        FROM account_move WHERE id=ANY(%s) AND state='posted'
    """, [inv_ids])

    for inv_id, partner_id, amount, inv_date, pstate in inv_data:
        if random.random() < CFG["overdue_b2b"]:
            continue  # 10% intentionally overdue
        amount = round(float(amount or 0), 2)
        if amount <= 0: continue
        pay_date = (inv_date or date(2023,1,1)) + timedelta(days=random.randint(5, 30))

        try:
            # Tạo payment qua XML-RPC → ORM tạo journal entry
            pay_id = api.create('account.payment', {
                'payment_type'         : 'inbound',
                'partner_type'         : 'customer',
                'partner_id'           : partner_id,
                'amount'               : amount,
                'journal_id'           : jnl_bank,
                'date'                 : pay_date.strftime('%Y-%m-%d'),
                'currency_id'          : ctx["cur"],
            })
            # action_post() has no return statement (implicit None) — guaranteed "cannot
            # marshal None" on every call, same cosmetic class as button_start/button_finish/
            # action_apply_inventory. The DB write (journal entry + move.action_post()) already
            # happens synchronously inside action_post() before the RPC response is marshalled,
            # so this is harmless — but a genuine posting failure (e.g. missing journal config)
            # would raise the SAME generic exception, so it must be told apart from the cosmetic
            # one instead of blindly SQL-patching payment_state='paid' either way.
            try:
                api.call('account.payment', 'action_post', [pay_id])
            except Exception as e:
                if "cannot marshal None" not in str(e):
                    raise

            # Reconcile với invoice: update amount_residual
            pg.q("UPDATE account_move SET payment_state='paid',amount_residual=0 WHERE id=%s",[inv_id])
            paid += 1
        except Exception as e:
            log.warning(f"  Payment failed (invoice {inv_id}): {e}")

        if paid % 200 == 0:
            pg.commit()
            log.info(f"  Payments: {paid}/{len(inv_data)}")

    pg.commit()
    log.info(f"  ✅ {paid} payments registered | {len(inv_data)-paid} overdue (intentional)")
    return paid

# ─── PHASE 2B: CRM LEADS (demand-driven, needs Phase 2's SO data) ────────────
def p2b_crm_leads(api, pg, ctx, so_id_filter=None) -> int:
    """
    Sinh crm.lead cho phễu Lead→Opportunity→SO — trước đây bảng này để trống
    hoàn toàn (0 dòng) dù master_plan/FRD-01 đã thiết kế sẵn campaign_id/
    source_id/medium_id trên crm.lead để phân tích conversion funnel.

    Won leads: 1:1 với MỌI sale_order đã có (kể cả state=cancel — lead vẫn
    "won" thành đơn, chỉ là đơn sau đó bị hủy; khác nghịch lý với lead
    chưa từng chuyển đổi). Lost leads: sinh thêm để đạt tỷ lệ chuyển đổi
    ~25% (KPI Sales Director, FRD-01) — không link partner thật, dùng
    contact_name/partner_name/email_from tự do (Odoo cho phép lead chưa
    thành khách hàng — không bắt buộc partner_id).

    so_id_filter: list sale_order.id để giới hạn phạm vi Won lead — dùng khi
    gọi hàm này LẦN THỨ HAI (ví dụ sau khi RFM tạo thêm SR-orders), tránh
    tạo lại Won lead trùng cho các SO đã có lead từ lần chạy trước.
    """
    log.info("Phase 2b — CRM Leads (Won 1:1 SO + Lost để đạt conversion ~25%)")
    cid = ctx["cid"]

    stage_won = pg.one("SELECT id FROM crm_stage WHERE is_won=true LIMIT 1")[0]
    stage_ids = {r[0]: r[1] for r in pg.all(
        "SELECT sequence, id FROM crm_stage WHERE is_won IS NOT TRUE ORDER BY sequence")}
    lost_reason_ids = [r[0] for r in pg.all("SELECT id FROM crm_lost_reason")]
    campaigns = [r[0] for r in pg.all("SELECT id FROM utm_campaign WHERE company_id=%s", [cid])]
    sources = [r[0] for r in pg.all("SELECT id FROM utm_source")]
    mediums = [r[0] for r in pg.all("SELECT id FROM utm_medium")]

    # Repair data do các bản generator cũ tạo: Won opportunity đã có nhưng
    # sale_order.opportunity_id và crm_lead.date_conversion bị bỏ trống. Chỉ động
    # tới record do generator nhận diện bằng tên "Opportunity — {SO name}".
    linked_existing = pg.q("""
        UPDATE sale_order so
           SET opportunity_id = cl.id
          FROM crm_lead cl
         WHERE so.opportunity_id IS NULL
           AND cl.type = 'opportunity'
           AND cl.partner_id = so.partner_id
           AND cl.name = 'Opportunity — ' || so.name
    """).rowcount
    converted_existing = pg.q("""
        UPDATE crm_lead
           SET date_conversion = COALESCE(date_conversion, date_open, create_date),
               date_last_stage_update = COALESCE(date_closed, write_date, date_last_stage_update)
         WHERE name LIKE 'Opportunity — %'
           AND type = 'opportunity'
           AND (date_conversion IS NULL OR date_last_stage_update IS NULL)
    """).rowcount

    # Lead bị mất sau khi đã qua Qualified/Proposition là lost opportunity,
    # không còn là lead thuần. Bản cũ để tất cả type='lead' làm sai
    # denominator của Win Rate. Chỉ repair record demo "Lead #...".
    repaired_lost_opportunities = pg.q("""
        UPDATE crm_lead cl
           SET type = 'opportunity',
               date_conversion = COALESCE(
                   cl.date_conversion,
                   cl.create_date + (COALESCE(cl.write_date, cl.create_date) - cl.create_date) / 2
               ),
               date_closed = COALESCE(cl.date_closed, cl.write_date),
               date_last_stage_update = COALESCE(cl.write_date, cl.date_last_stage_update)
          FROM crm_stage st
         WHERE cl.stage_id = st.id
           AND cl.active = false
           AND cl.name LIKE 'Lead #%'
           AND st.sequence >= 2
           AND cl.type = 'lead'
    """).rowcount
    closed_existing_lost = pg.q("""
        UPDATE crm_lead
           SET date_closed = COALESCE(date_closed, write_date),
               date_last_stage_update = COALESCE(write_date, date_last_stage_update)
         WHERE active = false
           AND name LIKE 'Lead #%'
           AND (date_closed IS NULL OR date_last_stage_update IS NULL)
    """).rowcount
    pg.commit()
    if linked_existing or converted_existing or repaired_lost_opportunities or closed_existing_lost:
        log.info(
            "  Repaired CRM links/history: %s SO links, %s conversion dates, "
            "%s lost opportunities, %s lost close dates",
            linked_existing, converted_existing, repaired_lost_opportunities, closed_existing_lost,
        )

    # ── 1. WON leads — 1:1 với sale_order (chưa có lead, theo so_id_filter nếu có) ──
    extra = "AND so.id = ANY(%s)" if so_id_filter is not None else ""
    params = [so_id_filter] if so_id_filter is not None else []
    so_rows = pg.all(f"""
        SELECT so.id, so.partner_id, so.date_order, so.amount_total, so.campaign_id, so.name
        FROM sale_order so
        WHERE NOT EXISTS (SELECT 1 FROM crm_lead cl WHERE cl.partner_id = so.partner_id
                           AND cl.name = 'Opportunity — ' || so.name)
        {extra}
    """, params)
    log.info(f"  Tạo {len(so_rows)} Won lead (1:1 với sale_order)...")

    won_vals, won_dates = [], []
    for so_id, partner_id, date_order, amount, camp_id, so_name in so_rows:
        open_dt = date_order - timedelta(days=random.randint(3, 21))
        won_vals.append({
            "name"            : f"Opportunity — {so_name}",
            "partner_id"      : int(partner_id),
            "type"            : "opportunity",
            "stage_id"        : stage_won,
            "probability"     : 100.0,
            "expected_revenue": float(amount or 0),
            "campaign_id"     : int(camp_id) if camp_id else False,
            "company_id"      : cid,
        })
        won_dates.append((so_id, open_dt, date_order))

    won_ids = []
    total = 0
    for chunk_vals, chunk_dates in zip(batches(won_vals, 200), batches(won_dates, 200)):
        try:
            ids = api.create('crm.lead', chunk_vals)
            if not isinstance(ids, list):
                ids = [ids]
            won_ids.extend(zip(ids, chunk_dates))
            total += len(ids)
            if total % 2000 == 0:
                log.info(f"    Won leads: {total}/{len(so_rows)}")
        except Exception as e:
            log.warning(f"  Won lead batch failed: {e}")

    # Restore historical timestamps (Odoo stamps now() lúc create) và ghi FK có cấu trúc
    # trên sale_order. date_conversion=open_dt vì demo tạo thẳng opportunity; không
    # có sự kiện lead trung gian để suy ra một thời điểm khác.
    for lid, (so_id, open_dt, closed_dt) in won_ids:
        pg.q("""UPDATE crm_lead
                   SET date_open=%s, date_conversion=%s, date_closed=%s,
                       date_last_stage_update=%s, create_date=%s
                 WHERE id=%s""",
             [open_dt, open_dt, closed_dt, closed_dt, open_dt, lid])
        pg.q("UPDATE sale_order SET opportunity_id=%s WHERE id=%s", [lid, so_id])
    pg.commit()
    log.info(f"  ✅ {len(won_ids)} Won leads created")

    # ── 2. LOST leads — chỉ sinh khi chạy KHÔNG scoped (tránh nhân đôi lúc gọi lại) ──
    lost_ids = []
    if so_id_filter is None:
        n_lost = len(so_rows) * 3  # conversion 25% = won/(won+lost) → lost = won×3
        log.info(f"  Tạo {n_lost} Lost lead (target conversion ~25%)...")

        lost_vals, lost_dates = [], []
        days_span = (CFG["end"] - CFG["start"]).days
        for i in range(n_lost):
            # Weighted: rớt sớm (New) nhiều hơn rớt muộn (Proposition) — đúng hình phễu thật
            seq = random.choices([1, 2, 3], weights=[0.5, 0.3, 0.2])[0]
            create_dt = CFG["start"] + timedelta(days=random.randint(0, days_span))
            lost_dt = create_dt + timedelta(days=random.randint(1, 30))
            became_opportunity = seq >= 2
            conversion_dt = (
                create_dt + (lost_dt - create_dt) / 2
                if became_opportunity else None
            )
            lost_vals.append({
                "name"          : f"Lead #{i+1}",
                "contact_name"  : fake.name(),
                "partner_name"  : fake.company(),
                "email_from"    : fake.company_email(),
                "type"          : "opportunity" if became_opportunity else "lead",
                "stage_id"      : stage_ids.get(seq),
                "probability"   : 0.0,
                "active"        : False,
                "lost_reason_id": random.choice(lost_reason_ids) if lost_reason_ids else False,
                "campaign_id"   : random.choice(campaigns) if campaigns and random.random() < 0.7 else False,
                "source_id"     : random.choice(sources) if sources and random.random() < 0.8 else False,
                "medium_id"     : random.choice(mediums) if mediums and random.random() < 0.8 else False,
                "company_id"    : cid,
            })
            lost_dates.append((create_dt, conversion_dt, lost_dt))

        total = 0
        for chunk_vals, chunk_dates in zip(batches(lost_vals, 200), batches(lost_dates, 200)):
            try:
                ids = api.create('crm.lead', chunk_vals)
                if not isinstance(ids, list):
                    ids = [ids]
                lost_ids.extend(zip(ids, chunk_dates))
                total += len(ids)
                if total % 5000 == 0:
                    log.info(f"    Lost leads: {total}/{n_lost}")
            except Exception as e:
                log.warning(f"  Lost lead batch failed: {e}")

        for lid, (create_dt, conversion_dt, lost_dt) in lost_ids:
            pg.q("""UPDATE crm_lead
                       SET create_date=%s, date_open=%s, date_conversion=%s,
                           date_closed=%s, date_last_stage_update=%s, write_date=%s
                     WHERE id=%s""",
                 [create_dt, create_dt, conversion_dt, lost_dt, lost_dt, lost_dt, lid])
        pg.commit()
        log.info(f"  ✅ {len(lost_ids)} Lost leads created")
    else:
        log.info("  Scoped run (so_id_filter) — bỏ qua sinh Lost lead mới")

    total_leads = len(won_ids) + len(lost_ids)
    conv_rate = len(won_ids) / (len(won_ids) + len(lost_ids)) * 100 if (won_ids or lost_ids) else 0
    log.info(f"  ✅ Tổng {total_leads} lead mới — conversion rate lô này: {conv_rate:.1f}%")
    return total_leads


def _load_campaign_channels():
    """Đọc channel hợp lệ của từng campaign từ source marketing chính thức."""
    if not MARKETING_CAMPAIGN_MASTER.exists():
        raise FileNotFoundError(
            f"Không tìm thấy campaign master: {MARKETING_CAMPAIGN_MASTER}"
        )

    result = {}
    with MARKETING_CAMPAIGN_MASTER.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            channels = [
                value.strip().lower()
                for value in (row.get("channels") or "").split("|")
                if value.strip()
            ]
            if channels:
                result[int(row["campaign_id"])] = channels
    return result


def _load_daily_paid_attribution(campaign_channels):
    """Map date -> campaign/channel có record spend thật trong CSV marketing."""
    if not MARKETING_AD_DAILY.exists():
        raise FileNotFoundError(f"Không tìm thấy ad performance: {MARKETING_AD_DAILY}")

    result = {}
    with MARKETING_AD_DAILY.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            campaign_id = int(row["campaign_id"])
            channel = row["channel"].strip().lower()
            if channel not in campaign_channels.get(campaign_id, []):
                raise ValueError(
                    f"Ad row dùng channel ngoài campaign master: "
                    f"campaign_id={campaign_id}, channel={channel}"
                )
            result.setdefault(row["date"], []).append((campaign_id, channel))
    return result


def _ensure_named_records(api, pg, model, table, names):
    """Tạo master record còn thiếu qua ORM và trả mapping lower(name) -> id."""
    mapping = {
        str(name).strip().lower(): record_id
        for record_id, name in pg.all(f"SELECT id, name FROM {table}")
        if name
    }
    for name in names:
        key = name.lower()
        if key not in mapping:
            mapping[key] = api.create(model, {"name": name})
    return mapping


def _delivery_mode_for_id(record_id):
    """Phân bổ deterministic 4/16/20/60; chạy lại không đổi carrier của cùng order."""
    bucket = int(record_id) % 100
    upper = 0
    for name, weight, _price in DELIVERY_MODES:
        upper += weight
        if bucket < upper:
            return name
    return DELIVERY_MODES[-1][0]


def _write_batches(api, model, ids, values, batch_size=1000):
    written = 0
    for chunk in batches(ids, batch_size):
        api.write(model, chunk, values)
        written += len(chunk)
    return written


def p2c_repair_mart_source_data(api, pg, ctx):
    """
    Bổ sung các field nghiệp vụ mà Mart cần nhưng generator cũ để trống:

    - sale_order/crm_lead: source_id + medium_id theo campaign master;
    - đơn không campaign: direct/organic/referral (không giả làm paid campaign);
    - sale_order/stock_picking: carrier_id theo 4 ship mode cố định.

    Toàn bộ business write đi qua Odoo ORM. Quy tắc phân bổ deterministic và chỉ
    dùng key nguồn đã kiểm soát nên hàm có thể chạy lại an toàn.
    """
    log.info("Phase 2c — Repair Mart source coverage (UTM + delivery carrier)")
    cid = ctx["cid"]
    campaign_channels = _load_campaign_channels()
    daily_paid_attribution = _load_daily_paid_attribution(campaign_channels)

    channel_to_source = {
        **PAID_CHANNEL_SOURCE,
        **NON_CAMPAIGN_CHANNEL_SOURCE,
    }
    medium_ids = _ensure_named_records(
        api,
        pg,
        "utm.medium",
        "utm_medium",
        sorted(channel_to_source),
    )
    source_ids = _ensure_named_records(
        api,
        pg,
        "utm.source",
        "utm_source",
        sorted(set(channel_to_source.values())),
    )

    # delivery.carrier.name là translated JSONB trong Odoo 18.
    carrier_rows = pg.all("""
        SELECT id, COALESCE(name->>'en_US', name->>'vi_VN'), product_id
        FROM delivery_carrier
        WHERE company_id = %s OR company_id IS NULL
    """, [cid])
    carrier_ids = {
        name: record_id
        for record_id, name, _product_id in carrier_rows
        if name
    }
    delivery_product_id = next(
        (product_id for _record_id, _name, product_id in carrier_rows if product_id),
        None,
    )
    if not delivery_product_id:
        row = pg.one("""
            SELECT pp.id
            FROM product_product pp
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            WHERE pt.type = 'service'
            ORDER BY pp.id
            LIMIT 1
        """)
        delivery_product_id = row[0] if row else None
    if not delivery_product_id:
        raise RuntimeError("Không có service product để tạo delivery carrier")

    for name, _weight, fixed_price in DELIVERY_MODES:
        if name not in carrier_ids:
            carrier_ids[name] = api.create("delivery.carrier", {
                "name": name,
                "delivery_type": "fixed",
                "product_id": int(delivery_product_id),
                "fixed_price": fixed_price,
                "company_id": cid,
            })

    order_rows = pg.all("""
        SELECT so.id,
               so.campaign_id,
               so.opportunity_id,
               so.medium_id,
               so.source_id,
               so.carrier_id,
               cl.medium_id,
               cl.source_id,
               cl.campaign_id,
               so.date_order::date
        FROM sale_order so
        LEFT JOIN crm_lead cl ON cl.id = so.opportunity_id
        WHERE so.company_id = %s
        ORDER BY so.id
    """, [cid])

    order_groups = {}
    opportunity_groups = {}
    carrier_by_order = {}
    owned_channels = sorted(NON_CAMPAIGN_CHANNEL_SOURCE)

    for (
        order_id,
        campaign_id,
        opportunity_id,
        current_medium_id,
        current_source_id,
        current_carrier_id,
        opportunity_medium_id,
        opportunity_source_id,
        opportunity_campaign_id,
        order_date,
    ) in order_rows:
        if campaign_id and daily_paid_attribution.get(order_date.isoformat()):
            paid_options = daily_paid_attribution[order_date.isoformat()]
            desired_campaign_id, channel = paid_options[
                int(order_id) % len(paid_options)
            ]
        else:
            desired_campaign_id = False
            channel = owned_channels[int(order_id) % len(owned_channels)]
        source = channel_to_source[channel]
        carrier_name = _delivery_mode_for_id(order_id)
        carrier_id = carrier_ids[carrier_name]
        key = (
            medium_ids[channel],
            source_ids[source],
            carrier_id,
            desired_campaign_id,
        )
        if (
            current_medium_id,
            current_source_id,
            current_carrier_id,
            campaign_id,
        ) != (
            medium_ids[channel],
            source_ids[source],
            carrier_id,
            desired_campaign_id or None,
        ):
            order_groups.setdefault(key, []).append(order_id)
        carrier_by_order[order_id] = carrier_id
        if opportunity_id and (
            opportunity_medium_id,
            opportunity_source_id,
            opportunity_campaign_id,
        ) != (
            medium_ids[channel],
            source_ids[source],
            desired_campaign_id or None,
        ):
            opportunity_groups.setdefault(
                (medium_ids[channel], source_ids[source], desired_campaign_id), []
            ).append(opportunity_id)

    order_written = 0
    for (medium_id, source_id, carrier_id, campaign_id), ids in order_groups.items():
        order_written += _write_batches(api, "sale.order", ids, {
            "medium_id": medium_id,
            "source_id": source_id,
            "carrier_id": carrier_id,
            "campaign_id": campaign_id,
        })

    opportunity_written = 0
    for (medium_id, source_id, campaign_id), ids in opportunity_groups.items():
        opportunity_written += _write_batches(api, "crm.lead", ids, {
            "medium_id": medium_id,
            "source_id": source_id,
            "campaign_id": campaign_id,
        })

    # Lost/demo leads không có sale_order: vẫn cần channel để phân tích funnel.
    lead_groups = {}
    lead_rows = pg.all("""
        SELECT id, campaign_id, medium_id, source_id, create_date::date
        FROM crm_lead
        WHERE company_id = %s
          AND name LIKE 'Lead #%%'
        ORDER BY id
    """, [cid])
    for (
        lead_id,
        campaign_id,
        current_medium_id,
        current_source_id,
        lead_date,
    ) in lead_rows:
        if campaign_id and daily_paid_attribution.get(lead_date.isoformat()):
            paid_options = daily_paid_attribution[lead_date.isoformat()]
            desired_campaign_id, channel = paid_options[
                int(lead_id) % len(paid_options)
            ]
        else:
            desired_campaign_id = False
            channel = owned_channels[int(lead_id) % len(owned_channels)]
        source = channel_to_source[channel]
        key = (medium_ids[channel], source_ids[source], desired_campaign_id)
        if (current_medium_id, current_source_id, campaign_id) != (
            medium_ids[channel],
            source_ids[source],
            desired_campaign_id or None,
        ):
            lead_groups.setdefault(key, []).append(lead_id)

    lost_lead_written = 0
    for (medium_id, source_id, campaign_id), ids in lead_groups.items():
        lost_lead_written += _write_batches(api, "crm.lead", ids, {
            "medium_id": medium_id,
            "source_id": source_id,
            "campaign_id": campaign_id,
        })

    picking_groups = {}
    for picking_id, sale_id, current_carrier_id in pg.all("""
        SELECT id, sale_id, carrier_id
        FROM stock_picking
        WHERE company_id = %s
          AND sale_id IS NOT NULL
    """, [cid]):
        carrier_id = carrier_by_order.get(sale_id)
        if carrier_id and current_carrier_id != carrier_id:
            picking_groups.setdefault(carrier_id, []).append(picking_id)

    picking_written = 0
    for carrier_id, ids in picking_groups.items():
        picking_written += _write_batches(
            api,
            "stock.picking",
            ids,
            {"carrier_id": carrier_id},
        )

    log.info(
        "  ✅ Mart coverage repaired: %s SO, %s linked opportunities, "
        "%s standalone leads, %s delivery pickings",
        order_written,
        opportunity_written,
        lost_lead_written,
        picking_written,
    )
    return {
        "orders": order_written,
        "opportunities": opportunity_written,
        "standalone_leads": lost_lead_written,
        "pickings": picking_written,
    }

# ─── PHASE 0.3: OPENING INVENTORY BALANCE ────────────────────────────────────
def p0_opening_inventory(pg, api, ctx, prod_ids) -> int:
    """
    Tồn kho đầu kỳ (Jan 2023) = ~4 tuần tiêu thụ ước tính mỗi SKU, chia cho 4 kho
    khu vực (WEST/EAST/CNTL/SOUT — nơi thực sự phục vụ giao hàng theo region khách
    hàng ở Phase 2). Dùng stock.quant inventory adjustment qua XML-RPC
    (action_apply_inventory) để ORM cập nhật quant đúng cách, KHÔNG raw SQL.
    Chạy TRƯỚC Phase 2 để có tồn kho sẵn khi bắt đầu backfill giao hàng.
    """
    log.info("Phase 0.3 — Opening Inventory Balance (Jan 2023)")
    wh_rows = pg.all("""
        SELECT code, lot_stock_id FROM stock_warehouse
        WHERE code IN ('WEST','EAST','CNTL','SOUT') AND lot_stock_id IS NOT NULL
    """)
    if not wh_rows:
        log.warning("  Không tìm thấy warehouse stock locations — bỏ qua opening inventory")
        return 0

    applied = 0
    for code, loc_id in wh_rows:
        vals_list = [{'product_id': int(pid), 'location_id': int(loc_id),
                      'inventory_quantity': random.randint(CFG["opening_stock_min"], CFG["opening_stock_max"])}
                     for pid in prod_ids]
        quant_ids = []
        for b in batches(vals_list, 200):
            try:
                ids = api._x('stock.quant', 'create', [b])
                quant_ids.extend(ids)
            except Exception as e:
                log.warning(f"  Opening quant create failed {code}: {e}")
        for b in batches(quant_ids, 200):
            try:
                api.call('stock.quant', 'action_apply_inventory', b)
                applied += len(b)
            except Exception as e:
                # action_apply_inventory() returns None, which Odoo's XML-RPC layer can't
                # marshal (allow_none=False) — the DB write still succeeds, this is cosmetic.
                if "cannot marshal None" in str(e):
                    applied += len(b)
                else:
                    log.warning(f"  Apply inventory batch failed {code}: {e}")
        log.info(f"  {code}: {len(quant_ids)} SKUs opening balance applied")

    log.info(f"  ✅ {applied} opening quants applied across {len(wh_rows)} kho khu vực")
    return applied

# ─── PHASE 3: P2P WORKFLOW ────────────────────────────────────────────────────
def p3_purchasing(api, pg, ctx, partners, prod_ids, extra_so_filter="") -> int:
    """
    P2P demand-driven: mỗi tháng nhập bù = replenish_cover_ratio × lượng ĐÃ BÁN
    tháng đó (theo product, từ sale_order_line thật) — thay vì lịch cố định
    ngẫu nhiên. Gom thành PO ~25 dòng/PO, chia ngẫu nhiên cho suppliers.
    Chạy SAU Phase 2 (O2C) vì cần sale_order_line đã có data thật để biết bù gì.

    extra_so_filter: mảnh SQL literal (constant nội bộ, KHÔNG bao giờ nhận input
    từ user) nối thêm vào WHERE — dùng để bù đắp riêng cho 1 tập con đơn hàng, ví
    dụ `AND so.name LIKE 'SR%%'` cho nhu cầu phát sinh thêm từ RFM enrichment
    chạy SAU khi Phase 3 gốc đã bù đắp xong, tránh nhập bù trùng lặp toàn bộ tháng.
    """
    log.info("Phase 3 — Purchasing P2P (demand-driven replenishment)")
    cid   = ctx["cid"]
    supps = partners["suppliers"]
    jnl_b = ctx["jnl"].get("bank") or ctx["jnl"].get("cash")

    cost_rows = pg.all("""
        SELECT pp.id, pt.list_price * 0.75 AS cost
        FROM product_product pp JOIN product_template pt ON pt.id=pp.product_tmpl_id
        WHERE pp.id = ANY(%s)
    """, [prod_ids])
    cost_map = {r[0]: float(r[1] or 50.0) for r in cost_rows}

    # PO mặc định nhận hàng vào kho "WH" (default company warehouse) — KHÔNG phải
    # WEST/EAST/CNTL/SOUT nơi deliveries thực sự rút hàng. Phải set picking_type_id
    # rõ ràng, chia ngẫu nhiên cho 4 kho khu vực, để hàng nhập vào đúng nơi hàng xuất.
    recv_types = pg.all("""
        SELECT sw.code, spt.id FROM stock_picking_type spt
        JOIN stock_warehouse sw ON sw.id = spt.warehouse_id
        WHERE spt.code='incoming' AND sw.code IN ('WEST','EAST','CNTL','SOUT')
    """)
    if not recv_types:
        log.warning("  Không tìm thấy receipt picking type kho khu vực — PO sẽ về kho WH mặc định")

    total_pos = 0

    recv_type_by_wh = {code: tid for code, tid in recv_types}

    # Duyệt theo tháng, bù đắp đúng lượng đã bán tháng đó — PHẢI group theo kho
    # (so.warehouse_id) chứ không phải company-wide, vì hàng bán ra rút đúng kho
    # của SO đó (REGION_WH routing ở p2_create_sos), nhưng PO nhận về CHỈ 1 kho.
    # Trước đây gom demand company-wide rồi route cả lô về 1 kho random → kho khác
    # bị âm tồn kho (physically impossible). Giống pattern đúng ở p4b (group theo
    # (product, warehouse, month)).
    cur = CFG["start"].replace(day=1)
    end_m = CFG["end"].replace(day=1)
    while cur <= end_m:
        nxt = cur.replace(year=cur.year+1, month=1) if cur.month == 12 else cur.replace(month=cur.month+1)

        sold = pg.all(f"""
            SELECT sol.product_id, sw.code AS wh_code, SUM(sol.product_uom_qty) AS qty
            FROM sale_order_line sol
            JOIN sale_order so ON so.id = sol.order_id
            JOIN stock_warehouse sw ON sw.id = so.warehouse_id
            WHERE so.state='sale' AND so.company_id=%s
              AND so.date_order >= %s AND so.date_order < %s
              {extra_so_filter}
            GROUP BY sol.product_id, sw.code HAVING SUM(sol.product_uom_qty) > 0
        """, [cid, cur, nxt])

        by_wh = {}
        for pid, wh_code, qty in sold:
            buy_qty = int(float(qty) * CFG["replenish_cover_ratio"]) + 1
            by_wh.setdefault(wh_code, []).append((pid, buy_qty))

        for wh_code, items in by_wh.items():
            recv_type_id = recv_type_by_wh.get(wh_code)
            if not recv_type_id:
                continue
            random.shuffle(items)
            for chunk in batches(items, 25):
                supp_id = random.choice(supps)
                po_date = cur + timedelta(days=random.randint(1, 8))
                deliv_date = po_date + timedelta(days=random.randint(7, 21))

                lines = []
                for pid, qty in chunk:
                    cost = cost_map.get(pid, 50.0)
                    price = round(jitter(cost, 0.10), 2)
                    lines.append((0, 0, {
                        "product_id": int(pid),
                        "product_qty": qty,
                        "price_unit": price,
                        "date_planned": deliv_date.strftime("%Y-%m-%d %H:%M:%S"),
                    }))

                try:
                    # 1. Tạo PO — route đúng kho đang có nhu cầu (wh_code), không để mặc định về WH
                    po_vals = {
                        "partner_id"  : supp_id,
                        "date_order"  : po_date.strftime("%Y-%m-%d %H:%M:%S"),
                        "company_id"  : cid,
                        "order_line"  : lines,
                    }
                    if recv_type_id:
                        po_vals["picking_type_id"] = recv_type_id
                    po_id = api.create('purchase.order', po_vals)

                    # 2. Confirm PO → ORM tạo stock.picking (Receipt)
                    api.call('purchase.order', 'button_confirm', [po_id])

                    # 3. Validate receipt
                    receipts = api.search('stock.picking',
                        [('purchase_id','=',po_id),('state','not in',['done','cancel'])])
                    if receipts:
                        for rec_id in receipts:
                            # Set qty_done trên moves
                            moves = api.search('stock.move',
                                [('picking_id','=',rec_id),('state','not in',['done','cancel'])])
                            for mv in moves:
                                mv_data = api.read('stock.move',[mv],['product_uom_qty'])[0]
                                try:
                                    api.write('stock.move',[mv],
                                        {'quantity': mv_data['product_uom_qty'], 'picked': True})
                                except: pass
                            try:
                                res = api._x('stock.picking','button_validate',[[rec_id]],
                                       {"context":{"skip_backorder":True,"skip_sms":True,
                                                   "picking_ids_not_to_backorder":[rec_id]}})
                                if res is not True:
                                    log.warning(f"  Receipt {rec_id} returned wizard instead of completing: {res}")
                                # button_validate() stamps date_done to now() — restore the
                                # historical receipt date now that the transfer is complete.
                                # scheduled_date/date_deadline = deliv_date (planned); actual
                                # receipt date is later for the late_delivery % (on-time
                                # delivery rate NCC imperfection per data_dictionary.md).
                                actual_date = deliv_date
                                if random.random() < late_delivery_rate(wh_code):
                                    actual_date = deliv_date + timedelta(days=random.randint(1, 5))
                                pg.q("""
                                    UPDATE stock_picking SET date=%s, date_done=%s,
                                        scheduled_date=%s, date_deadline=%s WHERE id=%s
                                """, [actual_date, actual_date, deliv_date, deliv_date, rec_id])
                                pg.q("UPDATE stock_move SET date=%s, date_deadline=%s WHERE picking_id=%s",
                                     [actual_date, deliv_date, rec_id])
                                pg.commit()
                            except Exception as e:
                                log.warning(f"  Receipt {rec_id} validate: {e}")

                    # 4. Tạo vendor bill
                    try:
                        api.call('purchase.order', 'action_create_invoice', [po_id])
                    except:
                        pass

                    # 5. Post vendor bill
                    bills = api.search('account.move',
                        [('purchase_id','=',po_id),('move_type','=','in_invoice'),
                         ('state','=','draft')])
                    if bills:
                        # Vendor bill date isn't auto-filled on create — required before posting.
                        bill_date = (deliv_date + timedelta(days=random.randint(0,3))).strftime('%Y-%m-%d')
                        try: api.write('account.move', bills, {'invoice_date': bill_date})
                        except: pass
                        try: api.call('account.move','action_post',bills)
                        except Exception as e: log.warning(f"  Bill post failed (PO {po_id}): {e}")

                        # 6. Pay vendor bill
                        for bill_id in bills:
                            try:
                                b_data = api.read('account.move',[bill_id],
                                                  ['amount_total','invoice_date','partner_id'])[0]
                                pay_date_v = (b_data.get('invoice_date') or po_date.strftime('%Y-%m-%d'))
                                if isinstance(pay_date_v, str):
                                    from datetime import datetime as dt2
                                    pay_date_v = dt2.strptime(pay_date_v[:10],'%Y-%m-%d').date()
                                pay_date_v = pay_date_v + timedelta(days=random.randint(15,30))
                                pay_id = api.create('account.payment',{
                                    'payment_type' : 'outbound',
                                    'partner_type' : 'supplier',
                                    'partner_id'   : supp_id,
                                    'amount'       : round(b_data.get('amount_total',0),2),
                                    'journal_id'   : jnl_b,
                                    'date'         : pay_date_v.strftime('%Y-%m-%d'),
                                    'currency_id'  : ctx["cur"],
                                })
                                # Unlike the customer-payment flow (p2_register_payments), this was
                                # never posted/reconciled — vendor bills stayed 'not_paid' forever
                                # despite a payment record existing. action_post() has no return
                                # statement (implicit None) → cosmetic "cannot marshal None".
                                try:
                                    api.call('account.payment', 'action_post', [pay_id])
                                except Exception as e:
                                    if "cannot marshal None" not in str(e):
                                        raise
                                pg.q("UPDATE account_move SET payment_state='paid',amount_residual=0 WHERE id=%s",[bill_id])
                                pg.commit()
                            except Exception as e:
                                log.warning(f"  Vendor payment failed: {e}")

                    total_pos += 1
                except Exception as e:
                    log.warning(f"  PO failed ({cur.strftime('%Y-%m')}): {e}")

        log.info(f"  POs: {total_pos} through {cur.strftime('%Y-%m')}")
        cur = nxt

    log.info(f"  ✅ {total_pos} POs processed (demand-driven, create→confirm→receive→bill→pay)")
    return total_pos

# ─── PHASE 4: MANUFACTURING WORKFLOW ──────────────────────────────────────────
def p4_manufacturing(api, pg, ctx, extra_so_filter="") -> int:
    """
    Manufacturing demand-driven: mỗi tháng tạo MO đủ bù lượng Furniture (có BOM)
    ĐÃ BÁN tháng đó (từ sale_order_line thật) — thay vì lịch cố định ngẫu nhiên.
    Chạy SAU Phase 2 (O2C) vì cần sale_order_line đã có data thật để biết bù gì.

    extra_so_filter: xem docstring `p3_purchasing` — cùng cơ chế bù đắp riêng cho
    1 tập con đơn hàng (ví dụ đơn RFM), literal nội bộ không nhận input ngoài.
    """
    log.info("Phase 4 — Manufacturing (demand-driven, cover Furniture sold)")
    cid = ctx["cid"]

    # Lấy Furniture products có BOM
    bom_data = pg.all("""
        SELECT mb.id AS bom_id, mb.product_tmpl_id, pp.id AS prod_id
        FROM mrp_bom mb
        JOIN product_product pp ON pp.product_tmpl_id = mb.product_tmpl_id
        WHERE mb.type = 'normal' AND pp.active = true
        LIMIT 20
    """)
    if not bom_data:
        log.warning("  Không tìm thấy BOMs — bỏ qua Manufacturing phase")
        log.warning("  Hint: Tạo BOM qua UI hoặc đảm bảo p0_create_boms() đã chạy")
        return 0
    bom_by_product = {prod_id: bom_id for bom_id, tmpl_id, prod_id in bom_data}

    # MO mặc định sản xuất vào kho "WH" (default company warehouse) — KHÔNG phải
    # WEST/EAST/CNTL/SOUT nơi deliveries thực sự rút hàng. Phải set picking_type_id
    # rõ ràng, route ĐÚNG kho đang có nhu cầu (theo so.warehouse_id) — KHÔNG random,
    # cùng bug/fix pattern như p3_purchasing: gộp demand company-wide rồi giao ngẫu
    # nhiên về 1 kho khiến kho khác bị âm tồn kho (physically impossible).
    mfg_types = pg.all("""
        SELECT sw.code, spt.id FROM stock_picking_type spt
        JOIN stock_warehouse sw ON sw.id = spt.warehouse_id
        WHERE spt.code='mrp_operation' AND sw.code IN ('WEST','EAST','CNTL','SOUT')
    """)
    mfg_type_by_wh = {code: tid for code, tid in mfg_types}
    if not mfg_type_by_wh:
        log.warning("  Không tìm thấy MFG picking type kho khu vực — MO sẽ về kho WH mặc định")

    # Odoo's own OEE ledger (mrp_workcenter_productivity + loss types availability/
    # performance/quality/productive) — dùng lại thay vì tự chế bảng mới, để các report OEE
    # built-in của Odoo cũng đọc được dữ liệu này.
    loss_rows = pg.all("SELECT id, loss_type FROM mrp_workcenter_productivity_loss")
    loss_type_by_id = {lid: ltype for lid, ltype in loss_rows}
    avail_loss_ids = [lid for lid, lt in loss_type_by_id.items() if lt == "availability"]
    quality_loss_ids = [lid for lid, lt in loss_type_by_id.items() if lt == "quality"]
    productive_loss_ids = [lid for lid, lt in loss_type_by_id.items() if lt == "productive"]
    productive_loss_id = productive_loss_ids[0] if productive_loss_ids else None

    total_mos = 0

    cur = CFG["start"].replace(day=1)
    end_m = CFG["end"].replace(day=1)
    while cur <= end_m:
        nxt = cur.replace(year=cur.year+1, month=1) if cur.month == 12 else cur.replace(month=cur.month+1)

        sold = pg.all(f"""
            SELECT sol.product_id, sw.code AS wh_code, SUM(sol.product_uom_qty) AS qty
            FROM sale_order_line sol
            JOIN sale_order so ON so.id = sol.order_id
            JOIN stock_warehouse sw ON sw.id = so.warehouse_id
            WHERE so.state='sale' AND so.company_id=%s
              AND so.date_order >= %s AND so.date_order < %s
              AND sol.product_id = ANY(%s)
              {extra_so_filter}
            GROUP BY sol.product_id, sw.code HAVING SUM(sol.product_uom_qty) > 0
        """, [cid, cur, nxt, list(bom_by_product.keys())])

        for prod_id, wh_code, qty_sold in sold:
            bom_id = bom_by_product[prod_id]
            mfg_type_id = mfg_type_by_wh.get(wh_code)
            if mfg_type_by_wh and not mfg_type_id:
                continue  # wh_code lạ (không phải WEST/EAST/CNTL/SOUT) — bỏ qua thay vì route sai kho
            qty = int(float(qty_sold) * CFG["replenish_cover_ratio"]) + 1
            plan_start = cur + timedelta(days=random.randint(1, 20))
            # NOTE: `date + timedelta(hours=N)` silently truncates to whole days in Python
            # (date.__add__ only reads .days, ignores the time component) — anchor to a real
            # datetime so the workorder-level cursor arithmetic below actually advances by
            # minutes/hours instead of collapsing to midnight.
            plan_start_dt = datetime.combine(plan_start, datetime.min.time().replace(hour=8))

            try:
                # 1. Tạo Manufacturing Order — route đúng kho đang có nhu cầu (wh_code)
                mo_vals = {
                    "product_id"          : int(prod_id),
                    "bom_id"              : int(bom_id),
                    "product_qty"         : float(qty),
                    "date_start"          : plan_start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "company_id"          : cid,
                }
                if mfg_type_id:
                    mo_vals["picking_type_id"] = mfg_type_id
                mo_id = api.create('mrp.production', mo_vals)

                # 2. Confirm MO → ORM tạo stock moves cho NVL
                api.call('mrp.production', 'action_confirm', [mo_id])

                # 3. Set qty_producing
                try:
                    api.write('mrp.production', [mo_id], {'qty_producing': float(qty)})
                except: pass

                # 4. Complete Work Orders (nếu có) — duration neo theo duration_expected
                # (Performance OEE) thay vì random rời rạc như trước (khiến hiệu suất trung
                # bình chỉ ~9.6% kế hoạch, vô nghĩa để phân tích OEE).
                wos = api.search('mrp.workorder',
                    [('production_id','=',mo_id),('state','not in',['done','cancel'])])
                wo_meta = {}
                if wos:
                    wo_rows = pg.all(
                        "SELECT id, duration_expected, workcenter_id FROM mrp_workorder WHERE id = ANY(%s)",
                        [wos])
                    wo_meta = {wid: {"expected": float(dexp or 60.0), "workcenter_id": wcid}
                               for wid, dexp, wcid in wo_rows}
                wo_actual = {}
                for wo_id in wos:
                    expected = wo_meta.get(wo_id, {}).get("expected", 60.0)
                    perf_factor = (random.uniform(1.4, 2.2) if random.random() < 0.06
                                   else random.uniform(0.85, 1.35))
                    actual_duration = max(5.0, expected * perf_factor)
                    try:
                        api.write('mrp.workorder',[wo_id], {'duration': actual_duration})
                    except Exception as e:
                        log.warning(f"  WorkOrder {wo_id} duration write: {e}")
                        continue
                    # button_start()/button_finish() return None, which Odoo's XML-RPC layer
                    # can't marshal (allow_none=False) — the DB write still succeeds, this is
                    # cosmetic (same class as action_apply_inventory() above). Record
                    # wo_actual regardless so the workorder still gets its historical dates +
                    # OEE loss blocks restored below; only a genuine (non-marshalling) failure
                    # should drop it from that.
                    try:
                        api.call('mrp.workorder','button_start',[wo_id])
                    except Exception as e:
                        if "cannot marshal None" not in str(e):
                            log.warning(f"  WorkOrder {wo_id} button_start: {e}")
                            continue
                    try:
                        api.call('mrp.workorder','button_finish',[wo_id])
                    except Exception as e:
                        if "cannot marshal None" not in str(e):
                            log.warning(f"  WorkOrder {wo_id} button_finish: {e}")
                            continue
                    wo_actual[wo_id] = actual_duration

                # 5. Set component quantities — raw material consumption moves are linked via
                # raw_material_production_id, NOT production_id (that's for the finished-goods move)
                try:
                    moves = api.search('stock.move',
                        [('raw_material_production_id','=',mo_id),('state','not in',['done','cancel'])])
                    for mv in moves:
                        mv_d = api.read('stock.move',[mv],['product_uom_qty'])[0]
                        api.write('stock.move',[mv],
                                  {'quantity':mv_d['product_uom_qty'], 'picked': True})
                except: pass

                # 6. Validate MO → ORM: tiêu thụ NVL + nhập thành phẩm
                # button_mark_done() returns a wizard action (consumption/backorder) instead of
                # raising when component quantities don't line up exactly — skip both via context.
                try:
                    res = api._x('mrp.production', 'button_mark_done', [[mo_id]],
                                  {"context": {"skip_consumption": True, "skip_backorder": True}})
                    if res is not True:
                        raise RuntimeError(f"button_mark_done returned a wizard instead of completing: {res}")
                    total_mos += 1

                    # workorder.button_start()/button_finish() stamp date_start/date_finished
                    # (both on mrp.production AND mrp.workorder, plus the auto-created
                    # mrp_workcenter_productivity block) to now() — same "actual vs planned"
                    # reset pattern as sale.order.date_order. Re-anchor everything to the
                    # historical plan_start_dt, walking each workorder in sequence so total
                    # elapsed time is internally consistent with the sum of actual durations
                    # (+ changeover gaps), and inject Availability/Quality loss blocks into
                    # Odoo's own OEE ledger for a subset of workorders — so OEE Availability/
                    # Performance/Quality are all analyzable instead of 100% "Fully Productive
                    # Time" clustered on today's date.
                    cursor = plan_start_dt
                    wo_date_rows = []
                    prod_inserts = []
                    now_ts = datetime.now()
                    for wo_id, actual_dur in wo_actual.items():
                        wc_id = wo_meta.get(wo_id, {}).get("workcenter_id")
                        wo_start = cursor
                        if avail_loss_ids and random.random() < 0.10:
                            dur = random.uniform(15, 90)
                            b_end = cursor + timedelta(minutes=dur)
                            if wc_id:
                                lid = random.choice(avail_loss_ids)
                                prod_inserts.append((wc_id, wo_id, lid, loss_type_by_id[lid], cursor, b_end, dur))
                            cursor = b_end
                        if quality_loss_ids and random.random() < 0.04:
                            dur = random.uniform(10, 40)
                            b_end = cursor + timedelta(minutes=dur)
                            if wc_id:
                                lid = random.choice(quality_loss_ids)
                                prod_inserts.append((wc_id, wo_id, lid, loss_type_by_id[lid], cursor, b_end, dur))
                            cursor = b_end
                        wo_end = cursor + timedelta(minutes=actual_dur)
                        if wc_id and productive_loss_id:
                            prod_inserts.append((wc_id, wo_id, productive_loss_id, "productive",
                                                  cursor, wo_end, actual_dur))
                        wo_date_rows.append((wo_id, wo_start, wo_end))
                        cursor = wo_end + timedelta(minutes=random.uniform(5, 20))  # changeover

                    finish_dt = wo_date_rows[-1][2] if wo_date_rows else \
                        plan_start_dt + timedelta(hours=random.randint(4, 48))

                    for wid, ws, we in wo_date_rows:
                        pg.q("UPDATE mrp_workorder SET date_start=%s, date_finished=%s WHERE id=%s",
                             [ws, we, wid])
                    if wo_date_rows:
                        pg.q("DELETE FROM mrp_workcenter_productivity WHERE workorder_id = ANY(%s)",
                             [[w[0] for w in wo_date_rows]])
                    for wc_id, wo_id, lid, ltype, b_start, b_end, dur in prod_inserts:
                        pg.q("""INSERT INTO mrp_workcenter_productivity
                                (workcenter_id, company_id, workorder_id, loss_id, loss_type,
                                 user_id, date_start, date_end, duration,
                                 create_uid, write_uid, create_date, write_date)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                             [wc_id, cid, wo_id, lid, ltype, ctx["uid"],
                              b_start, b_end, dur, ctx["uid"], ctx["uid"], now_ts, now_ts])

                    pg.q("""UPDATE mrp_production SET date_start=%s, date_finished=%s
                            WHERE id=%s""", [plan_start_dt, finish_dt, mo_id])
                    pg.q("""UPDATE stock_move SET date=%s
                            WHERE raw_material_production_id=%s OR production_id=%s""",
                         [finish_dt, mo_id, mo_id])
                    pg.commit()
                except Exception as e:
                    log.warning(f"  MO {mo_id} validate failed: {e}")

            except Exception as e:
                log.warning(f"  MO creation failed ({cur.strftime('%Y-%m')}): {e}")

        log.info(f"  MOs: {total_mos} through {cur.strftime('%Y-%m')}")
        cur = nxt

    log.info(f"  ✅ {total_mos} MOs completed (demand-driven, create→confirm→workorders→validate)")
    return total_mos

# ─── PHASE 4C: QUALITY SCRAP ──────────────────────────────────────────────────
def p4c_quality_scrap(api, pg, ctx, wo_id_filter=None) -> int:
    """
    Tạo stock.scrap thật cho các work order có quality loss block
    (mrp_workcenter_productivity.loss_type='quality', ~4% work order) — trước đây
    quality loss chỉ mô phỏng bằng THỜI GIAN xử lý lỗi, KHÔNG có số lượng phế phẩm
    thật, nên không tính được Quality = (qty_produced-scrap_qty)/qty_produced cho OEE.

    scrap_qty = 10-35% của qty_produced work order đó (tối thiểu 1) — vì chỉ ~4% WO
    có quality issue, defect rate tổng công ty sẽ ở mức thấp (~1%), dưới target <1.5%.

    wo_id_filter: list mrp_workorder.id để giới hạn phạm vi — dùng khi backfill cho
    work order đã tồn tại từ trước (không phải lần chạy hiện tại). Mặc định None =
    xử lý mọi work order quality-loss chưa có scrap (idempotent qua NOT EXISTS).
    """
    log.info("Phase 4c — Quality Scrap (tạo dữ liệu phế phẩm thật cho work order có quality loss)")
    cid = ctx["cid"]

    extra = ""
    params = []
    if wo_id_filter is not None:
        extra = "AND wo.id = ANY(%s)"
        params.append(wo_id_filter)

    candidates = pg.all(f"""
        SELECT DISTINCT wo.id, wo.production_id, mp.product_id, mp.name, wo.qty_produced,
               wo.date_finished
        FROM mrp_workorder wo
        JOIN mrp_production mp ON mp.id = wo.production_id
        JOIN mrp_workcenter_productivity p ON p.workorder_id = wo.id
        WHERE p.loss_type='quality' AND wo.state='done'
          AND NOT EXISTS (SELECT 1 FROM stock_scrap sc WHERE sc.workorder_id = wo.id)
          {extra}
    """, params)

    total = 0
    for wo_id, mo_id, prod_id, mo_name, qty_produced, wo_date in candidates:
        qty_produced = float(qty_produced or 0)
        if qty_produced < 1:
            continue
        scrap_qty = max(1, round(qty_produced * random.uniform(0.10, 0.35)))
        try:
            scrap_id = api.create('stock.scrap', {
                "product_id"    : int(prod_id),
                "production_id" : int(mo_id),
                "workorder_id"  : int(wo_id),
                "scrap_qty"     : float(scrap_qty),
                "origin"        : mo_name,
                "company_id"    : cid,
            })
            res = api.call('stock.scrap', 'action_validate', [scrap_id])
            if res is not True:
                log.warning(f"  Scrap {scrap_id} (WO {wo_id}) returned wizard instead of completing: {res}")
                continue
            # action_validate() stamps date_done to now() — restore historical date
            # matching the work order's actual completion date (same "planned vs
            # actual" reset pattern used everywhere else in this script).
            pg.q("UPDATE stock_scrap SET date_done=%s WHERE id=%s", [wo_date, scrap_id])
            pg.q("UPDATE stock_move SET date=%s WHERE scrap_id=%s", [wo_date, scrap_id])
            pg.commit()
            total += 1
        except Exception as e:
            log.warning(f"  Scrap failed for WO {wo_id}: {e}")

    log.info(f"  ✅ {total} scrap records created (quality defects)")
    return total

# ─── PHASE 4B: RAW MATERIAL REPLENISHMENT ────────────────────────────────────
def p4b_raw_material_replenishment(api, pg, ctx, partners, rm_ids, mo_id_filter=None) -> int:
    """
    Bù nguyên vật liệu (raw materials) đã bị Manufacturing Orders tiêu thụ.
    Chạy SAU Phase 4 vì cần biết MO đã tiêu thụ NVL nào/bao nhiêu/kho nào/tháng nào
    (từ stock_move.raw_material_production_id thật) — không thể biết trước khi
    MFG chạy xong. Gom theo (kho, tháng) thành 1 PO nhiều dòng, giống P2P thành phẩm.

    mo_id_filter: list các mrp_production.id để giới hạn phạm vi tính tiêu thụ —
    KHÁC với `extra_so_filter` ở p3/p4 vì hàm này tính theo stock_move (đã tiêu
    thụ), không theo tên đơn hàng. Bắt buộc dùng nếu gọi hàm này LẦN THỨ HAI trở
    đi (ví dụ sau khi RFM tạo thêm MO mới) — nếu không sẽ tính lại TOÀN BỘ tiêu
    thụ lịch sử (kể cả phần đã bù đắp ở lần gọi trước) và mua bù trùng lặp.
    """
    log.info("Phase 4b — Raw Material Replenishment (cover MFG consumption)")
    cid   = ctx["cid"]
    supps = partners["suppliers"]
    jnl_b = ctx["jnl"].get("bank") or ctx["jnl"].get("cash")

    rm_pids = list(rm_ids.values())
    cost_rows = pg.all("""
        SELECT pp.id, pt.list_price FROM product_product pp
        JOIN product_template pt ON pt.id=pp.product_tmpl_id
        WHERE pp.id = ANY(%s)
    """, [rm_pids])
    cost_map = {r[0]: float(r[1] or 20.0) for r in cost_rows}

    recv_types = pg.all("""
        SELECT sw.code, spt.id FROM stock_picking_type spt
        JOIN stock_warehouse sw ON sw.id = spt.warehouse_id
        WHERE spt.code='incoming' AND sw.code IN ('WEST','EAST','CNTL','SOUT')
    """)
    recv_type_by_wh = {code: tid for code, tid in recv_types}
    if not recv_type_by_wh:
        log.warning("  Không tìm thấy receipt picking type kho khu vực — bỏ qua RM replenishment")
        return 0

    extra = ""
    params = [rm_pids]
    if mo_id_filter is not None:
        extra = "AND sm.raw_material_production_id = ANY(%s)"
        params.append(mo_id_filter)
    consumed = pg.all(f"""
        SELECT sm.product_id, sw.code AS wh_code,
               date_trunc('month', sm.date)::date AS month,
               SUM(sm.product_uom_qty) AS qty
        FROM stock_move sm
        JOIN stock_location sl ON sl.id = sm.location_id
        JOIN stock_warehouse sw ON sw.id = sl.warehouse_id
        WHERE sm.raw_material_production_id IS NOT NULL AND sm.state='done'
          AND sm.product_id = ANY(%s)
          {extra}
        GROUP BY sm.product_id, sw.code, date_trunc('month', sm.date)
        HAVING SUM(sm.product_uom_qty) > 0
    """, params)

    grouped = {}
    for pid, wh_code, month, qty in consumed:
        grouped.setdefault((wh_code, month), []).append((pid, float(qty)))

    total_pos = 0
    for (wh_code, month), items in grouped.items():
        recv_type = recv_type_by_wh.get(wh_code)
        if not recv_type:
            continue
        supp_id = random.choice(supps)
        po_date = month  # đầu tháng tiêu thụ — bù trước khi MO trong tháng đó "tiêu thụ"
        deliv_date = po_date + timedelta(days=random.randint(3, 10))

        lines = []
        for pid, qty in items:
            buy_qty = int(qty * CFG["replenish_cover_ratio"]) + 1
            cost = cost_map.get(pid, 20.0)
            price = round(jitter(cost, 0.10), 2)
            lines.append((0, 0, {
                "product_id": int(pid),
                "product_qty": buy_qty,
                "price_unit": price,
                "date_planned": deliv_date.strftime("%Y-%m-%d %H:%M:%S"),
            }))

        try:
            po_id = api.create('purchase.order', {
                "partner_id"      : supp_id,
                "date_order"      : po_date.strftime("%Y-%m-%d %H:%M:%S"),
                "company_id"      : cid,
                "picking_type_id" : recv_type,
                "order_line"      : lines,
            })
            api.call('purchase.order', 'button_confirm', [po_id])

            receipts = api.search('stock.picking',
                [('purchase_id','=',po_id),('state','not in',['done','cancel'])])
            for rec_id in receipts:
                moves = api.search('stock.move',
                    [('picking_id','=',rec_id),('state','not in',['done','cancel'])])
                for mv in moves:
                    mv_data = api.read('stock.move',[mv],['product_uom_qty'])[0]
                    try:
                        api.write('stock.move',[mv],
                            {'quantity': mv_data['product_uom_qty'], 'picked': True})
                    except: pass
                try:
                    res = api._x('stock.picking','button_validate',[[rec_id]],
                           {"context":{"skip_backorder":True,"skip_sms":True,
                                       "picking_ids_not_to_backorder":[rec_id]}})
                    if res is not True:
                        log.warning(f"  RM Receipt {rec_id} returned wizard instead of completing: {res}")
                    actual_date = deliv_date
                    if random.random() < late_delivery_rate(wh_code):
                        actual_date = deliv_date + timedelta(days=random.randint(1, 5))
                    pg.q("""
                        UPDATE stock_picking SET date=%s, date_done=%s,
                            scheduled_date=%s, date_deadline=%s WHERE id=%s
                    """, [actual_date, actual_date, deliv_date, deliv_date, rec_id])
                    pg.q("UPDATE stock_move SET date=%s, date_deadline=%s WHERE picking_id=%s",
                         [actual_date, deliv_date, rec_id])
                    pg.commit()
                except Exception as e:
                    log.warning(f"  RM Receipt {rec_id} validate: {e}")

            try:
                api.call('purchase.order', 'action_create_invoice', [po_id])
            except: pass

            bills = api.search('account.move',
                [('purchase_id','=',po_id),('move_type','=','in_invoice'),('state','=','draft')])
            if bills:
                bill_date = (deliv_date + timedelta(days=random.randint(0,3))).strftime('%Y-%m-%d')
                try: api.write('account.move', bills, {'invoice_date': bill_date})
                except: pass
                try: api.call('account.move','action_post',bills)
                except Exception as e: log.warning(f"  RM Bill post failed (PO {po_id}): {e}")

                for bill_id in bills:
                    try:
                        b_data = api.read('account.move',[bill_id],
                                          ['amount_total','invoice_date'])[0]
                        pay_date_v = (b_data.get('invoice_date') or po_date.strftime('%Y-%m-%d'))
                        if isinstance(pay_date_v, str):
                            pay_date_v = datetime.strptime(pay_date_v[:10],'%Y-%m-%d').date()
                        pay_date_v = pay_date_v + timedelta(days=random.randint(15,30))
                        pay_id = api.create('account.payment',{
                            'payment_type' : 'outbound',
                            'partner_type' : 'supplier',
                            'partner_id'   : supp_id,
                            'amount'       : round(b_data.get('amount_total',0),2),
                            'journal_id'   : jnl_b,
                            'date'         : pay_date_v.strftime('%Y-%m-%d'),
                            'currency_id'  : ctx["cur"],
                        })
                        # See p3_purchasing: action_post() has no return statement (implicit
                        # None) → cosmetic "cannot marshal None"; without posting, the vendor
                        # bill stayed 'not_paid' forever despite the payment record existing.
                        try:
                            api.call('account.payment', 'action_post', [pay_id])
                        except Exception as e:
                            if "cannot marshal None" not in str(e):
                                raise
                        pg.q("UPDATE account_move SET payment_state='paid',amount_residual=0 WHERE id=%s",[bill_id])
                        pg.commit()
                    except Exception as e:
                        log.warning(f"  RM Vendor payment failed: {e}")

            total_pos += 1
        except Exception as e:
            log.warning(f"  RM PO failed ({wh_code}, {month.strftime('%Y-%m')}): {e}")

    log.info(f"  ✅ {total_pos} raw material replenishment POs processed ({len(grouped)} (kho,tháng) combos)")
    return total_pos

# ─── PHASE 5: VERIFY ──────────────────────────────────────────────────────────
def verify_all(pg, ctx):
    log.info("\n═══ VERIFICATION ═══")
    cid = ctx["cid"]
    checks = [
        ("sale_order",       "state='sale' AND company_id=%s",               "SOs confirmed"),
        ("sale_order_line",  "order_id IN (SELECT id FROM sale_order WHERE state='sale' AND company_id=%s)","SO Lines"),
        ("stock_picking",    "state='done' AND company_id=%s",               "Pickings done"),
        ("stock_move",       "state='done' AND company_id=%s",               "Moves done"),
        ("stock_quant",      "quantity>0 AND company_id=%s",                 "Stock positions"),
        ("account_move",     "move_type='out_invoice' AND state='posted' AND company_id=%s","Customer Invoices"),
        ("account_move_line","company_id=%s AND move_id IN (SELECT id FROM account_move WHERE state='posted')", "Journal Lines"),
        ("account_payment",  "state IN ('in_process','paid') AND company_id=%s","Payments"),
        ("purchase_order",   "state IN ('purchase','done') AND company_id=%s","Purchase Orders"),
        ("account_move",     "move_type='in_invoice' AND state='posted' AND company_id=%s", "Vendor Bills"),
        ("mrp_production",   "state='done' AND company_id=%s",               "MOs completed"),
        ("mrp_workorder",    "state='done' AND production_id IN (SELECT id FROM mrp_production WHERE company_id=%s)", "Work Orders done"),
        ("hr_employee",      "active=true AND company_id=%s",                "Employees"),
        ("hr_contract",      "company_id=%s",                                "Contracts (SCD2)"),
        ("utm_campaign",     "company_id=%s",                                "UTM Campaigns"),
    ]
    log.info(f"{'Item':<30} {'Count':>10}  Status")
    log.info("─"*50)
    for table, where, label in checks:
        try:
            r = pg.one(f"SELECT COUNT(*) FROM {table} WHERE {where}", [cid])
            n = r[0] if r else 0
            st = "✅" if n>0 else "⚠️ EMPTY"
            log.info(f"  {label:<28} {n:>10,}  {st}")
        except Exception as e:
            pg.rollback()  # a failed query aborts the transaction — must reset before the next check
            log.info(f"  {label:<28} {'ERR':>10}  ⚠️ {e}")
    log.info("─"*50)

# ─── MAIN ────────────────────────────────────────────────────────────────────
def run():
    if fake is None or np is None:
        raise RuntimeError(
            "Full generator cần faker và numpy. Cài requirements hoặc dùng "
            "target repair-mart-data của odoo_dev/makefile cho nhánh repair."
        )
    log.info("═══ SUPERSTORE DATA GENERATOR v3 — FULL WORKFLOW ═══")
    t0 = time.time()
    api = OdooAPI()
    pg  = PG()
    ctx = load_context(pg, api)

    try:
        # Phase 0: Prerequisites (raw materials only — BOMs need products from Phase 1 first)
        log.info("\n══ PHASE 0: Prerequisites ══")
        rm_ids  = p0_raw_materials(pg, api, ctx)

        # Phase 1: SQL Master Data
        log.info("\n══ PHASE 1: Master Data (SQL) ══")
        utm      = p1_utm(pg, ctx)
        cats     = p1_categories(pg, ctx)
        prod_ids = p1_products(pg, api, ctx, cats)
        partners = p1_partners(pg, ctx)
        emp_ids  = p1_employees(pg, ctx)

        # Phase 0.2: BOMs (needs Furniture products to exist)
        bom_ids = p0_create_boms(pg, api, ctx, rm_ids)

        # Phase 0.3: Opening inventory balance (needs stock before any delivery/MO consumes it)
        p0_opening_inventory(pg, api, ctx, prod_ids + list(rm_ids.values()))

        # Phase 2: O2C Full Workflow
        log.info("\n══ PHASE 2: O2C Workflow (XML-RPC) ══")
        so_list      = p2_create_sos(api, pg, ctx, partners, prod_ids, utm)
        conf_ids, _  = p2_confirm_orders(api, pg, so_list)
        p2_validate_deliveries(api, pg, ctx, conf_ids)
        inv_ids      = p2_create_and_post_invoices(api, pg, ctx, conf_ids)
        p2_register_payments(api, pg, ctx, inv_ids)

        # Phase 2b: CRM Leads (needs Phase 2's sale_order data for Won leads)
        log.info("\n══ PHASE 2b: CRM Leads (XML-RPC) ══")
        p2b_crm_leads(api, pg, ctx)

        # Phase 2c: enrich các khóa phân tích mà dữ liệu mô phỏng cũ để trống.
        # Chạy sau CRM để sale_order và opportunity nhận cùng một attribution.
        log.info("\n══ PHASE 2c: Mart Source Coverage (XML-RPC) ══")
        p2c_repair_mart_source_data(api, pg, ctx)

        # Phase 3: P2P demand-driven replenishment (needs Phase 2's sale_order_line data)
        log.info("\n══ PHASE 3: P2P Workflow (XML-RPC, demand-driven) ══")
        p3_purchasing(api, pg, ctx, partners, prod_ids)

        # Phase 4: Manufacturing demand-driven (needs Phase 2's sale_order_line data)
        log.info("\n══ PHASE 4: Manufacturing Workflow (XML-RPC, demand-driven) ══")
        p4_manufacturing(api, pg, ctx)

        # Phase 4b: Raw material replenishment (needs Phase 4's MO consumption data)
        log.info("\n══ PHASE 4b: Raw Material Replenishment (XML-RPC) ══")
        p4b_raw_material_replenishment(api, pg, ctx, partners, rm_ids)

        # Phase 4c: Quality scrap (needs Phase 4's quality-loss work orders)
        log.info("\n══ PHASE 4c: Quality Scrap (XML-RPC) ══")
        p4c_quality_scrap(api, pg, ctx)

        # Verify
        verify_all(pg, ctx)

        elapsed = round((time.time()-t0)/60, 1)
        log.info(f"\n═══ HOÀN THÀNH trong {elapsed} phút ═══")
        log.info("Bước tiếp:")
        log.info("  1. python superstore_rfm_customer_behaviors.py")
        log.info("  2. python superstore_marketing_data_generator.py --all")
        log.info("  3. Setup Debezium + dbt + Snowflake")

    except Exception as e:
        pg.rollback()
        log.error(f"Lỗi nghiêm trọng: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
    finally:
        pg.close()


def repair_crm_only():
    """Backfill link/ngày CRM do generator cũ bỏ trống, không sinh record mới."""
    log.info("═══ CRM REPAIR ONLY ═══")
    pg = PG()
    try:
        # Nhánh repair chỉ chạy các UPDATE có điều kiện ở đầu p2b_crm_leads;
        # không gọi Odoo ORM và không tạo thêm lead/opportunity.
        ctx = load_context(pg, api=None)
        # Empty scope: phần repair ở đầu p2b vẫn chạy; phần create Won/Lost = 0.
        p2b_crm_leads(api=None, pg=pg, ctx=ctx, so_id_filter=[])
        log.info("✅ CRM repair hoàn tất; không tạo thêm lead/opportunity")
    except Exception:
        pg.rollback()
        raise
    finally:
        pg.close()


def repair_mart_data_only():
    """Backfill UTM/channel/carrier qua Odoo ORM, không sinh order/lead mới."""
    log.info("═══ MART SOURCE DATA REPAIR ONLY ═══")
    api = OdooAPI()
    pg = PG()
    try:
        ctx = load_context(pg, api)
        result = p2c_repair_mart_source_data(api, pg, ctx)
        log.info("✅ Mart source repair hoàn tất: %s", result)
    except Exception:
        pg.rollback()
        raise
    finally:
        pg.close()


if __name__ == "__main__":
    if "--repair-crm" in sys.argv:
        repair_crm_only()
    elif "--repair-mart-data" in sys.argv:
        repair_mart_data_only()
    else:
        run()
