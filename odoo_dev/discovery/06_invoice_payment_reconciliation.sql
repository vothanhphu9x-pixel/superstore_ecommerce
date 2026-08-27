-- QUERY: Invoice Payment
SELECT
    m_inv.name AS ma_hoa_don,
    m_pay.name AS ma_chung_tu_thanh_toan,
    apr.amount AS so_tien_thanh_toan,
    m_pay.date AS ngay_thanh_toan,
    ap.state AS trang_thai_thanh_toan

FROM account_move AS m_inv

-- 1. Lấy dòng chi tiết thuộc tài khoản Phải thu của hóa đơn
JOIN account_move_line AS aml_inv
    ON aml_inv.move_id = m_inv.id
JOIN account_account AS acc_inv
    ON acc_inv.id = aml_inv.account_id
   AND acc_inv.account_type = 'asset_receivable'

-- 2. Dùng LEFT JOIN để giữ lại hóa đơn ngay cả khi chưa thanh toán (chưa có đối soát)
LEFT JOIN account_partial_reconcile AS apr
    ON apr.debit_move_id = aml_inv.id
    OR apr.credit_move_id = aml_inv.id

-- 3. Lấy dòng move_line đối ứng ở phía bên kia của bảng đối soát
LEFT JOIN account_move_line AS aml_pay
    ON aml_pay.id = CASE
        WHEN apr.debit_move_id = aml_inv.id THEN apr.credit_move_id
        ELSE apr.debit_move_id
    END

-- 4. Lấy thông tin chứng từ thanh toán/bút toán đối ứng
LEFT JOIN account_move AS m_pay
    ON m_pay.id = aml_pay.move_id

-- 5. Lấy trạng thái thanh toán (Dùng LEFT JOIN phòng trường hợp là bút toán thủ công không nằm trong account_payment)
LEFT JOIN account_payment AS ap
    ON ap.move_id = m_pay.id

WHERE m_inv.name = 'INV/2026/00106' -- Thay mã hóa đơn cần tra cứu vào đây
  AND m_inv.move_type = 'out_invoice';



-- QUERY: dinh khoan
SELECT
    m.name AS ma_chung_tu,
    m.move_type,
    m.date,
    aml.id AS move_line_id,

    -- Lấy mã tài khoản theo từng công ty (phòng trường hợp đa công ty multi-company)
    aa.code_store ->> m.company_id::text AS ma_tai_khoan,
    aa.name AS ten_tai_khoan,
    aa.account_type,

    aml.name AS noi_dung,
    aml.debit,
    aml.credit,
    aml.balance,
    aml.amount_residual,
    aml.full_reconcile_id

FROM account_move AS m

JOIN account_move_line AS aml
    ON aml.move_id = m.id

JOIN account_account AS aa
    ON aa.id = aml.account_id

WHERE m.name IN (
    'INV/2024/00013',   -- Thay danh sách mã chứng từ/hóa đơn
    'PBNK1/2024/00032'  -- hoặc thanh toán bạn muốn tra cứu vào đây
)

ORDER BY
    m.date,
    m.name,
    aml.id;