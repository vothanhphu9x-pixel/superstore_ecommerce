select mart_ar_aging_sk
from {{ ref('mart_ar_aging') }}
where invoice_count < 0
   or bucket_not_due < 0
   or bucket_0_30 < 0
   or bucket_31_60 < 0
   or bucket_61_90 < 0
   or bucket_over_90 < 0
   or bucket_unclassified < 0
   or abs(
        total_outstanding_amount
        - (
            bucket_not_due
            + bucket_0_30
            + bucket_31_60
            + bucket_61_90
            + bucket_over_90
            + bucket_unclassified
        )
   ) > 0.01
