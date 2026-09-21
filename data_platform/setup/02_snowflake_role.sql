-- ============================================================
-- BƯỚC 2: Tạo role read-only cho app query (RAG chatbot)
-- Chạy SAU khi dbt đã chạy xong (ANALYTIC_LAYER_GOLD_LAYER đã tồn tại)
-- Chạy với role ACCOUNTADMIN
-- ============================================================

-- Kiểm tra user hiện có những role gì
SHOW GRANTS TO USER phu;

-- Tạo role chỉ dùng để đọc, không xóa/sửa được
CREATE ROLE IF NOT EXISTS ANALYTICS_READONLY;

-- Cấp quyền dùng warehouse (chạy query, không tạo/xóa warehouse)
GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE ANALYTICS_READONLY;

-- Cấp quyền đọc database + schema gold layer + mart layer
-- (RAG_CHATBOT/analytics/templates.py query cả 2 schema: fact_*/dim_* ở GOLD_LAYER,
--  mart_* ở MART_LAYER riêng — theo dbt_project.yml models.mart.+schema: MART_LAYER)
GRANT USAGE ON DATABASE SUPERSTORE_DB TO ROLE ANALYTICS_READONLY;
GRANT USAGE ON SCHEMA SUPERSTORE_DB.ANALYTIC_LAYER_GOLD_LAYER TO ROLE ANALYTICS_READONLY;
GRANT USAGE ON SCHEMA SUPERSTORE_DB.ANALYTIC_LAYER_MART_LAYER TO ROLE ANALYTICS_READONLY;

-- Chỉ SELECT trên gold layer + mart layer — không DELETE, UPDATE, DROP
GRANT SELECT ON ALL TABLES IN SCHEMA SUPERSTORE_DB.ANALYTIC_LAYER_GOLD_LAYER TO ROLE ANALYTICS_READONLY;
GRANT SELECT ON ALL TABLES IN SCHEMA SUPERSTORE_DB.ANALYTIC_LAYER_MART_LAYER TO ROLE ANALYTICS_READONLY;

-- Tự động cấp SELECT cho table mới sau này (khi dbt chạy lại tạo table mới)
GRANT SELECT ON FUTURE TABLES IN SCHEMA SUPERSTORE_DB.ANALYTIC_LAYER_GOLD_LAYER TO ROLE ANALYTICS_READONLY;
GRANT SELECT ON FUTURE TABLES IN SCHEMA SUPERSTORE_DB.ANALYTIC_LAYER_MART_LAYER TO ROLE ANALYTICS_READONLY;

-- Gán role này cho user phu
GRANT ROLE ANALYTICS_READONLY TO USER phu;

-- Verify: kiểm tra role đã được gán chưa
SHOW GRANTS TO USER phu;

-- ── Tầng ML (Phase 4) ─────────────────────────────────────────────────────────
-- Bảng điểm số do ml_platform/score_batch.py ghi vào. App chỉ ĐỌC — việc ghi do
-- ml_platform làm bằng credential riêng, để role read-only của app không bao giờ có
-- quyền ghi vào bất cứ đâu.
GRANT USAGE  ON SCHEMA SUPERSTORE_DB.ANALYTIC_LAYER_ML_LAYER TO ROLE ANALYTICS_READONLY;
GRANT SELECT ON ALL    TABLES IN SCHEMA SUPERSTORE_DB.ANALYTIC_LAYER_ML_LAYER TO ROLE ANALYTICS_READONLY;
GRANT SELECT ON FUTURE TABLES IN SCHEMA SUPERSTORE_DB.ANALYTIC_LAYER_ML_LAYER TO ROLE ANALYTICS_READONLY;
