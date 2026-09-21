{#
    Staging = append-only typed log (naming_convention: mọi CDC event giữ nguyên, kể cả
    trùng natural key — KHÔNG dedup ở đây). Dedup "lấy bản mới nhất theo key" chuyển xuống
    snapshot (cho nhánh dim) hoặc silver/gold (cho nhánh fact đọc thẳng từ staging).
    Macro này chỉ giới hạn incremental run quét bronze mới thay vì full-scan mỗi lần chạy.
#}
{% macro incremental_filter(ingested_col='raw_data:ingested_at::timestamp_ntz') %}
{% if is_incremental() %}
where {{ ingested_col }} > (
    select coalesce(max(ingested_at), '1900-01-01'::timestamp_ntz) from {{ this }}
)
{% endif %}
{% endmacro %}

{#
    Dùng khi rollout thêm cột so sánh vào một incremental model đã tồn tại.
    `on_schema_change='sync_all_columns'` chỉ đồng bộ schema trong lúc materialization;
    source SQL vẫn lỗi nếu tham chiếu cột đích chưa tồn tại. Macro này giúp model
    thực hiện một lần reload có kiểm soát, rồi quay về detect-change bình thường.
#}
{% macro relation_has_column(relation, column_name) %}
    {% if execute and relation is not none %}
        {% set existing_columns = adapter.get_columns_in_relation(relation) %}
        {% set existing_names = [] %}
        {% for existing_column in existing_columns %}
            {% do existing_names.append(existing_column.name | lower) %}
        {% endfor %}
        {{ return(column_name | lower in existing_names) }}
    {% endif %}

    {{ return(false) }}
{% endmacro %}
