"""
superstore_rfm_customer_behaviors.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Bổ sung hành vi khách hàng tự nhiên để phân tích RFM có ý nghĩa.

VẤN ĐỀ với generator gốc:
  - Orders phân bổ random → mọi khách trông giống nhau
  - Không có lifecycle pattern → RFM chỉ ra 1 segment duy nhất
  - Không có churn / reactivation → không phân biệt được Lost vs Active

GIẢI PHÁP:
  - Gán 12 "lifecycle profile" cho mỗi customer khi tạo
  - Mỗi profile có số orders, AOV, active years khác nhau
  - Pattern thay đổi tự nhiên theo từng năm (2023→2026)
  - Kết quả: RFM phân tán thực tế thay vì cụm ở 1 điểm

CHẠY:
  python superstore_rfm_customer_behaviors.py

  Hoặc import vào generator chính:
  from superstore_rfm_customer_behaviors import assign_profiles, generate_rfm_orders
"""

import psycopg2
import psycopg2.extras
import random
import numpy as np
from datetime import datetime, timedelta, date
from faker import Faker
import logging

# Tái sử dụng pipeline O2C + replenishment ĐÃ VALIDATE từ generator chính thay vì
# tự viết lại bằng raw SQL — raw SQL không tự tạo đúng state machine của Odoo
# (thiếu stock.picking/account.move khiến đơn "sale"/"invoiced" không khớp thực
# tế: không xuất kho, không có invoice thật — vi phạm nguyên tắc tồn kho=Σmove).
try:
    from superstore_data_generator import (
        OdooAPI, PG, load_context, REGIONS, REGION_WH,
        p2_confirm_orders, p2_validate_deliveries,
        p2_create_and_post_invoices, p2_register_payments,
        p3_purchasing, p4_manufacturing, p4b_raw_material_replenishment,
    )
except ImportError:
    from scripts.superstore_data_generator import (
        OdooAPI, PG, load_context, REGIONS, REGION_WH,
        p2_confirm_orders, p2_validate_deliveries,
        p2_create_and_post_invoices, p2_register_payments,
        p3_purchasing, p4_manufacturing, p4b_raw_material_replenishment,
    )

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

fake = Faker("en_US")
random.seed(2025)
np.random.seed(2025)

DB_CONFIG = dict(dbname="superstore_erp", user="odoo", host="localhost", port=5432)

# ─────────────────────────────────────────────────────────────────────────────
# 12 LIFECYCLE PROFILES — Bản đồ hành vi khách hàng theo thời gian
# ─────────────────────────────────────────────────────────────────────────────
#
# orders_by_year: số đơn (min, max) mỗi năm
# aov_range: khoảng AOV (Average Order Value) theo năm
# Chú ý: "at_risk" giảm dần, "new_customer" chỉ xuất hiện cuối, "reactivated" có gap
#
# Phân phối thiết kế (tổng ~100%):
#   champions 8% tạo 35% revenue → giống Pareto
#   lost 16% tạo <1% revenue → chủ yếu là noise

PROFILES = {
    # ── NHÓM 1: ACTIVE & HIGH VALUE ──────────────────────────────────────────
    "champion": {
        "label": "Champions",
        "pct": 0.07,            # 7% customers (rescaled — 13 profiles originally summed to 1.10)
        "orders_by_year": {
            2023: (8, 14),      # Mua nhiều từ đầu
            2024: (10, 16),     # Tăng dần
            2025: (12, 20),
            2026: (14, 22),     # Đỉnh cao nhất
        },
        "aov_by_year": {
            2023: (600,  2000),
            2024: (700,  2200),
            2025: (750,  2500),
            2026: (800,  2800), # AOV tăng theo năm (upsell thành công)
        },
        "description": "Mua gần đây, rất thường xuyên, giá trị cao nhất",
        "rfm_target": "R=5 F=5 M=5 → Champions",
        "active_in": [2023, 2024, 2025, 2026],
        "last_purchase_window": (1, 30),   # Mua trong vòng 30 ngày
    },

    "loyal": {
        "label": "Loyal Customers",
        "pct": 0.10,
        "orders_by_year": {
            2023: (4, 8),
            2024: (4, 8),
            2025: (4, 9),
            2026: (5, 9),       # Tăng nhẹ nhưng ổn định
        },
        "aov_by_year": {
            2023: (350, 900),
            2024: (360, 950),
            2025: (380, 1000),
            2026: (400, 1050),
        },
        "description": "Mua đều đặn mỗi năm, giá trị ổn định",
        "rfm_target": "R=4-5 F=4-5 M=3-5 → Loyal",
        "active_in": [2023, 2024, 2025, 2026],
        "last_purchase_window": (1, 90),
    },

    # ── NHÓM 2: GROWING / POTENTIAL ──────────────────────────────────────────
    "potential_loyalist": {
        "label": "Potential Loyalists",
        "pct": 0.08,
        "orders_by_year": {
            2023: (0, 0),       # Chưa là khách
            2024: (1, 2),       # Lần đầu mua
            2025: (2, 4),       # Bắt đầu quen thuộc
            2026: (3, 6),       # Đang tăng trưởng
        },
        "aov_by_year": {
            2023: (0, 0),
            2024: (200, 600),
            2025: (250, 700),
            2026: (300, 800),
        },
        "description": "Khách mới 2024-2025, đang tăng tần suất",
        "rfm_target": "R=4-5 F=2-3 M=2-3 → Potential Loyalists",
        "active_in": [2024, 2025, 2026],
        "last_purchase_window": (30, 120),
    },

    "promising": {
        "label": "Promising",
        "pct": 0.06,
        "orders_by_year": {
            2023: (0, 0),
            2024: (0, 0),
            2025: (1, 2),
            2026: (2, 4),       # Mới nhưng đang tích cực
        },
        "aov_by_year": {
            2023: (0, 0),
            2024: (0, 0),
            2025: (150, 500),
            2026: (200, 600),
        },
        "description": "Khách rất mới (2025-2026), đang thăm dò",
        "rfm_target": "R=4-5 F=1-2 M=1-2 → Promising",
        "active_in": [2025, 2026],
        "last_purchase_window": (30, 180),
    },

    "new_2026": {
        "label": "New Customers",
        "pct": 0.05,
        "orders_by_year": {
            2023: (0, 0),
            2024: (0, 0),
            2025: (0, 0),
            2026: (1, 2),       # Chỉ xuất hiện trong 2026
        },
        "aov_by_year": {
            2023: (0, 0),
            2024: (0, 0),
            2025: (0, 0),
            2026: (100, 450),
        },
        "description": "Mới mua lần đầu trong năm 2026",
        "rfm_target": "R=5 F=1 M=1 → New Customers",
        "active_in": [2026],
        "last_purchase_window": (1, 60),
    },

    # ── NHÓM 3: AT RISK / DECLINING ──────────────────────────────────────────
    "at_risk": {
        "label": "At Risk",
        "pct": 0.09,
        "orders_by_year": {
            2023: (6, 10),      # Từng rất tích cực
            2024: (3, 6),       # Bắt đầu giảm
            2025: (1, 3),       # Giảm mạnh
            2026: (0, 1),       # Gần như không mua
        },
        "aov_by_year": {
            2023: (400, 1200),
            2024: (350, 1000),
            2025: (300, 800),
            2026: (200, 600),   # AOV cũng giảm
        },
        "description": "Từng loyal 2023, đang giảm dần — cần win-back",
        "rfm_target": "R=2-3 F=3-4 M=3-4 → At Risk",
        "active_in": [2023, 2024, 2025],  # 2026 chỉ thi thoảng
        "last_purchase_window": (120, 365),
    },

    "cant_lose": {
        "label": "Cant Lose Them",
        "pct": 0.04,
        "orders_by_year": {
            2023: (10, 18),     # Top spender, rất tích cực
            2024: (5, 10),      # Giảm mạnh
            2025: (1, 3),
            2026: (0, 1),
        },
        "aov_by_year": {
            2023: (1000, 3500), # AOV rất cao
            2024: (900, 3000),
            2025: (700, 2500),
            2026: (500, 2000),
        },
        "description": "Giá trị lịch sử CỰC CAO, đang ngừng mua",
        "rfm_target": "R=1-2 F=4-5 M=5 → Cant Lose Them",
        "active_in": [2023, 2024],
        "last_purchase_window": (180, 500),
    },

    "need_attention": {
        "label": "Need Attention",
        "pct": 0.08,
        "orders_by_year": {
            2023: (3, 6),
            2024: (2, 4),
            2025: (1, 3),
            2026: (1, 2),       # Vẫn mua nhưng đang giảm
        },
        "aov_by_year": {
            2023: (250, 700),
            2024: (230, 650),
            2025: (200, 600),
            2026: (180, 550),
        },
        "description": "Trên trung bình nhưng không tăng trưởng",
        "rfm_target": "R=2-3 F=2-3 M=2-3 → Need Attention",
        "active_in": [2023, 2024, 2025, 2026],
        "last_purchase_window": (90, 280),
    },

    # ── NHÓM 4: SLEEPING / LOST ───────────────────────────────────────────────
    "about_to_sleep": {
        "label": "About to Sleep",
        "pct": 0.08,
        "orders_by_year": {
            2023: (3, 5),
            2024: (2, 3),
            2025: (1, 2),
            2026: (0, 1),       # Gần như ngừng
        },
        "aov_by_year": {
            2023: (150, 450),
            2024: (130, 400),
            2025: (100, 350),
            2026: (80, 300),
        },
        "description": "Sắp ngủ đông — cần reactivation email ngay",
        "rfm_target": "R=2-3 F=1-2 M=1-2 → About to Sleep",
        "active_in": [2023, 2024, 2025],
        "last_purchase_window": (200, 400),
    },

    "hibernating": {
        "label": "Hibernating",
        "pct": 0.10,
        "orders_by_year": {
            2023: (2, 4),
            2024: (1, 2),
            2025: (0, 1),
            2026: (0, 0),       # Không mua gì trong 2026
        },
        "aov_by_year": {
            2023: (80, 280),
            2024: (70, 250),
            2025: (60, 200),
            2026: (0, 0),
        },
        "description": "Đang ngủ đông, không mua từ 2025+",
        "rfm_target": "R=1-2 F=1-2 M=1-2 → Hibernating",
        "active_in": [2023, 2024],
        "last_purchase_window": (365, 700),
    },

    "lost": {
        "label": "Lost",
        "pct": 0.14,
        "orders_by_year": {
            2023: (1, 3),       # Mua 1-3 lần rồi biến mất
            2024: (0, 1),
            2025: (0, 0),
            2026: (0, 0),
        },
        "aov_by_year": {
            2023: (50, 220),
            2024: (50, 200),
            2025: (0, 0),
            2026: (0, 0),
        },
        "description": "Mua 1-3 lần trong 2023, không quay lại",
        "rfm_target": "R=1 F=1 M=1 → Lost",
        "active_in": [2023],
        "last_purchase_window": (500, 1460),
    },

    # ── NHÓM 5: SPECIAL PATTERNS ─────────────────────────────────────────────
    "reactivated": {
        "label": "Reactivated",
        "pct": 0.02,
        "orders_by_year": {
            2023: (4, 7),       # Mua tốt ban đầu
            2024: (0, 0),       # GAP hoàn toàn — churn
            2025: (3, 6),       # ĐÃ QUAY LẠI! (win-back thành công)
            2026: (4, 8),       # Đang phục hồi
        },
        "aov_by_year": {
            2023: (300, 900),
            2024: (0, 0),
            2025: (350, 950),   # Quay lại với spend tương đương
            2026: (400, 1000),
        },
        "description": "Đã churn hoàn toàn 2024, quay lại 2025 — thú vị nhất cho retention",
        "rfm_target": "R=4-5 F=3-4 M=3-4 → Loyal (nhưng lịch sử có gap)",
        "active_in": [2023, 2025, 2026],  # KHÔNG có 2024!
        "last_purchase_window": (1, 90),
    },

    "seasonal_only": {
        "label": "Seasonal",
        "pct": 0.09,
        "orders_by_year": {
            2023: (2, 4),       # Chỉ mua Aug-Sep và Nov-Dec
            2024: (2, 4),
            2025: (2, 4),
            2026: (2, 4),
        },
        "aov_by_year": {
            2023: (200, 700),
            2024: (210, 720),
            2025: (220, 750),
            2026: (230, 780),
        },
        "description": "Chỉ mua trong mùa back-to-school và year-end",
        "rfm_target": "R=2-4 F=2 M=2-3 → Need Attention (do R lúc được lúc không)",
        "active_in": [2023, 2024, 2025, 2026],
        "last_purchase_window": (1, 400),  # Variable
        "seasonal_months": [8, 9, 11, 12], # CHỈ mua trong tháng này
    },
}

# Kiểm tra tổng tỷ lệ
_total = sum(p["pct"] for p in PROFILES.values())
assert abs(_total - 1.0) < 0.01, f"Tổng pct = {_total:.2f}, phải = 1.0"


# ─── HELPER FUNCTIONS ────────────────────────────────────────────────────────

def pick_order_date_for_profile(profile_name: str, year: int) -> date:
    """Sinh ngày đặt hàng phù hợp với behavior profile."""
    profile = PROFILES[profile_name]
    start = date(year, 1, 1)
    end   = date(year, 12, 31)

    # Seasonal: chỉ mua trong tháng chỉ định
    if "seasonal_months" in profile:
        target_months = profile["seasonal_months"]
        month = random.choice(target_months)
        # Trong tháng đó, chọn ngày ngẫu nhiên
        if month == 12:
            day_end = 28
        elif month in [8, 9]:
            day_end = 28
        else:
            day_end = 25
        d = date(year, month, random.randint(1, day_end))
        return d

    # Các profile khác: mùa vụ bình thường + không cuối tuần nhiều
    days = [(start + timedelta(d)) for d in range((end - start).days + 1)]

    # Trọng số mùa vụ
    def seasonal_w(d: date) -> float:
        m = d.month
        base = {1:0.55,2:0.60,3:0.80,4:0.85,5:0.90,6:0.88,
                7:0.92,8:1.40,9:1.45,10:1.10,11:1.55,12:1.50}.get(m, 1.0)
        weekend_factor = 0.5 if d.weekday() >= 5 else 1.0
        return base * weekend_factor

    wts = [seasonal_w(d) for d in days]
    total = sum(wts)
    wts = [w/total for w in wts]

    idx = np.random.choice(len(days), p=wts)
    return days[idx]


def pick_aov(profile_name: str, year: int) -> float:
    """Sinh AOV theo profile và năm (log-normal để realistic)."""
    profile = PROFILES[profile_name]
    aov_range = profile["aov_by_year"].get(year, (0, 0))
    if aov_range[0] == 0:
        return 0.0
    lo, hi = aov_range
    # Log-normal: median gần trung bình nhưng có outliers
    mean = (lo + hi) / 2
    sigma = 0.45
    val = np.random.lognormal(np.log(mean), sigma)
    return round(min(max(val, lo * 0.7), hi * 1.5), 2)


# ─── CORE FUNCTIONS ──────────────────────────────────────────────────────────

def assign_profiles_to_customers(db) -> dict[int, str]:
    """
    Gán lifecycle profile cho mỗi customer partner.
    Lưu profile vào field `ref` (External ID) của res.partner.
    Trả về {partner_id: profile_name}.
    """
    log.info("Assigning RFM lifecycle profiles to customers...")
    cur = db.cursor()
    now = datetime.now()

    # Lấy tất cả customer partners
    cur.execute("""
        SELECT id FROM res_partner
        WHERE customer_rank > 0 AND active = true
        ORDER BY id
    """)
    partner_ids = [r[0] for r in cur.fetchall()]

    if not partner_ids:
        log.error("Không tìm thấy customer nào. Chạy generator chính trước.")
        return {}

    n = len(partner_ids)
    log.info(f"Found {n} customers → assigning profiles...")

    # Tính số lượng customers theo mỗi profile
    profile_assignments = {}
    pool = list(partner_ids)
    random.shuffle(pool)

    start_idx = 0
    for profile_name, profile in PROFILES.items():
        count = round(n * profile["pct"])
        end_idx = min(start_idx + count, n)
        for pid in pool[start_idx:end_idx]:
            profile_assignments[pid] = profile_name
        start_idx = end_idx

    # Assign remaining (rounding errors)
    for pid in pool[start_idx:]:
        profile_assignments[pid] = "loyal"

    # Ghi vào database: dùng field `ref` để lưu profile label
    batch = [(profile_name, pid) for pid, profile_name in profile_assignments.items()]
    for profile_name, pid in batch:
        cur.execute(
            "UPDATE res_partner SET ref = %s, write_date = %s WHERE id = %s",
            [f"rfm:{profile_name}", now, pid]
        )

    db.commit()

    # Log phân bổ
    counts = {}
    for pid, pname in profile_assignments.items():
        counts[pname] = counts.get(pname, 0) + 1

    log.info("Profile distribution:")
    for pname, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        label = PROFILES[pname]["label"]
        log.info(f"  {label:<22} {cnt:>5} customers ({cnt/n*100:.1f}%)")

    return profile_assignments


def generate_rfm_orders(api, pg, ctx, profile_assignments: dict[int, str],
                        product_ids: list[int], start_seq: int = 1) -> int:
    """
    Sinh orders theo lifecycle profile của từng customer, qua XML-RPC ĐẦY ĐỦ
    (create → confirm → validate delivery → invoice → payment) — tái sử dụng
    nguyên các hàm phase O2C đã validate ở superstore_data_generator.py, để đơn
    RFM khớp đúng state machine Odoo: `state='sale'` phải có `stock.picking`
    thật, `invoice_status='invoiced'` phải có `account.move` thật — raw SQL
    insert thẳng header không làm được việc đó (đã audit thấy vi phạm nguyên
    tắc tồn kho=Σmove + state machine trong bản cũ).

    start_seq: số bắt đầu cho tên đơn SR000001, ... — mặc định 1 (lần chạy đầu).
    Khi gọi hàm này LẦN THỨ HAI (bổ sung thêm khách sau khi đã có SR-orders),
    PHẢI truyền start_seq = max(số hiện có) + 1 để tránh trùng tên đơn.
    """
    log.info("Generating RFM-driven orders (XML-RPC, full O2C cascade)...")
    cid = ctx["cid"]

    rows = pg.all("""
        SELECT pp.id, pt.list_price FROM product_product pp
        JOIN product_template pt ON pt.id = pp.product_tmpl_id
        WHERE pp.id = ANY(%s)
    """, [product_ids])
    prices = {r[0]: float(r[1]) for r in rows}

    campaigns = [r[0] for r in pg.all("SELECT id FROM utm_campaign WHERE company_id=%s", [cid])]

    # Precompute segment + kho khu vực cho từng khách 1 lần — cùng logic
    # p2_create_sos dùng cho backfill, tránh query lại mỗi đơn.
    partner_rows = pg.all("""
        SELECT rp.id, rp.comment, rcs.code
        FROM res_partner rp LEFT JOIN res_country_state rcs ON rcs.id = rp.state_id
        WHERE rp.customer_rank > 0
    """)
    default_wh = list(ctx["wh"].values())[0]
    partner_seg, partner_wh = {}, {}
    for pid, seg, state_code in partner_rows:
        partner_seg[pid] = seg or "Consumer"
        wh_id = default_wh
        if state_code:
            for reg, states in REGIONS.items():
                if state_code in states:
                    wh_id = ctx["wh"].get(REGION_WH.get(reg, "WEST"), default_wh)
                    break
        partner_wh[pid] = wh_id

    so_list = []  # (sid, "confirm", date) — đúng shape p2_confirm_orders cần
    buf = []
    total_orders = start_seq - 1
    years = [2023, 2024, 2025, 2026]

    for partner_id, profile_name in profile_assignments.items():
        profile = PROFILES[profile_name]
        wh_id = partner_wh.get(partner_id, default_wh)
        seg = partner_seg.get(partner_id, "Consumer")

        for year in years:
            if year not in profile["orders_by_year"]:
                continue
            n_min, n_max = profile["orders_by_year"][year]
            if n_max == 0:
                continue  # Profile không mua trong năm này (e.g. reactivated có gap 2024)

            n_orders = random.randint(n_min, n_max)

            for _ in range(n_orders):
                order_date = pick_order_date_for_profile(profile_name, year)
                aov = pick_aov(profile_name, year)
                if aov < 1:
                    continue

                n_lines = random.choices([1,2,3,4], weights=[0.35,0.30,0.22,0.13])[0]
                chosen = random.choices(product_ids, k=n_lines)
                raw_lines = []
                amount = 0
                for prod_id in chosen:
                    price = prices.get(prod_id, 150.0)
                    qty = max(1, int(aov / (n_lines * price)))
                    raw_lines.append((prod_id, qty, price))
                    amount += round(qty * price, 2)
                # Scale qty để Σline gần đúng AOV target
                scale = aov / max(1, amount)

                lines = []
                for prod_id, qty, price in raw_lines:
                    qty = max(1, round(qty * scale))
                    sub = qty * price
                    disc = 0.0
                    if seg == "Corporate":
                        if sub > 25000: disc = 20.0
                        elif sub > 10000: disc = 15.0
                        elif sub > 5000: disc = 10.0
                        elif sub > 2000: disc = 5.0
                    lines.append((0, 0, {"product_id": int(prod_id), "product_uom_qty": qty,
                                          "price_unit": round(price, 2), "discount": disc,
                                          "tax_id": [(5,)]}))

                campaign_id = random.choice(campaigns) if campaigns and random.random() < 0.45 else False
                order_dt = datetime.combine(order_date, datetime.min.time()).replace(
                    hour=random.randint(7, 18), minute=random.randint(0, 59))
                total_orders += 1
                so_name = f"SR{str(total_orders).zfill(6)}"  # SR = "Sales RFM"

                buf.append({
                    "name": so_name,
                    "partner_id": int(partner_id),
                    "date_order": order_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "warehouse_id": int(wh_id),
                    "campaign_id": int(campaign_id) if campaign_id else False,
                    "order_line": lines,
                    "_d": order_date,
                })

                if len(buf) >= 50:
                    _flush_rfm_create(api, buf, so_list)
                    buf.clear()
                    if total_orders % 500 == 0:
                        log.info(f"  RFM SOs created: {total_orders}")

    if buf:
        _flush_rfm_create(api, buf, so_list)

    log.info(f"RFM SOs created: {len(so_list)} — running O2C cascade (confirm→deliver→invoice→pay)...")

    # Tái sử dụng nguyên pipeline O2C đã validate ở generator chính.
    conf_ids, _ = p2_confirm_orders(api, pg, so_list)
    p2_validate_deliveries(api, pg, ctx, conf_ids)
    inv_ids = p2_create_and_post_invoices(api, pg, ctx, conf_ids)
    p2_register_payments(api, pg, ctx, inv_ids)

    log.info(f"RFM O2C cascade complete: {len(conf_ids)} confirmed orders, {len(inv_ids)} invoices")
    return len(conf_ids)


def _flush_rfm_create(api, buf, so_list):
    for v in buf:
        d = v.pop("_d")
        try:
            sid = api.create("sale.order", v)
            so_list.append((sid, "confirm", d))
        except Exception as e:
            log.warning(f"  RFM SO create err: {e}")


# ─── RFM VERIFICATION ────────────────────────────────────────────────────────

def compute_and_print_rfm(db, snapshot_date: date = None):
    """
    Tính RFM scores và in ra phân bổ segment.
    Dùng để kiểm chứng dữ liệu đã sinh ra đúng pattern chưa.

    Chạy sau khi generate xong:
        conn = psycopg2.connect(**DB_CONFIG)
        compute_and_print_rfm(conn, date(2026, 12, 31))
    """
    if snapshot_date is None:
        snapshot_date = date(2026, 12, 31)

    cur = db.cursor()

    log.info(f"\n{'═'*60}")
    log.info(f"RFM ANALYSIS — Snapshot date: {snapshot_date}")
    log.info(f"{'═'*60}")

    # Tính Recency, Frequency, Monetary cho từng customer
    cur.execute("""
        WITH rfm_raw AS (
            SELECT
                partner_id,
                MAX(date_order::date)                    AS last_order_date,
                COUNT(*)                                 AS frequency,
                SUM(amount_total)                        AS monetary,
                p.ref                                    AS rfm_profile
            FROM sale_order so
            JOIN res_partner p ON p.id = so.partner_id
            WHERE so.state IN ('sale','done')
              AND so.company_id = (SELECT id FROM res_company LIMIT 1)
            GROUP BY partner_id, p.ref
        ),
        rfm_scored AS (
            SELECT
                partner_id,
                rfm_profile,
                last_order_date,
                frequency,
                ROUND(monetary::numeric, 2) AS monetary,
                %s - last_order_date        AS recency_days,
                NTILE(5) OVER (ORDER BY last_order_date DESC)   AS r_score,
                NTILE(5) OVER (ORDER BY frequency)              AS f_score,
                NTILE(5) OVER (ORDER BY monetary)               AS m_score
            FROM rfm_raw
        )
        SELECT
            rfm_profile,
            COUNT(*)                        AS n_customers,
            ROUND(AVG(recency_days))        AS avg_recency_days,
            ROUND(AVG(frequency), 1)        AS avg_frequency,
            ROUND(AVG(monetary)::numeric,0) AS avg_monetary,
            ROUND(AVG(r_score), 2)          AS avg_r,
            ROUND(AVG(f_score), 2)          AS avg_f,
            ROUND(AVG(m_score), 2)          AS avg_m,
            ROUND(SUM(monetary)::numeric,0) AS total_revenue
        FROM rfm_scored
        WHERE rfm_profile IS NOT NULL
        GROUP BY rfm_profile
        ORDER BY total_revenue DESC
    """, [snapshot_date])

    rows = cur.fetchall()
    if not rows:
        log.warning("Không có dữ liệu RFM. Đảm bảo đã chạy generate_rfm_orders().")
        return

    total_rev = sum(r[8] for r in rows) or 1

    header = f"{'Profile':<22} {'Cust':>5} {'R_days':>7} {'Freq':>6} {'AOV$':>8} {'R':>4} {'F':>4} {'M':>4} {'Rev%':>6} {'Revenue$':>10}"
    log.info(header)
    log.info("─" * len(header))

    for row in rows:
        profile_key = row[0].replace("rfm:", "") if row[0] else "unknown"
        label = PROFILES.get(profile_key, {}).get("label", profile_key)
        rev_pct = row[8] / total_rev * 100
        log.info(
            f"{label:<22} {row[1]:>5} {row[2]:>7} {row[3]:>6} {row[4]:>8,} "
            f"{row[5]:>4} {row[6]:>4} {row[7]:>4} {rev_pct:>5.1f}% {row[8]:>10,}"
        )

    log.info("─" * len(header))
    log.info(f"{'TOTAL':<22} {sum(r[1] for r in rows):>5}{'':>27} {100:>5.1f}% {total_rev:>10,}")

    # SQL để dùng trong Power BI / dbt
    log.info("\n── SQL để dùng trong dbt (dim_rfm_segment) ──")
    print("""
-- Gold layer: dim_rfm_segment
-- Snapshot date: CURRENT_DATE hoặc tham số

WITH rfm_raw AS (
    SELECT
        partner_id,
        MAX(date_order)        AS last_purchase_date,
        COUNT(*)               AS frequency,
        SUM(amount_total)      AS monetary_total,
        CURRENT_DATE - MAX(date_order::date)  AS recency_days
    FROM sale_order
    WHERE state IN ('sale','done')
    GROUP BY partner_id
),
rfm_scores AS (
    SELECT *,
        NTILE(5) OVER (ORDER BY recency_days ASC)  AS r_score,  -- thấp = gần hơn = tốt
        NTILE(5) OVER (ORDER BY frequency DESC)    AS f_score,
        NTILE(5) OVER (ORDER BY monetary_total DESC) AS m_score
    FROM rfm_raw
),
rfm_segments AS (
    SELECT *,
        CONCAT(r_score, f_score, m_score) AS rfm_cell,
        CASE
            WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions'
            WHEN r_score >= 3 AND f_score >= 4                  THEN 'Loyal Customers'
            WHEN r_score >= 4 AND f_score <= 2                  THEN 'Potential Loyalists'
            WHEN r_score = 5  AND f_score = 1                   THEN 'New Customers'
            WHEN r_score >= 3 AND f_score <= 2 AND m_score <= 2 THEN 'Promising'
            WHEN r_score <= 2 AND f_score >= 3 AND m_score >= 3 THEN 'At Risk'
            WHEN r_score <= 2 AND f_score >= 4 AND m_score >= 4 THEN 'Cant Lose Them'
            WHEN r_score <= 3 AND f_score <= 3 AND m_score <= 3 THEN 'Need Attention'
            WHEN r_score <= 3 AND f_score <= 2                  THEN 'About to Sleep'
            WHEN r_score <= 2 AND f_score <= 2 AND m_score <= 2 THEN 'Hibernating'
            ELSE 'Lost'
        END AS rfm_segment
    FROM rfm_scores
)
SELECT
    p.id                    AS customer_id,
    p.name                  AS customer_name,
    p.ref                   AS lifecycle_profile,
    rs.last_purchase_date,
    rs.recency_days,
    rs.frequency,
    ROUND(rs.monetary_total, 2)  AS monetary_total,
    rs.r_score, rs.f_score, rs.m_score,
    rs.rfm_cell,
    rs.rfm_segment
FROM rfm_segments rs
JOIN res_partner p ON p.id = rs.partner_id
ORDER BY rs.monetary_total DESC;
""")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def rfm_replenish_stock(api, pg, ctx, partners, prod_ids, rm_ids, min_so_id=None):
    """
    Bù đắp tồn kho cho nhu cầu PHÁT SINH THÊM từ đơn RFM ('SR%') — tái sử dụng
    nguyên p3_purchasing/p4_manufacturing/p4b_raw_material_replenishment của
    generator chính, scope lại demand cho riêng đơn SR để KHÔNG tính lại (và
    mua/sản xuất trùng) phần demand gốc đã bù đắp lúc backfill.

    min_so_id: giới hạn thêm "AND so.id > min_so_id" — dùng khi gọi hàm này LẦN
    THỨ HAI trở đi (bổ sung thêm khách sau khi đã có SR-orders + đã bù kho cho
    chúng), để KHÔNG tính lại demand của các đơn SR cũ (đã bù đắp ở lần gọi
    trước) — chỉ bù cho phần orders mới (id lớn hơn mốc trước khi tạo batch mới).
    """
    log.info("Replenishing stock for RFM-driven demand (P2P + MFG + raw materials)...")
    rfm_filter = "AND so.name LIKE 'SR%%'"
    if min_so_id is not None:
        rfm_filter += f" AND so.id > {int(min_so_id)}"

    p3_purchasing(api, pg, ctx, partners, prod_ids, extra_so_filter=rfm_filter)

    before_mo_ids = {r[0] for r in pg.all("SELECT id FROM mrp_production")}
    p4_manufacturing(api, pg, ctx, extra_so_filter=rfm_filter)
    after_mo_ids = {r[0] for r in pg.all("SELECT id FROM mrp_production")}
    new_mo_ids = list(after_mo_ids - before_mo_ids)

    if new_mo_ids and rm_ids:
        p4b_raw_material_replenishment(api, pg, ctx, partners, rm_ids, mo_id_filter=new_mo_ids)
    else:
        log.info("  Không có MO mới từ RFM (Furniture demand thấp) — bỏ qua bù NVL")

    log.info("RFM stock replenishment complete")


def run():
    log.info("═══ SUPERSTORE RFM BEHAVIOR GENERATOR ═══")

    api = OdooAPI()
    pg = PG()
    ctx = load_context(pg, api)
    cid = ctx["cid"]

    # Guard chống chạy đôi — generate_rfm_orders() CHỒNG THÊM 1 loạt đơn SR mới
    # mỗi lần chạy, không ghi đè, dễ nhân đôi/ba dữ liệu nếu lỡ chạy nhầm lần nữa.
    existing = pg.one("SELECT count(*) FROM sale_order WHERE name LIKE 'SR%'")[0]
    if existing:
        log.error(f"Đã có {existing} đơn RFM ('SR%') trong DB — script này ĐÃ CHẠY rồi.")
        log.error("Chạy lại sẽ tạo THÊM 1 loạt đơn mới chồng lên, không ghi đè.")
        log.error("Muốn chạy lại từ đầu: xóa sale_order (+ line/picking/move/invoice liên "
                   "quan) có name LIKE 'SR%%' trước, rồi chạy lại script này.")
        pg.close()
        return

    # 1. Lấy product IDs — CHỈ sản phẩm sale_ok=true (loại raw materials dù
    # active=true — bản cũ không lọc field này, có rủi ro NVL lẫn vào pool bán).
    prod_rows = pg.all("""
        SELECT pp.id FROM product_product pp
        JOIN product_template pt ON pt.id=pp.product_tmpl_id
        WHERE pp.active=true AND pt.sale_ok=true
        LIMIT 450
    """)
    product_ids = [r[0] for r in prod_rows]
    if not product_ids:
        log.error("Không có products. Chạy superstore_data_generator.py trước.")
        pg.close()
        return

    # 2. Gán profile (raw SQL đơn giản, tái dùng connection gốc của PG)
    profile_assignments = assign_profiles_to_customers(pg.conn)
    if not profile_assignments:
        pg.close()
        return

    # 3. Sinh orders theo profile — full O2C qua XML-RPC (create→confirm→
    #    deliver→invoice→pay), khớp đúng state machine Odoo.
    total = generate_rfm_orders(api, pg, ctx, profile_assignments, product_ids)

    # 4. Bù đắp tồn kho cho nhu cầu phát sinh thêm từ các đơn RFM vừa tạo.
    supp_rows = pg.all("SELECT id FROM res_partner WHERE supplier_rank>0 AND company_id=%s", [cid])
    rm_rows = pg.all("SELECT default_code, id FROM product_product WHERE default_code LIKE 'RM-%'")
    partners = {"suppliers": [r[0] for r in supp_rows]}
    rm_ids = {code: pid for code, pid in rm_rows}
    rfm_replenish_stock(api, pg, ctx, partners, product_ids, rm_ids)

    # 5. Verify RFM
    log.info("\nVerifying RFM distribution...")
    compute_and_print_rfm(pg.conn, date(2026, 12, 31))

    pg.close()
    log.info(f"\n═══ HOÀN THÀNH: {total} RFM-driven orders (đầy đủ O2C + bù kho) ═══")
    log.info("Bước tiếp: kết nối Power BI → tạo RFM segment visualization")


if __name__ == "__main__":
    run()
