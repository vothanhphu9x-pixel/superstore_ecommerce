"""
superstore_live_simulator.py
━━━━━━━━━━━━━━━━━━━━━━━━━━
Live simulator 2027+ — sinh giao dịch mỗi ngày vào superstore_erp.
Chạy thủ công hoặc cài vào cron / n8n mỗi sáng.

Mỗi lần chạy — qua XML-RPC (tái sử dụng pipeline O2C đã validate ở
superstore_data_generator.py, khớp đúng state machine Odoo: đơn 'sale' có
stock.picking thật, 'invoiced' có account.move thật, không chỉ header suông):
  - Sinh 20-55 SO mới (ngày hôm nay), ~95% confirm→xuất kho→invoice→payment
    ngay, ~5% để lại draft (backlog imperfection có chủ đích)
  - Confirm một số SO draft cũ (kể cả backlog vừa để lại) → cùng cascade O2C
  - Ghi nhận thêm payment cho invoice cũ còn nợ (mô phỏng DSO — thu tiền dần
    theo thời gian, không chỉ ngay lúc tạo)
  - Sinh 1-4 PO mới, có receipt + vendor bill + payment thật (không chỉ header)
  - Thỉnh thoảng update customer info (SCD2 source)
  - Tất cả đều là INSERT/UPDATE thật trên DB → CDC events cho Debezium

Chạy:
    python superstore_live_simulator.py

Cron (hằng ngày 7:00 AM):
    0 7 * * 1-5 cd /path/to && python superstore_live_simulator.py >> simulator.log 2>&1
"""

import random
from datetime import datetime, timedelta, date
from faker import Faker
import logging
import sys

# Tái sử dụng pipeline O2C đã validate từ generator chính — raw SQL không tự
# tạo đúng state machine Odoo (đơn 'sale' không có stock.picking, 'invoiced'
# không có account.move thật — cùng lớp lỗi đã tìm và fix ở
# superstore_rfm_customer_behaviors.py).
try:
    from superstore_data_generator import (
        OdooAPI, PG, load_context, REGIONS, REGION_WH,
        p2_confirm_orders, p2_validate_deliveries,
        p2_create_and_post_invoices, p2_register_payments,
    )
except ImportError:
    from scripts.superstore_data_generator import (
        OdooAPI, PG, load_context, REGIONS, REGION_WH,
        p2_confirm_orders, p2_validate_deliveries,
        p2_create_and_post_invoices, p2_register_payments,
    )

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

fake = Faker("en_US")
random.seed(None)  # Random thật sự (không fix seed)

def load_extra_context(pg, ctx) -> dict:
    """Context bổ sung riêng cho live simulator, ngoài những gì load_context() gốc
    (superstore_data_generator) đã trả về (cid/cur/uid/wh/jnl...)."""
    cid = ctx["cid"]

    r = pg.one("""
        SELECT spt.id FROM stock_picking_type spt
        JOIN stock_warehouse sw ON sw.id = spt.warehouse_id
        WHERE spt.code='incoming' AND sw.company_id=%s
        ORDER BY RANDOM() LIMIT 1
    """, [cid])
    recv_picking_type_id = r[0] if r else None

    bank_jnl = ctx["jnl"].get("bank") or ctx["jnl"].get("cash")
    bank_account_id = None
    if bank_jnl:
        r = pg.one("SELECT default_account_id FROM account_journal WHERE id=%s", [bank_jnl])
        bank_account_id = r[0] if r else None

    # account_account has NO company_id column in Odoo 18 (multi-company via M2M
    # account_account_res_company_rel now) — và có thể có nhiều asset_receivable
    # account, nên lấy đúng cái đang dùng thật trên invoice khách hàng, không
    # random theo account_type.
    r = pg.one("""
        SELECT aml.account_id FROM account_move_line aml
        JOIN account_move am ON am.id = aml.move_id
        WHERE am.move_type='out_invoice' AND aml.debit > 0
        GROUP BY aml.account_id ORDER BY count(*) DESC LIMIT 1
    """)
    ar_account_id = r[0] if r else None

    return dict(bank_jnl=bank_jnl, bank_account_id=bank_account_id,
                ar_account_id=ar_account_id, recv_picking_type_id=recv_picking_type_id)


def simulate_day(today: date):
    log.info(f"═══ LIVE SIMULATOR — {today} ═══")
    api = OdooAPI()
    pg = PG()
    now = datetime.now()

    try:
        ctx = load_context(pg, api)
        cid = ctx["cid"]
        extra = load_extra_context(pg, ctx)

        # ── 1. Đọc pool: customers, products, campaigns ──────────────────────
        customer_pool = [r[0] for r in pg.all("""
            SELECT id FROM res_partner
            WHERE customer_rank > 0 AND company_id=%s AND active=true
            ORDER BY RANDOM() LIMIT 200
        """, [cid])]

        prod_rows = pg.all("""
            SELECT pp.id, pt.list_price FROM product_product pp
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            WHERE pp.active=true AND pt.sale_ok=true
            ORDER BY RANDOM() LIMIT 100
        """)
        products_pool = [(r[0], float(r[1])) for r in prod_rows]

        campaign_pool = [r[0] for r in pg.all("SELECT id FROM utm_campaign WHERE company_id=%s", [cid])]

        if not customer_pool or not products_pool:
            log.warning("Pool rỗng — chạy generator trước (superstore_data_generator.py)")
            pg.close()
            return

        # Customer -> kho khu vực (cùng logic p2_create_sos)
        partner_rows = pg.all("""
            SELECT rp.id, rcs.code FROM res_partner rp
            LEFT JOIN res_country_state rcs ON rcs.id = rp.state_id
            WHERE rp.id = ANY(%s)
        """, [customer_pool])
        default_wh = list(ctx["wh"].values())[0]
        partner_wh = {}
        for pid, state_code in partner_rows:
            wh_id = default_wh
            if state_code:
                for reg, states in REGIONS.items():
                    if state_code in states:
                        wh_id = ctx["wh"].get(REGION_WH.get(reg, "WEST"), default_wh)
                        break
            partner_wh[pid] = wh_id

        # ── 2. Sinh SO mới hôm nay qua XML-RPC — ~95% confirm ngay, ~5% để lại
        #    draft (backlog imperfection có chủ đích, confirm ở bước 3 sau) ───
        n_orders = random.randint(20, 55)
        so_list = []  # (sid, "confirm", date) — đúng shape p2_confirm_orders cần
        n_draft_left = 0
        for _ in range(n_orders):
            cust_id = random.choice(customer_pool)
            campaign_id = random.choice(campaign_pool) if campaign_pool and random.random() < 0.45 else False
            n_lines = random.choices([1,2,3,4], weights=[0.35,0.30,0.22,0.13])[0]
            chosen = random.choices(products_pool, k=n_lines)
            lines = [(0, 0, {"product_id": int(pid), "product_uom_qty": random.randint(1, 8),
                              "price_unit": round(price, 2), "tax_id": [(5,)]})
                     for pid, price in chosen]
            order_dt = datetime.combine(today, datetime.min.time()).replace(
                hour=random.randint(7, 18), minute=random.randint(0, 59))
            try:
                sid = api.create("sale.order", {
                    "partner_id": int(cust_id),
                    "date_order": order_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "warehouse_id": int(partner_wh.get(cust_id, default_wh)),
                    "campaign_id": int(campaign_id) if campaign_id else False,
                    "order_line": lines,
                })
                if random.random() > 0.05:
                    so_list.append((sid, "confirm", today))
                else:
                    n_draft_left += 1
            except Exception as e:
                log.warning(f"  SO create err: {e}")

        log.info(f"[{today}] +{n_orders} new SO created ({n_draft_left} left as draft)")

        # ── 3. Confirm một số SO draft cũ (kể cả vừa để lại ở bước 2) ─────
        old_drafts = [r[0] for r in pg.all("""
            SELECT id FROM sale_order WHERE state='draft' AND company_id=%s
            ORDER BY RANDOM() LIMIT %s
        """, [cid, random.randint(3, 10)])]
        for sid in old_drafts:
            so_list.append((sid, "confirm", today))

        # O2C cascade cho MỌI đơn confirm hôm nay (mới + backlog cũ): confirm →
        # validate delivery (xuất kho thật) → invoice → payment — tái sử dụng
        # nguyên pipeline đã validate ở generator chính, khớp đúng state machine
        # Odoo (đơn 'sale' phải có stock.picking thật, không chỉ header).
        conf_ids, inv_ids = [], []
        if so_list:
            conf_ids, _ = p2_confirm_orders(api, pg, so_list)
            p2_validate_deliveries(api, pg, ctx, conf_ids)
            inv_ids = p2_create_and_post_invoices(api, pg, ctx, conf_ids)
            p2_register_payments(api, pg, ctx, inv_ids)
        log.info(f"[{today}] {len(so_list)} SO confirmed today ({len(old_drafts)} from backlog) "
                 f"→ {len(conf_ids)} delivered, {len(inv_ids)} invoiced — CDC events")

        # ── 4. Ghi nhận thêm payment cho invoice CŨ còn nợ (thu tiền dần theo
        #    thời gian, không chỉ ngay lúc tạo — mô phỏng DSO thực tế) ───────
        bank_jnl = extra["bank_jnl"]; bank_account_id = extra["bank_account_id"]; ar_account_id = extra["ar_account_id"]
        n_paid = 0
        if bank_jnl and bank_account_id and ar_account_id:
            unpaid_invs = pg.all("""
                SELECT id, amount_total, partner_id FROM account_move
                WHERE move_type='out_invoice' AND state='posted'
                AND payment_state IN ('not_paid','partial')
                AND company_id=%s
                ORDER BY RANDOM() LIMIT %s
            """, [cid, random.randint(5, 20)])

            for inv_id, amount, partner_id in unpaid_invs:
                if random.random() < 0.6:  # 60% sẽ thanh toán hôm nay
                    amt = round(float(amount), 2)
                    # Journal entry thật (debit Bank / credit AR) — account_payment
                    # không tự sinh bút toán khi insert thẳng SQL như XML-RPC
                    # action_post() vẫn làm, thiếu bước này thì payment 'posted'
                    # không có gì đối ứng, phá vỡ nguyên tắc Σdebit=Σcredit.
                    pg.q("""
                        INSERT INTO account_move
                        (company_id, move_type, state, journal_id, currency_id, date, auto_post,
                         amount_untaxed, amount_total, amount_residual,
                         create_uid, write_uid, create_date, write_date)
                        VALUES(%s,'entry','posted',%s,%s,%s,'no',%s,%s,0,%s,%s,%s,%s)
                        RETURNING id
                    """, [cid, bank_jnl, ctx["cur"], today, amt, amt,
                          ctx["uid"], ctx["uid"], now, now])
                    move_id = pg.cur.fetchone()[0]
                    for acct, dr, cr in [(bank_account_id, amt, 0), (ar_account_id, 0, amt)]:
                        pg.q("""
                            INSERT INTO account_move_line
                            (move_id, account_id, partner_id, name, debit, credit,
                             date, company_id, currency_id, display_type,
                             create_uid, write_uid, create_date, write_date)
                            VALUES(%s,%s,%s,'Payment line',%s,%s,%s,%s,%s,'payment_term',%s,%s,%s,%s)
                        """, [move_id, acct, partner_id, dr, cr, today, cid,
                              ctx["cur"], ctx["uid"], ctx["uid"], now, now])

                    pg.q("""
                        INSERT INTO account_payment
                        (company_id, partner_id, amount, payment_type, partner_type, state,
                         journal_id, date, currency_id, move_id,
                         create_uid, write_uid, create_date, write_date)
                        VALUES(%s,%s,%s,'inbound','customer','posted',%s,%s,%s,%s,%s,%s,%s,%s)
                    """, [cid, partner_id, amt,
                          bank_jnl, today, ctx["cur"], move_id,
                          ctx["uid"], ctx["uid"], now, now])
                    pg.q("""
                        UPDATE account_move SET payment_state='paid', write_date=%s WHERE id=%s
                    """, [now, inv_id])
                    n_paid += 1
            pg.commit()
            log.info(f"[{today}] {n_paid} old-invoice payments registered (with journal entries) — CDC UPDATE events")
        else:
            log.warning(f"[{today}] Thiếu bank journal/AR account/bank account — bỏ qua payment simulation")

        # ── 5. Sinh PO nhỏ (reorder simulation) qua XML-RPC — có receipt +
        #    vendor bill + payment thật, không chỉ header suông ────────────
        supplier_pool = [r[0] for r in pg.all("""
            SELECT id FROM res_partner WHERE supplier_rank > 0 AND company_id=%s LIMIT 20
        """, [cid])]

        recv_picking_type_id = extra["recv_picking_type_id"]
        n_po = 0
        if supplier_pool and products_pool and recv_picking_type_id:
            n_po_target = random.randint(1, 4)
            for _ in range(n_po_target):
                supplier_id = random.choice(supplier_pool)
                n_lines = random.randint(1, 5)
                chosen = random.choices(products_pool, k=n_lines)
                po_lines = [(0, 0, {"product_id": int(pid), "product_qty": random.randint(5, 40),
                                     "price_unit": round(price * 0.75, 2)})
                            for pid, price in chosen]
                try:
                    po_id = api.create("purchase.order", {
                        "partner_id": int(supplier_id),
                        "date_order": datetime.combine(today, datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S"),
                        "picking_type_id": int(recv_picking_type_id),
                        "order_line": po_lines,
                    })
                    api.call("purchase.order", "button_confirm", [po_id])

                    receipts = api.search("stock.picking",
                        [("purchase_id", "=", po_id), ("state", "not in", ["done", "cancel"])])
                    for rec_id in receipts:
                        moves = api.search("stock.move",
                            [("picking_id", "=", rec_id), ("state", "not in", ["done", "cancel"])])
                        for mv in moves:
                            mv_d = api.read("stock.move", [mv], ["product_uom_qty"])[0]
                            try:
                                api.write("stock.move", [mv], {"quantity": mv_d["product_uom_qty"], "picked": True})
                            except Exception:
                                pass
                        try:
                            res = api._x("stock.picking", "button_validate", [[rec_id]],
                                          {"context": {"skip_backorder": True, "skip_sms": True,
                                                       "picking_ids_not_to_backorder": [rec_id]}})
                            if res is not True:
                                log.warning(f"  Receipt {rec_id} returned wizard instead of completing: {res}")
                        except Exception as e:
                            log.warning(f"  Receipt {rec_id} validate: {e}")

                    # Vendor bill + payment thật (cùng pattern đã validate ở p3_purchasing)
                    try:
                        api.call("purchase.order", "action_create_invoice", [po_id])
                    except Exception:
                        pass
                    bills = api.search("account.move",
                        [("purchase_id", "=", po_id), ("move_type", "=", "in_invoice"), ("state", "=", "draft")])
                    if bills:
                        bill_date = today.strftime("%Y-%m-%d")
                        try:
                            api.write("account.move", bills, {"invoice_date": bill_date})
                        except Exception:
                            pass
                        try:
                            api.call("account.move", "action_post", bills)
                        except Exception as e:
                            log.warning(f"  Bill post failed (PO {po_id}): {e}")
                        for bill_id in bills:
                            try:
                                b_data = api.read("account.move", [bill_id], ["amount_total"])[0]
                                pay_id = api.create("account.payment", {
                                    "payment_type": "outbound", "partner_type": "supplier",
                                    "partner_id": int(supplier_id),
                                    "amount": round(b_data.get("amount_total", 0), 2),
                                    "journal_id": int(bank_jnl) if bank_jnl else int(list(ctx["jnl"].values())[0]),
                                    "date": today.strftime("%Y-%m-%d"),
                                    "currency_id": int(ctx["cur"]),
                                })
                                try:
                                    api.call("account.payment", "action_post", [pay_id])
                                except Exception as e:
                                    if "cannot marshal None" not in str(e):
                                        raise
                                pg.q("UPDATE account_move SET payment_state='paid', amount_residual=0 WHERE id=%s",
                                     [bill_id])
                                pg.commit()
                            except Exception as e:
                                log.warning(f"  Vendor payment failed (PO {po_id}): {e}")

                    n_po += 1
                except Exception as e:
                    log.warning(f"  PO create/confirm err: {e}")

            log.info(f"[{today}] +{n_po} new PO (confirmed + received + billed) — CDC INSERT events")
        elif not recv_picking_type_id:
            log.warning(f"[{today}] Thiếu receipt picking type — bỏ qua PO simulation")

        # ── 6. Update một số customer info (gây SCD2 events) ───────────────
        if random.random() < 0.15:  # 15% ngày có khách đổi thông tin
            pg.q("""
                UPDATE res_partner
                SET phone=%s, write_date=%s
                WHERE id=(SELECT id FROM res_partner WHERE customer_rank>0
                          AND company_id=%s ORDER BY RANDOM() LIMIT 1)
            """, [fake.phone_number()[:20], now, cid])
            log.info(f"[{today}] 1 partner update — CDC UPDATE event (dim_customer SCD2 source)")

        pg.commit()
        log.info(f"[{today}] Simulation complete ✓")

    except Exception as e:
        pg.rollback()
        log.error(f"Lỗi: {e}")
        raise
    finally:
        pg.close()



if __name__ == "__main__":
    simulate_day(date.today())
