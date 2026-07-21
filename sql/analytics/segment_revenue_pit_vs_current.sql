-- Why SCD Type-2 is worth the effort, in one query.
--
-- point_in_time : join the fact to the customer version it was loaded against
--                 (fact.customer_key). Each sale is attributed to the segment the
--                 customer had *on the day of the sale*.
-- restated      : re-attribute every sale to the customer's *current* segment,
--                 by hopping from the versioned row to the current one via the
--                 natural key. This is the answer a Type-1 dimension would give.
--
-- The grand totals match, but the per-segment split differs -- that gap is
-- exactly the history a Type-1 overwrite would have destroyed.
WITH point_in_time AS (
    SELECT c.segment, SUM(f.net_amount) AS net_revenue
    FROM fact_sales f
    JOIN dim_customer c ON f.customer_key = c.customer_key
    GROUP BY c.segment
),
restated AS (
    SELECT cur.segment, SUM(f.net_amount) AS net_revenue
    FROM fact_sales f
    JOIN dim_customer ver ON f.customer_key = ver.customer_key
    JOIN dim_customer cur ON cur.customer_id = ver.customer_id AND cur.is_current
    GROUP BY cur.segment
)
SELECT
    pit.segment,
    ROUND(pit.net_revenue, 0)                     AS net_revenue_point_in_time,
    ROUND(res.net_revenue, 0)                     AS net_revenue_restated_current,
    ROUND(res.net_revenue - pit.net_revenue, 0)   AS delta
FROM point_in_time pit
JOIN restated res ON pit.segment = res.segment
ORDER BY pit.segment;
