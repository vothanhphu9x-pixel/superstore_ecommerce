"""
superstore_marketing_data_generator.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tạo toàn bộ dữ liệu Digital Marketing cho Superstore Inc. (2023–2026).

Output (6 CSV files):
  1. marketing_campaigns_master.csv      — Campaign metadata (16 chiến dịch/năm)
  2. ad_performance_daily.csv            — KPI hằng ngày theo campaign × channel
  3. email_campaigns.csv                 — Email marketing metrics theo chiến dịch
  4. ab_test_results.csv                 — Creative A/B test performance
  5. marketing_funnel_monthly.csv        — Funnel Awareness → Conversion theo kênh
  6. customer_acquisition_source.csv     — Nguồn thu hút khách hàng + LTV

Chạy:
    python superstore_marketing_data_generator.py [--year 2023] [--all]
    python superstore_marketing_data_generator.py --all   # 2023-2026 cùng lúc

KPI phân tích được sau khi chạy:
    ✓ ROAS by channel/campaign/month
    ✓ CAC (Cost per Acquisition) trend
    ✓ CTR, CPC, CPM theo kênh
    ✓ Email funnel: Open → Click → Convert
    ✓ Marketing funnel: Impressions → Leads → Orders
    ✓ A/B test: creative nào hiệu quả nhất
    ✓ Attribution: channel nào tạo revenue thật sự
    ✓ Seasonal performance (back-to-school vs year-end)
    ✓ LTV:CAC ratio theo acquisition channel
"""

import csv
import random
import math
import re
from datetime import date, timedelta
from pathlib import Path
import sys
import logging
import psycopg2

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger(__name__)

random.seed(42)
OUTPUT_DIR = Path(".")

DB_CFG = dict(dbname="superstore_erp", user="odoo", host="localhost", port=5432)

def fetch_real_odoo_campaigns() -> list[tuple[int, str, int]]:
    """
    Đọc utm_campaign THẬT từ Odoo — trả về [(id, slug, year), ...]. Tên campaign
    trong Odoo có dạng "{slug}-{year}" (xem CAMP_TYPES trong
    superstore_data_generator.py), parse ngược lại slug+year để khớp với
    CAMPAIGN_TEMPLATES bên dưới. Không kết nối được (DB chưa chạy backfill) →
    trả về [] và generate_campaigns_master() sẽ tự cảnh báo, không crash.
    """
    try:
        conn = psycopg2.connect(**DB_CFG)
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM utm_campaign ORDER BY id")
        rows = cur.fetchall()
        conn.close()
    except Exception as e:
        log.warning(f"Không kết nối được Odoo DB để đọc utm_campaign thật ({e}) — "
                    f"sẽ tự sinh campaign_id giả, KHÔNG join được với Odoo")
        return []

    parsed = []
    for camp_id, name in rows:
        m = re.match(r"^(.+)-(\d{4})$", name)
        if m:
            parsed.append((camp_id, m.group(1), int(m.group(2))))
        else:
            log.warning(f"  utm_campaign id={camp_id} name={name!r} không đúng format "
                        f"'{{slug}}-{{year}}' — bỏ qua")
    return parsed

# ─────────────────────────────────────────────────────────────────────────────
# SEED DATA — Campaign universe cho Superstore Inc.
# ─────────────────────────────────────────────────────────────────────────────

# avg_daily_budget đã nhân ×36 so với bản gốc — hiệu chỉnh sau khi campaign_id
# join được thật với sale_order (xem generate_campaigns_master()): doanh thu
# attributed qua campaign_id ($28.8M/4 năm) gấp ~108 lần budget gốc, ROAS ra
# số phi thực tế (32x-15,550x thay vì mục tiêu ~3x của FRD-02). ×36 đưa spend
# về ~$9.6M/4 năm, ROAS về đúng khoảng target (roas_target/channel bên dưới,
# vốn đã thiết kế đúng tỷ lệ TƯƠNG ĐỐI giữa các kênh — chỉ sai QUY MÔ tuyệt đối).
CHANNELS = {
    "google_search": {
        "label": "Google Search Ads",
        "type": "paid_search",
        "avg_daily_budget": 7200,         # USD/ngày (×36, xem ghi chú CHANNELS ở trên)
        "ctr_range": (0.025, 0.065),      # 2.5–6.5% (search intent cao hơn)
        "cpc_range": (0.80, 4.50),        # CPC: $0.80–$4.50
        "conv_rate_range": (0.020, 0.055),# Conversion rate 2–5.5%
        "roas_target": 3.8,
        "cpm_range": (25, 65),            # CPM (via effective)
        "lead_quality": 0.85,             # % leads có chất lượng cao
    },
    "google_display": {
        "label": "Google Display Network",
        "type": "display",
        "avg_daily_budget": 2880,         # USD/ngày (×36, xem ghi chú CHANNELS ở trên)
        "ctr_range": (0.003, 0.008),      # Display CTR rất thấp
        "cpc_range": (0.30, 1.20),
        "conv_rate_range": (0.008, 0.020),
        "roas_target": 2.2,
        "cpm_range": (2, 8),
        "lead_quality": 0.45,
    },
    "meta_facebook": {
        "label": "Meta Facebook Ads",
        "type": "paid_social",
        "avg_daily_budget": 4680,         # USD/ngày (×36, xem ghi chú CHANNELS ở trên)
        "ctr_range": (0.008, 0.022),
        "cpc_range": (0.50, 2.50),
        "conv_rate_range": (0.012, 0.035),
        "roas_target": 2.9,
        "cpm_range": (8, 22),
        "lead_quality": 0.60,
    },
    "meta_instagram": {
        "label": "Meta Instagram Ads",
        "type": "paid_social",
        "avg_daily_budget": 2520,         # USD/ngày (×36, xem ghi chú CHANNELS ở trên)
        "ctr_range": (0.006, 0.018),
        "cpc_range": (0.60, 2.80),
        "conv_rate_range": (0.010, 0.028),
        "roas_target": 2.6,
        "cpm_range": (10, 28),
        "lead_quality": 0.50,
    },
    "email_marketing": {
        "label": "Email Marketing",
        "type": "owned",
        "avg_daily_budget": 108,          # USD/ngày (×36, xem ghi chú CHANNELS ở trên — vốn "Chỉ platform fee")
        "ctr_range": (0.020, 0.055),      # Của email CTR (click/delivered)
        "cpc_range": (0.05, 0.30),        # Cost per click rất thấp
        "conv_rate_range": (0.015, 0.045),
        "roas_target": 9.5,               # Email có ROAS cao nhất
        "cpm_range": (1, 5),
        "lead_quality": 0.75,
    },
}

# Campaign templates — kết hợp với year để tạo tên cụ thể
# ⚠️ slug PHẢI khớp CHÍNH XÁC với CAMP_TYPES trong superstore_data_generator.py
# (dùng để tạo utm_campaign thật trong Odoo — xem generate_campaigns_master() bên dưới,
# giờ đọc thẳng tên chiến dịch THẬT từ Odoo thay vì tự bịa danh sách riêng, để CSV này
# và dữ liệu Odoo (sale_order/crm_lead/account_move qua campaign_id) join được bằng
# đúng 1 campaign_id — giống cách thật ngoài đời: marketing đặt tên trên Google/Meta Ads
# Manager, dán đúng tên đó vào UTM, CRM lưu lại UTM — không phải 2 hệ ID độc lập.
CAMPAIGN_TEMPLATES = [
    {
        "slug": "back-to-school",
        "name_tpl": "Back to School {year}",
        "objective": "CONVERSIONS",
        "target_segment": "Consumer,Home Office",
        "product_focus": "Office Supplies,Furniture",
        "start_month": 7, "start_day": 15,
        "end_month": 9, "end_day": 15,
        "budget_multiplier": 1.4,         # ngân sách cao hơn baseline
        "channels": ["google_search","meta_facebook","meta_instagram","email_marketing"],
    },
    {
        "slug": "year-end-promo",
        "name_tpl": "Year End Promo {year}",
        "objective": "CONVERSIONS",
        "target_segment": "Consumer,Corporate",
        "product_focus": "Technology,Office Supplies",
        "start_month": 11, "start_day": 1,
        "end_month": 12, "end_day": 31,
        "budget_multiplier": 1.6,
        "channels": ["google_search","meta_facebook","meta_instagram","email_marketing"],
    },
    {
        "slug": "corporate-outreach",
        "name_tpl": "Corporate Outreach {year}",
        "objective": "LEAD_GENERATION",
        "target_segment": "Corporate",
        "product_focus": "Furniture,Technology",
        "start_month": 1, "start_day": 15,
        "end_month": 3, "end_day": 31,
        "budget_multiplier": 0.9,
        "channels": ["google_search","meta_facebook","email_marketing"],
    },
    {
        "slug": "spring-office-refresh",
        "name_tpl": "Spring Office Refresh {year}",
        "objective": "AWARENESS",
        "target_segment": "Consumer,Home Office",
        "product_focus": "Furniture",
        "start_month": 3, "start_day": 1,
        "end_month": 5, "end_day": 31,
        "budget_multiplier": 0.85,
        "channels": ["google_display","meta_facebook","meta_instagram"],
    },
    {
        "slug": "new-year-sale",
        "name_tpl": "New Year Sale {year}",
        "objective": "CONVERSIONS",
        "target_segment": "Consumer,Home Office",
        "product_focus": "Office Supplies,Technology",
        "start_month": 1, "start_day": 2,
        "end_month": 1, "end_day": 31,
        "budget_multiplier": 1.1,
        "channels": ["google_search","meta_facebook","email_marketing"],
    },
    {
        "slug": "summer-deals",
        "name_tpl": "Summer Deals {year}",
        "objective": "CONVERSIONS",
        "target_segment": "Consumer",
        "product_focus": "Office Supplies,Furniture",
        "start_month": 6, "start_day": 1,
        "end_month": 7, "end_day": 14,
        "budget_multiplier": 0.7,         # Ngân sách thấp (mùa thấp điểm)
        "channels": ["meta_facebook","meta_instagram","email_marketing"],
    },
    {
        "slug": "email-newsletter",
        "name_tpl": "Email Newsletter {year}",
        "objective": "RETENTION",
        "target_segment": "Consumer,Corporate,Home Office",
        "product_focus": "All",
        "start_month": 1, "start_day": 1,
        "end_month": 12, "end_day": 31,
        "budget_multiplier": 0.3,
        "channels": ["email_marketing"],
    },
    {
        "slug": "black-friday",
        "name_tpl": "Black Friday {year}",
        "objective": "CONVERSIONS",
        "target_segment": "Consumer,Corporate,Home Office",
        "product_focus": "Technology,Office Supplies",
        "start_month": 11, "start_day": 20,
        "end_month": 11, "end_day": 30,
        "budget_multiplier": 2.0,         # Budget gấp đôi
        "channels": ["google_search","meta_facebook","meta_instagram","email_marketing"],
    },
]

# Bad campaigns (cố ý có ROAS thấp để tạo insight cắt ngân sách)
BAD_CAMPAIGN_SLOTS = {
    2023: ("summer-deals", "meta_instagram"),
    2024: ("spring-office-refresh", "google_display"),
    2025: ("corporate-outreach", "meta_facebook"),
    2026: ("summer-deals", "meta_facebook"),
}


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def jitter(val, pct=0.12):
    return val * (1 + random.uniform(-pct, pct))

def seasonal_multiplier(d: date) -> float:
    m = d.month
    base = {1:0.55,2:0.62,3:0.78,4:0.82,5:0.88,6:0.84,
            7:0.90,8:1.38,9:1.45,10:1.08,11:1.55,12:1.48}.get(m, 1.0)
    return base * (0.65 if d.weekday() >= 5 else 1.0)

def date_range(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)

def safe_div(a, b, default=0.0):
    return round(a / b, 4) if b else default


# ─── FILE 1: CAMPAIGN MASTER ─────────────────────────────────────────────────

def generate_campaigns_master(years: list[int]) -> list[dict]:
    """
    ⭐ campaign_id ở đây = ĐÚNG utm_campaign.id thật trong Odoo (số nguyên) —
    không còn tự sinh "C0001" độc lập nữa. Nhờ vậy sale_order.campaign_id /
    crm_lead.campaign_id / account_move.campaign_id trong Odoo JOIN thẳng
    được với ad_performance_daily.csv / marketing_campaigns_master.csv qua
    CHUNG 1 campaign_id — giống cách thật ngoài đời marketing dùng chung 1 tên
    chiến dịch trên cả Ads Manager lẫn CRM (xem thảo luận thiết kế ở trên).

    Nếu không kết nối được Odoo (offline/DB chưa backfill), fallback về sinh
    toàn bộ 8 template × N năm với id giả "C0001..." như bản cũ — vẫn chạy
    được độc lập, chỉ là không join được với Odoo cho tới khi backfill xong
    rồi chạy lại script này.
    """
    tpl_by_slug = {t["slug"]: t for t in CAMPAIGN_TEMPLATES}
    real_campaigns = [c for c in fetch_real_odoo_campaigns() if c[2] in years]

    rows = []

    if real_campaigns:
        log.info(f"Đọc được {len(real_campaigns)} utm_campaign THẬT từ Odoo — "
                 f"campaign_id sẽ khớp 1:1 với sale_order/crm_lead/account_move")
        source = [(camp_id, tpl_by_slug.get(slug), year, slug)
                  for camp_id, slug, year in real_campaigns]
    else:
        log.warning("Không có utm_campaign thật — fallback sinh toàn bộ template "
                    "× năm với campaign_id GIẢ (không join được với Odoo)")
        source = []
        for year in years:
            for tpl in CAMPAIGN_TEMPLATES:
                source.append((f"C{str(len(source) + 1).zfill(4)}", tpl, year, tpl["slug"]))

    for camp_id, tpl, year, slug in source:
        if tpl is None:
            log.warning(f"  Bỏ qua utm_campaign id={camp_id}: slug {slug!r} không "
                        f"khớp template nào trong CAMPAIGN_TEMPLATES")
            continue

        # Đặt ngày
        try:
            start = date(year, tpl["start_month"], tpl["start_day"])
            end   = date(year, tpl["end_month"],   tpl["end_day"])
        except ValueError:
            end_day = min(tpl["end_day"], 28)
            start = date(year, tpl["start_month"], tpl["start_day"])
            end   = date(year, tpl["end_month"], end_day)

        # Budget tổng = sum(daily budget các channel) × số ngày × multiplier
        duration_days = (end - start).days + 1
        base_budget = sum(
            CHANNELS[ch]["avg_daily_budget"] for ch in tpl["channels"]
        )
        total_budget = round(
            base_budget * duration_days * tpl["budget_multiplier"], 2
        )

        # Performance thực tế (giả lập từ trước)
        # Bad campaign slot?
        bad = BAD_CAMPAIGN_SLOTS.get(year)
        is_bad_any = bad and bad[0] == tpl["slug"]
        status = "completed" if end < date.today() else "active"

        rows.append({
            "campaign_id":         camp_id,
            "campaign_name":       tpl["name_tpl"].format(year=year),
            "year":                year,
            "objective":           tpl["objective"],
            "target_segment":      tpl["target_segment"],
            "product_focus":       tpl["product_focus"],
            "channels":            "|".join(tpl["channels"]),
            "start_date":          start.isoformat(),
            "end_date":            end.isoformat(),
            "duration_days":       duration_days,
            "total_budget_usd":    total_budget,
            "budget_multiplier":   tpl["budget_multiplier"],
            "status":              status,
            "is_underperformer":   "YES" if is_bad_any else "NO",
            "notes": (
                f"⚠️ Low ROAS — {bad[1] if bad else ''} channel underperformed"
                if is_bad_any else ""
            ),
        })

    log.info(f"Campaigns master: {len(rows)} rows")
    return rows


# ─── FILE 2: DAILY AD PERFORMANCE ────────────────────────────────────────────

def generate_ad_performance_daily(campaigns: list[dict]) -> list[dict]:
    rows = []

    for camp in campaigns:
        year       = camp["year"]
        camp_id    = camp["campaign_id"]
        camp_name  = camp["campaign_name"]
        start      = date.fromisoformat(camp["start_date"])
        end        = date.fromisoformat(camp["end_date"])
        channels   = camp["channels"].split("|")
        is_bad     = camp["is_underperformer"] == "YES"
        bad_slot   = BAD_CAMPAIGN_SLOTS.get(year)

        for ch_key in channels:
            ch = CHANNELS[ch_key]
            is_bad_channel = is_bad and bad_slot and bad_slot[1] == ch_key

            for d in date_range(start, end):
                season = seasonal_multiplier(d)
                budget = round(
                    ch["avg_daily_budget"] * float(camp["budget_multiplier"]) * season
                    * jitter(1.0, 0.15), 2
                )
                if budget < 1:
                    continue

                # CTR
                ctr = jitter(random.uniform(*ch["ctr_range"]), 0.10)
                if is_bad_channel:
                    ctr *= random.uniform(0.5, 0.75)  # CTR thấp hơn

                # CPC và clicks
                cpc    = jitter(random.uniform(*ch["cpc_range"]), 0.10)
                clicks = max(0, int(budget / cpc))

                # Impressions từ CTR
                impressions = max(clicks, int(clicks / max(ctr, 0.001)))

                # CPM
                cpm = round(budget / impressions * 1000, 2) if impressions else 0

                # Conversions (leads / orders)
                conv_rate = jitter(random.uniform(*ch["conv_rate_range"]), 0.15)
                if is_bad_channel:
                    conv_rate *= random.uniform(0.4, 0.65)

                conversions = max(0, int(clicks * conv_rate))
                leads       = max(conversions, int(clicks * conv_rate * 1.8))

                # Revenue
                avg_order   = random.uniform(280, 950)
                revenue     = round(conversions * avg_order * jitter(1.0, 0.20), 2)
                roas        = safe_div(revenue, budget)
                if is_bad_channel:
                    revenue = round(revenue * random.uniform(0.4, 0.70), 2)
                    roas    = safe_div(revenue, budget)

                # Derived KPIs
                cpa  = round(budget / conversions, 2) if conversions else None
                cpl  = round(budget / leads, 2) if leads else None
                freq = round(impressions / max(impressions * 0.7, 1), 2)  # approx reach

                rows.append({
                    "date":            d.isoformat(),
                    "campaign_id":     camp_id,
                    "campaign_name":   camp_name,
                    "channel":         ch_key,
                    "channel_label":   ch["label"],
                    "channel_type":    ch["type"],
                    "year":            year,
                    "month":           d.month,
                    "quarter":         f"Q{(d.month-1)//3+1}",
                    # Spend
                    "spend_usd":       budget,
                    # Reach & Engagement
                    "impressions":     impressions,
                    "reach":           max(1, int(impressions * random.uniform(0.55, 0.85))),
                    "clicks":          clicks,
                    "ctr":             round(ctr, 5),
                    "cpc_usd":         round(cpc, 3),
                    "cpm_usd":         cpm,
                    "frequency":       freq,
                    # Conversions
                    "leads":           leads,
                    "conversions":     conversions,
                    "conv_rate":       round(conv_rate, 5),
                    "cpa_usd":         cpa,
                    "cpl_usd":         cpl,
                    # Revenue
                    "revenue_usd":     revenue,
                    "roas":            round(roas, 3),
                    # Quality
                    "lead_quality_score": round(ch["lead_quality"] * jitter(1.0, 0.15), 3),
                    "is_underperformer": "YES" if is_bad_channel else "NO",
                })

    log.info(f"Ad performance daily: {len(rows):,} rows")
    return rows


# ─── FILE 3: EMAIL CAMPAIGNS ──────────────────────────────────────────────────

EMAIL_TEMPLATES = [
    {
        "type": "newsletter",
        "send_freq": "monthly",
        "list_name": "All Subscribers",
        "list_size_pct": 1.0,
        "subject_variants": [
            "New arrivals: SS Workspace line for your office",
            "Office upgrade deals — this month only",
            "5 tips for a more productive workspace + exclusive deals",
            "Your office, reimagined — new collections inside",
        ],
        "expected_open_rate": 0.24,
        "expected_ctr": 0.035,
        "goal": "brand_awareness",
    },
    {
        "type": "promotional",
        "send_freq": "campaign",
        "list_name": "Active Customers",
        "list_size_pct": 0.6,
        "subject_variants": [
            "FLASH SALE: 20% off office furniture — 48 hours only!",
            "Your exclusive early access to our Back-to-School deals",
            "Black Friday preview — corporate accounts get first look",
            "Year-end clearance: save big before December 31",
        ],
        "expected_open_rate": 0.29,
        "expected_ctr": 0.055,
        "goal": "direct_sales",
    },
    {
        "type": "win_back",
        "send_freq": "quarterly",
        "list_name": "Lapsed Customers",
        "list_size_pct": 0.15,
        "subject_variants": [
            "We miss you! Here's 15% off your next order",
            "It's been a while — see what's new at Superstore",
            "Come back and see what you've been missing",
            "Exclusive win-back offer just for you",
        ],
        "expected_open_rate": 0.18,
        "expected_ctr": 0.022,
        "goal": "reactivation",
    },
    {
        "type": "onboarding",
        "send_freq": "triggered",
        "list_name": "New Customers",
        "list_size_pct": 0.08,
        "subject_variants": [
            "Welcome to Superstore Inc. — here's how to get started",
            "Your first order shipped! Plus, tips for your new items",
            "3 ways to make the most of your Superstore account",
        ],
        "expected_open_rate": 0.42,
        "expected_ctr": 0.085,
        "goal": "retention_early",
    },
    {
        "type": "abandoned_cart",
        "send_freq": "triggered",
        "list_name": "Cart Abandoners",
        "list_size_pct": 0.05,
        "subject_variants": [
            "You left something behind — complete your order",
            "Your cart is waiting! Items may sell out soon",
            "Don't forget your office upgrade — still available",
        ],
        "expected_open_rate": 0.38,
        "expected_ctr": 0.072,
        "goal": "conversion",
    },
]

def generate_email_campaigns(years: list[int], campaigns: list[dict]) -> list[dict]:
    rows  = []
    total_subscribers_base = 12000  # danh sách email năm 2023
    email_id = 1

    for year in years:
        # Danh sách tăng trưởng ~15%/năm
        list_growth = (1.15 ** (year - 2023))
        base_subscribers = int(total_subscribers_base * list_growth)

        # Số lần gửi theo loại và tần suất
        sends_per_year = {
            "newsletter":    12,   # hàng tháng
            "promotional":   8,    # theo campaign
            "win_back":      4,    # hàng quý
            "onboarding":    24,   # triggered, ~2/tháng
            "abandoned_cart":52,   # triggered, ~1/tuần
        }

        for tpl in EMAIL_TEMPLATES:
            n_sends = sends_per_year[tpl["type"]]
            list_size = int(base_subscribers * tpl["list_size_pct"])

            # Sinh các lần gửi trong năm
            send_dates = sorted([
                date(year, 1, 1) + timedelta(days=random.randint(0, 364))
                for _ in range(n_sends)
            ])

            for send_date in send_dates:
                subject = random.choice(tpl["subject_variants"])

                # Các chỉ số email
                delivered_rate = random.uniform(0.96, 0.99)
                delivered      = int(list_size * delivered_rate)
                bounced        = list_size - delivered
                hard_bounce    = int(bounced * 0.35)
                soft_bounce    = bounced - hard_bounce

                # Seasonal effect on open rate
                season_factor = seasonal_multiplier(send_date)
                open_rate     = jitter(tpl["expected_open_rate"] * (0.85 + season_factor*0.15), 0.15)
                opens         = int(delivered * open_rate)
                unique_opens  = int(opens * random.uniform(0.82, 0.95))

                ctr           = jitter(tpl["expected_ctr"], 0.18)
                clicks        = int(delivered * ctr)
                unique_clicks = int(clicks * random.uniform(0.78, 0.92))
                ctor          = safe_div(unique_clicks, unique_opens)

                unsub_rate    = random.uniform(0.001, 0.006)
                unsubscribes  = max(0, int(delivered * unsub_rate))
                spam_reports  = max(0, int(delivered * 0.0001))

                # Conversions (% of clickers)
                conv_from_click = random.uniform(0.08, 0.22)
                conversions  = int(unique_clicks * conv_from_click)
                avg_order    = random.uniform(220, 680)
                revenue      = round(conversions * avg_order, 2)
                cost         = round(list_size * 0.012, 2)  # ~$12/1000 emails
                roas         = safe_div(revenue, cost)

                rows.append({
                    "email_id":         f"EM{str(email_id).zfill(5)}",
                    "year":             year,
                    "send_date":        send_date.isoformat(),
                    "month":            send_date.month,
                    "quarter":          f"Q{(send_date.month-1)//3+1}",
                    "email_type":       tpl["type"],
                    "goal":             tpl["goal"],
                    "list_name":        tpl["list_name"],
                    "subject_line":     subject,
                    # List metrics
                    "list_size":        list_size,
                    "delivered":        delivered,
                    "bounced_total":    bounced,
                    "hard_bounce":      hard_bounce,
                    "soft_bounce":      soft_bounce,
                    "deliverability":   round(delivered_rate, 4),
                    # Engagement
                    "opens":            opens,
                    "unique_opens":     unique_opens,
                    "open_rate":        round(open_rate, 4),
                    "clicks":           clicks,
                    "unique_clicks":    unique_clicks,
                    "ctr":              round(ctr, 4),
                    "ctor":             round(ctor, 4),     # Click-to-Open Rate
                    # Churn indicators
                    "unsubscribes":     unsubscribes,
                    "unsubscribe_rate": round(unsub_rate, 5),
                    "spam_reports":     spam_reports,
                    # Revenue
                    "conversions":      conversions,
                    "revenue_usd":      revenue,
                    "cost_usd":         cost,
                    "roas":             round(roas, 2),
                    "revenue_per_email": round(safe_div(revenue, delivered), 4),
                })
                email_id += 1

    log.info(f"Email campaigns: {len(rows):,} rows")
    return rows


# ─── FILE 4: A/B TEST RESULTS ─────────────────────────────────────────────────

AB_TESTS = [
    {
        "test_name": "CTA Button Copy Test",
        "channel": "google_search",
        "variants": [
            {"name": "A – Shop Now",      "ctr_boost": 1.0,  "conv_boost": 1.0},
            {"name": "B – Get Quote",     "ctr_boost": 0.88, "conv_boost": 1.25},  # B2B better
            {"name": "C – View Catalog",  "ctr_boost": 0.75, "conv_boost": 0.90},
        ],
        "winner": "B",
        "insight": "Get Quote drove 25% more conversions despite lower CTR — B2B intent",
    },
    {
        "test_name": "Ad Creative Format Test",
        "channel": "meta_facebook",
        "variants": [
            {"name": "A – Single Image",   "ctr_boost": 1.0,  "conv_boost": 1.0},
            {"name": "B – Carousel",       "ctr_boost": 1.35, "conv_boost": 1.18},
            {"name": "C – Video (15s)",    "ctr_boost": 1.65, "conv_boost": 0.92},
        ],
        "winner": "B",
        "insight": "Carousel showed 35% higher CTR; Video drove awareness but poor conversion",
    },
    {
        "test_name": "Email Subject Line Personalization",
        "channel": "email_marketing",
        "variants": [
            {"name": "A – Generic promo",         "ctr_boost": 1.0,  "conv_boost": 1.0},
            {"name": "B – First name + category", "ctr_boost": 1.28, "conv_boost": 1.32},
        ],
        "winner": "B",
        "insight": "Personalization +28% CTR, +32% conversion — always use first name",
    },
    {
        "test_name": "Landing Page Headline Test",
        "channel": "google_search",
        "variants": [
            {"name": "A – Price-focused: Save 20%",    "ctr_boost": 1.0,  "conv_boost": 1.0},
            {"name": "B – Quality-focused: SS Workspace", "ctr_boost": 0.92, "conv_boost": 1.22},
        ],
        "winner": "B",
        "insight": "Quality message = lower CTR but higher-intent visitors, better conv rate",
    },
    {
        "test_name": "Instagram Ad Audience Test",
        "channel": "meta_instagram",
        "variants": [
            {"name": "A – Broad 25-55",        "ctr_boost": 1.0,  "conv_boost": 1.0},
            {"name": "B – Lookalike 1%",       "ctr_boost": 1.42, "conv_boost": 1.65},
            {"name": "C – Interest targeting", "ctr_boost": 1.18, "conv_boost": 1.28},
        ],
        "winner": "B",
        "insight": "1% Lookalike audience drastically outperformed — build from top customers",
    },
    {
        "test_name": "Email Send Time Test",
        "channel": "email_marketing",
        "variants": [
            {"name": "A – Tuesday 10 AM",   "ctr_boost": 1.0,  "conv_boost": 1.0},
            {"name": "B – Thursday 2 PM",   "ctr_boost": 0.98, "conv_boost": 1.05},
            {"name": "C – Wednesday 6 AM",  "ctr_boost": 1.18, "conv_boost": 0.88},
        ],
        "winner": "A",
        "insight": "Tue 10 AM wins on conversions; Wed 6 AM high CTR but low purchase intent",
    },
    {
        "test_name": "Display Ad Size Test",
        "channel": "google_display",
        "variants": [
            {"name": "A – 300×250 rectangle", "ctr_boost": 1.0,  "conv_boost": 1.0},
            {"name": "B – 728×90 leaderboard", "ctr_boost": 0.72, "conv_boost": 0.85},
            {"name": "C – 160×600 skyscraper", "ctr_boost": 0.55, "conv_boost": 0.70},
        ],
        "winner": "A",
        "insight": "300×250 remains top performer; leaderboard/skyscraper poor ROI",
    },
    {
        "test_name": "Win-back Email Offer Test",
        "channel": "email_marketing",
        "variants": [
            {"name": "A – 10% discount",        "ctr_boost": 1.0,  "conv_boost": 1.0},
            {"name": "B – Free shipping",        "ctr_boost": 0.95, "conv_boost": 0.92},
            {"name": "C – 15% + free shipping",  "ctr_boost": 1.35, "conv_boost": 1.55},
        ],
        "winner": "C",
        "insight": "Combined offer (15%+free ship) best for win-back despite higher cost",
    },
]

def generate_ab_tests(years: list[int]) -> list[dict]:
    rows    = []
    test_id = 1

    for year in years:
        # Mỗi năm chạy tất cả A/B tests + đảo shuffle thứ tự
        tests_this_year = random.sample(AB_TESTS, len(AB_TESTS))

        for tpl in tests_this_year:
            ch      = CHANNELS[tpl["channel"]]
            test_start = date(year, random.randint(1, 11), random.randint(1, 28))
            test_end   = test_start + timedelta(days=random.randint(14, 28))

            # Base metrics cho test
            base_budget_daily  = ch["avg_daily_budget"] / len(tpl["variants"])
            test_days          = (test_end - test_start).days
            budget_per_variant = round(base_budget_daily * test_days, 2)

            base_ctr  = sum(ch["ctr_range"]) / 2
            base_conv = sum(ch["conv_rate_range"]) / 2

            for v in tpl["variants"]:
                ctr  = jitter(base_ctr * v["ctr_boost"], 0.08)
                cpc  = jitter(sum(ch["cpc_range"]) / 2, 0.10)
                impressions  = max(100, int(budget_per_variant / cpc * safe_div(1, ctr, 1)))
                clicks       = max(0, int(impressions * ctr))
                conv_rate    = jitter(base_conv * v["conv_boost"], 0.10)
                conversions  = max(0, int(clicks * conv_rate))
                revenue      = round(conversions * random.uniform(280, 950), 2)
                roas         = safe_div(revenue, budget_per_variant)
                cpa          = round(budget_per_variant / conversions, 2) if conversions else None
                is_winner    = "YES" if v["name"].startswith(tpl["winner"]) else "NO"

                rows.append({
                    "test_id":       f"AB{str(test_id).zfill(4)}",
                    "year":          year,
                    "test_name":     tpl["test_name"],
                    "channel":       tpl["channel"],
                    "start_date":    test_start.isoformat(),
                    "end_date":      test_end.isoformat(),
                    "duration_days": test_days,
                    "variant_name":  v["name"],
                    "is_winner":     is_winner,
                    "budget_usd":    budget_per_variant,
                    "impressions":   impressions,
                    "clicks":        clicks,
                    "ctr":           round(ctr, 5),
                    "conversions":   conversions,
                    "conv_rate":     round(conv_rate, 5),
                    "revenue_usd":   revenue,
                    "roas":          round(roas, 3),
                    "cpa_usd":       cpa,
                    "insight":       tpl["insight"] if is_winner == "YES" else "",
                })
            test_id += 1

    log.info(f"A/B tests: {len(rows)} rows")
    return rows


# ─── FILE 5: MARKETING FUNNEL MONTHLY ────────────────────────────────────────

def generate_marketing_funnel_monthly(years: list[int],
                                       ad_data: list[dict]) -> list[dict]:
    """Tổng hợp funnel Awareness → Leads → Orders → Revenue theo kênh × tháng."""
    from collections import defaultdict

    funnel = defaultdict(lambda: {
        "impressions": 0, "reach": 0, "clicks": 0, "spend": 0,
        "leads": 0, "conversions": 0, "revenue": 0,
    })

    for row in ad_data:
        key = (row["year"], row["month"], row["channel"])
        funnel[key]["impressions"] += row["impressions"]
        funnel[key]["reach"]       += row.get("reach", 0)
        funnel[key]["clicks"]      += row["clicks"]
        funnel[key]["spend"]       += row["spend_usd"]
        funnel[key]["leads"]       += row["leads"]
        funnel[key]["conversions"] += row["conversions"]
        funnel[key]["revenue"]     += row["revenue_usd"]

    rows = []
    for (year, month, channel), m in sorted(funnel.items()):
        impressions = m["impressions"]
        clicks      = m["clicks"]
        leads       = m["leads"]
        conversions = m["conversions"]
        spend       = round(m["spend"], 2)
        revenue     = round(m["revenue"], 2)

        rows.append({
            "year":               year,
            "month":              month,
            "quarter":            f"Q{(month-1)//3+1}",
            "channel":            channel,
            # Funnel stages
            "impressions":        impressions,       # Awareness
            "reach":              m["reach"],
            "clicks":             clicks,            # Interest
            "leads":              leads,             # Consideration
            "conversions":        conversions,       # Conversion (orders)
            # Funnel drop-off rates
            "ctr":                round(safe_div(clicks, impressions), 5),
            "click_to_lead_rate": round(safe_div(leads, clicks), 4),
            "lead_to_order_rate": round(safe_div(conversions, leads), 4),
            "end_to_end_rate":    round(safe_div(conversions, impressions), 6),
            # Economics
            "spend_usd":          spend,
            "revenue_usd":        revenue,
            "roas":               round(safe_div(revenue, spend), 3),
            "cac_usd":            round(safe_div(spend, conversions), 2) if conversions else None,
            "cpl_usd":            round(safe_div(spend, leads), 2) if leads else None,
            "cpc_usd":            round(safe_div(spend, clicks), 3) if clicks else None,
            "cpm_usd":            round(safe_div(spend, impressions) * 1000, 2) if impressions else None,
            # Volume KPIs
            "revenue_per_lead":   round(safe_div(revenue, leads), 2) if leads else None,
        })

    log.info(f"Marketing funnel monthly: {len(rows)} rows")
    return rows


# ─── FILE 6: CUSTOMER ACQUISITION SOURCE ─────────────────────────────────────

def generate_customer_acquisition_source(years: list[int],
                                          ad_data: list[dict]) -> list[dict]:
    """
    Mô phỏng nguồn thu hút khách hàng + LTV estimate.
    Dùng để phân tích: CAC, LTV:CAC, payback period theo channel.
    """
    rows      = []
    cust_id   = 1
    channels  = list(CHANNELS.keys()) + ["organic_search", "direct", "referral"]
    ch_weights= [0.22, 0.08, 0.18, 0.12, 0.15, 0.10, 0.08, 0.07]

    for year in years:
        # Số khách mới mỗi năm — PHẢI nhỏ hơn hẳn tổng customer base thật trong
        # Odoo (2,000, cố định từ generator chính, không tăng theo năm). Range
        # cũ (700-1000/năm × 4 năm ≈ 3,400) VƯỢT QUÁ tổng customer base thật —
        # nghịch lý khi so "khách mới do marketing acquire" với tổng khách có
        # trong ERP. Hạ xuống để tổng 4 năm ở dưới mức 2,000 (chừa dư địa cho
        # số khách không có "acquisition event" rõ ràng trong mô phỏng này).
        n_new = random.randint(350, 480)

        for _ in range(n_new):
            acq_date = date(year, 1, 1) + timedelta(days=random.randint(0, 364))
            ch       = random.choices(channels, weights=ch_weights)[0]
            segment  = random.choices(
                ["Consumer","Corporate","Home Office"], weights=[0.50,0.33,0.17]
            )[0]

            # CAC theo channel (paid cao hơn organic)
            cac_by_ch = {
                "google_search": random.uniform(55, 130),
                "google_display": random.uniform(40, 100),
                "meta_facebook": random.uniform(45, 110),
                "meta_instagram": random.uniform(40, 95),
                "email_marketing": random.uniform(8, 25),
                "organic_search": random.uniform(5, 20),
                "direct": 0,
                "referral": random.uniform(10, 40),
            }
            cac = round(cac_by_ch.get(ch, 50), 2)

            # First order value theo segment
            fov_by_seg = {
                "Consumer": random.uniform(80, 350),
                "Corporate": random.uniform(300, 2500),
                "Home Office": random.uniform(150, 800),
            }
            first_order_value = round(fov_by_seg[segment], 2)

            # Số tháng hoạt động từ lúc mua đến cuối 2026
            months_active = max(1, (date(2026, 12, 31) - acq_date).days // 30)

            # LTV estimate: first_order + repeat purchases
            # Champions buy 10-20x/year, Loyal buy 4-8x, others less
            ch_quality = CHANNELS.get(ch, {}).get("lead_quality", 0.5) if ch in CHANNELS else 0.4
            orders_per_year = max(1, int(ch_quality * random.uniform(2, 8)))
            aov_factor = fov_by_seg[segment] / random.uniform(150, 600)
            ltv_to_date = round(
                first_order_value +
                (orders_per_year * (months_active / 12) * first_order_value * 0.75
                 * jitter(1.0, 0.25)), 2
            )

            ltv_cac_ratio = round(safe_div(ltv_to_date, cac), 2) if cac else None
            payback_days  = round(safe_div(cac, ltv_to_date / max(months_active, 1) * 30), 0) if cac and ltv_to_date else None

            rows.append({
                "customer_id":            f"CUST{str(cust_id).zfill(6)}",
                "acquisition_date":       acq_date.isoformat(),
                "year":                   year,
                "month":                  acq_date.month,
                "quarter":                f"Q{(acq_date.month-1)//3+1}",
                "acquisition_channel":    ch,
                "acquisition_channel_type": CHANNELS.get(ch, {}).get("type","organic"),
                "customer_segment":       segment,
                "first_order_value_usd":  first_order_value,
                "cac_usd":                cac,
                "ltv_to_date_usd":        ltv_to_date,
                "ltv_cac_ratio":          ltv_cac_ratio,
                "months_active":          months_active,
                "est_orders_per_year":    orders_per_year,
                "payback_period_days":    payback_days,
                "is_profitable_acq":      "YES" if ltv_cac_ratio and ltv_cac_ratio >= 3.0 else "NO",
            })
            cust_id += 1

    log.info(f"Customer acquisition source: {len(rows):,} rows")
    return rows


# ─── WRITE CSV ────────────────────────────────────────────────────────────────

def write_csv(rows: list[dict], filename: str):
    if not rows:
        log.warning(f"No data for {filename}, skipping")
        return
    path = OUTPUT_DIR / filename
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    size_kb = path.stat().st_size // 1024
    log.info(f"  Saved {filename}: {len(rows):,} rows ({size_kb} KB)")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def run(years: list[int]):
    log.info(f"═══ SUPERSTORE MARKETING DATA GENERATOR ═══")
    log.info(f"Years: {years} | Output: {OUTPUT_DIR.resolve()}")
    log.info("")

    log.info("1/6 Generating campaign master...")
    campaigns = generate_campaigns_master(years)
    write_csv(campaigns, "marketing_campaigns_master.csv")

    log.info("2/6 Generating daily ad performance...")
    ad_daily = generate_ad_performance_daily(campaigns)
    write_csv(ad_daily, "ad_performance_daily.csv")

    log.info("3/6 Generating email campaigns...")
    emails = generate_email_campaigns(years, campaigns)
    write_csv(emails, "email_campaigns.csv")

    log.info("4/6 Generating A/B test results...")
    ab_tests = generate_ab_tests(years)
    write_csv(ab_tests, "ab_test_results.csv")

    log.info("5/6 Generating marketing funnel monthly...")
    funnel = generate_marketing_funnel_monthly(years, ad_daily)
    write_csv(funnel, "marketing_funnel_monthly.csv")

    log.info("6/6 Generating customer acquisition source...")
    acq = generate_customer_acquisition_source(years, ad_daily)
    write_csv(acq, "customer_acquisition_source.csv")

    log.info("")
    log.info("═══ DONE ═══")
    log.info("Files tạo ra:")
    for f in ["marketing_campaigns_master.csv","ad_performance_daily.csv",
              "email_campaigns.csv","ab_test_results.csv",
              "marketing_funnel_monthly.csv","customer_acquisition_source.csv"]:
        p = OUTPUT_DIR / f
        if p.exists():
            log.info(f"  {f}: {p.stat().st_size//1024} KB")

    log.info("")
    log.info("KPIs phân tích được:")
    log.info("  ✓ ROAS by channel/campaign/quarter (ad_performance_daily.csv)")
    log.info("  ✓ Email open rate, CTR, CTOR, unsubscribes (email_campaigns.csv)")
    log.info("  ✓ Funnel drop-off: Impression→Click→Lead→Order (marketing_funnel_monthly.csv)")
    log.info("  ✓ A/B winner analysis, CTA/creative insight (ab_test_results.csv)")
    log.info("  ✓ CAC, LTV:CAC, payback period by channel (customer_acquisition_source.csv)")
    log.info("  ✓ Campaign budget vs performance (marketing_campaigns_master.csv)")
    log.info("  ✓ Seasonal performance: back-to-school vs year-end vs flat months")
    log.info("")
    log.info("Bước tiếp: nạp CSV vào MinIO → dbt staging → Power BI Marketing dashboard")


if __name__ == "__main__":
    if "--all" in sys.argv:
        years = [2023, 2024, 2025, 2026]
    elif "--year" in sys.argv:
        idx   = sys.argv.index("--year")
        years = [int(sys.argv[idx + 1])]
    else:
        years = [2023, 2024, 2025, 2026]  # default: tất cả

    run(years)
